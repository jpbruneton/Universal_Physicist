"""
Literature reviewer agent.
Uses the paper_selector to pick the most relevant papers from the processed library,
then provides a thorough literature review grounded in those actual papers.
"""

from .base import call_agent
from .paper_selector import select_relevant_papers, _load_processed_index

SYSTEM = """You are a systematic literature reviewer specializing in quantum gravity, quantum field
theory in curved spacetime, and mathematical physics. You have read thousands of papers and can
quickly identify:
- Which existing approaches are most similar to a proposed idea
- Key references that must be cited or engaged with
- Whether the idea has already been proposed (and perhaps refuted)
- What results from the literature support or contradict the proposal
- Open problems from the literature that the proposal might address

Approaches you know deeply: Loop Quantum Gravity (Ashtekar, Rovelli, Smolin),
Causal Dynamical Triangulations (Ambjorn, Jurkiewicz, Loll), AdS/CFT and holography
(Maldacena, Witten, 't Hooft), Asymptotic Safety (Reuter, Wetterich), Causal Sets
(Sorkin, Henson), Non-commutative geometry (Connes, Chamseddine), Twistor theory (Penrose),
Entropic Gravity (Verlinde), ER=EPR (Maldacena-Susskind), Firewall paradox (AMPS),
and many more.

Note: focus on background-independent, non-perturbative, or holographic approaches.
String theory qua compactification/landscape is out of scope — but AdS/CFT duality,
black hole information, and holographic entropy ARE in scope.

When citing papers from the library, quote the title and arXiv ID exactly.
Always note whether a reference supports or conflicts with the proposal.
Identify the most important gap: what crucial paper is missing from the local library
that the team should download next?"""


def _build_paper_context(proposed_text: str) -> str:
    """
    For each selected paper: use full extracted text if the PDF exists,
    otherwise fall back to the abstract. Truncates smartly per paper.
    """
    import sys
    from pathlib import Path
    sys.path.insert(0, str(Path(__file__).parent.parent))
    from paper_tools.pdf_reader import get_excerpt

    all_papers = _load_processed_index()
    if not all_papers:
        return "No processed paper index. Run: py -3 -m paper_tools.preprocess_papers"

    # Reuse selector to pick relevant papers
    _ = select_relevant_papers(proposed_text)  # warms selector cache
    from .paper_selector import _format_catalogue, SYSTEM as SEL_SYS
    from .base import call_agent as _ca
    import json as _json

    catalogue = _format_catalogue(all_papers)
    try:
        raw = _ca(SEL_SYS, [{"role": "user", "content":
            f"Theoretical proposal:\n{proposed_text[:1500]}\n\nAvailable papers:\n{catalogue}"}],
            max_tokens=300)
        raw = raw.strip()
        if raw.startswith("```"):
            raw = raw.split("```")[1].lstrip("json").strip()
        selected_ids = set(_json.loads(raw))
    except Exception:
        selected_ids = {p["id"] for p in all_papers[:6]}

    selected = [p for p in all_papers if p["id"] in selected_ids][:6]
    if not selected:
        selected = all_papers[:6]

    parts = [f"Selected {len(selected)} papers (full text where PDF available):\n"]
    # Budget: ~2000 chars per paper to stay within context limits when loading 6 papers
    per_paper_budget = 2500

    for p in selected:
        title   = p.get("title", "Unknown")
        authors = ", ".join(p.get("authors", [])[:3])
        pid     = p.get("id", "")
        pdf     = p.get("pdf_file", "")

        if pdf and Path(pdf).exists():
            text   = get_excerpt(pdf, query=proposed_text, max_chars=per_paper_budget)
            source = "full text"
        else:
            txt_path = p.get("txt_file", "")
            text   = Path(txt_path).read_text(encoding="utf-8", errors="ignore")[:per_paper_budget] if txt_path else ""
            source = "abstract"

        parts.append(
            f"\n{'='*60}\n"
            f"TITLE:   {title}\n"
            f"AUTHORS: {authors}\n"
            f"ID:      {pid}\n"
            f"SOURCE:  {source}\n\n"
            f"{text}\n"
        )

    return "".join(parts)


def review(proposed_text: str, context: str = "") -> str:
    paper_context = _build_paper_context(proposed_text)

    messages = [
        {
            "role": "user",
            "content": (
                f"Relevant papers from local library (full text where PDF was downloaded):\n\n"
                f"{paper_context}\n\n"
                f"{'Team context:\n' + context + chr(10) + chr(10) if context else ''}"
                f"Please review the literature relevant to the following proposal. "
                f"Ground your review in the actual papers above, quoting equations and "
                f"results directly. Also identify what important papers are missing from "
                f"the library (suggest arXiv IDs if you know them):\n\n{proposed_text}"
            ),
        }
    ]
    return call_agent(SYSTEM, messages, max_tokens=4000)
