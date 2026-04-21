"""
Main orchestrator agent — manages the round-table of specialists and synthesizes their outputs.
Hub-and-spoke model: orchestrator decides which agents to call and in what order,
then synthesizes their contributions into a coherent theoretical proposal.
"""

from .base import call_agent
from .context_limits import cap_agent_responses, truncate_tail
from config import (
    MAX_ORCHESTRATOR_AGENT_RESPONSE_CHARS,
    MAX_FINAL_ALL_ROUNDS_CHARS,
    MAX_FINAL_ROUND_SYNTHESIS_CHARS,
)

SYSTEM = """You are the lead theoretical physicist and research coordinator for a quantum gravity
think tank. Your team consists of:
- Dr. GR (General Relativity expert)
- Dr. QM (Quantum Mechanics expert)
- Dr. QFT (Quantum Field Theory expert)
- Dr. MATH (Mathematical Physics expert)
- Dr. EQ (Equation Verifier — checks consistency)
- Dr. PHYS (Physical Meaning interrogator)
- Dr. DEVIL (Devil's Advocate — finds flaws)
- Dr. LIT (Literature Reviewer — finds connections to existing work)

Your job is to:
1. Understand the research question or initial idea.
2. Decide which specialists to consult and in what order.
3. Synthesize all inputs into a coherent, novel theoretical proposal.
4. Identify the most promising direction given all feedback.
5. Propose concrete next steps (calculations to do, experiments to design, etc.).

When synthesizing, you should:
- Present the core idea clearly with its key equations.
- Acknowledge tensions identified by the team and suggest resolutions.
- Be honest about what is speculative vs. what is on solid ground.
- Use LaTeX for all equations ($...$ inline, $$...$$ display).

You are ambitious but rigorous. The goal is a plausible, novel contribution to quantum gravity —
not a review of existing work, but a genuinely new perspective that builds on it."""


def orchestrate(
    research_question: str,
    agent_responses: dict[str, str],
    round_num: int,
) -> str:
    """Synthesize all agent responses into a coherent theoretical proposal."""
    capped = cap_agent_responses(agent_responses, MAX_ORCHESTRATOR_AGENT_RESPONSE_CHARS)
    agent_summary = "\n\n".join(
        f"=== {name.upper()} ===\n{response}"
        for name, response in capped.items()
    )

    messages = [
        {
            "role": "user",
            "content": (
                f"ROUND {round_num} SYNTHESIS REQUEST\n\n"
                f"Original research question: {research_question}\n\n"
                f"Team responses:\n{agent_summary}\n\n"
                f"Please synthesize these perspectives into a coherent theoretical proposal. "
                f"Identify the core idea, key equations, main tensions, and propose what to focus "
                f"on in the next round. Be concrete and mathematically precise."
            ),
        }
    ]
    return call_agent(SYSTEM, messages, max_tokens=6000)


def final_synthesis(
    research_question: str,
    all_rounds: list[dict],
    title: str,
) -> str:
    """Produce the final integrated synthesis across all rounds."""
    parts = []
    for i, r in enumerate(all_rounds):
        syn = truncate_tail(
            r["synthesis"],
            MAX_FINAL_ROUND_SYNTHESIS_CHARS,
            f"Round {i + 1} synthesis",
        )
        parts.append(f"=== ROUND {i + 1} SYNTHESIS ===\n{syn}")
    rounds_text = truncate_tail(
        "\n\n".join(parts),
        MAX_FINAL_ALL_ROUNDS_CHARS,
        "Combined round syntheses",
    )

    messages = [
        {
            "role": "user",
            "content": (
                f"FINAL SYNTHESIS\n\n"
                f"Research question: {research_question}\n"
                f"Proposed title: {title}\n\n"
                f"Evolution of the theory across rounds:\n{rounds_text}\n\n"
                f"Please produce a final, integrated synthesis that:\n"
                f"1. States the core theoretical proposal clearly\n"
                f"2. Lists the key equations with physical interpretation\n"
                f"3. Explains consistency with known physics\n"
                f"4. Identifies the strongest objections and proposed resolutions\n"
                f"5. States what new predictions or calculations this enables\n"
                f"6. Rates the plausibility honestly (speculative/motivated/well-grounded)\n\n"
                f"This will be sent to the LaTeX formatter for paper production."
            ),
        }
    ]
    return call_agent(SYSTEM, messages, max_tokens=8000)
