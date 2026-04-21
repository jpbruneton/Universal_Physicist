"""
Preprocess downloaded paper abstracts into a rich JSON index for the selector agent.
For each paper: generates a 100-word summary and keyword list via a fast Claude call.
Marks string-theory-heavy papers as excluded.

Usage:
    py -3 -m paper_tools.preprocess_papers           # process all unprocessed papers
    py -3 -m paper_tools.preprocess_papers --force   # reprocess everything
"""

import os
import json
import time
import argparse
from pathlib import Path

import anthropic

from config import EXCLUDE_KEYWORDS, EXCLUDE_SAFELIST, ANTHROPIC_API_KEY, get_papers_dir


def _processed_index_path() -> str:
    return os.path.join(get_papers_dir(), "processed_index.json")

SUMMARIZER_SYSTEM = """You are a scientific abstract analyzer. Given a physics paper abstract,
return ONLY a valid JSON object (no markdown, no explanation) with exactly these fields:
{
  "summary": "<100-word plain-English summary of the paper's core contribution>",
  "keywords": ["keyword1", "keyword2", ...],  // 5-10 physics keywords
  "approaches": ["LQG", "AdS/CFT", ...]  // QG approaches the paper relates to
}"""


def is_excluded(title: str, abstract: str) -> bool:
    text = (title + " " + abstract).lower()
    # Keep if any safelist keyword matches (holography, AdS/CFT, etc.)
    if any(kw.lower() in text for kw in EXCLUDE_SAFELIST):
        return False
    # Exclude only if 2+ strong string-theory-only keywords match
    hits = sum(1 for kw in EXCLUDE_KEYWORDS if kw.lower() in text)
    return hits >= 2


def summarize_paper(client: anthropic.Anthropic, title: str, abstract: str) -> dict:
    """Use Claude to generate a structured summary and keywords."""
    prompt = f"Title: {title}\n\nAbstract:\n{abstract}"
    try:
        response = client.messages.create(
            model="claude-haiku-4-5-20251001",  # fast + cheap for preprocessing
            max_tokens=400,
            system=SUMMARIZER_SYSTEM,
            messages=[{"role": "user", "content": prompt}],
        )
        raw = response.content[0].text.strip()
        # Strip markdown code fences if present
        if raw.startswith("```"):
            raw = raw.split("```")[1]
            if raw.startswith("json"):
                raw = raw[4:]
        return json.loads(raw)
    except Exception as e:
        return {"summary": abstract[:200], "keywords": [], "approaches": [], "error": str(e)}


def load_raw_index() -> list[dict]:
    index_path = Path(get_papers_dir()) / "index.json"
    if not index_path.exists():
        return []
    return json.loads(index_path.read_text(encoding="utf-8"))


def load_processed_index() -> dict:
    """Load existing processed index keyed by paper ID."""
    path = _processed_index_path()
    if not Path(path).exists():
        return {}
    return {p["id"]: p for p in json.loads(Path(path).read_text(encoding="utf-8"))}


def save_processed_index(processed: dict) -> None:
    entries = list(processed.values())
    Path(_processed_index_path()).write_text(
        json.dumps(entries, indent=2, default=str),
        encoding="utf-8"
    )


def extract_pdfs(force: bool) -> int:
    """Extract and cache full text for all downloaded PDFs in the active library directory."""
    try:
        from .pdf_reader import extract_library
        n = extract_library(get_papers_dir(), force=force)
        print(f"Full-text extraction: {n} new files created.")
        return n
    except ImportError:
        print("pymupdf not installed — run: pip install pymupdf")
        return 0


def extract_pdfs_for_paths(pdf_paths: list[str], force: bool) -> int:
    """Extract full text only for the listed PDFs (e.g. papers touched in this preprocess run)."""
    if not pdf_paths:
        return 0
    try:
        from .pdf_reader import extract_pdf_paths
        n = extract_pdf_paths(pdf_paths, force, True)
        print(f"Full-text extraction: {n} new files created.")
        return n
    except ImportError:
        print("pymupdf not installed — run: pip install pymupdf")
        return 0


def process_all(force: bool = False) -> None:
    raw_papers = load_raw_index()
    if not raw_papers:
        print("No papers in index.json. Run py -3 -m paper_tools.arxiv_downloader first.")
        return

    processed = {} if force else load_processed_index()
    client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)

    new_count = 0
    touched_ids: list[str] = []
    for paper in raw_papers:
        pid = paper["id"]
        if pid in processed and not force:
            continue
        touched_ids.append(pid)

        title = paper.get("title", "")
        abstract = paper.get("abstract", "")
        excluded = is_excluded(title, abstract)

        print(f"Processing: {title[:65]}{'  [EXCLUDED]' if excluded else ''}")

        if excluded:
            entry = {
                "id": pid,
                "title": title,
                "authors": paper.get("authors", []),
                "published": paper.get("published", ""),
                "txt_file": paper.get("txt_file", ""),
                "pdf_file": paper.get("pdf_file", ""),
                "excluded": True,
                "exclude_reason": "string-theory-heavy content",
                "summary": "",
                "keywords": [],
                "approaches": [],
            }
        else:
            ai_result = summarize_paper(client, title, abstract)
            entry = {
                "id": pid,
                "title": title,
                "authors": paper.get("authors", []),
                "published": paper.get("published", ""),
                "txt_file": paper.get("txt_file", ""),
                "pdf_file": paper.get("pdf_file", ""),
                "excluded": False,
                "summary": ai_result.get("summary", ""),
                "keywords": ai_result.get("keywords", []),
                "approaches": ai_result.get("approaches", []),
            }
            time.sleep(0.5)  # gentle rate limiting

        processed[pid] = entry
        new_count += 1

    save_processed_index(processed)
    included = sum(1 for p in processed.values() if not p.get("excluded"))
    excluded_count = sum(1 for p in processed.values() if p.get("excluded"))
    pdf_count = sum(1 for p in processed.values() if p.get("pdf_file") and Path(p["pdf_file"]).exists())
    print(f"\nDone. {new_count} papers processed.")
    print(f"Library: {included} included, {excluded_count} excluded.")
    print(f"PDFs available: {pdf_count} (run with --extract-pdfs to cache full text for the whole folder)")
    print(f"Index saved to: {_processed_index_path()}")

    # Full-text only for PDFs whose metadata entries were processed in this run — not every PDF
    # left in papers/ from older projects (extract_library would scan the whole directory).
    touched = set(touched_ids)
    pdf_paths_this_run: list[str] = []
    for paper in raw_papers:
        if paper["id"] not in touched:
            continue
        pdf = paper.get("pdf_file")
        if pdf and Path(pdf).exists():
            pdf_paths_this_run.append(pdf)
    if pdf_paths_this_run:
        extract_pdfs_for_paths(pdf_paths_this_run, force=False)


def show_index() -> None:
    processed = load_processed_index()
    if not processed:
        print("No processed index. Run py -3 -m paper_tools.preprocess_papers first.")
        return
    print(f"\nProcessed library: {len(processed)} papers\n")
    for p in processed.values():
        status = "[EXCL]" if p.get("excluded") else "      "
        kw = ", ".join(p.get("keywords", [])[:4])
        print(f"{status} {p['title'][:55]}")
        if not p.get("excluded"):
            print(f"         Keywords: {kw}")
    print()


if __name__ == "__main__":
    from config import set_papers_project

    parser = argparse.ArgumentParser(description="Preprocess arXiv paper abstracts")
    parser.add_argument(
        "--project",
        "-p",
        default="default",
        metavar="SLUG",
        help="Paper library subfolder under papers/ (default: default)",
    )
    parser.add_argument("--force", action="store_true", help="Reprocess all papers")
    parser.add_argument("--show", action="store_true", help="Show processed index")
    parser.add_argument("--extract-pdfs", action="store_true", help="Extract full text from all PDFs")
    args = parser.parse_args()
    set_papers_project(args.project)

    if args.show:
        show_index()
    elif args.extract_pdfs:
        extract_pdfs(force=args.force)
    else:
        process_all(force=args.force)
