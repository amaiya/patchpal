"""Tests for TinyAgent (small context windows): handoff compaction, selection, reading."""

from unittest.mock import MagicMock

import pytest

from patchpal.agent import TinyAgent, create_agent, create_tiny_agent

README = "# PatchPal\n\n" + ("PatchPal is a Python-native AI coding agent. " * 120)
LS_OUTPUT = "\n".join(f"drwxr-xr-x  5 user user 4096 Nov 20 10:00 dir{i}" for i in range(30))


def _mock_response(text):
    response = MagicMock()
    response.choices = [MagicMock()]
    response.choices[0].message.content = text
    response.usage = MagicMock(
        prompt_tokens=100,
        completion_tokens=50,
        cache_creation_input_tokens=0,
        cache_read_input_tokens=0,
    )
    return response


def _live_test_history():
    """Mirror of the live 8K test: 2 turns, the second with README + pyproject reads."""
    return [
        {"role": "user", "content": "List files in this folder"},
        {"role": "assistant", "content": "", "tool_calls": []},
        {"role": "tool", "tool_call_id": "1", "name": "run_shell", "content": LS_OUTPUT},
        {"role": "assistant", "content": "Here's what's in the folder: ..."},
        {"role": "user", "content": "What does this repo do?"},
        {"role": "assistant", "content": "", "tool_calls": []},
        {"role": "tool", "tool_call_id": "2", "name": "read_file", "content": README},
        {"role": "tool", "tool_call_id": "3", "name": "run_shell", "content": "[project]\n" * 50},
        {"role": "assistant", "content": "This repo is PatchPal, a Python-native agent."},
    ]


@pytest.fixture
def small_agent(monkeypatch, tmp_path):
    monkeypatch.setenv("PATCHPAL_CONTEXT_LIMIT", "8192")
    monkeypatch.delenv("PATCHPAL_SMALL_CONTEXT_THRESHOLD", raising=False)
    monkeypatch.setattr("patchpal.tools.common.PATCHPAL_DIR", tmp_path)

    memory_path = tmp_path / "MEMORY.md"
    memory_path.write_text("# Project Memory\n\n---\n\nUse pytest.\n", encoding="utf-8")
    monkeypatch.setattr("patchpal.tools.common.MEMORY_FILE", memory_path)

    agent = create_tiny_agent()
    assert agent.messages[0]["metadata"]["is_memory"]
    return agent


def _install_llm(agent, note="Objective: explain the repo. Remaining plan: done."):
    calls = []

    def fake_llm(msgs, max_tokens):
        calls.append({"msgs": msgs, "max_tokens": max_tokens})
        return _mock_response(note)

    agent._call_compaction_llm = fake_llm
    return calls


def test_small_window_uses_handoff_and_always_shrinks(small_agent):
    """Live test 2 regression: summary compaction grew the context by 835 tokens."""
    agent = small_agent
    memory_msg = agent.messages[0]
    agent.messages += _live_test_history()
    agent.last_prompt_tokens = 7171
    calls = _install_llm(agent)

    before = agent.context_manager.get_usage_stats(agent.messages)
    agent._perform_auto_compaction()
    after = agent.context_manager.get_usage_stats(agent.messages)

    assert len(calls) == 1
    # [memory, request + note, final reply]
    assert agent.messages[0] is memory_msg
    handoff = agent.messages[1]
    assert handoff["role"] == "user"
    assert handoff["metadata"]["is_handoff"]
    assert handoff["content"].startswith(
        "Original request (already in progress - continue from the note below; don't restart from scratch):\nWhat does this repo do?"
    )
    assert "Objective: explain the repo." in handoff["content"]
    assert agent.messages[2] == {
        "role": "assistant",
        "content": "This repo is PatchPal, a Python-native agent.",
    }
    assert len(agent.messages) == 3

    assert after["total_tokens"] < before["total_tokens"]
    # Conversation shrinks to a small fraction (tool schemas/system prompt are fixed overhead)
    assert after["message_tokens"] < before["message_tokens"] * 0.25
    assert agent.last_prompt_tokens is None
    assert agent._last_compaction_message_count == 3

    # Memory wasn't sent for the handoff; the note is capped
    sent = calls[0]["msgs"]
    assert not any(m.get("metadata", {}).get("is_memory") for m in sent)
    assert "handoff note" in sent[-1]["content"]
    assert calls[0]["max_tokens"] <= agent.context_manager.output_reserve


def test_handoff_saves_full_history(small_agent, tmp_path):
    agent = small_agent
    agent.messages += _live_test_history()
    _install_llm(agent)

    agent._perform_auto_compaction()

    saved = list((tmp_path / "history").glob("handoff_*.md"))
    assert len(saved) == 1
    text = saved[0].read_text(encoding="utf-8")
    assert "What does this repo do?" in text
    assert "PatchPal is a Python-native AI coding agent." in text
    assert str(saved[0]) in agent.messages[1]["content"]


def test_handoff_works_with_few_messages(small_agent):
    """No <10-message pruning path: compaction runs (live test 1 needed this)."""
    agent = small_agent
    agent.messages += [
        {"role": "user", "content": "Summarize the README"},
        {"role": "assistant", "content": "", "tool_calls": []},
        {"role": "tool", "tool_call_id": "1", "name": "read_file", "content": README},
    ]
    calls = _install_llm(agent)

    agent._perform_auto_compaction()

    assert len(calls) == 1
    # Mid-turn: no final reply kept; the request is preserved for the model to continue
    assert len(agent.messages) == 2
    assert agent.messages[1]["content"].startswith(
        "Original request (already in progress - continue from the note below; don't restart from scratch):\nSummarize the README"
    )


def test_loop_guard_only_skips_when_nothing_new(small_agent):
    """Live test 2 regression: the guard skipped compaction on the next turns at 124%."""
    agent = small_agent
    agent.messages += _live_test_history()
    calls = _install_llm(agent)

    agent._perform_auto_compaction()
    assert len(calls) == 1

    # Nothing new: skip
    agent._perform_auto_compaction()
    assert len(calls) == 1

    # One new turn (2 messages) is enough to compact again (old guard required 3)
    agent.messages += [
        {"role": "user", "content": "What is the capital of France?"},
        {"role": "assistant", "content": "Paris."},
    ]
    agent._perform_auto_compaction()
    assert len(calls) == 2
    assert agent.messages[1]["content"].startswith(
        "Original request (already in progress - continue from the note below; don't restart from scratch):\nWhat is the capital of France?"
    )
    assert agent.messages[2]["content"] == "Paris."


def test_second_handoff_in_one_turn_keeps_original_request(small_agent):
    agent = small_agent
    agent.messages += [
        {"role": "user", "content": "Refactor context.py"},
        {"role": "assistant", "content": "", "tool_calls": []},
        {"role": "tool", "tool_call_id": "1", "name": "read_file", "content": README},
    ]
    _install_llm(agent, note="first note")
    agent._perform_auto_compaction()

    # Same turn continues with more tool calls
    agent.messages += [
        {"role": "assistant", "content": "", "tool_calls": []},
        {"role": "tool", "tool_call_id": "2", "name": "read_file", "content": README},
    ]
    _install_llm(agent, note="second note")
    agent._perform_auto_compaction()

    content = agent.messages[1]["content"]
    assert content.startswith(
        "Original request (already in progress - continue from the note below; don't restart from scratch):\nRefactor context.py"
    )
    assert "second note" in content
    assert "first note" not in content  # Old note isn't nested


def test_handoff_failure_falls_back_to_truncation(small_agent):
    agent = small_agent
    agent.messages += _live_test_history()
    original_count = len(agent.messages)

    def failing_llm(msgs, max_tokens):
        raise RuntimeError("model error")

    agent._call_compaction_llm = failing_llm
    agent._perform_auto_compaction()

    assert len(agent.messages) == original_count  # History kept
    readme_msg = next(m for m in agent.messages if m.get("tool_call_id") == "2")
    assert len(readme_msg["content"]) < len(README)  # But large outputs truncated


def test_handoff_not_used_when_it_would_not_shrink(small_agent):
    agent = small_agent
    agent.messages += [
        {"role": "user", "content": "hi"},
        {"role": "assistant", "content": "hello"},
    ]
    original = list(agent.messages)
    _install_llm(agent, note="x" * 5000)

    agent._perform_auto_compaction()

    assert agent.messages == original


def test_patchpal_agent_keeps_summary_compaction(monkeypatch):
    """PatchPalAgent is unchanged, even with a small window: summary + last 2 turns."""
    monkeypatch.setenv("PATCHPAL_CONTEXT_LIMIT", "8192")
    agent = create_agent()
    assert not isinstance(agent, TinyAgent)
    assert not hasattr(agent, "_perform_handoff_compaction")
    agent.context_manager.create_compaction = MagicMock(
        return_value=({"role": "assistant", "content": "[COMPACTION SUMMARY]\n\ns"}, "s")
    )
    agent.messages = [{"role": "user", "content": "q"}, {"role": "assistant", "content": "a"}] * 6

    agent._perform_auto_compaction()

    assert agent.context_manager.create_compaction.called


@pytest.mark.parametrize(
    "limit,threshold,tiny_mode,expected",
    [
        (8192, None, None, True),
        (65536, None, None, True),  # Boundary is inclusive (64K)
        (65537, None, None, False),
        (200000, None, None, False),
        (16384, "0", None, False),  # 0 disables automatic selection
        (131072, "200000", None, True),  # Threshold is configurable
        (200000, None, "true", True),  # Forced on
        (8192, None, "false", False),  # Forced off
        (8192, "0", "true", True),  # Force wins over disabled threshold
    ],
)
def test_should_use_tiny_agent(monkeypatch, limit, threshold, tiny_mode, expected):
    from patchpal.agent.tiny import should_use_tiny_agent

    for var, value in (
        ("PATCHPAL_SMALL_CONTEXT_THRESHOLD", threshold),
        ("PATCHPAL_TINY_MODE", tiny_mode),
    ):
        if value is None:
            monkeypatch.delenv(var, raising=False)
        else:
            monkeypatch.setenv(var, value)
    assert should_use_tiny_agent(limit) == expected


def test_tiny_agent_defaults_to_minimal_tools(monkeypatch):
    monkeypatch.setenv("PATCHPAL_CONTEXT_LIMIT", "16384")
    monkeypatch.delenv("PATCHPAL_ENABLED_TOOLS", raising=False)
    monkeypatch.setenv("PATCHPAL_ENABLE_WEB", "false")

    agent = create_tiny_agent()
    names = {t["function"]["name"] for t in agent._build_tools()}
    assert names == {"read_file", "read_lines", "edit_file", "write_file", "run_shell"}
    assert agent.context_manager.tool_tokens < create_agent().context_manager.tool_tokens

    # Explicit tools win
    agent = create_tiny_agent(enabled_tools=["read_file", "run_shell"])
    assert {t["function"]["name"] for t in agent._build_tools()} == {"read_file", "run_shell"}


def test_tiny_agent_system_prompt_adds_selective_reading(monkeypatch):
    monkeypatch.setenv("PATCHPAL_CONTEXT_LIMIT", "16384")
    agent = create_tiny_agent()

    assert agent.system_prompt.startswith(create_agent().system_prompt)
    assert "## Small context window" in agent.system_prompt
    assert "16,384 tokens" in agent.system_prompt
    # Context manager counts the longer prompt
    assert agent.context_manager.system_prompt == agent.system_prompt


def test_tiny_agent_caps_tool_output_by_window(monkeypatch):
    """Live 16K regression: ~500-line read_lines results each filled half the window."""
    monkeypatch.setenv("PATCHPAL_CONTEXT_LIMIT", "16384")
    agent = create_tiny_agent()
    max_lines, max_chars = agent._tool_output_limits()
    assert max_chars == int(16384 * 0.15 * 3)  # 7,372 chars (~15% of the window)

    monkeypatch.setenv("PATCHPAL_CONTEXT_LIMIT", "8192")
    assert create_tiny_agent()._tool_output_limits()[1] == int(8192 * 0.15 * 3)

    # PatchPalAgent keeps the global limits
    assert create_agent()._tool_output_limits()[1] == 100_000


def test_tiny_agent_truncates_large_tool_result_in_run(monkeypatch, tmp_path):
    """End to end: a large read_lines result is truncated before it enters the history."""
    monkeypatch.setenv("PATCHPAL_CONTEXT_LIMIT", "16384")
    monkeypatch.setenv("PATCHPAL_REQUIRE_PERMISSION", "false")
    monkeypatch.setenv("PATCHPAL_STREAM_OUTPUT", "false")
    big = tmp_path / "big.py"
    big.write_text("".join(f"x_{i} = {i}  # some code on line {i}\n" for i in range(2000)))

    agent = create_tiny_agent()
    agent.enable_auto_compact = False

    tool_call = MagicMock()
    tool_call.id = "call_1"
    tool_call.function.name = "read_lines"
    tool_call.function.arguments = f'{{"path": "{big}", "start_line": 1, "end_line": 2000}}'
    first = _mock_response("")
    first.choices[0].message.tool_calls = [tool_call]
    second = _mock_response("Done.")
    second.choices[0].message.tool_calls = None

    from unittest.mock import patch

    import litellm

    with patch.object(litellm, "completion", side_effect=[first, second]):
        agent.run("read big.py")

    tool_msgs = [m for m in agent.messages if m.get("role") == "tool"]
    assert tool_msgs, "tool result missing"
    max_chars = agent._tool_output_limits()[1]
    assert len(tool_msgs[0]["content"]) < max_chars + 1_000  # capped (plus hint text)
    assert "read_lines" in tool_msgs[0]["content"]  # hint to read in chunks


def test_from_agent_converts_without_redetecting(monkeypatch):
    """The CLI creates a PatchPalAgent first (model detection), then converts."""
    monkeypatch.setenv("PATCHPAL_CONTEXT_LIMIT", "16384")
    monkeypatch.delenv("PATCHPAL_ENABLED_TOOLS", raising=False)
    base = create_agent()
    base.detected_model_name = "anthropic.claude-test"
    base.prompt_caching_supported = True
    full_tool_tokens = base.context_manager.tool_tokens

    tiny = TinyAgent.from_agent(base)

    assert isinstance(tiny, TinyAgent)
    assert tiny.detected_model_name == "anthropic.claude-test"
    assert tiny.prompt_caching_supported is True
    # Same conversation, except the base agent's memory message (which includes file paths)
    assert tiny.messages == [m for m in base.messages if not m.get("metadata", {}).get("is_memory")]
    assert "## Small context window" in tiny.system_prompt
    assert tiny.context_manager.tool_tokens < full_tool_tokens  # Minimal tools applied
    assert tiny.agent_type == "tiny"


def test_cli_selects_tiny_agent_for_small_window(monkeypatch, capsys):
    import sys
    from unittest.mock import patch

    monkeypatch.setenv("ANTHROPIC_API_KEY", "test-key")
    monkeypatch.setenv("PATCHPAL_CONTEXT_LIMIT", "16384")
    monkeypatch.delenv("PATCHPAL_TINY_MODE", raising=False)
    monkeypatch.delenv("PATCHPAL_SMALL_CONTEXT_THRESHOLD", raising=False)
    monkeypatch.setattr(sys, "argv", ["patchpal"])

    import importlib

    tiny_module = importlib.import_module("patchpal.agent.tiny")
    interactive = importlib.import_module("patchpal.cli.interactive")
    created = {}
    original = tiny_module.TinyAgent.from_agent.__func__

    def spy(cls, agent):
        created["agent"] = original(cls, agent)
        return created["agent"]

    with (
        patch.object(tiny_module.TinyAgent, "from_agent", classmethod(spy)),
        patch.object(interactive, "pt_prompt", side_effect=["exit"]),
    ):
        interactive.main()

    assert created.get("agent") is not None
    assert type(created["agent"]).__name__ == "TinyAgent"
    assert "Tiny agent (context window 16,384" in capsys.readouterr().out


def test_cli_uses_regular_agent_for_large_window(monkeypatch, capsys):
    import sys
    from unittest.mock import patch

    monkeypatch.setenv("ANTHROPIC_API_KEY", "test-key")
    monkeypatch.setenv("PATCHPAL_CONTEXT_LIMIT", "200000")
    monkeypatch.delenv("PATCHPAL_TINY_MODE", raising=False)
    monkeypatch.setattr(sys, "argv", ["patchpal"])

    import importlib

    tiny_module = importlib.import_module("patchpal.agent.tiny")
    interactive = importlib.import_module("patchpal.cli.interactive")
    with (
        patch.object(tiny_module.TinyAgent, "from_agent") as from_agent,
        patch.object(interactive, "pt_prompt", side_effect=["exit"]),
    ):
        interactive.main()

    from_agent.assert_not_called()
    assert "Tiny agent" not in capsys.readouterr().out


# ---------------------------------------------------------------------------
# Live 8K regression (qwen3.5:4b): "Read ./patchpal/agent/tiny.py" looped through
# compactions, re-reading the whole file each time and calling a nonexistent grep tool.
# ---------------------------------------------------------------------------


def test_selective_reading_prompt_names_real_tools_and_line_budget(monkeypatch):
    """A: the prompt must not suggest a 'grep' tool, and must give a realistic line budget."""
    monkeypatch.setenv("PATCHPAL_CONTEXT_LIMIT", "8192")
    agent = create_tiny_agent()
    prompt = agent.system_prompt.split("## Small context window", 1)[1]

    assert "run_shell with grep" in prompt
    assert "use grep (" not in prompt  # Old wording led the model to call grep() directly
    max_chars = agent._tool_output_limits()[1]
    assert f"roughly {max_chars // 50} lines" in prompt  # 3,686 // 50 = 73
    assert "summarize what matters" in prompt


def _run_read(agent, tool_name, args, monkeypatch):
    """Run one tool call through the real agent loop and return the tool result text."""
    import json

    import litellm

    monkeypatch.setenv("PATCHPAL_REQUIRE_PERMISSION", "false")
    monkeypatch.setenv("PATCHPAL_STREAM_OUTPUT", "false")
    agent.enable_auto_compact = False

    tool_call = MagicMock()
    tool_call.id = "call_1"
    tool_call.function.name = tool_name
    tool_call.function.arguments = json.dumps(args)
    first = _mock_response("")
    first.choices[0].message.tool_calls = [tool_call]
    second = _mock_response("Done.")
    second.choices[0].message.tool_calls = None

    from unittest.mock import patch

    with patch.object(litellm, "completion", side_effect=[first, second]):
        agent.run("read it")
    return next(m for m in agent.messages if m.get("role") == "tool")["content"]


def test_truncated_read_lines_says_where_to_continue(monkeypatch, tmp_path):
    """B: a truncated read_lines result names the last complete line and the next call."""
    monkeypatch.setenv("PATCHPAL_CONTEXT_LIMIT", "8192")
    f = tmp_path / "code.py"
    f.write_text(
        "".join(f"value_{i} = compute(arg_{i}, other_{i})  # line {i}\n" for i in range(1, 501))
    )
    agent = create_tiny_agent()

    result = _run_read(
        agent, "read_lines", {"path": str(f), "start_line": 51, "end_line": 400}, monkeypatch
    )

    import re

    m = re.search(r"Truncated after line (\d+).*start_line=(\d+), end_line=(\d+)", result)
    assert m, result[-400:]
    last, next_start, next_end = map(int, m.groups())
    assert next_start == last + 1
    assert 51 < last < 400
    # The reported last line really is the last complete line in the output
    assert f"# line {last}\n" in result
    assert f"# line {last + 1}\n" not in result
    assert next_end - next_start + 1 == agent._max_tool_output_lines_estimate()


def test_truncated_read_file_says_where_to_continue(monkeypatch, tmp_path):
    """B: read_file has no line numbers, so complete lines are counted."""
    monkeypatch.setenv("PATCHPAL_CONTEXT_LIMIT", "8192")
    f = tmp_path / "code.py"
    f.write_text(
        "".join(f"value_{i} = compute(arg_{i}, other_{i})  # line {i}\n" for i in range(1, 501))
    )
    agent = create_tiny_agent()

    result = _run_read(agent, "read_file", {"path": str(f)}, monkeypatch)

    import re

    m = re.search(r"Truncated after line (\d+).*start_line=(\d+)", result)
    assert m, result[-400:]
    last, next_start = map(int, m.groups())
    assert next_start == last + 1
    assert f"# line {last}\n" in result
    assert f"# line {last + 1}\n" not in result


def test_truncation_hint_for_other_tools_suggests_run_shell(monkeypatch):
    monkeypatch.setenv("PATCHPAL_CONTEXT_LIMIT", "8192")
    agent = create_tiny_agent()
    hint = agent._truncation_hint("run_shell", {"cmd": "cat big"}, "x" * 100, 2000, 3686)
    assert "run_shell with grep" in hint
    assert "Truncated after line" not in hint
    # Missing/invalid args don't crash
    assert "run_shell" in agent._truncation_hint("read_lines", {}, "x", 2000, 3686)


def test_patchpal_agent_truncation_hint_unchanged():
    agent = create_agent()
    hint = agent._truncation_hint("read_lines", {"path": "a.py"}, "  1  x\n", 2000, 100000)
    assert hint.startswith("Output exceeded limits (2,000 lines or 100,000 characters).")
    assert "Truncated after line" not in hint


def test_handoff_marks_request_as_in_progress(small_agent):
    """C: after a handoff the original request reads as ongoing, not a fresh instruction."""
    agent = small_agent
    agent.messages += [
        {"role": "user", "content": "Read ./patchpal/agent/tiny.py"},
        {"role": "assistant", "content": "", "tool_calls": []},
        {"role": "tool", "tool_call_id": "1", "name": "read_file", "content": README},
    ]
    _install_llm(agent, note="8. Already read - lines 1-50")
    agent._perform_auto_compaction()

    content = agent.messages[1]["content"]
    assert content.startswith("Original request (already in progress")
    assert "don't restart from scratch" in content
    assert "Read ./patchpal/agent/tiny.py" in content
    # The stored request stays verbatim, so repeated handoffs don't stack the label
    assert agent.messages[1]["metadata"]["request"] == "Read ./patchpal/agent/tiny.py"
    agent.messages += [
        {"role": "assistant", "content": "", "tool_calls": []},
        {"role": "tool", "tool_call_id": "2", "name": "read_file", "content": README},
    ]
    agent._perform_auto_compaction()
    assert agent.messages[1]["content"].count("Original request (already in progress") == 1


def _looping_run(agent, monkeypatch, tmp_path, turns_of_reads):
    """Simulate the live loop: every LLM call reads the big file again, never finishing."""
    import json

    import litellm

    monkeypatch.setenv("PATCHPAL_REQUIRE_PERMISSION", "false")
    monkeypatch.setenv("PATCHPAL_STREAM_OUTPUT", "false")
    big = tmp_path / "big.py"
    big.write_text(
        "".join(f"line_{i} = {i} * 2  # filler text to make it long\n" for i in range(2000))
    )
    _install_llm(agent, note="Remaining plan: keep reading.")

    calls = {"n": 0}

    def fake_completion(**kwargs):
        calls["n"] += 1
        if calls["n"] > turns_of_reads:
            resp = _mock_response("Finished.")
            resp.choices[0].message.tool_calls = None
            return resp
        tc = MagicMock()
        tc.id = f"c{calls['n']}"
        tc.function.name = "read_file"
        tc.function.arguments = json.dumps({"path": str(big)})
        resp = _mock_response("")
        resp.choices[0].message.tool_calls = [tc]
        return resp

    from unittest.mock import patch

    with patch.object(litellm, "completion", side_effect=fake_completion):
        result = agent.run("Read big.py")
    return result, calls["n"]


def test_handoff_limit_stops_runaway_loop(small_agent, monkeypatch, tmp_path):
    """D: stop after N handoffs in one turn instead of looping indefinitely."""
    monkeypatch.delenv("PATCHPAL_MAX_HANDOFFS_PER_TURN", raising=False)  # default 5
    agent = small_agent

    result, llm_calls = _looping_run(agent, monkeypatch, tmp_path, turns_of_reads=1000)

    assert agent._handoffs_this_turn == 5
    assert result.startswith("I stopped after 5 context compactions")
    assert "8,192-token context window" in result
    assert "PATCHPAL_MAX_HANDOFFS_PER_TURN" in result
    assert llm_calls < 50  # Stopped early rather than running to max_iterations


def test_handoff_limit_allows_multiple_handoffs(small_agent, monkeypatch, tmp_path):
    """D: tasks needing several handoffs (but fewer than the limit) still finish normally."""
    monkeypatch.setenv("PATCHPAL_MAX_HANDOFFS_PER_TURN", "5")
    agent = small_agent

    result, _ = _looping_run(agent, monkeypatch, tmp_path, turns_of_reads=6)

    assert result == "Finished."
    assert 2 <= agent._handoffs_this_turn < 5


def test_handoff_limit_resets_each_turn_and_can_be_disabled(small_agent, monkeypatch, tmp_path):
    agent = small_agent
    monkeypatch.setenv("PATCHPAL_MAX_HANDOFFS_PER_TURN", "2")
    result, _ = _looping_run(agent, monkeypatch, tmp_path, turns_of_reads=1000)
    assert result.startswith("I stopped after 2 context compactions")

    # A new user message (e.g., "continue") starts a fresh count
    from unittest.mock import patch

    import litellm

    done = _mock_response("ok")
    done.choices[0].message.tool_calls = None
    with patch.object(litellm, "completion", return_value=done):
        agent.run("continue")
    assert agent._handoffs_this_turn == 0

    # 0 = unlimited
    monkeypatch.setenv("PATCHPAL_MAX_HANDOFFS_PER_TURN", "0")
    assert agent._should_stop_turn() is None
    agent._handoffs_this_turn = 99
    assert agent._should_stop_turn() is None


def test_patchpal_agent_never_stops_turn_early():
    assert create_agent()._should_stop_turn() is None


def test_handoff_states_working_directory_and_labels_history_log(
    small_agent, monkeypatch, tmp_path
):
    """Live 8K regression: after a handoff the model read
    ~/.patchpal/repos/patchpal/agent/tiny.py, mistaking the saved-history location (the only
    absolute path in the message) for the project root."""
    from pathlib import Path

    project = Path("/home/user/projects/patchpal")
    monkeypatch.setattr("patchpal.tools.common.REPO_ROOT", project)
    agent = small_agent
    agent.messages += [
        {"role": "user", "content": "read ./patchpal/agent/tiny.py"},
        {"role": "assistant", "content": "", "tool_calls": []},
        {"role": "tool", "tool_call_id": "1", "name": "read_file", "content": README},
    ]
    _install_llm(agent, note="Next action: read ./patchpal/agent/tiny.py from line 80.")
    agent._perform_auto_compaction()

    content = agent.messages[1]["content"]
    assert (
        f"Working directory: {project} (relative paths in this note are relative to it)" in content
    )
    # The history path is labeled as a saved log, not part of the project
    saved = next((tmp_path / "history").glob("handoff_*.md"))
    assert (
        f"(not a project file; search it with grep/read_lines only if you need a detail from earlier): {saved}"
        in content
    )
    # Working directory comes before the history path, right after the note
    assert content.index("Working directory:") < content.index(str(saved))


def test_prune_handoff_history_keeps_newest_100(tmp_path):
    """Saved histories are capped at 100 (one is written per compaction)."""
    files = [tmp_path / f"handoff_20260101_{i:06d}_000000.md" for i in range(105)]
    for f in files:
        f.write_text("x")
    (tmp_path / "notes.md").write_text("unrelated")

    TinyAgent._prune_handoff_history(tmp_path, keep=files[-1])

    assert sorted(tmp_path.glob("handoff_*.md")) == files[-100:]
    assert (tmp_path / "notes.md").exists()  # Only handoff_*.md files are touched


def test_handoff_compaction_survives_pruning_failure(small_agent, monkeypatch):
    def failing_prune(history_dir, keep):
        raise PermissionError("read-only")

    monkeypatch.setattr(TinyAgent, "_prune_handoff_history", staticmethod(failing_prune))
    agent = small_agent
    agent.messages += _live_test_history()
    _install_llm(agent)
    agent._perform_auto_compaction()

    assert agent.messages[1]["metadata"]["is_handoff"]  # Compaction still completed


def test_system_prompt_states_working_directory(monkeypatch):
    """Live 16K regression: qwen3.5:4b's first call read ~/.patchpal/repos/patchpal/README.md.
    The MEMORY.md message's path was the only absolute path the model had seen."""
    from pathlib import Path

    project = Path("/home/user/projects/patchpal")
    monkeypatch.setattr("patchpal.tools.common.REPO_ROOT", project)
    monkeypatch.setenv("PATCHPAL_CONTEXT_LIMIT", "16384")

    prompt = create_tiny_agent().system_prompt
    section = prompt.split("## Small context window", 1)[1]
    assert f"Working directory: {project}. This is the project" in section
    assert (
        "For questions about this project, use its local files (read_file, read_lines,\n"
        "run_shell), not web_search or web_fetch." in section
    )
    assert "PatchPal" not in section  # The model is never told what PatchPal is
    # Don't mention the assistant's own data directory: a 4B model took it for the project
    assert ".patchpal" not in section
    # PatchPalAgent's prompt is unchanged
    assert "Working directory:" not in create_agent().system_prompt


def test_empty_memory_template_is_not_loaded(monkeypatch, tmp_path):
    """The empty template only carries a path under ~/.patchpal/, which a 4B model took for
    the project directory. TinyAgent skips it; PatchPalAgent still loads it."""
    memory_path = tmp_path / "MEMORY.md"
    memory_path.write_text("# Project Memory\n\nThis file persists across sessions.\n")
    monkeypatch.setattr("patchpal.tools.common.MEMORY_FILE", memory_path)
    monkeypatch.setattr(
        "patchpal.tools.common.get_memory_info",
        lambda: {"exists": True, "has_content": False, "path": memory_path, "content": ""},
    )

    tiny = create_tiny_agent()
    assert not any(m.get("metadata", {}).get("is_memory") for m in tiny.messages)
    assert str(memory_path) not in str(tiny.messages)
    # Converting a base agent (as the CLI does) also drops it
    base = create_agent()
    assert any(m.get("metadata", {}).get("is_memory") for m in base.messages)
    assert not any(
        m.get("metadata", {}).get("is_memory") for m in TinyAgent.from_agent(base).messages
    )


def test_memory_notes_are_loaded_without_paths(monkeypatch, tmp_path):
    memory_path = tmp_path / "MEMORY.md"
    notes = "# Project Memory\n\n---\n\nThis is a FastAPI project with PostgreSQL backend.\n"
    memory_path.write_text(notes)
    monkeypatch.setattr("patchpal.tools.common.MEMORY_FILE", memory_path)

    for agent in (create_tiny_agent(), TinyAgent.from_agent(create_agent())):
        memory = [m for m in agent.messages if m.get("metadata", {}).get("is_memory")]
        assert len(memory) == 1  # Kept (and tagged, so compaction preserves it)
        content = memory[0]["content"]
        assert "This is a FastAPI project with PostgreSQL backend." in content
        assert str(memory_path) not in content
        assert "edit_file" not in content
