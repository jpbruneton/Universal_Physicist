"""
INSPIRE-HEP downloader — queries the INSPIRE-HEP REST API (no key required) for
top-cited papers in each research direction, extracts arXiv IDs, and downloads
abstracts via the arxiv library.

INSPIRE-HEP is the authoritative citation database for HEP and GR — far better
than arXiv relevance search for finding seminal work.

API docs: https://inspirehep.net/api/literature

Usage:
    py -3 inspire_downloader.py                  # run all topic sweeps
    py -3 inspire_downloader.py --topic "loop quantum gravity" --n 80
    py -3 inspire_downloader.py --min-citations 50   # only highly cited
    py -3 inspire_downloader.py --dry-run        # print what would be fetched
"""

import time
import json
import argparse
import requests
from pathlib import Path
from arxiv_downloader import download_by_id, list_library
from config import PAPERS_DIR

INSPIRE_API = "https://inspirehep.net/api/literature"

# (topic query, max_results, min_citations)
# Broad single-concept queries — let INSPIRE's citation ranking do the filtering.
TOPIC_SWEEPS = [
    # -- Core quantum gravity approaches --------------------------------------
    ("quantum gravity",                100, 30),
    ("loop quantum gravity",           100, 15),
    ("spin foam",                       80, 10),
    ("loop quantum cosmology",          60, 10),
    ("causal dynamical triangulations", 60, 10),
    ("causal sets",                     50, 10),
    ("asymptotic safety",               50, 10),
    ("group field theory",              40,  5),
    ("non-commutative geometry",        40,  5),
    ("twistor theory",                  40, 10),

    # -- Black holes ----------------------------------------------------------
    ("black hole",                     100, 50),
    ("Hawking radiation",               80, 20),
    ("black hole entropy",              80, 20),
    ("information loss",                60, 15),
    ("white hole",                      40,  5),
    ("wormhole",                        60, 15),
    ("firewall",                        50, 10),

    # -- Holography & AdS/CFT ------------------------------------------------
    ("holography",                     100, 30),
    ("AdS/CFT",                        100, 30),
    ("holographic entanglement",        60, 10),
    ("entanglement entropy",            80, 20),

    # -- Spacetime emergence & quantum information ----------------------------
    ("spacetime emergence",             60, 10),
    ("quantum information gravity",     50, 10),
    ("it from qubit",                   30,  5),
    ("tensor network",                  50, 10),
    ("entropic gravity",                40, 10),

    # -- Generalised uncertainty & Planck scale physics ----------------------
    ("generalized uncertainty principle", 60, 10),
    ("GUP",                              40,  5),
    ("minimum length",                   50, 10),
    ("Planck scale",                     60, 15),
    ("quantum foam",                     30,  5),
    ("doubly special relativity",        40,  5),

    # -- Quantum cosmology & singularities ------------------------------------
    ("quantum cosmology",               60, 15),
    ("Wheeler-DeWitt",                  50, 15),
    ("quantum bounce",                  40,  5),
    ("singularity resolution",          50, 10),

    # -- Relational & foundational QM ----------------------------------------
    ("relational quantum mechanics",    40, 10),
    ("quantum reference frames",        40,  5),
    ("problem of time",                 40, 10),
    ("quantum measurement gravity",     30,  5),
]


def query_inspire_page(query: str, page: int, size: int) -> list[dict]:
    """Fetch one page of INSPIRE results.

    Uses phrase-quoted queries restricted to gr-qc / hep-th / quant-ph categories,
    sorted by citation count. Citation filtering is done client-side from the
    returned citation_count field (server-side `cn N+` syntax is unreliable).
    """
    # Use INSPIRE title/keyword search to get relevant-only results.
    # t: searches titles; k: searches keywords (PACS/subject tags).
    # OR-ing both gives good recall without noise from citations/abstract.
    full_query = f't "{query}" OR k "{query}"'
    params = {
        "sort": "mostcited",
        "size": size,
        "page": page,
        "fields": "arxiv_eprints,titles,authors,citation_count,abstracts",
        "q": full_query,
    }
    try:
        resp = requests.get(INSPIRE_API, params=params, timeout=30)
        resp.raise_for_status()
        return resp.json().get("hits", {}).get("hits", [])
    except requests.RequestException as e:
        print(f"    INSPIRE error: {e}")
        return []


def extract_arxiv_id(hit: dict) -> str | None:
    """Extract the best arXiv ID from an INSPIRE hit."""
    eprints = hit.get("metadata", {}).get("arxiv_eprints", [])
    for ep in eprints:
        val = ep.get("value", "")
        if val:
            return val
    return None


def extract_citation_count(hit: dict) -> int:
    return hit.get("metadata", {}).get("citation_count", 0)


def extract_title(hit: dict) -> str:
    titles = hit.get("metadata", {}).get("titles", [])
    return titles[0].get("title", "Unknown") if titles else "Unknown"


def fetch_topic(topic: str, max_results: int, min_citations: int, dry_run: bool = False) -> list[str]:
    """Fetch arXiv IDs for a topic from INSPIRE, sorted by citations.
    Citation count threshold is applied client-side for reliability.
    Stops early once results drop below min_citations (since sorted by mostcited).
    """
    page_size = 25
    collected_ids = []
    seen = set()
    page = 1

    while len(collected_ids) < max_results:
        batch = query_inspire_page(topic, page, page_size)
        if not batch:
            break

        below_threshold = 0
        for hit in batch:
            arxiv_id = extract_arxiv_id(hit)
            citations = extract_citation_count(hit)
            title = extract_title(hit)

            if citations < min_citations:
                below_threshold += 1
                continue

            if arxiv_id and arxiv_id not in seen:
                seen.add(arxiv_id)
                collected_ids.append(arxiv_id)
                if dry_run:
                    print(f"    [{citations:5d} cit] {title[:60]}  arXiv:{arxiv_id}")

        # If the whole page is below threshold, we're done (results are sorted by citations)
        if below_threshold == len(batch):
            break
        if len(batch) < page_size:
            break
        page += 1
        time.sleep(0.5)

    return collected_ids[:max_results]


def load_existing_arxiv_ids() -> set[str]:
    """Return set of arXiv IDs already in our library (to avoid re-downloading)."""
    index_path = Path(PAPERS_DIR) / "index.json"
    if not index_path.exists():
        return set()
    try:
        data = json.loads(index_path.read_text(encoding="utf-8"))
        ids = set()
        for p in data:
            pid = p.get("id", "")
            # Normalize: strip URL prefix and version suffix
            pid = pid.replace("http://arxiv.org/abs/", "").replace("https://arxiv.org/abs/", "")
            pid = pid.rsplit("v", 1)[0] if pid.count("v") == 1 and pid[-2:][0] == "v" else pid
            ids.add(pid)
        return ids
    except Exception:
        return set()


def run_all_sweeps(
    min_citations=None,      # int | None
    topics=None,             # list[str] | None
    dry_run: bool = False,
    download_pdfs: bool = False,
) -> None:
    existing = load_existing_arxiv_ids()
    print(f"Existing library: {len(existing)} papers\n")

    sweeps = TOPIC_SWEEPS
    if topics:
        sweeps = [(t, n, c) for t, n, c in TOPIC_SWEEPS if any(kw in t.lower() for kw in topics)]
        if not sweeps:
            print(f"No matching topics for: {topics}")
            return

    total_new = 0
    all_new_ids = []

    for topic, max_n, default_min_cit in sweeps:
        min_cit = min_citations if min_citations is not None else default_min_cit
        print(f"  [{min_cit}+ citations] {topic} (up to {max_n})")

        ids = fetch_topic(topic, max_n, min_cit, dry_run=dry_run)
        new_ids = [i for i in ids if i not in existing]
        print(f"    -> {len(ids)} found, {len(new_ids)} new")

        all_new_ids.extend(new_ids)
        existing.update(new_ids)  # prevent duplicates across topics
        time.sleep(1.0)  # polite between topics

    # Deduplicate across all sweeps
    all_new_ids = list(dict.fromkeys(all_new_ids))
    total_new = len(all_new_ids)

    print(f"\n{'-'*60}")
    print(f"Total new papers to download: {total_new}")

    if dry_run:
        print("(Dry run — nothing downloaded)")
        return

    if total_new == 0:
        print("Nothing new to download.")
        return

    # Estimate time
    est_seconds = total_new * 3.5
    est_min = est_seconds / 60
    print(f"Estimated download time: ~{est_min:.0f} min ({total_new} papers × ~3.5s each)")
    print("Downloading...\n")

    # Download in batches of 20 to show progress
    batch_size = 20
    downloaded = 0
    for i in range(0, len(all_new_ids), batch_size):
        batch = all_new_ids[i : i + batch_size]
        print(f"  Batch {i//batch_size + 1} / {(len(all_new_ids)-1)//batch_size + 1}")
        download_by_id(batch, download_pdfs=download_pdfs)
        downloaded += len(batch)
        print(f"  Progress: {downloaded}/{total_new}\n")

    print(f"\nDone. {total_new} new papers added.")
    print("Next step: py -3 preprocess_papers.py")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Download top-cited QG papers from INSPIRE-HEP"
    )
    parser.add_argument("--topic", "-t", nargs="+",
                        help="Filter to topics containing these keywords")
    parser.add_argument("--min-citations", "-c", type=int, default=None,
                        help="Override minimum citation count for all topics")
    parser.add_argument("--dry-run", action="store_true",
                        help="Show what would be downloaded, don't download")
    parser.add_argument("--pdf", action="store_true",
                        help="Also download PDFs (slow, ~5-10MB each)")
    parser.add_argument("--list", action="store_true",
                        help="List current library")
    args = parser.parse_args()

    if args.list:
        list_library()
    else:
        run_all_sweeps(
            min_citations=args.min_citations,
            topics=args.topic,
            dry_run=args.dry_run,
            download_pdfs=args.pdf,
        )
