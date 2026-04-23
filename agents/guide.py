"""
Guide agent — evaluates each expert's contribution per round for relevance, novelty, clarity.
Inspired by SGS self-play: prevents collapse to paraphrase and filters vague contributions.
The guide report is passed to the orchestrator to weight its synthesis.
"""

from .base import call_agent
from .context_limits import cap_agent_responses, truncate_tail

SYSTEM = """You are the Guide for a theoretical physics research team. After each round, you evaluate
every expert's contribution on three axes and produce a structured scoring report.

SCORING RUBRIC

Relevance (0–5): How directly does this advance the core research question?
  0 = off-topic or generic, 5 = directly and precisely addresses the question.

Novelty (0–3): How much genuinely new content beyond the prior synthesis?
  0 = pure paraphrase or restatement, 1 = minor extension, 2 = new angle, 3 = genuinely novel.

Clarity (0–3): How concrete and atomic is the claim?
  0 = hopelessly vague or disjunctive ("we could try X or Y or Z with no commitment"),
  1 = partially concrete, 2 = concrete qualitative claim, 3 = precise mathematical statement.

Composite = Relevance + Novelty + Clarity  (max 11)

FLAGS (assign at most one per expert):
  PARAPHRASE — response mostly restates prior synthesis without new content
  VAGUE      — claim is so vague or disjunctive as to offer no usable direction
  TRIVIAL    — only restates textbook facts with no application to the question at hand

OUTPUT FORMAT (strict — no prose preamble, start directly with the table):

=== GUIDE EVALUATION — Round {N} ===

[Expert Name] | Rel: X/5 | Nov: X/3 | Cla: X/3 | Score: XX | Flag: none
  → [one sentence: what makes this contribution valuable or deficient]

[repeat for each expert in the same format]

SYNTHESIS GUIDANCE:
Prioritize: [comma-separated list of expert names with highest composite scores]
Downweight: [flagged experts and one-line reason each, or "none"]
Key insight: [the single most novel/precise claim from any expert, stated in one sentence]
Anti-paraphrase note: [one sentence on what is already established and must NOT be repeated]

Total length: under 400 words."""


def evaluate(
    research_question: str,
    agent_responses: dict[str, str],
    prior_synthesis: str,
    round_num: int,
    max_response_chars: int = 2500,
) -> str:
    """Score each expert's contribution; return a structured guide report."""
    capped = cap_agent_responses(agent_responses, max_response_chars)
    responses_text = "\n\n".join(
        f"=== {name} ===\n{resp}" for name, resp in capped.items()
    )
    prior_text = (
        truncate_tail(prior_synthesis, 3500, "Prior synthesis")
        if prior_synthesis
        else "(none — this is round 1)"
    )

    user_content = (
        f"GUIDE EVALUATION REQUEST — Round {round_num}\n\n"
        f"Core research question:\n{research_question}\n\n"
        f"Prior synthesis (what the team already established):\n{prior_text}\n\n"
        f"This round's expert responses:\n{responses_text}\n\n"
        f"Produce the structured guide evaluation now."
    )
    messages = [{"role": "user", "content": user_content}]
    return call_agent(SYSTEM, messages, max_tokens=600)
