"""
Conjecturer agent — generates a minimal stepping-stone sub-problem for the team each round.
Inspired by SGS self-play: the conjecturer proposes intermediate-difficulty problems
whose solutions most advance the main research question without being trivial or impossibly open.
"""

from .base import call_agent
from .context_limits import truncate_tail

SYSTEM = """You are the Conjecturer for a theoretical physics research team.

Your role: propose ONE concrete, minimal stepping-stone sub-problem for this round.

A good sub-problem satisfies all of the following:
1. MORE concrete and tractable than the full research question
2. NOT trivially obvious — experts cannot answer it with a sentence from a textbook
3. NOT impossibly open-ended — it is plausibly resolvable with focused calculation or argument
4. If solved, would MEANINGFULLY advance the main research question
5. NOT already resolved in the current synthesis

Output format (strict — no preamble, no commentary outside these three fields):

SUB-PROBLEM: [one precise, mathematical statement of the sub-problem — include notation]
RATIONALE: [2–3 sentences: why this specific sub-problem, what its solution unlocks, why it is intermediate difficulty]
MATHEMATICAL HOOK: [a concrete equation, operator, construction, or calculation step that would constitute measurable progress]

Total length: under 200 words. Be mathematical, not rhetorical."""


def generate_subproblem(
    research_question: str,
    current_synthesis: str,
    round_num: int,
) -> str:
    """Generate a stepping-stone sub-problem to focus the team this round."""
    prior_text = (
        truncate_tail(current_synthesis, 2500, "Current synthesis")
        if current_synthesis
        else "(none — this is round 1, no prior synthesis)"
    )

    user_content = (
        f"CONJECTURER REQUEST — Round {round_num}\n\n"
        f"Main research question:\n{research_question}\n\n"
        f"What the team has established so far:\n{prior_text}\n\n"
        f"Propose ONE concrete stepping-stone sub-problem for this round."
    )
    messages = [{"role": "user", "content": user_content}]
    return call_agent(SYSTEM, messages, max_tokens=350)
