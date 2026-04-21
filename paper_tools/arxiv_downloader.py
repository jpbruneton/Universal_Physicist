"""
Download relevant quantum gravity papers from arXiv.
Saves abstracts as .txt and optionally downloads PDFs.
"""

import os
import time
import json
import argparse
import urllib.request
from pathlib import Path
from datetime import datetime

import arxiv

from config import ARXIV_CATEGORIES, ARXIV_SEARCH_TERMS, get_papers_dir


def search_and_download(
    query: str | None = None,
    categories: list[str] | None = None,
    max_results: int = 20,
    download_pdfs: bool = False,
    start_date: str | None = None,  # format: "YYYYMMDD"
) -> list[dict]:
    """Search arXiv and save abstracts (and optionally PDFs) to papers/."""
    os.makedirs(get_papers_dir(), exist_ok=True)

    search_query = query or " OR ".join(f'"{term}"' for term in ARXIV_SEARCH_TERMS[:5])
    if categories:
        cat_filter = " OR ".join(f"cat:{c}" for c in categories)
        search_query = f"({search_query}) AND ({cat_filter})"

    print(f"Searching arXiv: {search_query[:100]}...")

    client = arxiv.Client(
        page_size=100,
        delay_seconds=3,
        num_retries=3,
    )

    search = arxiv.Search(
        query=search_query,
        max_results=max_results,
        sort_by=arxiv.SortCriterion.Relevance,
    )

    downloaded = []
    index = []

    for paper in client.results(search):
        paper_id = paper.entry_id.split("/")[-1].replace("/", "_")
        safe_title = "".join(c if c.isalnum() or c in " _-" else "_" for c in paper.title)[:60]
        base_name = f"{paper_id}_{safe_title}"

        # Save abstract as .txt
        txt_path = Path(get_papers_dir()) / f"{base_name}.txt"
        if not txt_path.exists():
            abstract_text = (
                f"Title: {paper.title}\n"
                f"Authors: {', '.join(a.name for a in paper.authors)}\n"
                f"Published: {paper.published.strftime('%Y-%m-%d')}\n"
                f"arXiv ID: {paper.entry_id}\n"
                f"Categories: {', '.join(paper.categories)}\n"
                f"Abstract:\n{paper.summary}\n"
            )
            txt_path.write_text(abstract_text, encoding="utf-8")
            print(f"  Saved abstract: {paper.title[:60]}")
        else:
            print(f"  Already have: {paper.title[:60]}")

        meta = {
            "id": paper.entry_id,
            "title": paper.title,
            "authors": [a.name for a in paper.authors],
            "published": paper.published.isoformat(),
            "categories": paper.categories,
            "abstract": paper.summary,
            "txt_file": str(txt_path),
        }

        # Optionally download PDF
        if download_pdfs:
            pdf_path = Path(get_papers_dir()) / f"{base_name}.pdf"
            if not pdf_path.exists():
                try:
                    print(f"    Downloading PDF...")
                    paper.download_pdf(dirpath=str(get_papers_dir()), filename=f"{base_name}.pdf")
                    meta["pdf_file"] = str(pdf_path)
                    time.sleep(2)  # be polite to arXiv
                except Exception as e:
                    print(f"    PDF download failed: {e}")
            else:
                meta["pdf_file"] = str(pdf_path)

        downloaded.append(meta)
        index.append(meta)

    # Save index
    index_path = Path(get_papers_dir()) / "index.json"
    existing = []
    if index_path.exists():
        try:
            existing = json.loads(index_path.read_text())
        except Exception:
            pass

    # Merge: avoid duplicates by ID
    existing_ids = {p["id"] for p in existing}
    new_entries = [p for p in index if p["id"] not in existing_ids]
    all_entries = existing + new_entries
    index_path.write_text(json.dumps(all_entries, indent=2, default=str), encoding="utf-8")

    print(f"\nDone. {len(new_entries)} new papers added. Total in library: {len(all_entries)}.")
    return downloaded


def _arxiv_fetch_with_backoff(client, search, arxiv_id: str, max_attempts: int = 5):
    """Fetch arxiv results with exponential backoff on HTTP 429."""
    delay = 10
    for attempt in range(max_attempts):
        try:
            return list(client.results(search))
        except arxiv.HTTPError as e:
            if e.status == 429:
                print(f"  Rate limited (429) on {arxiv_id}, waiting {delay}s...")
                time.sleep(delay)
                delay = min(delay * 2, 120)
            else:
                raise
    print(f"  Giving up on {arxiv_id} after {max_attempts} attempts")
    return []


def download_by_id(arxiv_ids: list[str], download_pdfs: bool = True) -> list[dict]:
    """Download specific papers by arXiv ID (e.g., '2301.12345')."""
    os.makedirs(get_papers_dir(), exist_ok=True)
    client = arxiv.Client(
        page_size=1,
        delay_seconds=3,
        num_retries=3,
    )
    results = []

    for arxiv_id in arxiv_ids:
        search = arxiv.Search(id_list=[arxiv_id])
        papers = _arxiv_fetch_with_backoff(client, search, arxiv_id)
        if not papers:
            print(f"Not found: {arxiv_id}")
            continue

        paper = papers[0]
        paper_id = arxiv_id.replace("/", "_")
        safe_title = "".join(c if c.isalnum() or c in " _-" else "_" for c in paper.title)[:60]
        base_name = f"{paper_id}_{safe_title}"

        txt_path = Path(get_papers_dir()) / f"{base_name}.txt"
        abstract_text = (
            f"Title: {paper.title}\n"
            f"Authors: {', '.join(a.name for a in paper.authors)}\n"
            f"Published: {paper.published.strftime('%Y-%m-%d')}\n"
            f"arXiv ID: {paper.entry_id}\n"
            f"Categories: {', '.join(paper.categories)}\n"
            f"Abstract:\n{paper.summary}\n"
        )
        txt_path.write_text(abstract_text, encoding="utf-8")
        print(f"Saved: {paper.title[:70]}")

        if download_pdfs:
            try:
                paper.download_pdf(dirpath=str(get_papers_dir()), filename=f"{base_name}.pdf")
                print(f"  PDF downloaded.")
                time.sleep(2)
            except Exception as e:
                print(f"  PDF failed: {e}")

        meta = {
            "id": paper.entry_id,
            "title": paper.title,
            "authors": [a.name for a in paper.authors],
            "published": paper.published.isoformat(),
            "categories": paper.categories,
            "abstract": paper.summary,
            "txt_file": str(txt_path),
        }
        results.append(meta)
        time.sleep(3)  # polite inter-paper delay to avoid 429

    # Update index.json
    index_path = Path(get_papers_dir()) / "index.json"
    existing = []
    if index_path.exists():
        try:
            existing = json.loads(index_path.read_text())
        except Exception:
            pass
    existing_ids = {p["id"] for p in existing}
    new_entries = [p for p in results if p["id"] not in existing_ids]
    all_entries = existing + new_entries
    index_path.write_text(json.dumps(all_entries, indent=2, default=str), encoding="utf-8")
    print(f"\n{len(new_entries)} new papers added to library.")

    return results


def list_library() -> None:
    """Print current library contents."""
    index_path = Path(get_papers_dir()) / "index.json"
    if not index_path.exists():
        print("Library is empty. Run with --search to populate.")
        return

    papers = json.loads(index_path.read_text())
    print(f"\nLibrary: {len(papers)} papers\n")
    for i, p in enumerate(papers, 1):
        authors = p["authors"][:2]
        author_str = ", ".join(authors) + (" et al." if len(p["authors"]) > 2 else "")
        print(f"{i:3}. {p['title'][:65]}")
        print(f"     {author_str} | {p['published'][:10]} | {p['id']}")
    print()


if __name__ == "__main__":
    from config import set_papers_project

    parser = argparse.ArgumentParser(description="Download quantum gravity papers from arXiv")
    parser.add_argument(
        "--project",
        "-p",
        default="default",
        metavar="SLUG",
        help="Paper library subfolder under papers/ (default: default)",
    )
    parser.add_argument("--search", metavar="QUERY", help="Custom search query")
    parser.add_argument("--ids", nargs="+", metavar="ID", help="Specific arXiv IDs to download")
    parser.add_argument("--n", type=int, default=30, help="Max results (default 30)")
    parser.add_argument("--pdf", action="store_true", help="Also download PDFs (slow, large)")
    parser.add_argument("--categories", nargs="+", default=["gr-qc", "hep-th"],
                        help="arXiv categories to filter by")
    parser.add_argument("--list", action="store_true", help="List current library")
    parser.add_argument("--core", action="store_true",
                        help="Download a curated set of foundational QG papers by ID")
    args = parser.parse_args()
    set_papers_project(args.project)

    if args.list:
        list_library()
    elif args.ids:
        download_by_id(args.ids, download_pdfs=args.pdf)
    elif args.core:
        # Curated list: foundational QG + holography + QIT/spacetime emergence + graviticize-QM
        CORE_IDS = [
            # --- Loop Quantum Gravity / Background Independent ---
            "gr-qc/9606089",   # Thiemann - Quantum Spin Dynamics (QSD / LQG Hamiltonian)
            "gr-qc/0404018",   # Ashtekar & Lewandowski - Background independent QG (review)
            "gr-qc/0110034",   # Rovelli - Loop quantum gravity (book-level review)
            "gr-qc/9612035",   # Barbero - Real Ashtekar variables for Lorentzian gravity
            "gr-qc/9511071",   # Immirzi - Quantum gravity and Regge calculus (Barbero-Immirzi param)
            "gr-qc/0411032",   # Engle, Pereira, Rovelli - LQG vertex amplitude (EPRL precursor)
            "0905.4082",       # Engle, Pereira, Rovelli, Livine - EPRL spinfoam model
            "gr-qc/0501114",   # Ashtekar, Pawlowski, Singh - LQC: quantum nature of Big Bang
            "1507.00541",      # Haggard & Rovelli - Quantum gravity bounce and black-to-white hole

            # --- Black Holes / Hawking / Information Paradox ---
            "hep-th/9402044",  # Strominger & Vafa - Microscopic origin of BH entropy
            "hep-th/9310026",  # Hawking - Breakdown of predictability in gravitational collapse
            "hep-th/0612005",  # Mathur - The fuzzball proposal for black holes
            "1207.3123",       # AMPS - Black holes: complementarity or firewalls?
            "1304.6483",       # Maldacena & Susskind - ER=EPR (corrected ID)
            "1905.08762",      # Penington - Entanglement wedge reconstruction and the info paradox
            "1908.11970",      # Almheiri et al. - The entropy of bulk quantum fields and the island rule
            "2006.06872",      # Almheiri et al. - The Page curve of Hawking radiation from semiclassical geometry
            "hep-th/0106112",  # Hawking, Perry, Strominger - Soft hair on black holes

            # --- White Holes ---
            "1403.1486",       # Rovelli & Vidotto - Planck stars
            "1802.02264",      # Bianchi, Christodoulou et al. - White holes as remnants

            # --- Holography / AdS-CFT ---
            "hep-th/9711200",  # Maldacena - Large N limit / AdS-CFT
            "hep-th/9802150",  # Witten - Anti-de Sitter Space and Holography
            "gr-qc/9310026",   # 't Hooft - Dimensional Reduction / holographic principle

            # --- Causal Sets / CDT ---
            "gr-qc/0601121",   # Henson - Causal set approach to QG

            # --- QIT / Spacetime from Entanglement ---
            "1003.3016",       # Van Raamsdonk - Building spacetime from entanglement
            "hep-th/0603001",  # Ryu & Takayanagi - Holographic entanglement entropy
            "gr-qc/9504004",   # Jacobson - Thermodynamics of spacetime (Einstein eq. of state)
            "1504.01737",      # Jacobson - Entanglement equilibrium and Einstein equations
            "1001.0785",       # Verlinde - On the origin of gravity (entropic)

            # --- Relational QM / Graviticize QM ---
            "quant-ph/9609002",# Rovelli - Relational Quantum Mechanics
            "1805.12099",      # Giacomini, Castro-Ruiz, Brukner - Quantum reference frames (2018)
            "1712.07207",      # Höhn & Vanrietvelde - Switching quantum reference frames

            # --- Spacetime from Hilbert space (Carroll et al.) ---
            "1803.04490",      # Cao, Carroll & Michalakis - Space from Hilbert space
        ]
        print("Downloading core foundational QG + LQG + BH/information + QIT papers...")
        download_by_id(CORE_IDS, download_pdfs=args.pdf)
    else:
        search_and_download(
            query=args.search,
            categories=args.categories,
            max_results=args.n,
            download_pdfs=args.pdf,
        )
