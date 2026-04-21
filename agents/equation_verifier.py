"""Equation verifier: combines SymPy symbolic checks with an LLM physics consistency check."""

import re
import sympy as sp
from .base import call_agent

SYSTEM = """You are a rigorous equation verifier for theoretical physics. Given a proposed equation
or set of equations in a quantum gravity context, you perform:

1. DIMENSIONAL ANALYSIS: Check that all terms have consistent dimensions/units. Use Planck units
   (G=ℏ=c=k_B=1) by default. Flag any dimensionally inconsistent equation.

2. SYMMETRY CHECK: Verify that the equation respects the stated symmetries (Lorentz/diffeomorphism
   covariance, gauge invariance, CPT symmetry if applicable). Check index placement (up/down).

3. LIMIT CHECK: Does the equation reduce to known results in appropriate limits?
   - ℏ → 0: classical GR
   - G → 0: flat spacetime QFT
   - c → ∞: Newtonian gravity
   - Low energy: Einstein-Hilbert action

4. SIGN AND FACTOR CHECK: Are factors of 2, π, i correct? Are metric signature conventions stated?

5. SELF-CONSISTENCY: Do the equations form a consistent system? Are there overconstrained or
   underdetermined aspects?

Output your verdict as:
- PASS: equation is dimensionally and symmetry-consistent
- WARNING: equation has issues that need clarification (specify)
- FAIL: equation is definitely wrong (specify why)

Use LaTeX for equations. Be brief and precise."""


def verify_with_sympy(equation_str: str) -> dict:
    """Attempt basic SymPy checks on a simple equation string (best-effort)."""
    results = {}
    try:
        # Try to parse and simplify
        expr = sp.sympify(equation_str)
        results["parsed"] = True
        results["simplified"] = str(sp.simplify(expr))
        results["free_symbols"] = [str(s) for s in expr.free_symbols]
    except Exception as e:
        results["parsed"] = False
        results["error"] = str(e)
    return results


def _extract_equations(text: str) -> list[str]:
    """Extract LaTeX equations from text for SymPy attempts."""
    # Look for $...$ and $$...$$ patterns
    display = re.findall(r'\$\$(.+?)\$\$', text, re.DOTALL)
    inline = re.findall(r'\$([^$]+?)\$', text)
    return display + inline


def verify(proposed_text: str, context: str = "") -> str:
    """Full verification: SymPy best-effort + LLM physics check."""
    sympy_results = []
    equations = _extract_equations(proposed_text)
    for eq in equations[:5]:  # limit to first 5 equations
        # Strip LaTeX commands for sympy (best effort)
        clean = eq.replace(r'\frac', '').replace(r'\partial', 'D').replace('^', '**')
        clean = re.sub(r'\\[a-zA-Z]+', '', clean).strip()
        if clean:
            result = verify_with_sympy(clean)
            sympy_results.append(f"Equation `{eq[:60]}...`: {result}")

    sympy_summary = "\n".join(sympy_results) if sympy_results else "No parseable equations found for SymPy."

    messages = [
        {
            "role": "user",
            "content": (
                f"Please verify the following proposed physics equations/theory:\n\n"
                f"{proposed_text}\n\n"
                f"{'Context: ' + context if context else ''}\n\n"
                f"SymPy basic parse results (informational):\n{sympy_summary}"
            ),
        }
    ]
    return call_agent(SYSTEM, messages)
