# Universal Physicist

Agent-powered theoretical physicist: describe a topic in one phrase, pull papers, preprocess the library, and run multi-round expert sessions with optional LaTeX output.

<!-- Example block: bordered callout (renders on GitHub) -->
<div align="left" style="border: 1px solid #d0d7de; border-radius: 8px; padding: 14px 18px; background-color: #f6f8fa; margin: 12px 0 20px 0;">

<p><strong>Example</strong> — sample command and abbreviated console output (illustration only; your run will differ).</p>

<pre style="margin: 10px 0 0 0; padding: 10px 12px; background: #fff; border: 1px solid #e1e4e8; border-radius: 6px; overflow-x: auto;"><code>py -3 main.py --phrase "look for a theory of QM on non continous fields instead of C, maybe Q or finite fields, explore building constraints and testable predictions"</code></pre>

<pre style="margin: 10px 0 0 0; padding: 10px 12px; background: #fff; border: 1px solid #e1e4e8; border-radius: 6px; overflow-x: auto; white-space: pre-wrap;">[1/4] Planning session (prompt, agents, arXiv query)...

Title: Quantum Mechanics over Discrete Algebraic Fields: Foundations, Constraints, and Phenomenology
Refined question (1051 chars) — preview:

  Can a physically consistent and empirically distinguishable formulation of quantum mechanics be constructed over a non-continuous number field — specifically the rationals Q, p-adic fields Q_p, or finite fields F_q (with q = p^n) — replacing the standard Hilbert space H over C? Concretely: (1) What algebraic and structural constraints (inner-product positivity, spectral theorems, Born-rule analogs...

Built-in + dynamic agents:
  + dynamic: padic_expert — p-adic & Non-Archimedean Analysis Expert
  + dynamic: finite_field_expert — Finite Field & Algebraic Geometry Specialist
  + dynamic: phenomenology_expert — Quantum Foundations Phenomenologist
  + dynamic: algebra_structures_expert — Operator Algebras & Representation Theory Expert

Rounds (agent keys per round):
  Round 1: algebra_structures_expert, padic_expert, finite_field_expert, math
  Round 2: padic_expert, finite_field_expert, qft, verifier
  Round 3: algebra_structures_expert, qm, padic_expert, wild
  Round 4: phenomenology_expert, qm, verifier, finite_field_expert
  Round 5: devil, phenomenology_expert, algebra_structures_expert, padic_expert
  Round 6: lit, meaning, wild, phenomenology_expert

arXiv: abs:(quantum mechanics p-adic OR finite field OR discrete field OR non-archimedean OR rational field Hilbert space) OR t...
Categories: ['quant-ph', 'hep-th', 'math-ph']  |  max papers: 28

[2/4] Searching arXiv and saving abstracts...  → papers/<slug>/

Searching arXiv: (abs:(quantum mechanics p-adic OR finite field OR discrete field OR non-archimedean OR rational fiel...</pre>

</div>

## 1. API key setup

Create **`.claude/settings.json`** yourself under the project root. 
Put your Anthropic API key under `env`:

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

## 2. Running `main.py`

### Phrase mode (default)

As given in the example above:

```bash
py -3 main.py --phrase "what you want to explore"
```

Or start interactive mode and type the phrase when prompted:

```bash
py -3 main.py -i
```

### Structured instructions (JSON)

Copy [`instructions.example.json`](instructions.example.json) → `instructions.json` (gitignored), or use `--instructions path\to\file.json`. Run:

```bash
py -3 main.py --use-instructions
```

Example file (required: `query`, `keywords`, `authors`; optional: `exclude_keywords`, `exclude_authors` — use **plain** words; the pipeline turns them into `all:` / `au:` and `ANDNOT` in the final arXiv query):

```json
{
  "query": "QM on non-continuous fields; constraints and predictions.",
  "keywords": ["p-adic quantum mechanics", "finite field"],
  "authors": ["Volovich", "Dragovich"],
  "exclude_keywords": ["MOND"],
  "exclude_authors": ["Smith"]
}
```

The planner sees all fields; `main.py` then **merges** include terms and appends **ANDNOT** for exclusions. Do not use `--phrase` or `-i` with `--use-instructions`.

**Layout:** generated session replays and older standalone project scripts live under [`written_projects/`](written_projects/). From the repo root, run e.g. `py -3 written_projects/quantum_gravity_project.py`. Windows helpers are in [`scripts/`](scripts/) (`run.bat` and `download_papers.bat` at the repo root are thin wrappers that call those).

### Concrete examples

**Quantum gravity** — a single phrase; the planner turns it into a detailed question, arXiv query, and expert rounds:

```bash
py -3 main.py --phrase "What is the most promising path to a theory of quantum gravity, and what does it imply about the nature of spacetime?"
```

**Discrete-time QM / relativity** — different domain, same interface:

```bash
py -3 main.py --phrase "Discrete-time quantum mechanics that stays unitary and compatible with special relativity, with testable Planck-scale effects"
```

## Example outputs (two saved sessions)

These runs were produced in this project before the universal `main.py` pipeline; they use the same **output layout** as current sessions: LaTeX under `output/<session_id>/`, full state in `sessions/session_<id>.json`.

| Session ID | Topic | Main LaTeX output | PDF (compiled) | Checkpoints |
|------------|--------|---------------------|----------------|-------------|
| `74f0fded` | Quantum gravity — most promising path, nature of spacetime | [output/74f0fded/final_paper.tex](output/74f0fded/final_paper.tex) | [session_74f0fded_quantum_gravity.pdf](assets/session_74f0fded_quantum_gravity.pdf) | `round_01_checkpoint.tex` … `round_03_checkpoint.tex` |
| `969486d9` | Discrete-time QM — unitarity, Lorentz covariance, dispersion | [output/969486d9/final_paper.tex](output/969486d9/final_paper.tex) | [session_969486d9_discrete_time_qm.pdf](assets/session_969486d9_discrete_time_qm.pdf) | `round_01_checkpoint.tex` … `round_04_checkpoint.tex` |

First-page previews (click to open the full PDF):

| `74f0fded` — quantum gravity | `969486d9` — discrete-time QM |
|:---:|:---:|
| [![](assets/preview_74f0fded_quantum_gravity.png)](assets/session_74f0fded_quantum_gravity.pdf) | [![](assets/preview_969486d9_discrete_time_qm.png)](assets/session_969486d9_discrete_time_qm.pdf) |

Each run writes **`.tex`** files under `output/<session_id>/` (final paper and round checkpoints). A **PDF** appears there **only if** `pdflatex` or `latexmk` is on your `PATH` when the session runs (via `latex_tools/`). The two example sessions above are checked in as **sources** under `output/`; **built PDFs** for the readme live in [`assets/`](assets/).

## 3. What the pipeline does (concise)

1. **Plan** — A planner model turns your short phrase into a structured plan: a precise research question, an arXiv search query, categories, how many papers to pull, which **built-in** experts (GR, QM, QFT, math, literature, etc.) join each round, and how the discussion is staged. **Experts are also created on the fly when needed:** if your topic calls for niche skills (e.g. p-adic analysis, finite fields, a specific phenomenology), the planner invents one or more **dynamic specialists** for that run only—each gets its own system prompt and participates like any other agent. You do not configure them by hand.

2. **Papers (in `main.py`)** — The library is **per project** under `papers/<slug>/` (derived from the planned session title; CLI tools use `--project <slug>` or `papers/default/` until something sets it). Step **arXiv**: relevance search using the planned query and categories; results merge into `papers/<slug>/index.json` with **abstract** text and sidecar `.txt` files. If **`papers.inspire`** / **`papers.semantic_scholar`** are true in `config` (see `config.default.yaml`), `main.py` then runs a **single-topic** supplement on each: INSPIRE (top-cited) and Semantic Scholar, using the session title (or the refined question if the title is too short). That is **not** the same as `py -3 -m paper_tools.main_preprocessing`, which runs long **multi-topic** sweeps; turn off the YAML flags if you want arXiv only.

   PDF downloads follow **`papers.arxiv_pdf`** and `main.py --pdf` / `--no-pdf` (see config comments).

   If you still have an old **flat** `papers/index.json` at the repo root, move it (and any sidecar files) into `papers/default/` yourself, or pick a slug and pass `--project` consistently.

3. **Preprocess** — `paper_tools.preprocess_papers` walks everything in `papers/<slug>/index.json` that is not yet in `processed_index.json` in the same folder. For each paper it uses **title + abstract only** (Claude Haiku) to build summaries, keywords, and simple tags—not the full PDF. If a PDF file exists for an entry, the script can optionally **extract full text** into a cached `.fulltext.txt` (for agents that read the library); that path is separate from the Haiku pass.

4. **Discussion** — Multiple rounds: specialists answer the refined question with shared context from prior round syntheses; an orchestrator synthesizes after each round; LaTeX checkpoints and a final write-up go under `output/<session_id>/`. Session state is stored in `sessions/session_<id>.json`.

## 4. Cost

- **Papers** — arXiv access is free. Preprocessing uses a **small, fast** model (Haiku-class) per abstract; that part is relatively **cheap** compared to the main loop.
- **Experts** — Each specialist and each orchestration step uses a **large** model (Sonnet-class). A full run with several rounds and many agents is **not** cheap; **roughly on the order of $5 USD per full run** is a reasonable ballpark, but actual cost depends on prompt length, rounds, and current API pricing—check your Anthropic usage dashboard.

Use `--plan-only` to preview the plan without papers or the expert session. Use `--skip-papers` / `--skip-preprocess` if you already have a library and only want the discussion.

## 5. Todos / future work

- **Better paper integration** — Wire the literature reviewer and sessions more tightly to each project’s `papers/<slug>/index.json` / `processed_index.json` (e.g. inject top-matching abstracts or summaries into context, retrieval by keywords, optional full-text snippets from PDFs). Today, papers are fetched and preprocessed mainly to grow the local library; deeper RAG-style use is still to be improved.
