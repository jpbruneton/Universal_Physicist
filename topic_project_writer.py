"""
Emit a standalone `<slug>_project.py` script from a session plan (refined prompt + roster).
"""

import json
import re
from datetime import datetime, timezone
from pathlib import Path


def slugify_session_title(session_title: str) -> str:
    """Filesystem-safe slug ending with _project (without .py)."""
    s = session_title.lower()
    s = re.sub(r"[^a-z0-9]+", "_", s)
    s = s.strip("_")
    if len(s) > 50:
        s = s[:50].rstrip("_")
    if not s:
        s = "session"
    return f"{s}_project"


def write_topic_project_file(plan: dict, user_phrase: str, project_root: Path) -> Path:
    """
    Write `<slug>_project.py` under project_root. Embeds the full plan JSON for replay.
    """
    slug = slugify_session_title(plan["session_title"])
    path = project_root / f"{slug}.py"
    plan_json = json.dumps(plan, ensure_ascii=False)
    plan_repr = repr(plan_json)
    generated_at = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    phrase_safe = user_phrase.replace('"""', "'''")
    doc_phrase_block = phrase_safe

    parts = [
        '"""',
        "Session project generated from `main.py` (frozen plan + improved research prompt).",
        "",
        "Original phrase:",
        doc_phrase_block,
        "",
        "Run from the repository root, for example:",
        f"  py -3 {path.name}",
        f"  py -3 {path.name} --fetch-papers",
        f"  py -3 {path.name} --rounds 3 --quiet",
        "",
        "This file embeds the planner output (refined question, title, arXiv query, dynamic agents,",
        "and round roster). Re-running it repeats the expert discussion without calling the planner.",
        "",
        f"Generated at: {generated_at}",
        '"""',
        "",
        "import argparse",
        "import io",
        "import json",
        "import sys",
        "from pathlib import Path",
        "",
        "if sys.stdout.encoding.lower() != \"utf-8\":",
        "    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding=\"utf-8\", errors=\"replace\")",
        "    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding=\"utf-8\", errors=\"replace\")",
        "",
        "from config import ANTHROPIC_API_KEY, PAPERS_ARXIV_PDF",
        "",
        "if not ANTHROPIC_API_KEY:",
        "    print(",
        "        \"ERROR: Set ANTHROPIC_API_KEY in the environment or .claude/settings.json \"",
        "        \"(env.ANTHROPIC_API_KEY).\"",
        "    )",
        "    sys.exit(1)",
        "",
        "from main import (",
        "    SLEEP_BEFORE_EXPERT_SESSION_SEC,",
        "    _pacing_sleep,",
        "    build_merged_registry,",
        "    run_pipeline_session,",
        ")",
        "",
        f"PLAN = json.loads({plan_repr})",
        "",
        "",
        "def main() -> None:",
        "    parser = argparse.ArgumentParser(",
        "        description=\"Replay expert session from embedded plan (no planner call).\",",
        "    )",
        "    parser.add_argument(",
        "        \"--fetch-papers\",",
        "        action=\"store_true\",",
        "        help=\"Run arXiv search/download and preprocess before the discussion\",",
        "    )",
        "    parser.add_argument(",
        "        \"--skip-preprocess\",",
        "        action=\"store_true\",",
        "        help=\"With --fetch-papers: skip paper_tools.preprocess_papers\",",
        "    )",
        "    parser.add_argument(",
        "        \"--pdf\",",
        "        action=\"store_true\",",
        "        help=\"With --fetch-papers: force arXiv PDFs (overrides config)\",",
        "    )",
        "    parser.add_argument(",
        "        \"--no-pdf\",",
        "        action=\"store_true\",",
        "        help=\"With --fetch-papers: skip arXiv PDFs (overrides config)\",",
        "    )",
        "    parser.add_argument(",
        "        \"--rounds\",",
        "        \"-r\",",
        "        type=int,",
        "        default=None,",
        "        help=\"Max discussion rounds (default: full plan)\",",
        "    )",
        "    parser.add_argument(\"--no-latex\", action=\"store_true\")",
        "    parser.add_argument(\"--quiet\", action=\"store_true\")",
        "    args = parser.parse_args()",
        "",
        "    if args.pdf and args.no_pdf:",
        "        parser.error(\"Use either --pdf or --no-pdf, not both.\")",
        "",
        "    if args.fetch_papers:",
        "        print(\"\\n  [2/4] Searching arXiv and saving abstracts to papers/...\\n\")",
        "        from paper_tools.arxiv_downloader import search_and_download",
        "",
        "        if args.pdf:",
        "            download_pdfs = True",
        "        elif args.no_pdf:",
        "            download_pdfs = False",
        "        else:",
        "            download_pdfs = PAPERS_ARXIV_PDF",
        "        search_and_download(",
        "            query=PLAN[\"arxiv_search_query\"],",
        "            categories=PLAN[\"arxiv_categories\"],",
        "            max_results=PLAN[\"max_papers\"],",
        "            download_pdfs=download_pdfs,",
        "        )",
        "        if not args.skip_preprocess:",
        "            print(\"\\n  [3/4] Preprocessing paper library...\\n\")",
        "            from paper_tools.preprocess_papers import process_all",
        "",
        "            process_all(force=False)",
        "        else:",
        "            print(\"\\n  [3/4] Skipped (--skip-preprocess).\\n\")",
        "    else:",
        "        print(\"\\n  [2–3/4] Skipping papers (use --fetch-papers to run arXiv + preprocess).\\n\")",
        "",
        "    round_groups = PLAN[\"round_agent_groups\"]",
        "    if args.rounds is not None:",
        "        round_groups = round_groups[: max(1, args.rounds)]",
        "",
        "    merged_registry = build_merged_registry(PLAN)",
        "",
        "    print(\"\\n  [4/4] Expert discussion...\\n\")",
        "    _pacing_sleep(SLEEP_BEFORE_EXPERT_SESSION_SEC, \"preprocessing — before expert discussion\")",
        "    run_pipeline_session(",
        "        question=PLAN[\"refined_research_question\"],",
        "        title=PLAN[\"session_title\"],",
        "        agent_registry=merged_registry,",
        "        round_groups=round_groups,",
        "        planning=PLAN,",
        "        produce_latex=not args.no_latex,",
        "        verbose=not args.quiet,",
        "    )",
        "",
        "",
        'if __name__ == "__main__":',
        "    main()",
        "",
    ]
    path.write_text("\n".join(parts), encoding="utf-8")
    return path
