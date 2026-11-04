"""Tests for prompt cache warming (patchpal.agent.cache_warmer)."""

import importlib
import os
import time
from types import SimpleNamespace
from unittest import mock

import pytest


def _cw():
    """Return the live cache_warmer module.

    Resolved fresh on each access (not bound at import time) because other test
    modules (notably test_agent.py) delete ``patchpal.agent.*`` from
    ``sys.modules`` to force env-var reloads. Importing the module here ensures
    our ``CacheWarmer`` instances and our ``mock.patch`` targets always refer to
    the same, current module object.
    """
    return importlib.import_module("patchpal.agent.cache_warmer")


@pytest.fixture(autouse=True)
def _ensure_fresh_cache_warmer_module():
    """Guarantee a consistent cache_warmer module object for each test.

    Re-import the module (repopulating sys.modules if a prior test purged it) so
    the attribute patched via the string path "patchpal.agent.cache_warmer.*"
    and the class used to build warmers come from the same module copy.
    """
    importlib.import_module("patchpal.agent.cache_warmer")
    yield


def _usage(prompt=8000, read=7000, write=1000):
    """Build a fake LiteLLM usage object."""
    return SimpleNamespace(
        prompt_tokens=prompt,
        cache_read_input_tokens=read,
        cache_creation_input_tokens=write,
    )


def _make_warmer(
    mode="streaming",
    ttl=300,
    min_savings=0.05,
    model="anthropic/claude-sonnet-4-5",
    litellm_kwargs=None,
):
    return _cw().CacheWarmer(
        model_id=model,
        mode=mode,
        ttl_seconds=ttl,
        min_savings=min_savings,
        litellm_kwargs=litellm_kwargs or {},
    )


def test_off_mode_is_disabled():
    w = _make_warmer(mode="off")
    assert w.enabled is False
    # record/arm are no-ops in off mode
    w.record_request([{"role": "user", "content": "hi"}], None, _usage())
    assert w._messages is None


def test_is_replayable_no_thinking_is_safe():
    """Without any thinking/reasoning directive, every model is replayable."""
    _is_replayable = _cw()._is_replayable
    assert _is_replayable("anthropic/claude-sonnet-4-5", {}) is True
    assert _is_replayable("bedrock/anthropic.claude-sonnet-4-5", {}) is True
    assert _is_replayable("openai/gpt-4o", {}) is True


def test_is_replayable_anthropic_thinking_is_unsafe():
    """Thinking on Anthropic (direct or Bedrock) is NOT safely replayable."""
    _is_replayable = _cw()._is_replayable
    thinking = {"thinking": {"type": "enabled", "budget_tokens": 2000}}
    assert _is_replayable("anthropic/claude-sonnet-4-5", thinking) is False
    assert _is_replayable("bedrock/anthropic.claude-sonnet-4-5", thinking) is False
    # reasoning_effort form also counts as thinking requested.
    assert _is_replayable("anthropic/claude-sonnet-4-5", {"reasoning_effort": "high"}) is False


def test_is_replayable_opaque_arn_with_thinking_is_unsafe():
    """An opaque Bedrock inference-profile ARN + thinking is treated as unsafe."""
    _is_replayable = _cw()._is_replayable
    arn = "arn:aws:bedrock:us-east-1:123:application-inference-profile/abc123"
    assert _is_replayable(arn, {"thinking": {"budget_tokens": 1}}) is False
    # ...but with no thinking requested it's replayable.
    assert _is_replayable(arn, {}) is True


def test_is_replayable_known_non_anthropic_thinking_is_safe():
    """Known non-Anthropic reasoning providers stay replayable even with thinking."""
    _is_replayable = _cw()._is_replayable
    assert _is_replayable("openai/o3", {"reasoning_effort": "high"}) is True
    assert _is_replayable("gemini/gemini-2.5-pro", {"reasoning": {"effort": "high"}}) is True


def test_unreplayable_warmer_is_disabled_and_noop():
    """A warmer built for an unreplayable config must disable itself."""
    w = _make_warmer(
        mode="idle",
        model="anthropic/claude-sonnet-4-5",
        litellm_kwargs={"thinking": {"type": "enabled", "budget_tokens": 2000}},
    )
    assert w.enabled is False
    # record_request is a no-op (enabled gate), so nothing is captured and arm
    # schedules no timer.
    w.record_request([{"role": "user", "content": "hi"}], None, _usage(read=100000))
    assert w._messages is None
    w.arm(warming_streaming=True)
    assert w._timer is None


def test_record_request_captures_snapshot():
    w = _make_warmer()
    msgs = [{"role": "user", "content": "hi"}]
    tools = [{"type": "function", "function": {"name": "x"}}]
    w.record_request(msgs, tools, _usage(prompt=8000, read=7000, write=1000))
    assert w._messages == msgs
    assert w._tools == tools
    assert w._prompt_tokens == 8000
    assert w._cache_read_tokens == 7000
    assert w._cache_write_tokens == 1000
    # Snapshot must be a distinct list container (not the caller's list).
    assert w._messages is not msgs


def test_savings_gate_known_pricing_large_prompt_warms():
    """With a large cached prefix and known pricing, streaming warm clears threshold."""
    w = _make_warmer(min_savings=0.05)
    w.record_request([{"role": "user", "content": "hi"}], None, _usage(read=100000))
    # Base input price ~ $3/1M tokens for Sonnet. read=0.1x, write=1.25x.
    # miss_cost = 100000 * (3.75e-6 - 3e-7) ≈ 0.345 ; warm_cost = 100000*3e-7 = 0.03
    # streaming P=1.0 -> savings ≈ 0.315 >> 0.05
    with mock.patch(
        "patchpal.agent.cache_warmer._get_cache_rates",
        return_value=(3e-7, 3.75e-6),
    ):
        savings = w._estimate_savings(warming_streaming=True)
    assert savings > 0.05


def test_savings_gate_unknown_pricing_returns_zero():
    """Unknown pricing must not warm (no blind warming)."""
    w = _make_warmer()
    w.record_request([{"role": "user", "content": "hi"}], None, _usage(read=100000))
    with mock.patch(
        "patchpal.agent.cache_warmer._get_cache_rates",
        return_value=(None, None),
    ):
        assert w._estimate_savings(warming_streaming=True) == 0.0


def test_idle_probability_lowers_savings():
    """Idle continuation probability (0.15) yields lower savings than streaming (1.0)."""
    w = _make_warmer()
    w.record_request([{"role": "user", "content": "hi"}], None, _usage(read=100000))
    with mock.patch(
        "patchpal.agent.cache_warmer._get_cache_rates",
        return_value=(3e-7, 3.75e-6),
    ):
        streaming = w._estimate_savings(warming_streaming=True)
        idle = w._estimate_savings(warming_streaming=False)
    assert idle < streaming


def test_streaming_mode_ignores_idle_arm():
    """In streaming mode, an idle arm (warming_streaming=False) must not schedule a timer."""
    w = _make_warmer(mode="streaming")
    w.record_request([{"role": "user", "content": "hi"}], None, _usage())
    w.arm(warming_streaming=False)
    assert w._timer is None


def test_arm_below_threshold_does_not_schedule():
    w = _make_warmer(min_savings=1000.0)  # impossibly high threshold
    w.record_request([{"role": "user", "content": "hi"}], None, _usage(read=100000))
    with mock.patch(
        "patchpal.agent.cache_warmer._get_cache_rates",
        return_value=(3e-7, 3.75e-6),
    ):
        w.arm(warming_streaming=True)
    assert w._timer is None


def test_arm_schedules_timer_and_cancel_clears_it():
    w = _make_warmer(ttl=300, min_savings=0.0)
    w.record_request([{"role": "user", "content": "hi"}], None, _usage(read=100000))
    with mock.patch(
        "patchpal.agent.cache_warmer._get_cache_rates",
        return_value=(3e-7, 3.75e-6),
    ):
        w.arm(warming_streaming=True)
    assert w._timer is not None
    assert w._timer.is_alive()
    w.cancel()
    assert w._timer is None


def test_arm_stops_past_safety_horizon():
    """Re-arming with an old chain_start must stop (no new timer) past the horizon.

    Regression: the safety horizon must measure total time since warming started,
    not time since the most recent re-arm. Otherwise idle warming re-arms forever.
    """
    import time as _time

    from patchpal.agent import cache_warmer as cw

    w = _make_warmer(mode="idle", ttl=300, min_savings=0.0)
    w.record_request([{"role": "user", "content": "hi"}], None, _usage(read=100000))
    # Chain started well beyond the 30-min idle horizon.
    old_start = _time.monotonic() - (cw._MAX_IDLE_WARMING_AGE_S + 60)
    with mock.patch(
        "patchpal.agent.cache_warmer._get_cache_rates",
        return_value=(3e-7, 3.75e-6),
    ):
        w.arm(warming_streaming=False, chain_start=old_start)
    assert w._timer is None  # past horizon -> not re-armed

    # A fresh chain (default chain_start=None) still arms normally.
    with mock.patch(
        "patchpal.agent.cache_warmer._get_cache_rates",
        return_value=(3e-7, 3.75e-6),
    ):
        w.arm(warming_streaming=False)
    assert w._timer is not None
    w.cancel()


def test_fire_sends_one_token_replay():
    """When the timer fires, it issues a max_tokens=1 completion with the snapshot."""
    # Small TTL so it fires fast, but large enough that delay = min(ttl*0.9, ttl-10)
    # leaves a non-zero refresh-deadline margin ((ttl-delay)/2). ttl=12 -> delay=2s,
    # margin=5s, so the warm dispatches well inside the deadline.
    w = _make_warmer(ttl=12, min_savings=0.0)
    msgs = [{"role": "user", "content": "hi"}]
    tools = [{"type": "function", "function": {"name": "x"}}]
    w.record_request(msgs, tools, _usage(read=100000))

    calls = []

    def fake_completion(**kwargs):
        calls.append(kwargs)
        # Cancel to prevent re-arm recursion during the test.
        w.cancel()
        return SimpleNamespace(usage=_usage())

    with (
        mock.patch(
            "patchpal.agent.cache_warmer._get_cache_rates",
            return_value=(3e-7, 3.75e-6),
        ),
        mock.patch("patchpal.agent.cache_warmer.litellm.completion", side_effect=fake_completion),
    ):
        w.arm(warming_streaming=True)
        # ttl=12 -> delay=2s; wait a bit longer for the timer to fire.
        time.sleep(3)

    assert len(calls) == 1
    assert calls[0]["max_tokens"] == 1
    assert calls[0]["messages"] == msgs
    assert calls[0]["tools"] == tools


def test_fire_swallows_errors():
    """A failing warm replay must never raise."""
    w = _make_warmer(ttl=12, min_savings=0.0)
    w.record_request([{"role": "user", "content": "hi"}], None, _usage(read=100000))

    def boom(**kwargs):
        w.cancel()
        raise RuntimeError("provider exploded")

    with (
        mock.patch(
            "patchpal.agent.cache_warmer._get_cache_rates",
            return_value=(3e-7, 3.75e-6),
        ),
        mock.patch("patchpal.agent.cache_warmer.litellm.completion", side_effect=boom),
    ):
        w.arm(warming_streaming=True)
        time.sleep(3)  # should not raise; errors are swallowed
    # If we got here without an exception, the best-effort contract holds.


def test_superseded_timer_does_not_fire():
    """A timer invalidated by a newer cancel/arm must not issue a replay."""
    w = _make_warmer(ttl=12, min_savings=0.0)
    w.record_request([{"role": "user", "content": "hi"}], None, _usage(read=100000))

    calls = []
    with (
        mock.patch(
            "patchpal.agent.cache_warmer._get_cache_rates",
            return_value=(3e-7, 3.75e-6),
        ),
        mock.patch(
            "patchpal.agent.cache_warmer.litellm.completion",
            side_effect=lambda **k: calls.append(k),
        ),
    ):
        w.arm(warming_streaming=True)
        w.cancel()  # supersede immediately
        time.sleep(3)
    assert calls == []


def test_fire_past_refresh_deadline_does_not_warm():
    """A timer that fires after the refresh deadline must not send a warm.

    Simulates a late fire (machine sleep / blocked loop) where the cache entry has
    likely already expired. Sending the replay then would be a full-price cache
    WRITE, so the warmer must abort instead (ported from pi-mono's
    refreshDeadlineMissed).
    """
    w = _make_warmer(mode="streaming", ttl=300, min_savings=0.0)
    w.record_request([{"role": "user", "content": "hi"}], None, _usage(read=100000))
    # Make this generation current so the supersede check passes.
    w._generation = 7

    calls = []
    with mock.patch(
        "patchpal.agent.cache_warmer.litellm.completion",
        side_effect=lambda **k: calls.append(k),
    ):
        # refresh_deadline is in the past -> must skip without warming.
        w._fire(
            generation=7,
            warming_streaming=True,
            armed_at=time.monotonic(),
            refresh_deadline=time.monotonic() - 1.0,
        )
    assert calls == []


def test_config_cache_warming_default_and_validation():
    from patchpal.config import config

    os.environ.pop("PATCHPAL_CACHE_WARMING", None)
    assert config.CACHE_WARMING == "idle"

    os.environ["PATCHPAL_CACHE_WARMING"] = "streaming"
    assert config.CACHE_WARMING == "streaming"

    os.environ["PATCHPAL_CACHE_WARMING"] = "off"
    assert config.CACHE_WARMING == "off"

    # Invalid value falls back to default.
    os.environ["PATCHPAL_CACHE_WARMING"] = "bogus"
    assert config.CACHE_WARMING == "idle"

    del os.environ["PATCHPAL_CACHE_WARMING"]
