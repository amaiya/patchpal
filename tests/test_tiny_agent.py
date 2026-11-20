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
    assert handoff["content"].startswith("What does this repo do?")
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
    assert agent.messages[1]["content"].startswith("Summarize the README")


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
    assert agent.messages[1]["content"].startswith("What is the capital of France?")
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
    assert content.startswith("Refactor context.py")
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
    assert tiny.messages == base.messages
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
