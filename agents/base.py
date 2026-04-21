import random
import time

import anthropic
from config import AGENT_MODEL, ANTHROPIC_API_KEY, LARGE_REQUEST_WARN_INPUT_CHARS

_client = None

# Transient overload / rate limits: wait and retry without surfacing as failure.
_INITIAL_BACKOFF_SEC = 45.0
_MAX_BACKOFF_SEC = 420.0
_BACKOFF_MULTIPLIER = 1.75


def get_client() -> anthropic.Anthropic:
    global _client
    if _client is None:
        _client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)
    return _client


def _is_retryable(exc: BaseException) -> bool:
    """True for rate limits, overload, and transient network — safe to wait and retry."""
    if isinstance(exc, anthropic.RateLimitError):
        return True
    if isinstance(exc, (anthropic.APIConnectionError, anthropic.APITimeoutError)):
        return True
    if isinstance(exc, anthropic.APIStatusError):
        code = getattr(exc, "status_code", None)
        return code in (429, 503, 529)
    return False


def _approx_input_chars(system_prompt: str, messages: list[dict]) -> int:
    """Rough character count for logging (not exact tokens)."""
    n = len(system_prompt)
    for m in messages:
        c = m.get("content")
        if isinstance(c, str):
            n += len(c)
        elif isinstance(c, list):
            for block in c:
                if isinstance(block, dict) and block.get("type") == "text":
                    n += len(block.get("text", ""))
    return n


def _looks_like_request_too_large(exc: BaseException) -> bool:
    s = str(exc).lower()
    if "prompt is too long" in s or "context length" in s:
        return True
    if "token" in s and ("limit" in s or "exceed" in s or "too many" in s):
        return True
    if "input" in s and "long" in s:
        return True
    return False


def _retry_pause_explanation(exc: BaseException) -> str:
    """Short reason shown while sleeping before retry (user-facing)."""
    if isinstance(exc, anthropic.RateLimitError):
        return "Anthropic API rate limit — your org quota or requests-per-minute was exceeded"
    if isinstance(exc, anthropic.APIStatusError):
        code = getattr(exc, "status_code", None)
        if code == 429:
            return "HTTP 429 — API rate limit"
        if code == 503:
            return "HTTP 503 — API temporarily overloaded"
        if code == 529:
            return "HTTP 529 — API overloaded"
    if isinstance(exc, anthropic.APIConnectionError):
        return "network connection error to Anthropic API"
    if isinstance(exc, anthropic.APITimeoutError):
        return "request timeout to Anthropic API"
    return "transient API error"


def call_agent(system_prompt: str, messages: list[dict], max_tokens: int = 4096) -> str:
    """Call the model; on rate limit / transient API errors, sleep with backoff and retry."""
    client = get_client()
    delay = _INITIAL_BACKOFF_SEC
    attempt = 0
    while True:
        try:
            approx_in = _approx_input_chars(system_prompt, messages)
            if approx_in > LARGE_REQUEST_WARN_INPUT_CHARS:
                print(
                    f"  [API] Large request (~{approx_in} chars estimated input; "
                    f"output max_tokens={max_tokens}). "
                    f"Big calls burn TPM and increase 429 risk — "
                    f"lower MAX_*_CHARS in config.py if this persists.",
                    flush=True,
                )
            response = client.messages.create(
                model=AGENT_MODEL,
                max_tokens=max_tokens,
                system=[
                    {
                        "type": "text",
                        "text": system_prompt,
                        "cache_control": {"type": "ephemeral"},
                    }
                ],
                messages=messages,
            )
            return response.content[0].text
        except Exception as e:
            if not _is_retryable(e):
                if _looks_like_request_too_large(e):
                    print(
                        "  [API] Request may be too large — trim "
                        "MAX_EXPERT_CONTEXT_CHARS / MAX_FINAL_* / MAX_ORCHESTRATOR_* in config.py.",
                        flush=True,
                    )
                raise
            attempt += 1
            jitter = random.uniform(0.0, min(5.0, delay * 0.15))
            wait = min(delay + jitter, _MAX_BACKOFF_SEC)
            name = type(e).__name__
            msg = str(e).split("\n")[0][:120]
            why = _retry_pause_explanation(e)
            print(
                f"  [API retry] {name} (attempt {attempt}): {msg}\n"
                f"  Pausing {wait:.1f}s because of: {why}.\n"
                f"  (Completed rounds stay saved; will retry this same call after the pause.)",
                flush=True,
            )
            time.sleep(wait)
            delay = min(delay * _BACKOFF_MULTIPLIER, _MAX_BACKOFF_SEC)
