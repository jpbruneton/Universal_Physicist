"""Ad-hoc specialist built from a generated system prompt (see session_planner + main.py)."""

from .base import call_agent


_DEFINE_TERMS_PREFIX = """MANDATORY STYLE RULE — apply to every response without exception:
Define every mathematical object, symbol, and technical term the first time you use it.
This means: when you write an equation, immediately state what every symbol denotes.
When you introduce a geometric structure (connection, tensor, bundle, etc.), state its type
and transformation law in one sentence before using it.
Do NOT assume shared context — write as if the reader has not seen the prior rounds.

"""


def make_consult(system_prompt: str):
    """Return a consult(question, context) callable compatible with other agents."""
    full_system = _DEFINE_TERMS_PREFIX + system_prompt

    def consult(question: str, context: str) -> str:
        messages = []
        if context:
            messages.append(
                {"role": "user", "content": f"Context from team:\n{context}\n\nQuestion: {question}"}
            )
        else:
            messages.append({"role": "user", "content": question})
        return call_agent(full_system, messages, max_tokens=7000)

    return consult
