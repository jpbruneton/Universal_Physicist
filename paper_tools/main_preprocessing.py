"""
main_preprocessing.py — one-shot pipeline that builds the complete paper library.

Steps (all automatic):
  1. Core curated papers         — paper_tools.arxiv_downloader  --core
  2. INSPIRE-HEP top-cited sweep — paper_tools.inspire_downloader (all topics)
  3. Semantic Scholar sweep      — paper_tools.semantic_scholar   (QIT / foundations)
  4. Full-text PDF extraction    — paper_tools.pdf_reader         (for any downloaded PDFs)
  5. AI preprocessing            — paper_tools.preprocess_papers  (summaries, keywords, exclusions)

Usage:
  py -3 -m paper_tools.main_preprocessing                    # full pipeline, abstracts only
  py -3 -m paper_tools.main_preprocessing --pdf              # also download full PDFs (slow)
  py -3 -m paper_tools.main_preprocessing --min-citations 30 # stricter citation filter
  py -3 -m paper_tools.main_preprocessing --quick            # core papers only + preprocess
  py -3 -m paper_tools.main_preprocessing --skip-inspire     # skip INSPIRE (use if offline)
  py -3 -m paper_tools.main_preprocessing --skip-semantic    # skip Semantic Scholar
  py -3 -m paper_tools.main_preprocessing --force            # re-preprocess everything
  py -3 -m paper_tools.main_preprocessing --status           # show current library status

Estimated time (abstracts only): ~45-60 min (dominated by INSPIRE/S2 API calls + arXiv downloads).
Estimated cost (AI preprocessing): < $1 via Claude Haiku.
"""

import os
import sys
import time
import json
import argparse
from pathlib import Path
from datetime import datetime

from config import (
    ANTHROPIC_API_KEY,
    PAPERS_ARXIV_PDF,
    PAPERS_INSPIRE,
    PAPERS_SEMANTIC_SCHOLAR,
    get_papers_dir,
    set_papers_project,
)


def _banner(msg: str) -> None:
    print(f"\n{'='*70}")
    print(f"  {msg}")
    print(f"{'='*70}\n")


def _step(n: int, total: int, msg: str) -> None:
    print(f"\n[{n}/{total}] {msg}")
    print("-" * 60)


def _library_status() -> dict:
    index  = Path(get_papers_dir()) / "index.json"
    pindex = Path(get_papers_dir()) / "processed_index.json"

    raw_count  = len(json.loads(index.read_text())  ) if index.exists()  else 0
    proc_count = 0
    pdf_count  = 0
    ft_count   = 0
    excl_count = 0

    if pindex.exists():
        processed = json.loads(pindex.read_text())
        proc_count = len(processed)
        excl_count = sum(1 for p in processed if p.get("excluded"))
        pdf_count  = sum(1 for p in processed
                         if p.get("pdf_file") and Path(p["pdf_file"]).exists())
        ft_count   = sum(1 for p in processed
                         if p.get("pdf_file") and
                         Path(str(p["pdf_file"]).replace(".pdf", ".fulltext.txt")).exists())

    return {
        "raw":       raw_count,
        "processed": proc_count,
        "excluded":  excl_count,
        "pdfs":      pdf_count,
        "fulltext":  ft_count,
    }


def show_status() -> None:
    s = _library_status()
    print(f"\nLibrary status ({get_papers_dir()}):")
    print(f"  Papers in index:     {s['raw']}")
    print(f"  AI-preprocessed:     {s['processed']}  ({s['excluded']} excluded)")
    print(f"  PDFs downloaded:     {s['pdfs']}")
    print(f"  Full text cached:    {s['fulltext']}")

    pindex = Path(get_papers_dir()) / "processed_index.json"
    if pindex.exists():
        processed = json.loads(pindex.read_text())
        included  = [p for p in processed if not p.get("excluded")]
        kw_filled = sum(1 for p in included if p.get("keywords"))
        print(f"  Keywords extracted:  {kw_filled} / {len(included)}")
    print()


def run_pipeline(
    download_pdfs:  bool = False,
    min_citations:  int  = None,
    skip_inspire:   bool = False,
    skip_semantic:  bool = False,
    quick:          bool = False,
    force_preproc:  bool = False,
    s2_api_key:     str  = None,
    papers_project: str  = "bulk_library",
) -> None:
    set_papers_project(papers_project)
    print(f"  Paper library folder: {get_papers_dir()}\n")

    total_steps = 2 if quick else (5 - skip_inspire - skip_semantic)
    step = 0
    t0   = time.time()

    _banner(f"Quantum Gravity Paper Library — Full Pipeline  [{datetime.now():%Y-%m-%d %H:%M}]")
    show_status()

    # ── Step 1: Core curated papers ──────────────────────────────────────────
    step += 1
    _step(step, total_steps, "Downloading core curated papers (arXiv IDs)")
    try:
        from .arxiv_downloader import download_by_id

        CORE_IDS = [
            # LQG / background-independent
            "gr-qc/9606089",    # Thiemann - QSD
            "gr-qc/0404018",    # Ashtekar & Lewandowski - background-independent QG
            "gr-qc/0110034",    # Thiemann - Modern Canonical QGR
            "0905.4082",        # EPRL spinfoam
            "gr-qc/9710008",    # Rovelli - Loop quantum gravity (review)
            "gr-qc/0407052",    # Black hole entropy in LQG
            # Black holes / information paradox
            "1207.3123",        # AMPS - Black holes: complementarity or firewalls?
            "1905.08762",       # Penington - entanglement wedge + info paradox
            "2006.06872",       # Almheiri et al. - entropy of Hawking radiation
            "hep-th/0106112",   # Maldacena - Eternal black holes in AdS
            "gr-qc/9504004",    # Jacobson - thermodynamics of spacetime
            # Holography / AdS-CFT
            "hep-th/9711200",   # Maldacena - Large N / AdS-CFT
            "hep-th/9802150",   # Witten - Anti-de Sitter and holography
            "gr-qc/9310026",    # 't Hooft - dimensional reduction / holographic principle
            "hep-th/0603001",   # Ryu & Takayanagi - holographic entanglement entropy
            # QIT / spacetime from entanglement
            "1003.3016",        # Van Raamsdonk - building spacetime from entanglement
            "1504.01737",       # Jacobson - entanglement equilibrium + Einstein eqs
            "1001.0785",        # Verlinde - entropic gravity
            # Relational QM / graviticize QM
            "quant-ph/9609002", # Rovelli - Relational QM
            "1803.04490",       # Giacomini et al. - quantum reference frames
            # Causal / CDT
            "gr-qc/0601121",    # Henson - causal sets
            # LQC
            "gr-qc/0501114",    # Ashtekar, Pawlowski, Singh - LQC bounce
            # White holes
            "1403.1486",        # Rovelli & Vidotto - Planck stars
        ]
        download_by_id(CORE_IDS, download_pdfs=download_pdfs)
    except Exception as e:
        print(f"  Core download error: {e}")

    if quick:
        # Skip INSPIRE / Semantic Scholar, go straight to preprocessing
        pass
    else:
        # ── Step 2: INSPIRE-HEP sweep ────────────────────────────────────────
        if not skip_inspire:
            step += 1
            _step(step, total_steps, "INSPIRE-HEP top-cited sweep")
            print("  This queries INSPIRE for top-cited papers across all QG topics.")
            print("  Estimated: 20-40 min, 300-600 new papers.\n")
            try:
                from .inspire_downloader import run_all_sweeps as inspire_sweep
                inspire_sweep(
                    min_citations=min_citations,
                    download_pdfs=download_pdfs,
                )
            except Exception as e:
                print(f"  INSPIRE sweep error: {e}")

        # ── Step 3: Semantic Scholar sweep ───────────────────────────────────
        if not skip_semantic:
            step += 1
            _step(step, total_steps, "Semantic Scholar QIT/foundations sweep")
            print("  Estimated: 5-15 min, 100-200 new papers.\n")
            try:
                from .semantic_scholar import run_all_sweeps as s2_sweep
                s2_sweep(
                    min_citations=min_citations,
                    download_pdfs=download_pdfs,
                    api_key=s2_api_key,
                )
            except Exception as e:
                print(f"  Semantic Scholar sweep error: {e}")

    # ── Step 4: Full-text extraction ──────────────────────────────────────────
    step += 1
    _step(step, total_steps, "Extracting full text from downloaded PDFs")
    try:
        from .pdf_reader import extract_library
        n = extract_library(get_papers_dir(), force=False)
        print(f"  {n} new full-text files extracted.")
    except Exception as e:
        print(f"  PDF extraction error: {e}")

    # ── Step 5: AI preprocessing ──────────────────────────────────────────────
    step += 1
    _step(step, total_steps, "AI preprocessing (summaries + keywords via Claude Haiku)")

    if not ANTHROPIC_API_KEY:
        print("  SKIPPED — ANTHROPIC_API_KEY not set.")
        print("  Set it and run:  py -3 -m paper_tools.preprocess_papers")
    else:
        s_before = _library_status()
        try:
            from .preprocess_papers import process_all
            process_all(force=force_preproc)
        except Exception as e:
            print(f"  Preprocessing error: {e}")
        s_after = _library_status()
        new_kw = s_after["processed"] - s_before["processed"]
        print(f"  {new_kw} papers newly preprocessed.")

    # ── Summary ───────────────────────────────────────────────────────────────
    elapsed = time.time() - t0
    _banner(f"Pipeline complete  ({elapsed/60:.1f} min)")
    show_status()
    print("Next step:")
    print("  py -3 main.py --phrase 'short description of your topic'")
    print("  py -3 written_projects/quantum_gravity_project.py --question 'Your research question here'")
    print("  scripts\\run.bat  (Windows: same as py -3 main.py)\n")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Full quantum gravity paper library pipeline",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    parser.add_argument("--pdf",           action="store_true",
                        help="Download arXiv PDFs (overrides config papers.arxiv_pdf)")
    parser.add_argument("--no-pdf",        action="store_true",
                        help="Skip arXiv PDF downloads (overrides config papers.arxiv_pdf)")
    parser.add_argument("--min-citations", "-c", type=int, default=None,
                        help="Minimum citation count for INSPIRE/S2 sweeps")
    parser.add_argument("--skip-inspire",  action="store_true",
                        help="Skip INSPIRE (also off if papers.inspire is false in config)")
    parser.add_argument("--skip-semantic", action="store_true",
                        help="Skip Semantic Scholar (also off if papers.semantic_scholar is false in config)")
    parser.add_argument("--quick",         action="store_true",
                        help="Core papers only — no INSPIRE/S2 sweeps")
    parser.add_argument("--force",         action="store_true",
                        help="Re-preprocess even if already done")
    parser.add_argument("--s2-key",        metavar="KEY",
                        help="Semantic Scholar API key")
    parser.add_argument("--status",        action="store_true",
                        help="Show library status and exit")
    parser.add_argument(
        "--project",
        "-p",
        default="bulk_library",
        metavar="SLUG",
        help="Paper library subfolder under papers/ for this pipeline (default: bulk_library)",
    )
    args = parser.parse_args()

    if args.pdf and args.no_pdf:
        parser.error("Use either --pdf or --no-pdf, not both.")

    if args.status:
        set_papers_project(args.project)
        show_status()
    else:
        if args.pdf:
            download_pdfs = True
        elif args.no_pdf:
            download_pdfs = False
        else:
            download_pdfs = PAPERS_ARXIV_PDF
        skip_inspire = args.skip_inspire or not PAPERS_INSPIRE
        skip_semantic = args.skip_semantic or not PAPERS_SEMANTIC_SCHOLAR
        run_pipeline(
            download_pdfs  = download_pdfs,
            min_citations  = args.min_citations,
            skip_inspire   = skip_inspire,
            skip_semantic  = skip_semantic,
            quick          = args.quick,
            force_preproc  = args.force,
            s2_api_key     = args.s2_key,
            papers_project = args.project,
        )
