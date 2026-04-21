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
from .context_limits import truncate_tail
from .paper_selector import (
    _format_catalogue,
    _load_processed_index,
    narrow_papers_for_catalogue,
)
from config import MAX_LATEX_SYNTHESIS_CHARS, MAX_PAPER_CATALOGUE_ENTRIES, OUTPUT_DIR

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

    candidates = narrow_papers_for_catalogue(all_papers, text, MAX_PAPER_CATALOGUE_ENTRIES)
    catalogue = _format_catalogue(candidates)
    from .paper_selector import SYSTEM as SEL_SYS
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
        selected_ids = {p["id"] for p in candidates[:6]}

    papers = [p for p in candidates if p["id"] in selected_ids][:8]
    if not papers:
        papers = candidates[:6]

    cite_keys = _make_unique_keys(papers)
    bibliography = _build_bibliography(papers, cite_keys)
    return papers, cite_keys, bibliography


# ─── Document integrity ──────────────────────────────────────────────────────

def _strip_markdown_fence(tex: str) -> str:
    """Remove ```latex / ``` fences that LLMs sometimes wrap around output."""
    tex = tex.strip()
    if tex.startswith("```"):
        tex = tex.split("```", 2)[1]
        if tex.startswith("latex"):
            tex = tex[4:]
        tex = tex.lstrip("\n")
    if tex.endswith("```"):
        tex = tex[: tex.rfind("```")].rstrip()
    return tex


def _inject_bibliography(tex: str, bibliography: str) -> str:
    """
    Remove any LLM-generated bibliography block and inject the pre-built one.
    Then ensure \\end{document} is present.
    """
    # Strip existing (possibly truncated) thebibliography
    tex = re.sub(
        r"\\begin\{thebibliography\}.*",
        "",
        tex,
        flags=re.DOTALL,
    ).rstrip()

    # Strip stray \end{document} so we can re-append cleanly
    tex = tex.replace(r"\end{document}", "").rstrip()

    if bibliography:
        return tex + "\n\n" + bibliography + "\n\n\\end{document}\n"
    return tex + "\n\n\\end{document}\n"


# ─── LLM formatting calls ────────────────────────────────────────────────────

CHECKPOINT_SYSTEM = r"""You are a scientific LaTeX formatter. Produce ONLY valid LaTeX — no
markdown fences, no explanation outside the document. The document is an intermediate
research checkpoint, not a finished paper. It should be honest about what is provisional.

Use this exact preamble:
\documentclass[11pt,a4paper]{article}
\usepackage{amsmath,amssymb,amsthm,physics,bm,geometry,xcolor,microtype}
\usepackage[colorlinks=true,linkcolor=blue,citecolor=blue,urlcolor=blue]{hyperref}
\geometry{margin=2.5cm}
\newtheorem{proposition}{Proposition}
\newtheorem{definition}{Definition}
\newtheorem{remark}{Remark}

Sections to include (keep under 5 pages total):
1. Abstract — what the team has settled on so far (3-5 sentences)
2. Current Theoretical Proposal — the core idea with key equations (numbered)
3. Points of Consensus — what all specialists agree on
4. Open Tensions — explicit list of unresolved issues
5. Next Steps — what needs to be worked out in the next round

IMPORTANT: End your output with ONLY the line:
\end{document}
Do NOT include a \\begin{thebibliography} block — it will be appended automatically.
Use \\cite{key} where relevant; valid keys are listed in the user message.

Rules:
- Use \\label{eq:N} on every numbered equation
- Natural units G = \\hbar = c = 1 unless stated otherwise
- Mark speculative claims with \\textcolor{red}{[speculative]} inline
- Never invent references"""


FINAL_SYSTEM = r"""You are a scientific LaTeX formatter producing a complete research paper.
Output ONLY valid LaTeX — no markdown fences, no explanations outside the document.

Preamble:
\documentclass[12pt,a4paper]{article}
\usepackage{amsmath,amssymb,amsthm,physics,bm,geometry,xcolor,microtype,graphicx}
\usepackage[colorlinks=true,linkcolor=blue,citecolor=blue,urlcolor=blue]{hyperref}
\geometry{margin=2.5cm}
\newtheorem{theorem}{Theorem}
\newtheorem{proposition}{Proposition}
\newtheorem{definition}{Definition}
\newtheorem{conjecture}{Conjecture}
\newtheorem{remark}{Remark}

Sections (all required — be concise, max 10 pages total):
1. Abstract (~100 words)
2. Introduction — motivation and problem statement
3. Mathematical Framework — key definitions and structures
4. Core Equations and Results — numbered equations with derivation sketches
5. Physical Interpretation — operational meaning of each construct
6. Consistency Checks — classical limit and symmetry
7. Connections to Existing Approaches — brief comparison
8. Bold Proposals and Open Conjectures — marked with \\begin{conjecture}
9. Open Problems and Future Directions
10. Conclusion

IMPORTANT: End your output with ONLY the line:
\end{document}
Do NOT include a \\begin{thebibliography} block — the bibliography will be appended automatically.
Use \\cite{key} throughout; valid keys are listed below.

Rules:
- All equations numbered with \\label{eq:name}
- Mark conjectures with \\begin{conjecture}...\\end{conjecture}
- State metric signature convention explicitly
- Never invent references — only \\cite keys from the provided list"""


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
    syn_for_ctx = truncate_tail(synthesis, MAX_LATEX_SYNTHESIS_CHARS, "Round synthesis")
    papers, cite_keys, bibliography = _get_relevant_papers_and_keys(syn_for_ctx)

    # Build agent summary for context
    agent_summary = "\n\n".join(
        f"[{name}]\n{resp[:600]}" for name, resp in agent_responses.items()
    )

    cite_key_list = "\n".join(f"  \\cite{{{v}}} -> {k}" for k, v in cite_keys.items()) or "  (none)"

    messages = [{
        "role": "user",
        "content": (
            f"Produce a LaTeX checkpoint document for ROUND {round_num}.\n\n"
            f"Round synthesis:\n{syn_for_ctx}\n\n"
            f"Agent responses summary:\n{agent_summary[:3000]}\n\n"
            f"Available cite keys (use \\cite{{key}} with these):\n{cite_key_list}"
        ),
    }]

    tex_content = call_agent(CHECKPOINT_SYSTEM, messages, max_tokens=8000)
    tex_content = _strip_markdown_fence(tex_content)
    tex_content = _inject_bibliography(tex_content, bibliography)

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
    syn_for_ctx = truncate_tail(synthesis, MAX_LATEX_SYNTHESIS_CHARS, "Final synthesis")
    papers, cite_keys, bibliography = _get_relevant_papers_and_keys(syn_for_ctx)

    rounds_summary = "\n\n".join(
        f"=== ROUND {r['round']} ===\n{r['synthesis'][:800]}" for r in all_rounds
    )

    cite_key_list = "\n".join(f"  \\cite{{{v}}} -> {k}" for k, v in cite_keys.items()) or "  (none)"

    messages = [{
        "role": "user",
        "content": (
            f"Produce a complete LaTeX paper with title: {title}\n\n"
            f"Final synthesis:\n{syn_for_ctx}\n\n"
            f"Evolution across rounds:\n{rounds_summary[:4000]}\n\n"
            f"Available cite keys (use \\cite{{key}} with these):\n{cite_key_list}"
        ),
    }]

    tex_content = call_agent(FINAL_SYSTEM, messages, max_tokens=14000)
    tex_content = _strip_markdown_fence(tex_content)
    tex_content = _inject_bibliography(tex_content, bibliography)

    filename = "final_paper.tex"
    tex_path  = _output_path(session_id, filename)
    result = _write_and_compile(tex_content, tex_path, "Final paper")
    result["papers_used"] = [p["title"] for p in papers]
    return result
