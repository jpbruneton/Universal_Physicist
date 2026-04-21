# How to use Universal Physicist

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

## 3. What the pipeline does (concise)

1. **Plan** — A planner model turns your short phrase into a structured plan: a precise research question, an arXiv search query, categories, how many papers to pull, which built-in experts to use, optional **new** specialist agents (custom system prompts), and which experts speak in each round.

2. **Papers** — arXiv is searched; abstracts (and optionally PDFs) are saved under `papers/` and merged into `papers/index.json`.

3. **Preprocess** — Each new abstract is summarized and tagged (for library search and filtering).

4. **Discussion** — Multiple rounds: specialists answer the refined question with shared context from prior round syntheses; an orchestrator synthesizes after each round; LaTeX checkpoints and a final write-up go under `output/<session_id>/`. Session state is stored in `sessions/session_<id>.json`.

## 4. Cost

- **Papers** — arXiv access is free. Preprocessing uses a **small, fast** model (Haiku-class) per abstract; that part is relatively **cheap** compared to the main loop.
- **Experts** — Each specialist and each orchestration step uses a **large** model (Sonnet-class). A full run with several rounds and many agents is **not** cheap; **roughly on the order of $5 USD per full run** is a reasonable ballpark, but actual cost depends on prompt length, rounds, and current API pricing—check your Anthropic usage dashboard.

Use `--plan-only` to preview the plan without papers or the expert session. Use `--skip-papers` / `--skip-preprocess` if you already have a library and only want the discussion.

## 5. Todos / future work

- **Better paper integration** — Wire the literature reviewer and sessions more tightly to `papers/index.json` / `processed_index.json` (e.g. inject top-matching abstracts or summaries into context, retrieval by keywords, optional full-text snippets from PDFs). Today, papers are fetched and preprocessed mainly to grow the local library; deeper RAG-style use is still to be improved.
