"""
Deep reader agent — given a specific paper (title / arXiv ID), reads its full text
(if the PDF is available) and extracts insights relevant to the current proposal.

The orchestrator can invoke this when a specific paper appears particularly important
and the abstract alone is insufficient.
"""

import json
from pathlib import Path
from .base import call_agent
from config import get_papers_dir

SYSTEM = """You are a meticulous scientific reader specializing in quantum gravity and
mathematical physics. You are given the full text (or a large excerpt) of a research paper
and a specific research question. Your job is to extract:

1. KEY EQUATIONS — the most important equations in the paper, reproduced in LaTeX, with
   a one-sentence explanation of what each means.

2. MAIN CLAIMS — the central results or conjectures, stated precisely.

3. METHODS / MATHEMATICAL TOOLS — what formalism does the paper use? What are the key
   mathematical ingredients?

4. DIRECT RELEVANCE — how does this paper's content bear on the current research question?
   What does it support, contradict, or suggest?

5. HIDDEN GEMS — results buried in the paper that are not in the abstract but are highly
   relevant to quantum gravity. Look for lemmas, remarks, and appendices.

6. LIMITATIONS — what does the paper explicitly NOT address? What assumptions does it make
   that might not hold in our context?

Be precise and technical. Quote equations verbatim in LaTeX. Cite section numbers when
you refer to specific results."""


def read_paper(
    paper_title: str,
    paper_text: str,
    research_question: str,
    context: str = "",
) -> str:
    messages = [{
        "role": "user",
        "content": (
            f"Research question: {research_question}\n\n"
            f"{'Team context:\n' + context + chr(10) + chr(10) if context else ''}"
            f"Please deep-read the following paper and extract all insights relevant to "
            f"the research question.\n\n"
            f"PAPER: {paper_title}\n\n"
            f"{'='*60}\n"
            f"{paper_text}"
        ),
    }]
    return call_agent(SYSTEM, messages, max_tokens=5000)


def read_by_id(
    arxiv_id: str,
    research_question: str,
    context: str = "",
    max_chars: int = 40000,
) -> str:
    """
    Find a paper in the library by arXiv ID, load its full text or abstract,
    and run the deep-reader agent on it.
    """
    import sys
    sys.path.insert(0, str(Path(__file__).parent.parent))
    from paper_tools.pdf_reader import get_excerpt

    # Find in index
    index_path = Path(get_papers_dir()) / "processed_index.json"
    if not index_path.exists():
        return "[No processed index — run py -3 -m paper_tools.preprocess_papers first]"

    papers = json.loads(index_path.read_text(encoding="utf-8"))
    paper = next(
        (p for p in papers if arxiv_id in p.get("id", "") or arxiv_id in p.get("txt_file", "")),
        None
    )

    if paper is None:
        return f"[Paper not found in library: {arxiv_id}]"

    title = paper.get("title", "Unknown")

    # Try full text first
    pdf_path = paper.get("pdf_file", "")
    if pdf_path and Path(pdf_path).exists():
        text = get_excerpt(pdf_path, query=research_question, max_chars=max_chars)
        source = "full text"
    else:
        # Fall back to abstract
        txt_path = paper.get("txt_file", "")
        text = Path(txt_path).read_text(encoding="utf-8", errors="ignore") if txt_path else ""
        source = "abstract only (no PDF downloaded)"

    if not text:
        return f"[No text available for: {title}]"

    print(f"  Deep reading '{title[:60]}' ({source}, {len(text):,} chars)")
    return read_paper(title, text, research_question, context)
