# Universal Physicist

Agent-powered theoretical physicist: describe a topic in one phrase, pull papers, preprocess the library, and run multi-round expert sessions with optional LaTeX output.

## 1. API key setup

Create **`.claude/settings.json`** yourself under the project root (this file is gitignored; do not commit it). Put your Anthropic API key under `env`:

```json
{
  "permissions": {
    "allow": ["Bash(*)"]
  },
  "env": {
    "ANTHROPIC_API_KEY": "sk-ant-api03-..."
  }
}
```

Alternatively, set the environment variable `ANTHROPIC_API_KEY` in your shell or system. The app reads the environment variable first, then `.claude/settings.json` if the variable is unset.

If you need a starting shape only, the repo may ship a `.claude/settings.example.json` with a placeholder `your-api-key`—copy it to `settings.json` and replace the value with your real key.

## 2. Running `main.py`

In practice: *“write in main what you want”* means: give **one short phrase** that states your goal, then run:

```bash
py -3 main.py --phrase "what you want to explore"
```

Or start interactive mode and type the phrase when prompted:

```bash
py -3 main.py -i
```

On Windows you can also use `run.bat`, which invokes `main.py`.

That is the main workflow: **say what you want**, **execute** `main.py` with `--phrase` or `-i`. Optional flags (see `py -3 main.py --help`) let you skip paper download, skip preprocessing, only print the planner JSON (`--plan-only`), cap rounds, etc.

### Concrete examples

**Quantum gravity** — a single phrase; the planner turns it into a detailed question, arXiv query, and expert rounds:

```bash
py -3 main.py --phrase "What is the most promising path to a theory of quantum gravity, and what does it imply about the nature of spacetime?"
```

**Discrete-time QM / relativity** — different domain, same interface:

```bash
py -3 main.py --phrase "Discrete-time quantum mechanics that stays unitary and compatible with special relativity, with testable Planck-scale effects"
```

Shorter phrases work too (e.g. `"covariant MOND and cluster lensing"`). The planner fills in scope, literature search, and roster.

## Example outputs (two saved sessions)

These runs were produced in this project before the universal `main.py` pipeline; they use the same **output layout** as current sessions: LaTeX under `output/<session_id>/`, full state in `sessions/session_<id>.json`.

| Session ID | Topic | Main LaTeX output | Checkpoints |
|------------|--------|---------------------|-------------|
| `74f0fded` | Quantum gravity — most promising path, nature of spacetime | [output/74f0fded/final_paper.tex](output/74f0fded/final_paper.tex) | `round_01_checkpoint.tex` … `round_03_checkpoint.tex` |
| `969486d9` | Discrete-time QM — unitarity, Lorentz covariance, dispersion | [output/969486d9/final_paper.tex](output/969486d9/final_paper.tex) | `round_01_checkpoint.tex` … `round_04_checkpoint.tex` |

**PDFs:** During a run, if `pdflatex` or `latexmk` is available on your `PATH`, the tool also writes `final_paper.pdf` (and checkpoint PDFs) next to the `.tex` files. **This repository only stores the `.tex` sources** for those two sessions—no PDFs are committed. To build a PDF locally, from the project root:

```bash
cd output/74f0fded
pdflatex -interaction=nonstopmode final_paper.tex
pdflatex -interaction=nonstopmode final_paper.tex
```

Repeat for `output/969486d9/`, or use `latexmk -pdf final_paper.tex`. See [LaTeX / PDF post-processing](#latex--pdf-post-processing) below.

## 3. What the pipeline does (concise)

1. **Plan** — A planner model turns your short phrase into a structured plan: a precise research question, an arXiv search query, categories, how many papers to pull, which built-in experts to use, optional **new** specialist agents (custom system prompts), and which experts speak in each round.

2. **Papers** — arXiv is searched; abstracts (and optionally PDFs) are saved under `papers/` and merged into `papers/index.json`.

3. **Preprocess** — Each new abstract is summarized and tagged (for library search and filtering).

4. **Discussion** — Multiple rounds: specialists answer the refined question with shared context from prior round syntheses; an orchestrator synthesizes after each round; LaTeX checkpoints and a final write-up go under `output/<session_id>/`. Session state is stored in `sessions/session_<id>.json`.

## 4. Cost

- **Papers** — arXiv access is free. Preprocessing uses a **small, fast** model (Haiku-class) per abstract; that part is relatively **cheap** compared to the main loop.
- **Experts** — Each specialist and each orchestration step uses a **large** model (Sonnet-class). A full run with several rounds and many agents is **not** cheap; **roughly on the order of $5 USD per full run** is a reasonable ballpark, but actual cost depends on prompt length, rounds, and current API pricing—check your Anthropic usage dashboard.

Use `--plan-only` to preview the plan without papers or the expert session. Use `--skip-papers` / `--skip-preprocess` if you already have a library and only want the discussion.

## Paper download / preprocess (CLI)

Scripts live under the **`paper_tools/`** package. Run them from the project root with `-m`, for example:

```bash
py -3 -m paper_tools.arxiv_downloader --list
py -3 -m paper_tools.main_preprocessing --quick
py -3 -m paper_tools.preprocess_papers
```

`download_papers.bat` is updated to call these modules.

## LaTeX / PDF post-processing

PDF compilation lives in **`latex_tools/`** (used by `agents/latex_formatter.py` after each checkpoint and final paper):

```bash
py -3 -m latex_tools.compile_latex   # prints whether pdflatex/latexmk is on PATH
```

Install [MiKTeX](https://miktex.org) or TeX Live and ensure `pdflatex` or `latexmk` is available if you want `.tex` outputs compiled to PDF automatically.

## 6. Todos / future work

- **Better paper integration** — Wire the literature reviewer and sessions more tightly to `papers/index.json` / `processed_index.json` (e.g. inject top-matching abstracts or summaries into context, retrieval by keywords, optional full-text snippets from PDFs). Today, papers are fetched and preprocessed mainly to grow the local library; deeper RAG-style use is still to be improved.
