"""
Session project generated from `main.py` (frozen plan + improved research prompt).

Original phrase:
{"query": "Explore quantum mechanics formulated over non-continuous fields (e.g. rationals, p-adics, or finite fields): algebraic constraints, Hilbert-space analogs, and testable predictions.", "keywords": ["finite field quantum", "p-adic quantum mechanics", "non-Archimedean Hilbert space"], "authors": ["Volovich", "Dragovich"]}

Run from the repository root, for example:
  py -3 written_projects/quantum_mechanics_over_non_continuous_fields_algeb_project.py
  py -3 written_projects/quantum_mechanics_over_non_continuous_fields_algeb_project.py --fetch-papers
  py -3 written_projects/quantum_mechanics_over_non_continuous_fields_algeb_project.py --rounds 3 --quiet

This file embeds the planner output (refined question, title, arXiv query, dynamic agents,
and round roster). Re-running it repeats the expert discussion without calling the planner.

Generated at: 2026-04-21T14:59:05Z
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

PLAN = json.loads('{"session_title": "Quantum Mechanics over Non-Continuous Fields: Algebraic Structure, Hilbert-Space Analogs, and Physical Predictions", "refined_research_question": "Can quantum mechanics be consistently formulated over non-Archimedean or discrete algebraic fields (rationals Q, p-adic numbers Q_p, or finite fields F_q)? Specifically: (1) What algebraic constraints govern the definition of inner-product spaces and self-adjoint operators when the underlying scalar field lacks the standard Archimedean order or completeness (e.g., replacing |psi> in L^2(R) with modules over Z_p or vector spaces over F_q)? (2) Do viable p-adic or finite-field analogs of the Schrödinger equation, Born rule, and unitary evolution exist, and under what conditions do they reduce to or depart from standard complex QM? (3) What phenomenological or experimental signatures—such as discrete energy spectra, modified interference patterns, or arithmetic constraints on observable eigenvalues—could distinguish these frameworks from standard QM, and what energy or length scales would make them accessible?", "arxiv_search_query": "((abs:\\"finite field quantum\\" OR abs:\\"p-adic quantum mechanics\\" OR abs:\\"non-Archimedean Hilbert space\\" OR ti:\\"p-adic quantum\\" OR ti:\\"finite field quantum mechanics\\" OR all:\\"p-adic Hilbert space\\") AND (au:Volovich OR au:Dragovich)) AND (all:\\"finite field quantum\\" OR all:\\"p-adic quantum mechanics\\" OR all:\\"non-Archimedean Hilbert space\\") AND (au:Volovich OR au:Dragovich)", "arxiv_categories": ["hep-th", "math-ph", "quant-ph"], "max_papers": 36, "dynamic_agent_specs": [{"id": "padic_expert", "display_name": "p-adic & Non-Archimedean Analysis Expert", "system_prompt": "You are an expert in p-adic analysis, non-Archimedean functional analysis, and their applications to theoretical physics. You have deep knowledge of p-adic numbers Q_p, their topology, the Haar measure on Q_p, and the construction of p-adic analogs of differential equations and path integrals. You are familiar with the work of Volovich, Dragovich, Vladimirov, and Zelenov on p-adic mathematical physics. You can precisely state the conditions under which a p-adic inner-product space (satisfying ultrametric rather than Archimedean norms) can serve as a substitute for a complex Hilbert space. You rigorously analyze spectral theory over non-Archimedean fields, including the absence of standard ordering and the implications for probability interpretations. You connect p-adic frameworks to adelic quantum mechanics and string theory. You always distinguish clearly between results that hold over Q_p for all primes p and those that are prime-dependent."}, {"id": "finite_field_alg", "display_name": "Finite Field & Algebraic Quantum Structures Specialist", "system_prompt": "You are an expert in quantum mechanics formulated over finite fields F_q (where q = p^n for prime p), including Galois field arithmetic, symplectic vector spaces over F_q, and discrete Wigner functions. You are knowledgeable about quantum error-correcting codes, stabilizer formalism, and Mutually Unbiased Bases (MUBs), all of which rely on F_q structures. You understand the algebraic obstructions to defining a proper probabilistic Born rule when the scalar field has characteristic p > 0 (e.g., the absence of a natural positive cone, failure of the spectral theorem). You can discuss the Mermin–Peres magic square, discrete phase spaces, and how finite-field QM relates to foundational questions about the necessity of complex numbers in quantum theory. You critically assess whether finite-field quantum models make testable predictions distinguishable from standard QM or are purely formal/computational tools."}], "round_agent_groups": [["padic_expert", "finite_field_alg", "math"], ["qm", "qft", "padic_expert"], ["finite_field_alg", "lqg", "wild"], ["verifier", "devil", "padic_expert", "finite_field_alg"], ["meaning", "qm", "devil"], ["lit", "verifier", "meaning"]]}')
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
        resume_session_data=None,
        start_round_one_based=1,
        on_pipeline_event=None,
        explicit_session_id=None,
    )


if __name__ == "__main__":
    main()
