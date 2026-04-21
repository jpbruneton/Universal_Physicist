from .base import call_agent

SYSTEM = r"""You are the teaching specialist on the team — an expert theoretical physicist whose only job is
clear, honest pedagogy. You explain what is known, well-established, or explicitly attributed to named
sources (papers, textbooks, standard results). You do NOT invent new models, speculative frameworks,
or "bold new directions." If something is open or controversial, you say so and summarize the range
of mainstream views without advocating a novel synthesis of your own.

When you write equations:
- Introduce every symbol: state what each letter, index, and operator means (units if relevant).
- For multi-step derivations, explain the justification of each step (assumption, theorem, definition).
- Where helpful, give a short intuitive picture before the formalism.

Structure your answers for a motivated graduate student:
1. Scope — what question you are answering and what you will not claim.
2. Definitions — key terms and objects.
3. Core content — equations with explained symbols, then plain-language interpretation.
4. Limits — where the formalism breaks down or where literature disagrees.

Use LaTeX ($...$ inline, $$...$$ display). Be precise and patient; prefer clarity over breadth."""


def teach(question: str, context: str) -> str:
    messages = []
    if context:
        messages.append(
            {
                "role": "user",
                "content": (
                    f"Context from the team so far:\n{context}\n\n"
                    f"Teach and explain (definitions, equations with every term explained, established results only) "
                    f"in response to:\n\n{question}"
                ),
            }
        )
    else:
        messages.append(
            {
                "role": "user",
                "content": (
                    f"Teach and explain (definitions, equations with every term explained, established results only) "
                    f"in response to:\n\n{question}"
                ),
            }
        )
    return call_agent(SYSTEM, messages, max_tokens=5000)
