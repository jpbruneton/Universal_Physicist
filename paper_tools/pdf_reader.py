"""
PDF text extraction for the quantum gravity paper library.

Hierarchy of what agents get to read:
  1. Abstract (.txt) — always available, used by paper_selector
  2. Full text (.fulltext.txt) — extracted from PDF when available
  3. Sections dict — structured extraction: intro / body / conclusion

Text is extracted once and cached as <base>.fulltext.txt alongside the PDF.
The cache means repeated agent calls are cheap (no re-parsing).
"""

import re
from pathlib import Path

# ── Extraction backend ────────────────────────────────────────────────────────

def _extract_with_pymupdf(pdf_path: str) -> str:
    import pymupdf  # type: ignore
    doc = pymupdf.open(pdf_path)
    pages = []
    for page in doc:
        pages.append(page.get_text("text"))
    doc.close()
    return "\n".join(pages)


def _extract_with_pypdf(pdf_path: str) -> str:
    import pypdf  # type: ignore
    reader = pypdf.PdfReader(pdf_path)
    return "\n".join(p.extract_text() or "" for p in reader.pages)


def extract_raw_text(pdf_path: str) -> str:
    """Extract full raw text from a PDF. Tries pymupdf, falls back to pypdf."""
    try:
        return _extract_with_pymupdf(pdf_path)
    except ImportError:
        pass
    try:
        return _extract_with_pypdf(pdf_path)
    except ImportError:
        return ""
    except Exception as e:
        return f"[Extraction error: {e}]"


# ── Section splitter ──────────────────────────────────────────────────────────

# Common section header patterns in physics papers
_SECTION_RE = re.compile(
    r"^\s{0,4}(?:\d+\.?\s+)?"      # optional numbering: "1. " or "1 "
    r"(Abstract|Introduction|Motivation|Background|"
    r"Framework|Formalism|Mathematical\s+\w+|"
    r"Main\s+Results?|Results?|Equations?|"
    r"Discussion|Physical\s+Interpretation|"
    r"Consistency|Limits?|Classical\s+Limit|"
    r"Black\s+Holes?|Quantum\s+\w+|Holograph\w*|"
    r"Conclusion|Summary|Outlook|Future|"
    r"Acknowledgements?|References?|Bibliography)"
    r"\s*$",
    re.IGNORECASE | re.MULTILINE,
)


def split_sections(text: str) -> dict[str, str]:
    """
    Split extracted text into a dict of {section_name: content}.
    Falls back to coarse quartile split if no headers are found.
    """
    matches = list(_SECTION_RE.finditer(text))
    if len(matches) < 2:
        # No clear section headers — split by quarters
        n = len(text)
        return {
            "Part 1 (beginning)": text[:n//4],
            "Part 2":             text[n//4:n//2],
            "Part 3":             text[n//2:3*n//4],
            "Part 4 (end)":       text[3*n//4:],
        }

    sections = {}
    for i, m in enumerate(matches):
        name    = m.group(1).strip()
        start   = m.end()
        end     = matches[i + 1].start() if i + 1 < len(matches) else len(text)
        content = text[start:end].strip()
        # Deduplicate section names
        key = name if name not in sections else f"{name} ({i})"
        sections[key] = content

    return sections


# ── Smart truncation ──────────────────────────────────────────────────────────

def smart_excerpt(text: str, query: str = "", max_chars: int = 12000) -> str:
    """
    Return the most useful portion of a full paper text, up to max_chars.

    Strategy:
      - Always include Abstract + Introduction (first ~3000 chars)
      - Always include Conclusion (last ~2000 chars)
      - Fill the middle budget with sections whose names/content match the query
    """
    if len(text) <= max_chars:
        return text

    sections = split_sections(text)
    query_lower = query.lower()

    # Priority tiers
    must_have  = []   # Abstract, Introduction, Conclusion
    relevant   = []   # sections whose name or first 200 chars match query terms
    remainder  = []   # everything else

    for name, content in sections.items():
        nl = name.lower()
        if any(k in nl for k in ("abstract", "introduction", "conclusion", "summary")):
            must_have.append((name, content))
        elif query_lower and (
            any(w in nl for w in query_lower.split())
            or any(w in content[:300].lower() for w in query_lower.split())
        ):
            relevant.append((name, content))
        else:
            remainder.append((name, content))

    parts  = []
    budget = max_chars

    for name, content in must_have + relevant + remainder:
        snippet = f"\n\n=== {name.upper()} ===\n{content}"
        if budget - len(snippet) > 200:
            parts.append(snippet)
            budget -= len(snippet)
        else:
            # Take what fits
            parts.append(f"\n\n=== {name.upper()} ===\n{content[:budget-100]}...[truncated]")
            break

    return "".join(parts)


# ── Cache layer ───────────────────────────────────────────────────────────────

def fulltext_cache_path(pdf_path: str) -> Path:
    return Path(pdf_path).with_suffix(".fulltext.txt")


def get_full_text(pdf_path: str, force: bool = False) -> str:
    """
    Return full extracted text for a PDF, using cached .fulltext.txt if available.
    Returns empty string if PDF doesn't exist.
    """
    pdf = Path(pdf_path)
    if not pdf.exists():
        return ""

    cache = fulltext_cache_path(pdf_path)
    if cache.exists() and not force:
        return cache.read_text(encoding="utf-8", errors="ignore")

    text = extract_raw_text(pdf_path)
    if text:
        cache.write_text(text, encoding="utf-8", errors="ignore")
    return text


def get_excerpt(pdf_path: str, query: str = "", max_chars: int = 12000) -> str:
    """
    Return a smart excerpt from a PDF, suitable for passing to an agent.
    Uses cached full text when available.
    """
    full = get_full_text(pdf_path)
    if not full:
        return ""
    return smart_excerpt(full, query=query, max_chars=max_chars)


# ── Batch extraction ──────────────────────────────────────────────────────────

def extract_library(papers_dir: str, force: bool = False, verbose: bool = True) -> int:
    """
    Extract and cache full text for all PDFs in papers_dir.
    Returns count of newly extracted files.
    """
    count = 0
    for pdf in Path(papers_dir).glob("*.pdf"):
        cache = fulltext_cache_path(str(pdf))
        if cache.exists() and not force:
            continue
        if verbose:
            print(f"  Extracting: {pdf.name[:60]}")
        text = extract_raw_text(str(pdf))
        if text:
            cache.write_text(text, encoding="utf-8", errors="ignore")
            count += 1
        elif verbose:
            print(f"    (empty — possible scanned PDF)")
    return count


if __name__ == "__main__":
    import argparse, sys
    from config import PAPERS_DIR

    parser = argparse.ArgumentParser(description="Extract text from downloaded PDFs")
    parser.add_argument("--force", action="store_true", help="Re-extract even if cache exists")
    parser.add_argument("--pdf",   help="Extract a single PDF and print excerpt")
    parser.add_argument("--query", default="", help="Query for smart excerpt relevance")
    parser.add_argument("--chars", type=int, default=4000, help="Max chars for excerpt")
    args = parser.parse_args()

    if args.pdf:
        excerpt = get_excerpt(args.pdf, query=args.query, max_chars=args.chars)
        print(excerpt or "(no text extracted)")
    else:
        print(f"Extracting PDFs in {PAPERS_DIR} ...")
        n = extract_library(PAPERS_DIR, force=args.force)
        print(f"Done. {n} new full-text files created.")
