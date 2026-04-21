"""
Load and apply structured research instructions (JSON) for main.py.

Required keys: query, keywords, authors.
Optional keys: exclude_keywords, exclude_authors (plain names; code adds au:/all: and ANDNOT).
Optional key: mode — "researcher" (default) or "teacher" (expository session; no wild theorist).
Optional key: session_name — human-readable label for output/session folders (slugified for paths).
"""

import json
import re
from pathlib import Path


def load_instructions_file(path: Path) -> dict:
    """
    Read JSON from path and return a dict with query, keywords, authors,
    exclude_keywords, exclude_authors.
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
    exclude_keywords = _normalize_optional_string_list(data.get("exclude_keywords"))
    exclude_authors = _normalize_optional_string_list(data.get("exclude_authors"))
    mode = data.get("mode", "researcher")
    if mode not in ("researcher", "teacher"):
        raise ValueError('Instructions "mode" must be "researcher" or "teacher".')
    sn = data.get("session_name")
    if sn is None:
        session_name = ""
    elif isinstance(sn, str):
        session_name = sn.strip()
    else:
        raise ValueError('Instructions "session_name" must be a string.')
    return {
        "query": query.strip(),
        "keywords": keywords,
        "authors": authors,
        "exclude_keywords": exclude_keywords,
        "exclude_authors": exclude_authors,
        "mode": mode,
        "session_name": session_name,
    }


def sanitize_session_name(raw: str) -> str:
    """Filesystem-safe slug for session_id (output/, sessions/). Empty input → empty string."""
    s = raw.strip().lower()
    s = re.sub(r"[^a-z0-9]+", "_", s)
    s = s.strip("_")
    if len(s) > 50:
        s = s[:50].rstrip("_")
    return s


def _normalize_optional_string_list(value: object) -> list[str]:
    """Optional list: missing/null → []; comma string or list of non-empty strings."""
    if value is None:
        return []
    if isinstance(value, str):
        parts = [p.strip() for p in value.split(",")]
        return [p for p in parts if p]
    if not isinstance(value, list):
        raise ValueError(
            'Optional exclude fields must be a list of strings or a comma-separated string.'
        )
    out = []
    for item in value:
        if not isinstance(item, str) or not item.strip():
            raise ValueError("exclude list entries must be non-empty strings.")
        out.append(item.strip())
    return out


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


def _all_field_term(term: str) -> str:
    t = term.strip()
    if any(c.isspace() for c in t):
        escaped = t.replace('"', '\\"')
        return f'all:"{escaped}"'
    return f"all:{t}"


def _au_field_term(name: str) -> str:
    a = name.strip()
    if any(c.isspace() for c in a):
        escaped = a.replace('"', '\\"')
        return f'au:"{escaped}"'
    return f"au:{a}"


def merge_arxiv_search_query(
    base_query: str,
    keywords: list[str],
    authors: list[str],
    exclude_keywords: list[str],
    exclude_authors: list[str],
) -> str:
    """
    Combine the planner's arXiv query with mandatory keyword and author clauses,
    then apply ANDNOT for exclusions (arXiv boolean query).
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
        kw_terms.append(_all_field_term(k))
    if kw_terms:
        parts.append("(" + " OR ".join(kw_terms) + ")")
    au_terms = []
    for a in authors:
        a = a.strip()
        if not a:
            continue
        au_terms.append(_au_field_term(a))
    if au_terms:
        parts.append("(" + " OR ".join(au_terms) + ")")
    positive = " AND ".join(parts)
    neg_chunks: list[str] = []
    for k in exclude_keywords:
        k = k.strip()
        if not k:
            continue
        neg_chunks.append(f"ANDNOT {_all_field_term(k)}")
    for a in exclude_authors:
        a = a.strip()
        if not a:
            continue
        neg_chunks.append(f"ANDNOT {_au_field_term(a)}")
    if not neg_chunks:
        return positive
    return f"({positive}) " + " ".join(neg_chunks)


def instructions_summary(instr: dict) -> str:
    """Short line for logs and generated topic project files."""
    return json.dumps(
        {
            "query": instr["query"],
            "keywords": instr["keywords"],
            "authors": instr["authors"],
            "exclude_keywords": instr["exclude_keywords"],
            "exclude_authors": instr["exclude_authors"],
            "mode": instr["mode"],
            "session_name": instr["session_name"],
        },
        ensure_ascii=False,
    )
