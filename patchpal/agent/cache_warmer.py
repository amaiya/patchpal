"""Prompt cache warming.

Keeps a prompt cache entry (system prompt + tools + conversation prefix) alive by
re-sending its request with a one-token output cap just before the entry's TTL
expires. This converts would-be cache *misses* (full-price prefix re-writes) into
cheap cache *reads* on the next real turn.

Design ported from pi-mono's ``cache-warmer.ts`` (see PI_MONO_CACHE_WARMING.md):

- A background timer fires at ~90% of the assumed TTL.
- On fire, a throwaway ``max_tokens=1`` replay re-reads the cached prefix, which
  resets the provider-side TTL clock.
- Warming is economically gated: it only fires when the expected savings from
  avoiding a cache miss exceed the cost of the warming replay.
- It is best-effort: a failed or stale warm never disrupts the live run.

The warmer is deliberately self-contained. The agent records the most recent
request after each real LLM call and arms the warmer; the agent cancels the
warmer before each real call (the real turn supersedes any pending warm) and when
the conversation context changes.
"""

from __future__ import annotations

import os
import threading
import time
from typing import Any, Dict, List, Optional

import litellm

# Probability that a real request arrives before the cache entry expires.
# While the agent is actively streaming through a multi-step turn, another
# intra-turn round-trip is almost certain, so the probability is ~1.0. While the
# session is idle (waiting on the human), empirically only ~15% of idle gaps see
# a follow-up request before expiry (pi-mono's measured IDLE_CONTINUATION_PROBABILITY).
_STREAMING_CONTINUATION_PROBABILITY = 1.0
_IDLE_CONTINUATION_PROBABILITY = 0.15

# Safety horizons: stop warming after this much wall-clock time to avoid warming
# an entry forever when the user has clearly walked away.
_MAX_STREAMING_WARMING_AGE_S = 60 * 60  # 60 min
_MAX_IDLE_WARMING_AGE_S = 30 * 60  # 30 min


def _debug(msg: str) -> None:
    if os.environ.get("PATCHPAL_DEBUG_CACHE") == "true":
        print(f"[CACHE WARM] {msg}", flush=True)


class CacheWarmer:
    """Schedules and fires best-effort prompt-cache-warming replays.

    Thread-safety: a single :class:`threading.Timer` is armed at a time, guarded by
    an internal lock. :meth:`arm` cancels any previously-armed timer before arming
    a new one; :meth:`cancel` cancels the pending timer.
    """

    def __init__(
        self,
        model_id: str,
        mode: str,
        ttl_seconds: int,
        min_savings: float,
        litellm_kwargs: Optional[Dict[str, Any]] = None,
        pricing_model_id: Optional[str] = None,
    ):
        """Initialize the cache warmer.

        Args:
            model_id: LiteLLM model identifier used to INVOKE the model. Must be
                the exact same identifier as the real calls (e.g. the full Bedrock
                inference-profile ARN) so the replay reads the same cache entry and
                targets a valid endpoint.
            mode: One of 'streaming', 'idle', or 'off'.
            ttl_seconds: Assumed cache TTL; the warmer fires at ~90% of this.
            min_savings: Minimum expected savings (USD) required to fire a warm.
            litellm_kwargs: Extra kwargs forwarded to litellm.completion (e.g.
                drop_params for Bedrock). The warming replay must mirror real-call
                kwargs so it reads the same cache entry.
            pricing_model_id: Identifier used ONLY for pricing lookups in the
                economic gate. Bedrock ARNs aren't in LiteLLM's cost map, so this
                should be the resolved model name (e.g. 'bedrock/anthropic.claude-
                opus-4'). Defaults to ``model_id`` when not provided.
        """
        self.model_id = model_id
        self.pricing_model_id = pricing_model_id or model_id
        self.mode = mode
        self.ttl_seconds = max(1, int(ttl_seconds))
        self.min_savings = float(min_savings)
        self.litellm_kwargs = dict(litellm_kwargs or {})

        # A max_tokens=1 replay is NOT safe to send for Anthropic budget-based
        # thinking: Anthropic derives `budget_tokens` from `max_tokens` and keys
        # the message cache on it, so the replay would (a) read a DIFFERENT cache
        # entry (defeating the warm) and (b) could still think for thousands of
        # tokens at full price. When thinking/reasoning is requested on an
        # Anthropic model we therefore refuse to warm (ported from pi-mono's
        # isReplayable). Computed once: model_id and litellm_kwargs are fixed for
        # the warmer's lifetime.
        self._replayable = _is_replayable(self.model_id, self.litellm_kwargs)
        if not self._replayable:
            _debug(
                "disabled: request is not safely replayable (thinking/reasoning "
                "enabled on an Anthropic model); max_tokens=1 warm would miss the "
                "cache and may incur thinking cost"
            )

        self._lock = threading.Lock()
        self._timer: Optional[threading.Timer] = None
        self._generation = 0  # bumped on every arm()/cancel() to invalidate stale fires

        # Snapshot of the last real request, captured by record_request().
        self._messages: Optional[List[Dict[str, Any]]] = None
        self._tools: Optional[List[Dict[str, Any]]] = None
        self._prompt_tokens: int = 0
        self._cache_read_tokens: int = 0
        self._cache_write_tokens: int = 0

    @property
    def enabled(self) -> bool:
        """True if warming is active.

        Requires a warming mode ('streaming' or 'idle') AND a request that can be
        safely replayed with a one-token output cap (see ``_is_replayable``).
        """
        return self.mode in ("streaming", "idle") and self._replayable

    def record_request(
        self,
        messages: List[Dict[str, Any]],
        tools: Optional[List[Dict[str, Any]]],
        usage: Any,
    ) -> None:
        """Record the most recent real request so it can be replayed to warm the cache.

        Args:
            messages: The exact messages list sent on the last real call (already
                carrying cache_control / cachePoint markers).
            tools: The tools list sent on the last real call.
            usage: The response ``usage`` object, used to size the economic gate.
        """
        if not self.enabled:
            return
        # Shallow-copy the list container so later mutation of the agent's working
        # list doesn't change our snapshot; message dicts themselves are not mutated
        # by the warmer (we only read them).
        self._messages = list(messages) if messages else None
        self._tools = list(tools) if tools else None
        self._prompt_tokens = int(getattr(usage, "prompt_tokens", 0) or 0)
        self._cache_read_tokens = int(getattr(usage, "cache_read_input_tokens", 0) or 0)
        self._cache_write_tokens = int(getattr(usage, "cache_creation_input_tokens", 0) or 0)

    def _continuation_probability(self, warming_streaming: bool) -> float:
        return (
            _STREAMING_CONTINUATION_PROBABILITY
            if warming_streaming
            else _IDLE_CONTINUATION_PROBABILITY
        )

    def _estimate_savings(self, warming_streaming: bool) -> float:
        """Estimate expected USD savings from firing one warming replay.

        expected_savings = P(continuation) * miss_cost - warm_cost

        - miss_cost  = extra cost if the entry expires and the prefix is re-written
                       at the cache-write rate instead of read at the cache-read rate.
        - warm_cost  = cost of reading the whole prefix once (the 1-token output is
                       negligible).
        """
        # Number of prefix tokens that would be re-written on a miss. Prefer the
        # measured cache-read size (the stable prefix that got served from cache);
        # fall back to total prompt tokens if cache stats are unavailable.
        prefix_tokens = self._cache_read_tokens or self._prompt_tokens
        if prefix_tokens <= 0:
            return 0.0

        read_rate, write_rate = _get_cache_rates(self.pricing_model_id)
        if read_rate is None or write_rate is None:
            # Pricing unknown for this model; can't gate economically. Returning 0
            # means "don't warm" — we never warm blindly without a cost basis.
            return 0.0

        miss_cost = max(0.0, prefix_tokens * (write_rate - read_rate))
        warm_cost = prefix_tokens * read_rate
        probability = self._continuation_probability(warming_streaming)
        return probability * miss_cost - warm_cost

    def arm(self, warming_streaming: bool, chain_start: Optional[float] = None) -> None:
        """Arm (or re-arm) the warming timer.

        Args:
            warming_streaming: True when called mid-turn (agent actively working);
                False when called at end-of-turn to warm during idle time. In 'idle'
                mode both are honored; in 'streaming' mode only the streaming arm is.
            chain_start: Monotonic time at which the CURRENT warming chain began.
                ``None`` starts a fresh chain (uses now). When ``_fire`` re-arms for
                the next window it passes the original value so the safety horizon
                measures total time since warming started — not time since the last
                re-arm — otherwise re-arming would reset the clock and warming would
                continue forever instead of stopping after the horizon.
        """
        if not self.enabled or self._messages is None:
            return

        # In 'streaming' mode we only warm during active turns, not while idle.
        if self.mode == "streaming" and not warming_streaming:
            self.cancel()
            return

        # Stop re-arming once the warming chain has run past its safety horizon.
        # (A fresh chain, chain_start=None, always passes.)
        now = time.monotonic()
        origin = now if chain_start is None else chain_start
        max_age = _MAX_STREAMING_WARMING_AGE_S if warming_streaming else _MAX_IDLE_WARMING_AGE_S
        if now - origin > max_age:
            _debug(
                f"stop arm: past safety horizon ({now - origin:.0f}s > {max_age}s, "
                f"streaming={warming_streaming})"
            )
            self.cancel()
            return

        savings = self._estimate_savings(warming_streaming)
        if savings < self.min_savings:
            _debug(
                f"skip arm: expected savings ${savings:.4f} < threshold "
                f"${self.min_savings:.4f} (streaming={warming_streaming})"
            )
            self.cancel()
            return

        # Fire at ~90% of TTL, leaving margin for timer slop.
        delay = max(1.0, min(self.ttl_seconds * 0.9, self.ttl_seconds - 10))

        # Latest safe wall-clock time to actually dispatch this warm. A timer can
        # run late (machine sleep, blocked event loop); if it fires after the
        # cache entry has likely expired, the replay lands as a full-price cache
        # WRITE instead of a cheap read — the opposite of what warming is for. We
        # keep half of the pre-expiry margin (ttl - delay) for timer slop and
        # request dispatch, and abort the warm if that deadline has passed (ported
        # from pi-mono's refreshDeadlineAt). ``now`` was captured above for the
        # safety-horizon check and is reused here.
        refresh_deadline = now + delay + max(0.0, (self.ttl_seconds - delay) / 2.0)

        with self._lock:
            self._generation += 1
            generation = self._generation
            if self._timer is not None:
                self._timer.cancel()
            self._timer = threading.Timer(
                delay,
                self._fire,
                args=(generation, warming_streaming, origin, refresh_deadline),
            )
            self._timer.daemon = True
            self._timer.start()
        _debug(
            f"armed: delay={delay:.0f}s expected_savings=${savings:.4f} "
            f"streaming={warming_streaming}"
        )

    def cancel(self) -> None:
        """Cancel any pending warming timer. Safe to call repeatedly."""
        with self._lock:
            self._generation += 1
            if self._timer is not None:
                self._timer.cancel()
                self._timer = None

    def _fire(
        self,
        generation: int,
        warming_streaming: bool,
        armed_at: float,
        refresh_deadline: float,
    ) -> None:
        """Timer callback: send a 1-token replay to refresh the cache entry.

        Best-effort: any failure is swallowed so a bad warm never disrupts the run.
        """
        # Bail if a newer arm()/cancel() superseded this timer.
        with self._lock:
            if generation != self._generation:
                _debug("fire: superseded, skipping")
                return

        now = time.monotonic()

        # Respect the safety horizon.
        max_age = _MAX_STREAMING_WARMING_AGE_S if warming_streaming else _MAX_IDLE_WARMING_AGE_S
        if now - armed_at > max_age:
            _debug("fire: past safety horizon, skipping")
            return

        # Abort if the timer fired so late that the cache entry has likely already
        # expired (machine sleep, blocked event loop). Sending the warm now would
        # land as a full-price cache WRITE rather than a cheap read — strictly
        # worse than doing nothing. Do NOT re-arm: the recorded prefix is stale and
        # the next real turn will re-establish the cache (ported from pi-mono's
        # refreshDeadlineMissed).
        if now > refresh_deadline:
            _debug("fire: past refresh deadline (cache likely expired), skipping")
            return

        messages = self._messages
        tools = self._tools
        if not messages:
            return

        try:
            kwargs: Dict[str, Any] = {
                "model": self.model_id,
                "messages": messages,
                "max_tokens": 1,
                "stream": False,
                **self.litellm_kwargs,
            }
            if tools:
                kwargs["tools"] = tools
                kwargs["tool_choice"] = "auto"

            resp = litellm.completion(**kwargs)
            if os.environ.get("PATCHPAL_DEBUG_CACHE") == "true":
                usage = getattr(resp, "usage", None)
                reads = int(getattr(usage, "cache_read_input_tokens", 0) or 0)
                writes = int(getattr(usage, "cache_creation_input_tokens", 0) or 0)
                _debug(f"fired: replay read={reads} write={writes}")
        except Exception as e:  # noqa: BLE001 - warming must never raise
            _debug(f"fire failed (ignored): {e}")
            return

        # Re-arm for the next TTL window (only if still current). Pass the
        # original chain start (armed_at) so the safety horizon counts total idle
        # time, not time since this single fire — otherwise warming never stops.
        with self._lock:
            still_current = generation == self._generation
        if still_current:
            self.arm(warming_streaming, chain_start=armed_at)


# ---------------------------------------------------------------------------
# Replayability
# ---------------------------------------------------------------------------

# Keys in litellm_kwargs that indicate thinking/reasoning is requested. PatchPal
# never sets these itself; they only arrive via PATCHPAL_LITELLM_KWARGS.
_THINKING_KEYS = ("thinking", "reasoning", "reasoning_effort")


def _is_replayable(model_id: str, litellm_kwargs: Dict[str, Any]) -> bool:
    """Whether a max_tokens=1 replay safely re-reads the same cache entry.

    Unsafe only for Anthropic (direct or via Bedrock) when thinking/reasoning is
    enabled: Anthropic derives ``budget_tokens`` from ``max_tokens`` and keys the
    message cache on it, so a one-token replay would read a different entry
    (defeating the warm) and could still incur thinking cost. For every other
    case — no thinking requested, or non-Anthropic providers — the replay is safe.

    Ported from pi-mono's ``isReplayable``.
    """
    thinking_requested = any(litellm_kwargs.get(key) for key in _THINKING_KEYS)
    if not thinking_requested:
        return True

    # Thinking is requested. It's only safe to replay for providers we can
    # positively identify as NOT using Anthropic budget-based thinking. Known
    # non-Anthropic reasoning providers (OpenAI, Gemini, xAI, DeepSeek, etc.)
    # don't tie the cache key to max_tokens, so their replay is safe. Anything
    # else — including opaque Bedrock inference-profile ARNs that hide the
    # underlying model — is treated as potentially Anthropic and NOT replayed,
    # because a wrong "safe" guess risks a cache-missing, thinking-billed warm.
    mid = model_id.lower()
    known_safe_prefixes = (
        "openai/",
        "azure/",
        "gemini/",
        "vertex_ai/",
        "xai/",
        "deepseek/",
        "groq/",
        "mistral/",
        "ollama/",
        "openrouter/",
    )
    return mid.startswith(known_safe_prefixes)


# ---------------------------------------------------------------------------
# Pricing helpers
# ---------------------------------------------------------------------------

# Anthropic prompt-caching multipliers relative to the base input price:
#   - cache *write* (ephemeral, 5-min): ~1.25x base input
#   - cache *read*: ~0.1x base input
# These are used as a fallback when LiteLLM's model cost map doesn't expose
# explicit cache rates for the model.
_CACHE_WRITE_MULTIPLIER = 1.25
_CACHE_READ_MULTIPLIER = 0.1


def _get_cache_rates(model_id: str) -> tuple[Optional[float], Optional[float]]:
    """Return (cache_read_rate, cache_write_rate) in USD per token for a model.

    Tries LiteLLM's model cost map for explicit cache rates first, then falls back
    to deriving them from the base input-token price using Anthropic's documented
    multipliers. Returns (None, None) if the base price is unknown.
    """
    info: Dict[str, Any] = {}
    try:
        info = litellm.get_model_info(model_id) or {}
    except Exception:
        # Bedrock ARNs / application inference profiles often aren't in the map.
        info = {}

    read_rate = info.get("cache_read_input_token_cost")
    write_rate = info.get("cache_creation_input_token_cost")
    if isinstance(read_rate, (int, float)) and isinstance(write_rate, (int, float)):
        if read_rate > 0 and write_rate > 0:
            return float(read_rate), float(write_rate)

    base = info.get("input_cost_per_token")
    if isinstance(base, (int, float)) and base > 0:
        return base * _CACHE_READ_MULTIPLIER, base * _CACHE_WRITE_MULTIPLIER

    return None, None
