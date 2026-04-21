"""
Load and apply structured research instructions (JSON) for main.py.

Schema (all keys required when using --use-instructions):
  query: string — main research question / topic (drives the session planner).
  keywords: list of strings — terms that must appear in the arXiv search query.
  authors: list of strings — author names, each used in an arXiv au: clause.
"""

import json
from pathlib import Path


def load_instructions_file(path: Path) -> dict:
    """
    Read JSON from path and return a dict with keys query, keywords, authors.
    """
    if not path.is_file():
        raise FileNotFoundError(f"Instructions file not found: {path}")
    raw = path.read_text(encoding="utf-8")
    data = json.loads(raw)
    if not isinstance(data, dict):
        raise ValueError("Instructions JSON must be a single object.")
    for key in ("query", "keywords", "authors"):
        if key not in data:
            raise ValueError(f"Instructions JSON missing required key: {key!r}")
    query = data["query"]
    if not isinstance(query, str) or not query.strip():
        raise ValueError('Instructions "query" must be a non-empty string.')
    keywords = _normalize_string_list(data["keywords"], "keywords")
    authors = _normalize_string_list(data["authors"], "authors")
    if not keywords:
        raise ValueError('Instructions "keywords" must be a non-empty list of strings.')
    if not authors:
        raise ValueError('Instructions "authors" must be a non-empty list of strings.')
    return {
        "query": query.strip(),
        "keywords": keywords,
        "authors": authors,
    }


def _normalize_string_list(value: object, field_name: str) -> list[str]:
    if isinstance(value, str):
        parts = [p.strip() for p in value.split(",")]
        out = [p for p in parts if p]
        if not out:
            raise ValueError(f'Instructions "{field_name}" string must not be empty.')
        return out
    if not isinstance(value, list):
        raise ValueError(f'Instructions "{field_name}" must be a list of strings or a comma-separated string.')
    out = []
    for item in value:
        if not isinstance(item, str) or not item.strip():
            raise ValueError(f'Instructions "{field_name}" entries must be non-empty strings.')
        out.append(item.strip())
    return out


def merge_arxiv_search_query(base_query: str, keywords: list[str], authors: list[str]) -> str:
    """
    Combine the planner's arXiv query with mandatory keyword and author clauses
    so every instruction field affects the search string sent to arXiv.
    """
    parts = []
    b = base_query.strip()
    if b:
        parts.append(f"({b})")
    kw_terms = []
    for k in keywords:
        k = k.strip()
        if not k:
            continue
        if any(c.isspace() for c in k):
            escaped = k.replace('"', '\\"')
            kw_terms.append(f'all:"{escaped}"')
        else:
            kw_terms.append(f"all:{k}")
    if kw_terms:
        parts.append("(" + " OR ".join(kw_terms) + ")")
    au_terms = []
    for a in authors:
        a = a.strip()
        if not a:
            continue
        if any(c.isspace() for c in a):
            escaped = a.replace('"', '\\"')
            au_terms.append(f'au:"{escaped}"')
        else:
            au_terms.append(f"au:{a}")
    if au_terms:
        parts.append("(" + " OR ".join(au_terms) + ")")
    return " AND ".join(parts)


def instructions_summary(instr: dict) -> str:
    """Short line for logs and generated topic project files."""
    return json.dumps(
        {"query": instr["query"], "keywords": instr["keywords"], "authors": instr["authors"]},
        ensure_ascii=False,
    )
