"""
Paper selector agent — given the current theoretical proposal, selects the most
relevant papers from the processed index and returns their full abstracts.
This feeds into the literature_reviewer agent.
"""

import json
import os
import re
from pathlib import Path
from .base import call_agent
from config import MAX_PAPER_CATALOGUE_ENTRIES, get_papers_dir


def _processed_index_path() -> str:
    return os.path.join(get_papers_dir(), "processed_index.json")

SYSTEM = """You are a scientific paper selector for a quantum gravity research team.
Given a theoretical proposal and a list of available papers (with titles, keywords, and summaries),
select the 5-8 most relevant papers that:
1. Directly address the mathematical or physical approach being proposed
2. Contain results, techniques, or constraints the proposal must engage with
3. Present competing or complementary approaches worth comparing

Return ONLY a JSON array of paper IDs to select, like:
["http://arxiv.org/abs/hep-th/9711200v3", "http://arxiv.org/abs/gr-qc/9606089v1"]

No explanation, just the JSON array."""


def _load_processed_index() -> list[dict]:
    path = _processed_index_path()
    if not Path(path).exists():
        return []
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    return [p for p in data if not p.get("excluded", False)]


def narrow_papers_for_catalogue(papers: list[dict], query_text: str, max_papers: int) -> list[dict]:
    """
    When the library has more than max_papers entries, keep the top max_papers
    by simple lexical overlap with query_text (title + summary + keywords).
    Avoids sending the entire index to the LLM (hundreds of kB → 429s).
    """
    if len(papers) <= max_papers:
        return papers
    q = set(re.findall(r"[a-zA-Z][a-zA-Z\-]{2,}", query_text.lower()))
    if not q:
        return papers[-max_papers:]
    scored: list[tuple[int, dict]] = []
    for p in papers:
        blob = (
            f"{p.get('title', '')} {p.get('summary', '')} "
            f"{' '.join(p.get('keywords') or [])}"
        )
        w = set(re.findall(r"[a-zA-Z][a-zA-Z\-]{2,}", blob.lower()))
        scored.append((len(q & w), p))
    scored.sort(key=lambda sp: sp[0], reverse=True)
    return [p for _, p in scored[:max_papers]]


def _format_catalogue(papers: list[dict]) -> str:
    lines = []
    for p in papers:
        kw = ", ".join(p.get("keywords", [])[:6])
        approaches = ", ".join(p.get("approaches", []))
        lines.append(
            f'ID: {p["id"]}\n'
            f'Title: {p["title"]}\n'
            f'Keywords: {kw}\n'
            f'Approaches: {approaches}\n'
            f'Summary: {p.get("summary", "")[:200]}\n'
        )
    return "\n---\n".join(lines)


def _read_abstract(paper: dict) -> str:
    txt_path = paper.get("txt_file", "")
    if txt_path and Path(txt_path).exists():
        return Path(txt_path).read_text(encoding="utf-8", errors="ignore")
    return f"Title: {paper['title']}\nSummary: {paper.get('summary', '')}"


def select_relevant_papers(proposal: str, max_papers: int = 6) -> str:
    """
    Returns a formatted string of selected paper abstracts relevant to the proposal.
    Falls back gracefully if the processed index is missing.
    """
    papers = _load_processed_index()
    if not papers:
        return (
            "No processed paper index available. "
            "Run: py -3 -m paper_tools.preprocess_papers\n"
            "Then: py -3 -m paper_tools.arxiv_downloader --core"
        )

    papers = narrow_papers_for_catalogue(papers, proposal, MAX_PAPER_CATALOGUE_ENTRIES)
    catalogue = _format_catalogue(papers)

    # Ask the selector agent which papers to pick
    messages = [
        {
            "role": "user",
            "content": (
                f"Theoretical proposal:\n{proposal[:1500]}\n\n"
                f"Available papers:\n{catalogue}"
            ),
        }
    ]

    try:
        raw = call_agent(SYSTEM, messages, max_tokens=300)
        # Parse the JSON array
        raw = raw.strip()
        if raw.startswith("```"):
            raw = raw.split("```")[1].lstrip("json").strip()
        selected_ids = set(json.loads(raw))
    except Exception:
        # Fallback: just take first max_papers
        selected_ids = {p["id"] for p in papers[:max_papers]}

    selected = [p for p in papers if p["id"] in selected_ids][:max_papers]
    if not selected:
        selected = papers[:max_papers]

    # Build rich context string for the literature reviewer
    parts = [f"Selected {len(selected)} relevant papers:\n"]
    for p in selected:
        abstract = _read_abstract(p)
        kw = ", ".join(p.get("keywords", []))
        parts.append(
            f"{'='*60}\n"
            f"TITLE: {p['title']}\n"
            f"AUTHORS: {', '.join(p.get('authors', [])[:3])}\n"
            f"KEYWORDS: {kw}\n"
            f"ABSTRACT:\n{abstract[:600]}\n"
        )

    return "\n".join(parts)
