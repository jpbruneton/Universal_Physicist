"""
Universal Physicist — one entry point from a short phrase to a full expert session.

Pipeline:
  1) You describe what you want in a simple phrase
  2) A planner expands it into a detailed question, arXiv query, agent roster,
     and optional new specialist agents (dynamic experts)
  3) Paper fetch: arXiv (required), then optional INSPIRE + Semantic Scholar supplements from config
  4) paper_tools.preprocess_papers enriches the library
  5) Multi-round discussion with built-in + dynamic agents, orchestrator, LaTeX output

Usage:
    py -3 main.py --phrase "explore entropic gravity and black hole information"
    py -3 main.py --phrase "..." --mode teacher
    py -3 main.py --use-instructions
    py -3 main.py --use-instructions --instructions path/to/instructions.json
    py -3 main.py -i
    py -3 main.py --phrase "..." --skip-papers
    py -3 main.py --phrase "..." --skip-preprocess
    py -3 main.py --plan-only --phrase "..."
    py -3 main.py --phrase "..." --mode teacher --resume
"""

import argparse
import copy
import io
import json
import os
import sys
import time
import uuid
from collections.abc import Callable
from datetime import datetime
from pathlib import Path

# Force UTF-8 output on Windows
if sys.stdout.encoding.lower() != "utf-8":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8", errors="replace")

from config import (
    ANTHROPIC_API_KEY,
    MAX_ARXIV_PAPERS,
    MAX_EXPERT_CONTEXT_CHARS,
    MIN_ARXIV_PAPERS,
    OUTPUT_DIR,
    PAPERS_ARXIV_PDF,
    PAPERS_INSPIRE,
    PAPERS_SEMANTIC_SCHOLAR,
    SESSIONS_DIR,
    get_papers_dir,
    set_papers_project,
)

if not ANTHROPIC_API_KEY:
    print(
        "ERROR: Set ANTHROPIC_API_KEY in the environment or .claude/settings.json "
        "(env.ANTHROPIC_API_KEY)."
    )
    sys.exit(1)

from agents import (
    gr_expert,
    qm_expert,
    qft_expert,
    math_expert,
    lqg_expert,
    bh_expert,
    wild_theorist,
    teacher,
    equation_verifier,
    physical_meaning,
    devil_advocate,
    literature_reviewer,
    orchestrator,
    latex_formatter,
    guide,
    conjecturer,
)
from agents import dynamic_expert
from agents import session_planner
from agents.context_limits import truncate_tail
from research_instructions import (
    instructions_summary,
    load_instructions_file,
    merge_arxiv_search_query,
    sanitize_session_name,
)
from topic_project_writer import slugify_papers_subdir, write_topic_project_file
from pipeline_checkpoint import (
    SCHEMA_VERSION,
    canonical_fingerprint_inputs,
    delete_state,
    fingerprint_hex,
    pipeline_fully_done,
    load_state,
    save_state,
)

TOPIC = "universal-pipeline"

# Pacing between Anthropic calls — conservative defaults to reduce org-wide 429s
# (many agents per round × orchestrator × LaTeX = bursty usage).
SLEEP_AFTER_AGENT_SEC = 8.0
SLEEP_AFTER_ORCHESTRATE_SEC = 6.0
SLEEP_AFTER_CHECKPOINT_SEC = 5.0
SLEEP_BEFORE_EXPERT_SESSION_SEC = 4.0

BASE_AGENT_REGISTRY = {
    "gr":       ("GR Expert",            gr_expert.consult),
    "qm":       ("QM Expert",            qm_expert.consult),
    "qft":      ("QFT Expert",           qft_expert.consult),
    "math":     ("Math Expert",          math_expert.consult),
    "lqg":      ("LQG Expert",           lqg_expert.consult),
    "bh":       ("Black Hole Expert",    bh_expert.consult),
    "wild":     ("Wild Theorist",        wild_theorist.propose),
    "teacher":  ("Teacher",              teacher.teach),
    "verifier": ("Equation Verifier",    equation_verifier.verify),
    "meaning":  ("Physical Meaning",     physical_meaning.interrogate),
    "devil":    ("Devil's Advocate",     devil_advocate.critique),
    "lit":      ("Literature Reviewer",  literature_reviewer.review),
}


def _session_path(session_id: str) -> Path:
    return Path(SESSIONS_DIR) / f"session_{session_id}.json"


def _allocate_session_id(base_slug: str) -> str:
    """Unique directory name under output/ and sessions/; base_slug is non-empty sanitized."""
    out = Path(OUTPUT_DIR)
    sdir = Path(SESSIONS_DIR)
    candidate = base_slug
    n = 1
    while (out / candidate).exists() or (sdir / f"session_{candidate}.json").exists():
        n += 1
        candidate = f"{base_slug}_{n}"
    return candidate


def _supplemental_topic_from_plan(plan: dict) -> str:
    """Short topic string for INSPIRE / S2 single-topic sweeps in main.py."""
    title = (plan.get("session_title") or "").strip()
    if len(title) >= 8:
        return title[:280]
    q = (plan.get("refined_research_question") or "").strip()
    return q[:280] if q else "quantum gravity"


def _pacing_sleep(seconds: float, after_what: str) -> None:
    """Proactive delay between Anthropic calls; explain why we pause."""
    print(
        f"  Pausing {seconds:.0f}s after {after_what} — spacing API calls to reduce Anthropic rate-limit risk.",
        flush=True,
    )
    time.sleep(seconds)


def save_session(session_data: dict) -> Path:
    os.makedirs(SESSIONS_DIR, exist_ok=True)
    path = _session_path(session_data["session_id"])
    path.write_text(json.dumps(session_data, indent=2, default=str), encoding="utf-8")
    return path


def build_merged_registry(plan: dict) -> dict:
    """Built-in experts plus dynamically defined specialists."""
    reg = dict(BASE_AGENT_REGISTRY)
    for spec in plan["dynamic_agent_specs"]:
        cid = spec["id"]
        fn = dynamic_expert.make_consult(spec["system_prompt"])
        reg[cid] = (spec["display_name"], fn)
    return reg


def _save_round_checkpoint(session_data: dict, round_data: dict, produce_latex: bool) -> None:
    save_session(session_data)
    if not produce_latex:
        return
    print(f"  Writing checkpoint LaTeX for round {round_data['round']}...")
    try:
        result = latex_formatter.format_checkpoint(
            synthesis=round_data["synthesis"],
            round_num=round_data["round"],
            session_id=session_data["session_id"],
            agent_responses=round_data["responses"],
        )
        round_data["latex"] = result
        save_session(session_data)
    except Exception as e:
        print(f"  LaTeX checkpoint failed: {e}")


def run_pipeline_session(
    question: str,
    title: str,
    agent_registry: dict,
    round_groups: list,
    planning: dict,
    produce_latex: bool,
    verbose: bool,
    resume_session_data: dict | None,
    start_round_one_based: int,
    on_pipeline_event: Callable[[str, dict], None] | None,
    explicit_session_id: str | None,
) -> dict:
    session_mode = planning.get("session_mode", "researcher")
    total_rounds = len(round_groups)

    if resume_session_data is None:
        if explicit_session_id is not None and explicit_session_id.strip():
            session_id = explicit_session_id.strip()
        else:
            session_id = uuid.uuid4().hex[:8]
        session_start = datetime.now()
        all_rounds: list = []
        session_data = {
            "session_id":      session_id,
            "timestamp":       session_start.isoformat(),
            "topic":           TOPIC,
            "question":        question,
            "title":             title,
            "session_mode":    session_mode,
            "planning":          planning,
            "rounds":            all_rounds,
            "final_synthesis":   "",
        }
        if on_pipeline_event:
            on_pipeline_event(
                "session_started",
                {
                    "session_data": copy.deepcopy(session_data),
                    "total_rounds": total_rounds,
                },
            )
    else:
        session_data = copy.deepcopy(resume_session_data)
        session_id = session_data["session_id"]
        all_rounds = session_data["rounds"]

    current_context = ""
    if all_rounds:
        joined_ctx = "\n\n".join(
            f"Round {r['round']} synthesis:\n{r['synthesis']}" for r in all_rounds
        )
        current_context = truncate_tail(
            joined_ctx,
            MAX_EXPERT_CONTEXT_CHARS,
            "Prior round syntheses (expert context)",
        )

    print(f"\n{'='*70}")
    print(f"  UNIVERSAL PHYSICIST  |  Session {session_id}  |  mode: {session_mode}")
    print(f"{'='*70}")
    print(f"\nTitle: {title}\n")
    print(f"Question:\n{question}\n")

    if start_round_one_based > total_rounds:
        print("  (No remaining rounds to run.)\n")

    for round_num in range(start_round_one_based, total_rounds + 1):
        agent_keys = round_groups[round_num - 1]
        print(f"\n{'-'*70}")
        print(f"  ROUND {round_num}  (session {session_id})")
        print(f"{'-'*70}\n")

        # Conjecturer: generate a stepping-stone sub-problem (researcher mode only)
        conjecturer_subproblem = ""
        if session_mode == "researcher":
            print(f"  [{round_num}] Conjecturer generating sub-problem...")
            try:
                conjecturer_subproblem = conjecturer.generate_subproblem(
                    question, current_context, round_num
                )
                if verbose:
                    print(f"\n  [CONJECTURER SUB-PROBLEM]\n  {'-'*40}")
                    for line in conjecturer_subproblem.split("\n"):
                        print(f"  {line}")
                    print()
                else:
                    preview = conjecturer_subproblem.split("\n")[0][:100]
                    print(f"    Sub-problem: {preview}")
            except Exception as e:
                print(f"  Conjecturer error (non-fatal): {e}")
            _pacing_sleep(SLEEP_AFTER_AGENT_SEC, "Conjecturer call")

        # Build per-round expert context augmented with the sub-problem
        round_context = current_context
        if conjecturer_subproblem:
            round_context = (
                (current_context + "\n\n" if current_context else "")
                + "[STEPPING-STONE SUB-PROBLEM FOR THIS ROUND — direct your response toward this]\n"
                + conjecturer_subproblem
            )

        agent_responses = {}
        for agent_key in agent_keys:
            if agent_key not in agent_registry:
                print(f"  Unknown agent key '{agent_key}', skipping.")
                continue
            name, fn = agent_registry[agent_key]
            print(f"  [{round_num}] Consulting {name}...")
            try:
                response = fn(question, context=round_context)
                agent_responses[name] = response
                if verbose:
                    print(f"\n  [{name}]\n  {'-'*40}")
                    preview = response[:500] + ("..." if len(response) > 500 else "")
                    for line in preview.split("\n"):
                        print(f"  {line}")
                    print()
            except Exception as e:
                print(f"  ERROR from {name}: {e}")
                agent_responses[name] = f"[Error: {e}]"
            _pacing_sleep(SLEEP_AFTER_AGENT_SEC, "this agent call")

        # Guide: evaluate expert responses before synthesis (researcher mode only)
        guide_report = ""
        if session_mode == "researcher" and agent_responses:
            print(f"  [{round_num}] Guide evaluating expert contributions...")
            try:
                guide_report = guide.evaluate(
                    question, agent_responses, current_context, round_num
                )
                if verbose:
                    print(f"\n  [GUIDE EVALUATION]\n  {'-'*40}")
                    for line in guide_report.split("\n"):
                        print(f"  {line}")
                    print()
                else:
                    print(f"    Guide report: {len(guide_report)} chars")
            except Exception as e:
                print(f"  Guide error (non-fatal): {e}")
            _pacing_sleep(SLEEP_AFTER_AGENT_SEC, "Guide evaluation")

        print(f"  Synthesizing round {round_num}...")
        synthesis = orchestrator.orchestrate(
            question, agent_responses, round_num, session_mode, guide_report=guide_report
        )
        _pacing_sleep(SLEEP_AFTER_ORCHESTRATE_SEC, "round orchestration")

        round_data = {
            "round":                  round_num,
            "agents":                 list(agent_responses.keys()),
            "responses":              agent_responses,
            "synthesis":              synthesis,
            "conjecturer_subproblem": conjecturer_subproblem,
            "guide_report":           guide_report,
        }
        all_rounds.append(round_data)
        session_data["rounds"] = all_rounds

        if verbose:
            print(f"\n  [SYNTHESIS — Round {round_num}]\n  {'='*40}")
            preview = synthesis[:800] + ("..." if len(synthesis) > 800 else "")
            for line in preview.split("\n"):
                print(f"  {line}")
            print()

        _save_round_checkpoint(session_data, round_data, produce_latex)
        print(f"  Checkpoint saved (round {round_num}).")
        _pacing_sleep(SLEEP_AFTER_CHECKPOINT_SEC, "checkpoint / LaTeX")

        joined = "\n\n".join(
            f"Round {r['round']} synthesis:\n{r['synthesis']}" for r in all_rounds
        )
        current_context = truncate_tail(
            joined,
            MAX_EXPERT_CONTEXT_CHARS,
            "Prior round syntheses (expert context)",
        )

        if on_pipeline_event:
            on_pipeline_event(
                "round_done",
                {
                    "session_data": copy.deepcopy(session_data),
                    "round": round_num,
                    "total_rounds": total_rounds,
                },
            )

    print(f"\n{'='*70}")
    print("  FINAL SYNTHESIS")
    print(f"{'='*70}\n")
    final = orchestrator.final_synthesis(question, all_rounds, title, session_mode)
    session_data["final_synthesis"] = final

    if verbose:
        print(final)

    if produce_latex:
        print("\n  Writing final paper LaTeX...")
        try:
            result = latex_formatter.format_final(final, title, session_id, all_rounds)
            session_data["final_latex"] = result
        except Exception as e:
            print(f"  Final LaTeX failed: {e}")

    save_session(session_data)

    if on_pipeline_event:
        on_pipeline_event(
            "session_complete",
            {"session_data": copy.deepcopy(session_data)},
        )

    print(f"\n{'='*70}")
    print(f"  DONE  |  Session {session_id}")
    print(f"  Output: {Path(OUTPUT_DIR) / session_id}")
    print(f"  Session JSON: {_session_path(session_id)}")
    print(f"{'='*70}\n")

    return session_data


def _prompt_yes_no(message: str) -> bool:
    while True:
        r = input(f"{message} [yes/no]: ").strip().lower()
        if r in ("y", "yes"):
            return True
        if r in ("n", "no"):
            return False
        print("  Please answer yes or no.")


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Universal Physicist — phrase → plan → papers → expert session",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    parser.add_argument(
        "--phrase",
        "-p",
        type=str,
        help="Short description of what you want to explore",
    )
    parser.add_argument(
        "--use-instructions",
        action="store_true",
        help="Load structured instructions from JSON (query, keywords, authors) instead of --phrase",
    )
    parser.add_argument(
        "--instructions",
        type=str,
        default=None,
        help="Path to instructions JSON (default: instructions.json next to main.py)",
    )
    parser.add_argument(
        "-i",
        "--interactive",
        action="store_true",
        help="Prompt for a phrase interactively",
    )
    parser.add_argument(
        "--rounds",
        "-r",
        type=int,
        default=None,
        help="Max number of discussion rounds (default: use full plan)",
    )
    parser.add_argument("--no-latex", action="store_true")
    parser.add_argument("--quiet", action="store_true")
    parser.add_argument(
        "--skip-papers",
        action="store_true",
        help="Skip arXiv search/download",
    )
    parser.add_argument(
        "--skip-preprocess",
        action="store_true",
        help="Skip paper_tools.preprocess_papers (still requires existing index.json if you need context)",
    )
    parser.add_argument(
        "--plan-only",
        action="store_true",
        help="Only run the planner and print JSON; no papers or session",
    )
    parser.add_argument(
        "--max-papers",
        type=int,
        default=None,
        help=f"Override planner max_papers for arXiv download (clamped to {MIN_ARXIV_PAPERS}–{MAX_ARXIV_PAPERS}; raise MAX_ARXIV_PAPERS in config.py for a higher ceiling)",
    )
    parser.add_argument(
        "--pdf",
        action="store_true",
        help="Download arXiv PDFs for this search (overrides config papers.arxiv_pdf)",
    )
    parser.add_argument(
        "--no-pdf",
        action="store_true",
        help="Do not download arXiv PDFs (overrides config papers.arxiv_pdf)",
    )
    parser.add_argument(
        "--no-topic-project",
        action="store_true",
        help="Do not write written_projects/<slug>_project.py with the frozen plan (default: write after planning)",
    )
    parser.add_argument(
        "--mode",
        type=str,
        choices=("researcher", "teacher"),
        default=None,
        help=(
            "Session mode: researcher (default) explores new ideas and may use the wild theorist; "
            "teacher is expository only (no wild, uses the teacher agent). "
            "Overrides the optional \"mode\" field in instructions JSON when set."
        ),
    )
    parser.add_argument(
        "--resume",
        action="store_true",
        help="Continue from pipeline_state checkpoint for this prompt (same phrase/mode/skip flags as stored).",
    )
    parser.add_argument(
        "--force-fresh",
        action="store_true",
        help="Delete checkpoint for this prompt and run the full pipeline from the planner.",
    )
    parser.add_argument(
        "--session-name",
        type=str,
        default=None,
        help=(
            "Human-readable name for output/<name>/ and sessions/session_<name>.json (slugified). "
            "Phrase mode only; with --use-instructions use \"session_name\" in the JSON file."
        ),
    )
    args = parser.parse_args()

    if args.pdf and args.no_pdf:
        parser.error("Use either --pdf or --no-pdf, not both.")

    if args.use_instructions and args.phrase:
        parser.error("Use either --phrase or --use-instructions, not both.")
    if args.use_instructions and args.interactive:
        parser.error("--interactive applies to --phrase mode; do not combine with --use-instructions.")
    if args.resume and args.plan_only:
        parser.error("Cannot combine --resume with --plan-only.")
    if args.resume and args.force_fresh:
        parser.error("Cannot combine --resume with --force-fresh.")
    if args.use_instructions and args.session_name:
        parser.error("Use \"session_name\" in instructions.json with --use-instructions, not --session-name.")

    root_dir = Path(__file__).resolve().parent
    instructions_path = (
        Path(args.instructions)
        if args.instructions is not None
        else root_dir / "instructions.json"
    )

    phrase_for_project: str
    instr: dict | None = None

    if args.use_instructions:
        try:
            instr = load_instructions_file(instructions_path)
        except (FileNotFoundError, json.JSONDecodeError, ValueError) as e:
            print(f"ERROR: Could not load instructions ({e}).")
            sys.exit(1)
        phrase_for_project = instructions_summary(instr)
    else:
        phrase = args.phrase
        if args.interactive or not phrase:
            print("\nDescribe what you want in one short phrase (Enter to abort):\n")
            phrase = input("> ").strip()
            if not phrase:
                print("Aborted.")
                sys.exit(0)
        phrase_for_project = phrase

    if args.mode is not None:
        resolved_session_mode = args.mode
    elif instr is not None:
        resolved_session_mode = instr["mode"]
    else:
        resolved_session_mode = "researcher"

    if args.plan_only:
        print("\n  [1/4] Planning session (prompt, agents, arXiv query)...\n")
        try:
            if instr is not None:
                plan = session_planner.plan_session_from_instructions(
                    instr["query"],
                    instr["keywords"],
                    instr["authors"],
                    instr["exclude_keywords"],
                    instr["exclude_authors"],
                    resolved_session_mode,
                )
                plan["arxiv_search_query"] = merge_arxiv_search_query(
                    plan["arxiv_search_query"],
                    instr["keywords"],
                    instr["authors"],
                    instr["exclude_keywords"],
                    instr["exclude_authors"],
                )
            else:
                plan = session_planner.plan_session(phrase_for_project, resolved_session_mode)
        except (json.JSONDecodeError, ValueError) as e:
            print(f"ERROR: Session planner failed ({e}). Try a slightly different phrase or run again.")
            sys.exit(1)
        plan["session_mode"] = resolved_session_mode
        if args.max_papers is not None:
            plan["max_papers"] = max(MIN_ARXIV_PAPERS, min(MAX_ARXIV_PAPERS, args.max_papers))
        papers_slug = slugify_papers_subdir(plan["session_title"])
        set_papers_project(papers_slug)
        print(f"  Papers library: papers/{papers_slug}/")
        print(f"  Session mode: {resolved_session_mode}")
        print(f"  Title: {plan['session_title']}")
        print("\n" + json.dumps(plan, indent=2, ensure_ascii=False))
        sys.exit(0)

    if instr is not None:
        session_name_raw = instr.get("session_name") or ""
    elif args.session_name:
        session_name_raw = args.session_name
    else:
        session_name_raw = ""

    fp_inputs = canonical_fingerprint_inputs(
        resolved_session_mode,
        phrase_for_project,
        args.use_instructions,
        args.skip_papers,
        args.skip_preprocess,
        args.max_papers,
        args.rounds,
        args.no_latex,
        args.pdf,
        args.no_pdf,
        session_name_raw,
    )
    fp_hex = fingerprint_hex(fp_inputs)
    state = load_state(root_dir, fp_hex)

    if args.force_fresh:
        delete_state(root_dir, fp_hex)
        state = None

    out_root = Path(OUTPUT_DIR)
    resume_became_fresh = False

    if args.resume and state is not None and pipeline_fully_done(state, out_root):
        print(
            "This pipeline run already finished for this prompt (checkpoint complete; "
            "final paper exists when LaTeX is enabled)."
        )
        if _prompt_yes_no("Delete the checkpoint and start a fresh pipeline from the planner now?"):
            delete_state(root_dir, fp_hex)
            state = None
            resume_became_fresh = True
        else:
            sys.exit(0)

    if args.resume and state is None and not resume_became_fresh:
        print(
            "ERROR: No checkpoint for this prompt. The fingerprint must match a previous run "
            f"(pipeline_state/{fp_hex[:16]}/). Run once without --resume, or check phrase/mode/skip flags."
        )
        sys.exit(1)

    if not args.resume:
        if state and pipeline_fully_done(state, out_root):
            print(
                "A completed run already exists for this exact prompt (same mode, phrase/instructions, and flags).\n"
                "To run again from scratch, delete the checkpoint or pass --force-fresh."
            )
            if _prompt_yes_no("Delete checkpoint and start a fresh pipeline from the planner?"):
                delete_state(root_dir, fp_hex)
                state = None
            else:
                sys.exit(0)
        elif state and not pipeline_fully_done(state, out_root):
            print(
                "ERROR: An incomplete checkpoint exists for this prompt.\n"
                "Continue with:  py -3 main.py ... --resume\n"
                "Or discard it with:  --force-fresh"
            )
            sys.exit(1)

    load_from_checkpoint = bool(args.resume and state is not None)

    if not load_from_checkpoint:
        print("\n  [1/4] Planning session (prompt, agents, arXiv query)...\n")
        try:
            if instr is not None:
                plan = session_planner.plan_session_from_instructions(
                    instr["query"],
                    instr["keywords"],
                    instr["authors"],
                    instr["exclude_keywords"],
                    instr["exclude_authors"],
                    resolved_session_mode,
                )
                plan["arxiv_search_query"] = merge_arxiv_search_query(
                    plan["arxiv_search_query"],
                    instr["keywords"],
                    instr["authors"],
                    instr["exclude_keywords"],
                    instr["exclude_authors"],
                )
            else:
                plan = session_planner.plan_session(phrase_for_project, resolved_session_mode)
        except (json.JSONDecodeError, ValueError) as e:
            print(f"ERROR: Session planner failed ({e}). Try a slightly different phrase or run again.")
            sys.exit(1)

        plan["session_mode"] = resolved_session_mode

        if args.max_papers is not None:
            plan["max_papers"] = max(MIN_ARXIV_PAPERS, min(MAX_ARXIV_PAPERS, args.max_papers))

        round_groups_effective = plan["round_agent_groups"]
        if args.rounds is not None:
            round_groups_effective = round_groups_effective[: max(1, args.rounds)]

        papers_slug = slugify_papers_subdir(plan["session_title"])
        set_papers_project(papers_slug)

        alloc_session_id = None
        slug = ""
        if instr is not None:
            slug = sanitize_session_name(instr.get("session_name") or "")
        elif args.session_name:
            slug = sanitize_session_name(args.session_name)
        if slug:
            alloc_session_id = _allocate_session_id(slug)

        save_state(
            root_dir,
            fp_hex,
            {
                "schema_version": SCHEMA_VERSION,
                "fingerprint": fp_hex,
                "fingerprint_inputs": fp_inputs,
                "step": "planned",
                "plan": plan,
                "round_groups_effective": round_groups_effective,
                "phrase_for_project": phrase_for_project,
                "papers_slug": papers_slug,
                "no_latex": args.no_latex,
                "alloc_session_id": alloc_session_id,
            },
        )
    else:
        plan = state["plan"]
        resolved_session_mode = plan["session_mode"]
        round_groups_effective = state["round_groups_effective"]
        papers_slug = state["papers_slug"]
        alloc_session_id = state.get("alloc_session_id")
        set_papers_project(papers_slug)
        print(
            f"\n  [resume] Loaded checkpoint  step={state['step']}  "
            f"library papers/{papers_slug}/\n"
        )

    print(f"  Papers library: papers/{papers_slug}/")
    if alloc_session_id:
        print(f"  Session folder: {Path(OUTPUT_DIR) / alloc_session_id}/")

    if not load_from_checkpoint and not args.no_topic_project:
        try:
            gen_path = write_topic_project_file(plan, phrase_for_project, root_dir)
            rel = gen_path.relative_to(root_dir)
            print(f"\n  Wrote session replay script: {rel.as_posix()}")
        except OSError as e:
            print(f"\n  WARNING: Could not write topic project file: {e}")

    print(f"  Session mode: {resolved_session_mode}")
    print(f"  Title: {plan['session_title']}")
    print(f"  Refined question ({len(plan['refined_research_question'])} chars) — preview:\n")
    print(f"    {plan['refined_research_question'][:400]}...")
    print("\n  Built-in + dynamic agents:")
    for spec in plan["dynamic_agent_specs"]:
        print(f"    + dynamic: {spec['id']} — {spec['display_name']}")
    print("\n  Rounds (agent keys per round):")
    for i, grp in enumerate(round_groups_effective, 1):
        print(f"    Round {i}: {', '.join(grp)}")
    print(f"\n  arXiv: {plan['arxiv_search_query'][:120]}...")
    print(f"  Categories: {plan['arxiv_categories']}  |  max papers: {plan['max_papers']}")

    step = state["step"] if load_from_checkpoint else "planned"

    if step == "planned":
        if not args.skip_papers:
            print(f"\n  [2/4] Searching arXiv and saving abstracts...\n  → {get_papers_dir()}\n")
            from paper_tools.arxiv_downloader import search_and_download

            if args.pdf:
                download_pdfs = True
            elif args.no_pdf:
                download_pdfs = False
            else:
                download_pdfs = PAPERS_ARXIV_PDF

            search_and_download(
                query=plan["arxiv_search_query"],
                categories=plan["arxiv_categories"],
                max_results=plan["max_papers"],
                download_pdfs=download_pdfs,
            )

            topic_extra = _supplemental_topic_from_plan(plan)
            if PAPERS_INSPIRE:
                print("\n  [2b/4] INSPIRE-HEP supplement (session topic, top-cited)...\n")
                try:
                    from paper_tools.inspire_downloader import fetch_and_download_topic as inspire_fetch

                    inspire_fetch(topic_extra, 40, 15, download_pdfs)
                except Exception as e:
                    print(f"  WARNING: INSPIRE supplement failed ({e}). Continuing.\n")
            else:
                print("\n  [2b/4] Skipped INSPIRE (papers.inspire is false in config).\n")

            if PAPERS_SEMANTIC_SCHOLAR:
                print("\n  [2c/4] Semantic Scholar supplement (session topic)...\n")
                try:
                    from paper_tools.semantic_scholar import fetch_and_download_topic as s2_fetch

                    s2_key = os.environ.get("SEMANTIC_SCHOLAR_API_KEY")
                    s2_fetch(topic_extra, 40, 15, download_pdfs, s2_key)
                except Exception as e:
                    print(f"  WARNING: Semantic Scholar supplement failed ({e}). Continuing.\n")
            else:
                print("\n  [2c/4] Skipped Semantic Scholar (papers.semantic_scholar is false in config).\n")
        else:
            print("\n  [2/4] Skipped (--skip-papers).\n")

        cur = load_state(root_dir, fp_hex) or {}
        cur.update(
            {
                "schema_version": SCHEMA_VERSION,
                "fingerprint": fp_hex,
                "fingerprint_inputs": fp_inputs,
                "step": "after_papers",
                "plan": plan,
                "round_groups_effective": round_groups_effective,
                "phrase_for_project": phrase_for_project,
                "papers_slug": papers_slug,
                "no_latex": args.no_latex,
                "alloc_session_id": alloc_session_id,
            }
        )
        save_state(root_dir, fp_hex, cur)
        step = "after_papers"

    if step == "after_papers":
        if not args.skip_preprocess:
            print("\n  [3/4] Preprocessing paper library...\n")
            from paper_tools.preprocess_papers import process_all

            process_all(force=False)
        else:
            print("\n  [3/4] Skipped (--skip-preprocess).\n")

        cur = load_state(root_dir, fp_hex) or {}
        cur.update(
            {
                "schema_version": SCHEMA_VERSION,
                "fingerprint": fp_hex,
                "fingerprint_inputs": fp_inputs,
                "step": "after_preprocess",
                "plan": plan,
                "round_groups_effective": round_groups_effective,
                "phrase_for_project": phrase_for_project,
                "papers_slug": papers_slug,
                "no_latex": args.no_latex,
                "alloc_session_id": alloc_session_id,
            }
        )
        save_state(root_dir, fp_hex, cur)
        step = "after_preprocess"

    if step in ("after_preprocess", "session_in_progress"):
        merged_registry = build_merged_registry(plan)

        resume_session_data = None
        start_round_one = 1
        if step == "session_in_progress":
            resume_session_data = state["session_data"]
            start_round_one = int(state.get("completed_rounds", 0)) + 1
            print(
                f"\n  [4/4] Resuming expert discussion from round {start_round_one}...\n"
            )
        else:
            print("\n  [4/4] Expert discussion...\n")

        def on_pipeline_event(event: str, payload: dict) -> None:
            cur = load_state(root_dir, fp_hex) or {}
            cur.update(
                {
                    "schema_version": SCHEMA_VERSION,
                    "fingerprint": fp_hex,
                    "fingerprint_inputs": fp_inputs,
                    "plan": plan,
                    "round_groups_effective": round_groups_effective,
                    "phrase_for_project": phrase_for_project,
                    "papers_slug": papers_slug,
                    "no_latex": args.no_latex,
                    "alloc_session_id": alloc_session_id,
                }
            )
            sd = payload["session_data"]
            sid = sd["session_id"]
            n_done = len(sd["rounds"])
            if event == "session_started":
                cur["step"] = "session_in_progress"
                cur["session_id"] = sid
                cur["session_data"] = sd
                cur["completed_rounds"] = n_done
            elif event == "round_done":
                cur["step"] = "session_in_progress"
                cur["session_id"] = sid
                cur["session_data"] = sd
                cur["completed_rounds"] = n_done
            elif event == "session_complete":
                cur["step"] = "completed"
                cur["session_id"] = sid
                cur["session_data"] = sd
                cur["completed_rounds"] = n_done
            save_state(root_dir, fp_hex, cur)

        _pacing_sleep(SLEEP_BEFORE_EXPERT_SESSION_SEC, "preprocessing — before expert discussion")
        run_pipeline_session(
            question=plan["refined_research_question"],
            title=plan["session_title"],
            agent_registry=merged_registry,
            round_groups=round_groups_effective,
            planning=plan,
            produce_latex=not args.no_latex,
            verbose=not args.quiet,
            resume_session_data=resume_session_data,
            start_round_one_based=start_round_one,
            on_pipeline_event=on_pipeline_event,
            explicit_session_id=alloc_session_id,
        )


if __name__ == "__main__":
    main()
