# Universal Physicist

Agent-powered theoretical physicist: describe a topic in one phrase, pull papers, preprocess the library, and run multi-round expert sessions with optional LaTeX output.

Example run : 
py -3 main.py --phrase "look for a theory of QM on non continous fields instead of C, maybe Q or finite fields, explore building constraints and testable predictions"

Outputs : 
  [1/4] Planning session (prompt, agents, arXiv query)...

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

  [2/4] Searching arXiv and saving abstracts to papers/...

Searching arXiv: (abs:(quantum mechanics p-adic OR finite field OR discrete field OR non-archimedean OR rational fiel...

and running

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

As given in the example above

```bash
py -3 main.py --phrase "what you want to explore"
```

Or start interactive mode and type the phrase when prompted:

```bash
py -3 main.py -i
```

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

| Session ID | Topic | Main LaTeX output | Checkpoints |
|------------|--------|---------------------|-------------|
| `74f0fded` | Quantum gravity — most promising path, nature of spacetime | [output/74f0fded/final_paper.tex](output/74f0fded/final_paper.tex) | `round_01_checkpoint.tex` … `round_03_checkpoint.tex` |
| `969486d9` | Discrete-time QM — unitarity, Lorentz covariance, dispersion | [output/969486d9/final_paper.tex](output/969486d9/final_paper.tex) | `round_01_checkpoint.tex` … `round_04_checkpoint.tex` |

Each run always writes **`.tex`** files under `output/<session_id>/` (final paper and round checkpoints). You can copy those elsewhere and compile with your own TeX setup. A **PDF** is produced in that same folder **only if** `pdflatex` or `latexmk` is on your `PATH` when the session runs (via `latex_tools/`); otherwise you only get the sources. The examples above are checked in as `.tex` only.

## 3. What the pipeline does (concise)

1. **Plan** — A planner model turns your short phrase into a structured plan: a precise research question, an arXiv search query, categories, how many papers to pull, which **built-in** experts (GR, QM, QFT, math, literature, etc.) join each round, and how the discussion is staged. **Experts are also created on the fly when needed:** if your topic calls for niche skills (e.g. p-adic analysis, finite fields, a specific phenomenology), the planner invents one or more **dynamic specialists** for that run only—each gets its own system prompt and participates like any other agent. You do not configure them by hand.

2. **Papers (in `main.py`)** — Only the **arXiv API** is called: a relevance search using the planned query and categories. Results are merged into `papers/index.json` with metadata and the **abstract** text (also saved as sidecar `.txt` files). **INSPIRE-HEP** and **Semantic Scholar** are *not* invoked by `main.py`; optional helpers live under **`paper_tools/`** (e.g. `inspire_downloader`, `semantic_scholar`, `main_preprocessing`; use `--help` on each module). If you run those *before* a session, merged hits land in the same `index.json`, so the expert step can still benefit from a larger library. You do **not** need any of that for a normal run—`main.py` already performs arXiv fetch and preprocessing when papers are not skipped.

   By default, **PDFs are not** downloaded. Use `main.py --pdf` if you also want arXiv PDFs on disk (slower, larger).

3. **Preprocess** — `paper_tools.preprocess_papers` walks everything in `papers/index.json` that is not yet in `processed_index.json`. For each paper it uses **title + abstract only** (Claude Haiku) to build summaries, keywords, and simple tags—not the full PDF. If a PDF file exists for an entry, the script can optionally **extract full text** into a cached `.fulltext.txt` (for agents that read the library); that path is separate from the Haiku pass.

4. **Discussion** — Multiple rounds: specialists answer the refined question with shared context from prior round syntheses; an orchestrator synthesizes after each round; LaTeX checkpoints and a final write-up go under `output/<session_id>/`. Session state is stored in `sessions/session_<id>.json`.

## 4. Cost

- **Papers** — arXiv access is free. Preprocessing uses a **small, fast** model (Haiku-class) per abstract; that part is relatively **cheap** compared to the main loop.
- **Experts** — Each specialist and each orchestration step uses a **large** model (Sonnet-class). A full run with several rounds and many agents is **not** cheap; **roughly on the order of $5 USD per full run** is a reasonable ballpark, but actual cost depends on prompt length, rounds, and current API pricing—check your Anthropic usage dashboard.

Use `--plan-only` to preview the plan without papers or the expert session. Use `--skip-papers` / `--skip-preprocess` if you already have a library and only want the discussion.

## 5. Todos / future work

- **Better paper integration** — Wire the literature reviewer and sessions more tightly to `papers/index.json` / `processed_index.json` (e.g. inject top-matching abstracts or summaries into context, retrieval by keywords, optional full-text snippets from PDFs). Today, papers are fetched and preprocessed mainly to grow the local library; deeper RAG-style use is still to be improved.
