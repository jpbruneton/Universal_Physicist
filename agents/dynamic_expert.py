"""Ad-hoc specialist built from a generated system prompt (see session_planner + main.py)."""

from .base import call_agent


def make_consult(system_prompt: str):
    """Return a consult(question, context) callable compatible with other agents."""

    def consult(question: str, context: str) -> str:
        messages = []
        if context:
            messages.append(
                {"role": "user", "content": f"Context from team:\n{context}\n\nQuestion: {question}"}
            )
        else:
            messages.append({"role": "user", "content": question})
        return call_agent(system_prompt, messages)

    return consult
