"""
Session project generated from `main.py` (frozen plan + improved research prompt).

Original phrase:
explain Hawking radiation to a graduate student

Run from the repository root, for example:
  py -3 written_projects/hawking_radiation_a_graduate_level_exposition_project.py
  py -3 written_projects/hawking_radiation_a_graduate_level_exposition_project.py --fetch-papers
  py -3 written_projects/hawking_radiation_a_graduate_level_exposition_project.py --rounds 3 --quiet

This file embeds the planner output (refined question, title, arXiv query, dynamic agents,
and round roster). Re-running it repeats the expert discussion without calling the planner.

Generated at: 2026-04-21T15:29:43Z
"""

import argparse
import io
import json
import sys
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parent.parent
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

if sys.stdout.encoding.lower() != "utf-8":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8", errors="replace")

from config import ANTHROPIC_API_KEY, PAPERS_ARXIV_PDF, get_papers_dir, set_papers_project
from topic_project_writer import slugify_papers_subdir

if not ANTHROPIC_API_KEY:
    print(
        "ERROR: Set ANTHROPIC_API_KEY in the environment or .claude/settings.json "
        "(env.ANTHROPIC_API_KEY)."
    )
    sys.exit(1)

from main import (
    SLEEP_BEFORE_EXPERT_SESSION_SEC,
    _pacing_sleep,
    build_merged_registry,
    run_pipeline_session,
)

PLAN = json.loads('{"session_title": "Hawking Radiation: A Graduate-Level Exposition", "refined_research_question": "How does quantum field theory on a curved spacetime background give rise to Hawking radiation from a black hole horizon? Specifically: what is the Bogoliubov transformation relating in- and out-vacuum states, why does the Planckian spectrum T_H = hbar c^3 / (8 pi G M k_B) emerge, what is the physical role of the near-horizon geometry and Unruh effect, and what are the key open questions regarding unitarity and information loss?", "arxiv_search_query": "abs:(Hawking radiation derivation Bogoliubov transformation black hole thermodynamics Unruh effect information paradox) AND (abs:tutorial OR abs:review OR abs:lecture OR abs:pedagogical)", "arxiv_categories": ["gr-qc", "hep-th", "quant-ph"], "max_papers": 24, "dynamic_agent_specs": [{"id": "qft_curved", "display_name": "QFT in Curved Spacetime Specialist", "system_prompt": "You are an expert in quantum field theory in curved spacetime, with deep knowledge of the canonical quantization of scalar, spinor, and gauge fields on fixed curved backgrounds. You can carefully define the mode expansion of a quantum field in Schwarzschild and Rindler spacetimes, explain the notion of a particle as observer-dependent, and walk through the Bogoliubov transformation step by step, defining every symbol: alpha_{omega omega\'} and beta_{omega omega\'} coefficients, the in-vacuum |0_in>, the out-vacuum |0_out>, and the number operator N_omega. You explain why |beta_{omega omega\'}|^2 evaluated for the Schwarzschild geometry yields a thermal Planck distribution with temperature T_H = hbar kappa / (2 pi c k_B) where kappa is the surface gravity. You cite the original Hawking 1974/1975 papers, the Parker 1969 work on particle creation in cosmology, and the textbooks by Birrell-Davies and Wald. You never invent speculative new physics; your role is rigorous, patient exposition."}], "round_agent_groups": [["gr", "teacher"], ["qft_curved", "teacher"], ["qft_curved", "qm", "verifier"], ["meaning", "bh", "teacher"], ["devil", "lit"], ["teacher", "verifier"]], "session_mode": "teacher"}')
set_papers_project(slugify_papers_subdir(PLAN["session_title"]))


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Replay expert session from embedded plan (no planner call).",
    )
    parser.add_argument(
        "--fetch-papers",
        action="store_true",
        help="Run arXiv search/download and preprocess before the discussion",
    )
    parser.add_argument(
        "--skip-preprocess",
        action="store_true",
        help="With --fetch-papers: skip paper_tools.preprocess_papers",
    )
    parser.add_argument(
        "--pdf",
        action="store_true",
        help="With --fetch-papers: force arXiv PDFs (overrides config)",
    )
    parser.add_argument(
        "--no-pdf",
        action="store_true",
        help="With --fetch-papers: skip arXiv PDFs (overrides config)",
    )
    parser.add_argument(
        "--rounds",
        "-r",
        type=int,
        default=None,
        help="Max discussion rounds (default: full plan)",
    )
    parser.add_argument("--no-latex", action="store_true")
    parser.add_argument("--quiet", action="store_true")
    args = parser.parse_args()

    if args.pdf and args.no_pdf:
        parser.error("Use either --pdf or --no-pdf, not both.")

    if args.fetch_papers:
        print(f"\n  [2/4] Searching arXiv and saving abstracts...\n  → {get_papers_dir()}\n")
        from paper_tools.arxiv_downloader import search_and_download

        if args.pdf:
            download_pdfs = True
        elif args.no_pdf:
            download_pdfs = False
        else:
            download_pdfs = PAPERS_ARXIV_PDF
        search_and_download(
            query=PLAN["arxiv_search_query"],
            categories=PLAN["arxiv_categories"],
            max_results=PLAN["max_papers"],
            download_pdfs=download_pdfs,
        )
        if not args.skip_preprocess:
            print("\n  [3/4] Preprocessing paper library...\n")
            from paper_tools.preprocess_papers import process_all

            process_all(force=False)
        else:
            print("\n  [3/4] Skipped (--skip-preprocess).\n")
    else:
        print("\n  [2–3/4] Skipping papers (use --fetch-papers to run arXiv + preprocess).\n")

    round_groups = PLAN["round_agent_groups"]
    if args.rounds is not None:
        round_groups = round_groups[: max(1, args.rounds)]

    merged_registry = build_merged_registry(PLAN)

    print("\n  [4/4] Expert discussion...\n")
    _pacing_sleep(SLEEP_BEFORE_EXPERT_SESSION_SEC, "preprocessing — before expert discussion")
    run_pipeline_session(
        question=PLAN["refined_research_question"],
        title=PLAN["session_title"],
        agent_registry=merged_registry,
        round_groups=round_groups,
        planning=PLAN,
        produce_latex=not args.no_latex,
        verbose=not args.quiet,
    )


if __name__ == "__main__":
    main()
