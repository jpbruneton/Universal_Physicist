import random
import time

import anthropic
from config import ANTHROPIC_API_KEY, AGENT_MODEL

_client = None

# Transient overload / rate limits: wait and retry without surfacing as failure.
_INITIAL_BACKOFF_SEC = 12.0
_MAX_BACKOFF_SEC = 300.0
_BACKOFF_MULTIPLIER = 1.6


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


def call_agent(system_prompt: str, messages: list[dict], max_tokens: int = 4096) -> str:
    """Call the model; on rate limit / transient API errors, sleep with backoff and retry."""
    client = get_client()
    delay = _INITIAL_BACKOFF_SEC
    attempt = 0
    while True:
        try:
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
                raise
            attempt += 1
            jitter = random.uniform(0.0, min(5.0, delay * 0.15))
            wait = min(delay + jitter, _MAX_BACKOFF_SEC)
            name = type(e).__name__
            msg = str(e).split("\n")[0][:120]
            print(
                f"  [API retry] {name} (attempt {attempt}): {msg}\n"
                f"  Pausing {wait:.1f}s — completed rounds stay saved; will retry this call…",
                flush=True,
            )
            time.sleep(wait)
            delay = min(delay * _BACKOFF_MULTIPLIER, _MAX_BACKOFF_SEC)
