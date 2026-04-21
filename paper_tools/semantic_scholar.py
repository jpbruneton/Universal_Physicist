"""
Semantic Scholar downloader — queries the S2 public API for top-cited papers,
extracts arXiv IDs, and downloads via the arxiv library.

Complements INSPIRE-HEP with broader coverage (quantum information / foundations
papers that may not be indexed on INSPIRE).

API: https://api.semanticscholar.org/graph/v1/paper/search
No API key required for basic use (100 req / 5 min).
Free API key (https://www.semanticscholar.org/product/api) raises limit to 1 req/sec.

Usage:
    py -3 -m paper_tools.semantic_scholar                    # run all topic sweeps
    py -3 -m paper_tools.semantic_scholar --topic "quantum reference frames"
    py -3 -m paper_tools.semantic_scholar --min-citations 30
    py -3 -m paper_tools.semantic_scholar --dry-run
    py -3 -m paper_tools.semantic_scholar --api-key YOUR_KEY
"""

import time
import json
import argparse
import requests
from pathlib import Path
from .arxiv_downloader import download_by_id
from config import PAPERS_DIR

S2_API = "https://api.semanticscholar.org/graph/v1/paper/search"
S2_FIELDS = "title,authors,year,citationCount,externalIds,abstract"

# (topic, max_results, min_citations)
# S2 complements INSPIRE with broader QIT/CS/foundations coverage.
# Keep queries broad — citation ranking handles precision.
TOPIC_SWEEPS = [
    # -- Quantum information & spacetime --------------------------------------
    ("quantum gravity",                 80, 20),
    ("quantum information gravity",     60, 10),
    ("entanglement entropy",            80, 15),
    ("holography",                      60, 15),
    ("tensor network",                  60, 10),

    # -- Black holes & information --------------------------------------------
    ("black hole information",          60, 15),
    ("Hawking radiation",               60, 15),
    ("black hole entropy",              60, 15),
    ("information paradox",             50, 10),
    ("scrambling",                      40, 10),
    ("quantum chaos",                   40, 10),

    # -- Wormholes & ER=EPR --------------------------------------------------
    ("wormhole",                        50, 10),
    ("traversable wormhole",            30,  5),

    # -- Relational & foundational QM ----------------------------------------
    ("relational quantum mechanics",    40,  5),
    ("quantum reference frames",        40,  5),
    ("decoherence gravity",             40, 10),
    ("quantum foundations gravity",     30,  5),

    # -- Spacetime emergence -------------------------------------------------
    ("spacetime emergence",             50, 10),
    ("emergent gravity",                50, 10),
    ("entropic gravity",                40, 10),

    # -- Uncertainty & Planck scale ------------------------------------------
    ("generalized uncertainty",         50,  5),
    ("minimum length",                  40,  5),
    ("quantum foam",                    30,  5),

    # -- Causal structure ----------------------------------------------------
    ("causal structure",                40,  5),
    ("indefinite causal order",         30,  3),
]


def query_s2(query: str, offset: int, limit: int, api_key: str | None) -> dict:
    params = {
        "query": query,
        "fields": S2_FIELDS,
        "limit": limit,
        "offset": offset,
    }
    headers = {}
    if api_key:
        headers["x-api-key"] = api_key
    try:
        resp = requests.get(S2_API, params=params, headers=headers, timeout=30)
        resp.raise_for_status()
        return resp.json()
    except requests.RequestException as e:
        print(f"    S2 error: {e}")
        return {}


def extract_arxiv_id(paper: dict) -> str | None:
    eids = paper.get("externalIds", {})
    return eids.get("ArXiv")


def fetch_topic(
    topic: str, max_results: int, min_citations: int,
    api_key, dry_run: bool  # api_key: str | None
) -> list[str]:
    collected = []
    seen = set()
    offset = 0
    page_size = 100  # S2 supports up to 100 per page

    while len(collected) < max_results:
        data = query_s2(topic, offset, min(page_size, max_results - len(collected)), api_key)
        papers = data.get("data", [])
        if not papers:
            break

        for p in papers:
            cit = p.get("citationCount", 0) or 0
            if cit < min_citations:
                continue
            arxiv_id = extract_arxiv_id(p)
            if arxiv_id and arxiv_id not in seen:
                seen.add(arxiv_id)
                collected.append(arxiv_id)
                if dry_run:
                    print(f"    [{cit:5d} cit] {p.get('title','')[:60]}  arXiv:{arxiv_id}")

        total = data.get("total", 0)
        offset += len(papers)
        if offset >= total or len(papers) == 0:
            break
        time.sleep(1.0)  # S2 rate limit

    return collected[:max_results]


def load_existing_arxiv_ids() -> set[str]:
    index_path = Path(PAPERS_DIR) / "index.json"
    if not index_path.exists():
        return set()
    try:
        data = json.loads(index_path.read_text(encoding="utf-8"))
        ids = set()
        for p in data:
            pid = p.get("id", "").replace("http://arxiv.org/abs/", "").replace("https://arxiv.org/abs/", "")
            if "v" in pid[-3:]:
                pid = pid.rsplit("v", 1)[0]
            ids.add(pid)
        return ids
    except Exception:
        return set()


def run_all_sweeps(
    min_citations=None,      # int | None
    topics=None,             # list[str] | None
    dry_run: bool = False,
    download_pdfs: bool = False,
    api_key=None,            # str | None
) -> None:
    existing = load_existing_arxiv_ids()
    print(f"Existing library: {len(existing)} papers\n")

    sweeps = TOPIC_SWEEPS
    if topics:
        sweeps = [(t, n, c) for t, n, c in TOPIC_SWEEPS
                  if any(kw.lower() in t.lower() for kw in topics)]
        if not sweeps:
            print(f"No matching topics for: {topics}")
            return

    all_new_ids = []

    for topic, max_n, default_min in sweeps:
        min_cit = min_citations if min_citations is not None else default_min
        print(f"  [{min_cit}+ citations] {topic} (up to {max_n})")
        ids = fetch_topic(topic, max_n, min_cit, api_key, dry_run)
        new_ids = [i for i in ids if i not in existing]
        print(f"    → {len(ids)} found, {len(new_ids)} new")
        all_new_ids.extend(new_ids)
        existing.update(new_ids)
        time.sleep(1.5)

    all_new_ids = list(dict.fromkeys(all_new_ids))
    print(f"\n{'-'*60}")
    print(f"Total new papers to download: {len(all_new_ids)}")

    if dry_run or not all_new_ids:
        if dry_run:
            print("(Dry run — nothing downloaded)")
        return

    est_min = len(all_new_ids) * 3.5 / 60
    print(f"Estimated time: ~{est_min:.0f} min")

    batch_size = 20
    downloaded = 0
    for i in range(0, len(all_new_ids), batch_size):
        batch = all_new_ids[i : i + batch_size]
        print(f"  Batch {i//batch_size + 1} / {(len(all_new_ids)-1)//batch_size + 1}")
        download_by_id(batch, download_pdfs=download_pdfs)
        downloaded += len(batch)
        print(f"  Progress: {downloaded}/{len(all_new_ids)}\n")

    print(f"\nDone. {len(all_new_ids)} new papers added.")
    print("Next step: py -3 -m paper_tools.preprocess_papers")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Download top-cited QG papers from Semantic Scholar")
    parser.add_argument("--topic", "-t", nargs="+")
    parser.add_argument("--min-citations", "-c", type=int, default=None)
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--pdf", action="store_true")
    parser.add_argument("--api-key", help="Semantic Scholar API key (free, raises rate limits)")
    args = parser.parse_args()

    run_all_sweeps(
        min_citations=args.min_citations,
        topics=args.topic,
        dry_run=args.dry_run,
        download_pdfs=args.pdf,
        api_key=args.api_key,
    )
