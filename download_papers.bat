@echo off
REM ─── Quantum Gravity Paper Library Manager ───────────────────────────────
REM
REM RECOMMENDED WORKFLOW (run in order):
REM
REM   Step 1 — curated foundational papers (~40, ~2 min):
REM     download_papers.bat --core
REM
REM   Step 2 — INSPIRE-HEP top-cited sweep (~300-500 papers, ~30 min):
REM     download_papers.bat --inspire
REM     download_papers.bat --inspire --dry-run     (preview first)
REM     download_papers.bat --inspire --min-citations 50  (only highly cited)
REM
REM   Step 3 — Semantic Scholar QIT/foundations sweep (~100-200 papers, ~15 min):
REM     download_papers.bat --semantic
REM     download_papers.bat --semantic --api-key YOUR_S2_KEY
REM
REM   Step 4 — preprocess (generate keywords/summaries via Claude Haiku, ~3 min/100 papers):
REM     download_papers.bat --preprocess
REM
REM   Step 5 — show library:
REM     download_papers.bat --show
REM
REM   Optional — add specific papers by arXiv ID:
REM     download_papers.bat --ids 1207.3123 hep-th/9711200
REM
REM   Optional — also download full PDFs (slow, ~5MB each):
REM     download_papers.bat --inspire --pdf

if "%1"=="--inspire" (
    shift
    py -3 inspire_downloader.py %*
    goto :eof
)
if "%1"=="--semantic" (
    shift
    py -3 semantic_scholar.py %*
    goto :eof
)
if "%1"=="--preprocess" (
    py -3 preprocess_papers.py
    goto :eof
)
if "%1"=="--preprocess-force" (
    py -3 preprocess_papers.py --force
    goto :eof
)
if "%1"=="--show" (
    py -3 preprocess_papers.py --show
    goto :eof
)
py -3 arxiv_downloader.py %*
