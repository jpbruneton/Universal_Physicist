"""
Bound how much text we send in a single API call. Long multi-round sessions
otherwise grow prompts without limit (higher TPM usage, 429 risk, cost).
"""


def truncate_tail(text: str, max_chars: int, label: str) -> str:
    """
    Keep the end of `text` (most recent content). If truncated, prepend a notice.
    """
    if len(text) <= max_chars:
        return text
    omitted = len(text) - max_chars
    return (
        f"[{label}: omitted {omitted} characters from earlier content; "
        f"newest portion follows — full text remains in session JSON]\n\n"
        + text[-max_chars:]
    )


def cap_agent_responses(agent_responses: dict[str, str], max_chars_per: int) -> dict[str, str]:
    """Return a copy with each specialist response capped (orchestrator input)."""
    return {
        name: truncate_tail(body, max_chars_per, f"{name} reply")
        for name, body in agent_responses.items()
    }
