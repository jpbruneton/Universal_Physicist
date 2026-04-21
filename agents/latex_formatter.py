"""
LaTeX formatter agent.

Two entry points:
  format_checkpoint(synthesis, round_num, session_id, agent_responses)
      -> intermediate .tex (and optionally .pdf) after each round

  format_final(synthesis, title, session_id, all_rounds)
      -> full paper .tex (and optionally .pdf) after all rounds

Both functions:
  - Pull relevant papers from the processed index via paper_selector
  - Build real \\bibitem entries from the library metadata
  - Attempt PDF compilation via latex_tools.compile_latex
"""

import os
import json
import re
from pathlib import Path
from datetime import datetime

from .base import call_agent
from .paper_selector import select_relevant_papers, _load_processed_index
from config import OUTPUT_DIR

try:
    from latex_tools.compile_latex import compile as _compile_tex, is_available as _compiler_is_available
    COMPILER_AVAILABLE = _compiler_is_available()
except ImportError:
    _compile_tex = None
    COMPILER_AVAILABLE = False


# ─── Bibliography helpers ────────────────────────────────────────────────────

def _cite_key(paper: dict) -> str:
    """Generate a short BibTeX-style cite key: firstauthorYYYY."""
    authors = paper.get("authors", ["Unknown"])
    first = authors[0].split()[-1].lower() if authors else "anon"
    first = re.sub(r"[^a-z]", "", first)
    year = paper.get("published", "0000")[:4]
    return f"{first}{year}"


def _make_unique_keys(papers: list[dict]) -> dict:
    """Return {paper_id -> unique_cite_key}, appending a/b/c if needed."""
    seen = {}
    keys = {}
    for p in papers:
        base = _cite_key(p)
        if base in seen:
            seen[base] += 1
            key = f"{base}{chr(96 + seen[base])}"  # a, b, c ...
        else:
            seen[base] = 1
            key = base
        keys[p["id"]] = key
    return keys


def _build_bibitem(paper: dict, cite_key: str) -> str:
    authors = paper.get("authors", [])
    if len(authors) > 3:
        author_str = f"{authors[0]} et al."
    else:
        author_str = ", ".join(authors)

    year = paper.get("published", "")[:4]
    title = paper.get("title", "Unknown title")
    arxiv_id = paper.get("id", "").replace("http://arxiv.org/abs/", "").replace("https://arxiv.org/abs/", "")

    return (
        f"\\bibitem{{{cite_key}}}\n"
        f"{author_str}.\n"
        f"\\textit{{{title}}}.\n"
        f"arXiv:{arxiv_id} ({year})."
    )


def _build_bibliography(papers: list[dict], cite_keys: dict) -> str:
    if not papers:
        return ""
    items = [_build_bibitem(p, cite_keys[p["id"]]) for p in papers]
    return (
        "\\begin{thebibliography}{99}\n\n"
        + "\n\n".join(items)
        + "\n\n\\end{thebibliography}"
    )


def _get_relevant_papers_and_keys(text: str) -> tuple[list[dict], dict, str]:
    """
    Select relevant papers from the library for the given text.
    Returns (papers, cite_keys_dict, bibliography_latex).
    """
    all_papers = _load_processed_index()
    if not all_papers:
        return [], {}, ""

    # Use selector to pick relevant subset
    _ = select_relevant_papers(text)  # warms selector; we re-fetch for metadata
    # Re-run selection logic directly to get paper objects, not just formatted text
    from .paper_selector import _format_catalogue, SYSTEM as SEL_SYS
    catalogue = _format_catalogue(all_papers)
    from .base import call_agent as _ca
    import json as _json
    try:
        raw = _ca(SEL_SYS, [{"role": "user", "content":
            f"Theoretical proposal:\n{text[:1500]}\n\nAvailable papers:\n{catalogue}"}],
            max_tokens=300)
        raw = raw.strip()
        if raw.startswith("```"):
            raw = raw.split("```")[1].lstrip("json").strip()
        selected_ids = set(_json.loads(raw))
    except Exception:
        selected_ids = {p["id"] for p in all_papers[:6]}

    papers = [p for p in all_papers if p["id"] in selected_ids][:8]
    if not papers:
        papers = all_papers[:6]

    cite_keys = _make_unique_keys(papers)
    bibliography = _build_bibliography(papers, cite_keys)
    return papers, cite_keys, bibliography


# ─── Document integrity ──────────────────────────────────────────────────────

def _ensure_document_closed(tex: str) -> str:
    """If the LLM output was truncated before \\end{document}, close it cleanly."""
    if r"\end{document}" in tex:
        return tex
    # Close any open environments and add \end{document}
    closers = []
    if r"\begin{thebibliography}" in tex and r"\end{thebibliography}" not in tex:
        closers.append(r"\end{thebibliography}")
    closers.append(r"\end{document}")
    return tex.rstrip() + "\n\n" + "\n".join(closers) + "\n"


# ─── LLM formatting calls ────────────────────────────────────────────────────

CHECKPOINT_SYSTEM = r"""You are a scientific LaTeX formatter. Produce ONLY valid LaTeX — no
explanation outside the document. The document is an intermediate research checkpoint,
not a finished paper. It should be honest about what is provisional.

Use this exact preamble:
\documentclass[11pt,a4paper]{article}
\usepackage{amsmath,amssymb,amsthm,physics,bm,hyperref,geometry,xcolor,microtype}
\usepackage[colorlinks=true,linkcolor=blue,citecolor=blue,urlcolor=blue]{hyperref}
\geometry{margin=2.5cm}
\newtheorem{proposition}{Proposition}
\newtheorem{definition}{Definition}
\newtheorem{remark}{Remark}

Sections to include:
1. Abstract — what the team has settled on so far (3-5 sentences)
2. Current Theoretical Proposal — the core idea with key equations (numbered)
3. Points of Consensus — what all specialists agree on
4. Open Tensions — explicit list of unresolved issues
5. Next Steps — what needs to be worked out in the next round
6. References — use the \\bibitem entries provided verbatim

Rules:
- Use \\label{eq:N} on every numbered equation
- Natural units G = \\hbar = c = 1 unless stated otherwise
- Cite the provided references with \\cite{key} where relevant
- Mark speculative claims with \\textcolor{red}{[speculative]} inline
- Never invent references — only cite from the provided bibliography
- Keep the document under 6 pages — be concise, no padding, no repetition
- Always end with \\end{thebibliography} then \\end{document}"""


FINAL_SYSTEM = r"""You are a scientific LaTeX formatter producing a complete research paper.
Output ONLY valid LaTeX.

Preamble:
\documentclass[12pt,a4paper]{article}
\usepackage{amsmath,amssymb,amsthm,physics,bm,hyperref,geometry,xcolor,microtype,graphicx}
\usepackage[colorlinks=true,linkcolor=blue,citecolor=blue,urlcolor=blue]{hyperref}
\geometry{margin=2.5cm}
\newtheorem{theorem}{Theorem}
\newtheorem{proposition}{Proposition}
\newtheorem{definition}{Definition}
\newtheorem{conjecture}{Conjecture}
\newtheorem{remark}{Remark}

Sections (all required):
1. Abstract (~150 words)
2. Introduction — motivation, problem statement, overview of the paper
3. Mathematical Framework — definitions, key structures, Hilbert space
4. Core Equations and Results — numbered equations with derivation sketches
5. Physical Interpretation — operational meaning of each construct
6. Consistency Checks — classical limit, dimensional analysis, symmetry
7. Connections to Existing Approaches — brief comparison table or discussion
8. Bold Proposals and Open Conjectures — most speculative directions, marked clearly
9. Open Problems and Future Directions
10. Conclusion
11. References — use \\bibitem entries provided verbatim

Rules:
- All equations numbered with \\label{eq:name}
- \\cite{key} for every claim that connects to provided references
- Mark conjectures explicitly with \\begin{conjecture}...\\end{conjecture}
- State metric signature convention (+−−−) or (−+++) explicitly
- State whether Planck units or SI units are used
- Never invent references"""


def _output_path(session_id: str, filename: str) -> str:
    dirpath = Path(OUTPUT_DIR) / session_id
    dirpath.mkdir(parents=True, exist_ok=True)
    return str(dirpath / filename)


def _write_and_compile(tex_content: str, tex_path: str, label: str) -> dict:
    """Write .tex, attempt compilation, return result dict."""
    with open(tex_path, "w", encoding="utf-8") as f:
        f.write(tex_content)

    result = {"tex": tex_path, "pdf": None, "compiled": False, "log": ""}

    if COMPILER_AVAILABLE and _compile_tex is not None:
        success, pdf_path, log = _compile_tex(tex_path)
        result.update({"pdf": pdf_path, "compiled": success, "log": log[-2000:]})
        status = "PDF generated" if success else "compilation failed"
        print(f"    {label}: {status}")
        if not success:
            print(f"    Log tail: {log[-400:]}")
    else:
        print(f"    {label}: .tex saved (no LaTeX compiler on PATH — install MiKTeX or TeX Live)")

    return result


# ─── Public API ──────────────────────────────────────────────────────────────

def format_checkpoint(
    synthesis: str,
    round_num: int,
    session_id: str,
    agent_responses: dict,
) -> dict:
    """Format and optionally compile a per-round checkpoint."""
    papers, cite_keys, bibliography = _get_relevant_papers_and_keys(synthesis)

    # Build agent summary for context
    agent_summary = "\n\n".join(
        f"[{name}]\n{resp[:600]}" for name, resp in agent_responses.items()
    )

    cite_key_list = "\n".join(f"  \\cite{{{v}}} -> {k}" for k, v in cite_keys.items()) or "  (none)"

    messages = [{
        "role": "user",
        "content": (
            f"Produce a LaTeX checkpoint document for ROUND {round_num}.\n\n"
            f"Round synthesis:\n{synthesis}\n\n"
            f"Agent responses summary:\n{agent_summary[:3000]}\n\n"
            f"Available cite keys (use these in \\cite{{}} commands):\n{cite_key_list}\n\n"
            f"Bibliography (include verbatim at end of document):\n{bibliography}"
        ),
    }]

    tex_content = call_agent(CHECKPOINT_SYSTEM, messages, max_tokens=8000)
    tex_content = _ensure_document_closed(tex_content)

    filename = f"round_{round_num:02d}_checkpoint.tex"
    tex_path  = _output_path(session_id, filename)
    result = _write_and_compile(tex_content, tex_path, f"Round {round_num} checkpoint")
    result["round"] = round_num
    result["papers_used"] = [p["title"] for p in papers]
    return result


def format_final(
    synthesis: str,
    title: str,
    session_id: str,
    all_rounds: list[dict],
) -> dict:
    """Format and optionally compile the final paper."""
    papers, cite_keys, bibliography = _get_relevant_papers_and_keys(synthesis)

    rounds_summary = "\n\n".join(
        f"=== ROUND {r['round']} ===\n{r['synthesis'][:800]}" for r in all_rounds
    )

    cite_key_list = "\n".join(f"  \\cite{{{v}}} -> {k}" for k, v in cite_keys.items()) or "  (none)"

    messages = [{
        "role": "user",
        "content": (
            f"Produce a complete LaTeX paper with title: {title}\n\n"
            f"Final synthesis:\n{synthesis}\n\n"
            f"Evolution across rounds:\n{rounds_summary[:4000]}\n\n"
            f"Available cite keys:\n{cite_key_list}\n\n"
            f"Bibliography (include verbatim):\n{bibliography}"
        ),
    }]

    tex_content = call_agent(FINAL_SYSTEM, messages, max_tokens=12000)
    tex_content = _ensure_document_closed(tex_content)

    filename = "final_paper.tex"
    tex_path  = _output_path(session_id, filename)
    result = _write_and_compile(tex_content, tex_path, "Final paper")
    result["papers_used"] = [p["title"] for p in papers]
    return result
