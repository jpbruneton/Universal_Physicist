"""
Turn a short user phrase into a session plan: refined question, arXiv search, agent roster,
optional new specialist agents, and per-round agent groups.
"""

import json
import re

from config import MAX_ARXIV_PAPERS, MIN_ARXIV_PAPERS

from .base import call_agent

# Built-in specialists the model may assign (no deepread here — needs paper IDs).
ALLOWED_BASE_KEYS = frozenset(
    {
        "gr",
        "qm",
        "qft",
        "math",
        "lqg",
        "bh",
        "wild",
        "teacher",
        "verifier",
        "meaning",
        "devil",
        "lit",
    }
)

PLANNER_SYSTEM_BASE = f"""You are a scientific session planner for a theoretical-physics think tank.

The user will give a SHORT phrase describing what they want to explore. Your job is to design ONE coherent research session.

Reply with ONLY a single JSON object (no markdown fences, no commentary) using exactly this schema:
{{
  "session_title": "<short academic title>",
  "refined_research_question": "<detailed, precise research question the experts will answer>",
  "arxiv_search_query": "<arXiv API query string: use field prefixes like ti:, abs:, all: and OR/AND as needed>",
  "arxiv_categories": ["<category>", ...],
  "max_papers": <integer {MIN_ARXIV_PAPERS}-{MAX_ARXIV_PAPERS}>,
  "dynamic_agent_specs": [
    {{
      "id": "<unique_snake_case_id like plasma_expert>",
      "display_name": "<human-readable name>",
      "system_prompt": "<full system prompt: You are an expert in ...>"
    }}
  ],
  "round_agent_groups": [
    ["<agent_key>", ...],
    ...
  ]
}}

Rules:
- refined_research_question must be self-contained and technically pointed (equations welcome in plain text/LaTeX).
- arxiv_search_query must target papers directly relevant to the phrase; prefer abs: or all: with key technical terms.
- arxiv_categories: choose from gr-qc, hep-th, hep-ph, quant-ph, astro-ph, cond-mat, math-ph as appropriate (1-4 categories).
- max_papers: pick based on breadth (narrow topic ~12, medium ~24, very broad literature sweeps up to ~{MAX_ARXIV_PAPERS}).
- dynamic_agent_specs: 0 to 4 entries. Add NEW specialists ONLY when the topic needs expertise not covered by built-ins (e.g. plasma astrophysics, lattice QCD, biophysics). Each system_prompt must be 4-12 sentences, concrete.
- round_agent_groups: 3 to 6 rounds. Each round is a list of 2-5 agents. Use built-in keys and/or ids from dynamic_agent_specs.
- Built-in agent keys you may use: gr, qm, qft, math, lqg, bh, wild, teacher, verifier, meaning, devil, lit
  - gr: General Relativity / classical gravity
  - qm, qft: quantum mechanics / quantum field theory
  - math: mathematical methods
  - lqg: loop quantum gravity / background-independent approaches
  - bh: black holes / quantum information in gravity
  - wild: creative speculative constructions (researcher sessions only — see session mode rules below)
  - teacher: pedagogical explanation only — defines terms, unpacks every symbol in equations, cites established results; does not invent new models
  - verifier: consistency and equations
  - meaning: physical interpretation
  - devil: critique and failure modes
  - lit: literature and connections

Design rounds so early rounds establish formalism, middle rounds explore proposals, later rounds stress-test and connect to literature.
"""

PLANNER_APPEND_RESEARCHER = """
SESSION MODE — RESEARCHER (default research mode):
- Aim to advance understanding toward new ideas, models, or syntheses. You may assign "wild" where bold but defensible speculation helps.
- Use "teacher" only when a round genuinely needs careful definitions or unpacking of known material.
"""

PLANNER_APPEND_TEACHER = """
SESSION MODE — TEACHER (expository only):
- The user wants teaching, not invention. Do NOT assign the agent key "wild" in any round. Replace any instinct to use "wild" with "teacher".
- Use "teacher" generously in middle rounds to explain derivations, define every symbol in key equations, and connect to standard references.
- The refined_research_question should ask for clear explanation of established physics and literature, not for proposing novel speculative frameworks.
- dynamic_agent_specs: if you add specialists, they should deepen explanation (e.g. mathematical background), not advocate new speculative theories.
- Design rounds for learning: setup → core formalism with explanations → literature connections and consistency checks. Avoid "propose a new model" as the goal.
"""


def _planner_system(session_mode: str) -> str:
    if session_mode == "teacher":
        return PLANNER_SYSTEM_BASE + PLANNER_APPEND_TEACHER
    return PLANNER_SYSTEM_BASE + PLANNER_APPEND_RESEARCHER


def _normalize_rounds_for_session_mode(plan: dict, session_mode: str) -> None:
    """Teacher mode forbids wild — swap to teacher. Dedupe within each round."""
    if session_mode != "teacher":
        return
    cleaned = []
    for r in plan["round_agent_groups"]:
        row = []
        for k in r:
            nk = "teacher" if k == "wild" else k
            row.append(nk)
        seen: set[str] = set()
        deduped = []
        for k in row:
            if k not in seen:
                seen.add(k)
                deduped.append(k)
        cleaned.append(deduped)
    plan["round_agent_groups"] = cleaned


def _extract_json_object(text: str) -> str:
    t = text.strip()
    if t.startswith("```"):
        lines = t.split("\n")
        if len(lines) >= 2:
            inner = "\n".join(lines[1:])
            if inner.rstrip().endswith("```"):
                inner = inner.rstrip()[:-3]
            t = inner.strip()
    m = re.search(r"\{[\s\S]*\}\s*$", t)
    if m:
        return m.group(0)
    return t


def plan_session(user_phrase: str, session_mode: str) -> dict:
    """Call the planner model; return a validated plan dict."""
    messages = [
        {
            "role": "user",
            "content": f"User phrase:\n{user_phrase}\n\nProduce the JSON plan.",
        }
    ]
    raw = call_agent(_planner_system(session_mode), messages, max_tokens=8192)
    blob = _extract_json_object(raw)
    plan = json.loads(blob)
    plan = _validate_plan(plan)
    _normalize_rounds_for_session_mode(plan, session_mode)
    return plan


def plan_session_from_instructions(
    query: str,
    keywords: list[str],
    authors: list[str],
    exclude_keywords: list[str],
    exclude_authors: list[str],
    session_mode: str,
) -> dict:
    """
    Same as plan_session, but the user message carries structured query, keywords,
    authors, and optional exclusions so the model must fold them into refined_research_question
    and arxiv_search_query (main.py also applies a deterministic merge afterward).
    """
    kw_block = "\n".join(f"- {k}" for k in keywords)
    au_block = "\n".join(f"- {a}" for a in authors)
    extra = ""
    if exclude_keywords:
        exk = "\n".join(f"- {k}" for k in exclude_keywords)
        extra += (
            f"\nExclude these keywords from relevance (use ANDNOT with all:, abs:, or ti: as appropriate):\n{exk}\n"
        )
    if exclude_authors:
        exa = "\n".join(f"- {a}" for a in exclude_authors)
        extra += (
            f"\nExclude these authors (use ANDNOT au: with each plain name as arXiv author search):\n{exa}\n"
        )
    messages = [
        {
            "role": "user",
            "content": (
                "Structured research instructions (every field must be reflected in your JSON output):\n\n"
                f"Main query (foundation for session_title and refined_research_question):\n{query}\n\n"
                f"Keywords (each must appear in arxiv_search_query using abs:, ti:, or all: as appropriate):\n"
                f"{kw_block}\n\n"
                f"Authors (each must appear in arxiv_search_query using the arXiv au: prefix):\n"
                f"{au_block}\n"
                f"{extra}\n"
                "Produce the JSON plan. The refined_research_question must align with the main query. "
                "arxiv_search_query must be relevant to the topic and must incorporate every keyword and every author."
                + (
                    " Exclusions must appear as ANDNOT clauses in arxiv_search_query."
                    if (exclude_keywords or exclude_authors)
                    else ""
                )
            ),
        }
    ]
    raw = call_agent(_planner_system(session_mode), messages, max_tokens=8192)
    blob = _extract_json_object(raw)
    plan = json.loads(blob)
    plan = _validate_plan(plan)
    _normalize_rounds_for_session_mode(plan, session_mode)
    return plan


def _validate_plan(plan: dict) -> dict:
    required = [
        "session_title",
        "refined_research_question",
        "arxiv_search_query",
        "arxiv_categories",
        "max_papers",
        "dynamic_agent_specs",
        "round_agent_groups",
    ]
    for k in required:
        if k not in plan:
            raise ValueError(f"Plan missing key: {k}")

    if not isinstance(plan["arxiv_categories"], list) or not plan["arxiv_categories"]:
        plan["arxiv_categories"] = ["gr-qc", "hep-th"]

    n = int(float(plan["max_papers"]))
    plan["max_papers"] = max(MIN_ARXIV_PAPERS, min(MAX_ARXIV_PAPERS, n))

    specs = plan["dynamic_agent_specs"]
    if not isinstance(specs, list):
        raise ValueError("dynamic_agent_specs must be a list")
    if len(specs) > 4:
        specs = specs[:4]
        plan["dynamic_agent_specs"] = specs

    for s in specs:
        for field in ("id", "display_name", "system_prompt"):
            if field not in s or not isinstance(s[field], str) or not s[field].strip():
                raise ValueError(f"Invalid dynamic_agent_specs entry: {s}")
        if not re.match(r"^[a-z][a-z0-9_]{1,48}$", s["id"]):
            raise ValueError(f"Invalid dynamic agent id: {s['id']}")
        if s["id"] in ALLOWED_BASE_KEYS:
            raise ValueError(f"Dynamic agent id clashes with built-in: {s['id']}")

    rounds = plan["round_agent_groups"]
    if not isinstance(rounds, list) or len(rounds) < 3:
        raise ValueError("round_agent_groups must be a list of at least 3 rounds")

    allowed = ALLOWED_BASE_KEYS | {s["id"] for s in specs}
    cleaned = []
    for r in rounds:
        if not isinstance(r, list):
            continue
        row = []
        for key in r:
            if not isinstance(key, str):
                continue
            k = key.strip()
            if k in allowed:
                row.append(k)
        if row:
            cleaned.append(row[:5])
    if len(cleaned) < 3:
        raise ValueError("After validation, fewer than 3 non-empty rounds")
    plan["round_agent_groups"] = cleaned
    return plan
