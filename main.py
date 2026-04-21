"""
Quantum Gravity Agent Team — main entry point.

Usage:
    py -3 main.py                              # interactive mode
    py -3 main.py --question "..."             # one-shot
    py -3 main.py --rounds 6                   # more rounds
    py -3 main.py --resume SESSION_ID          # resume from last checkpoint
    py -3 main.py --resume SESSION_ID --input "New direction: consider p-adic fields"
    py -3 main.py --no-latex                   # skip LaTeX/PDF output
    py -3 main.py --agents gr qm wild          # custom agent set (all rounds)
    py -3 main.py --list-sessions              # show previous sessions
"""

import os
import sys
import io
import json
import argparse
import uuid
from datetime import datetime
from pathlib import Path

# Force UTF-8 output on Windows
if sys.stdout.encoding.lower() != "utf-8":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8", errors="replace")

from config import ANTHROPIC_API_KEY, MAX_ROUNDS, SESSIONS_DIR, OUTPUT_DIR

if not ANTHROPIC_API_KEY:
    print("ERROR: Set ANTHROPIC_API_KEY in the environment or .claude/settings.json (env.ANTHROPIC_API_KEY).")
    sys.exit(1)
from agents import gr_expert, qm_expert, qft_expert, math_expert
from agents import lqg_expert, bh_expert, wild_theorist
from agents import equation_verifier, physical_meaning, devil_advocate
from agents import literature_reviewer, deep_reader, orchestrator, latex_formatter

DEFAULT_QUESTION = (
    "We want to develop a plausible theory of quantum gravity. "
    "Start from the core tension: GR treats spacetime as a smooth manifold while QM requires "
    "a Hilbert space and operators. Propose a concrete framework to resolve this tension, "
    "give its key equations, and explain what new physics it predicts."
)

AGENT_REGISTRY = {
    "gr":       ("GR Expert",            gr_expert.consult),
    "qm":       ("QM Expert",            qm_expert.consult),
    "qft":      ("QFT Expert",           qft_expert.consult),
    "math":     ("Math Expert",          math_expert.consult),
    "lqg":      ("LQG Expert",           lqg_expert.consult),
    "bh":       ("Black Hole Expert",    bh_expert.consult),
    "wild":     ("Wild Theorist",        wild_theorist.propose),
    "verifier": ("Equation Verifier",    equation_verifier.verify),
    "meaning":  ("Physical Meaning",     physical_meaning.interrogate),
    "devil":    ("Devil's Advocate",     devil_advocate.critique),
    "lit":      ("Literature Reviewer",  literature_reviewer.review),
    "deepread": ("Deep Reader",          lambda q, context="": deep_reader.read_by_id(
                                             q.split("|")[0].strip(),
                                             q.split("|")[1].strip() if "|" in q else q,
                                             context=context)),
}

DEFAULT_ROUND_AGENTS = [
    ["gr", "qm", "qft"],               # Round 1: establish core physics constraints
    ["lqg", "bh", "math"],             # Round 2: specialist depth
    ["wild", "meaning", "devil"],       # Round 3: bold moves + interpretation + critique
    ["verifier", "lit"],               # Round 4: rigor check + literature grounding
]


# ─── Session persistence ──────────────────────────────────────────────────────

def _session_path(session_id: str) -> Path:
    return Path(SESSIONS_DIR) / f"session_{session_id}.json"


def save_session(session_data: dict) -> Path:
    os.makedirs(SESSIONS_DIR, exist_ok=True)
    path = _session_path(session_data["session_id"])
    path.write_text(json.dumps(session_data, indent=2, default=str), encoding="utf-8")
    return path


def load_session(session_id: str) -> dict:
    path = _session_path(session_id)
    if not path.exists():
        raise FileNotFoundError(f"No session found: {session_id}")
    return json.loads(path.read_text(encoding="utf-8"))


def list_sessions() -> list[dict]:
    os.makedirs(SESSIONS_DIR, exist_ok=True)
    sessions = []
    for p in sorted(Path(SESSIONS_DIR).glob("session_*.json")):
        try:
            data = json.loads(p.read_text(encoding="utf-8"))
            sessions.append({
                "id":        data["session_id"],
                "timestamp": data["timestamp"][:19],
                "rounds":    len(data.get("rounds", [])),
                "question":  data.get("question", "")[:70],
                "title":     data.get("title", ""),
            })
        except Exception:
            pass
    return sessions


def print_sessions() -> None:
    sessions = list_sessions()
    if not sessions:
        print("No sessions found.")
        return
    print(f"\n{'ID':10}  {'Date':19}  {'Rounds':6}  Question")
    print("-" * 80)
    for s in sessions:
        print(f"{s['id']:10}  {s['timestamp']:19}  {s['rounds']:6}  {s['question']}")
    print()


# ─── Round checkpoint ─────────────────────────────────────────────────────────

def _save_round_checkpoint(session_data: dict, round_data: dict, produce_latex: bool) -> None:
    """Persist round JSON + optionally write/compile LaTeX checkpoint."""
    # Always save the session JSON (incremental)
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
        save_session(session_data)  # update with latex paths
    except Exception as e:
        print(f"  LaTeX checkpoint failed: {e}")


# ─── Core session runner ──────────────────────────────────────────────────────

def run_session(
    question: str,
    n_rounds: int = MAX_ROUNDS,
    selected_agents=None,
    title: str = "Towards a Plausible Theory of Quantum Gravity",
    produce_latex: bool = True,
    verbose: bool = True,
    resume_data: dict = None,    # pass existing session to continue it
    human_input: str = "",       # injected into context when resuming
) -> dict:

    # ── Init or resume ───────────────────────────────────────────────────────
    if resume_data:
        session_id    = resume_data["session_id"]
        session_start = datetime.fromisoformat(resume_data["timestamp"])
        all_rounds    = resume_data.get("rounds", [])
        title         = resume_data.get("title", title)
        question      = resume_data.get("question", question)
        start_round   = len(all_rounds) + 1

        # Build context from all previous syntheses
        current_context = "\n\n".join(
            f"Round {r['round']} synthesis:\n{r['synthesis']}"
            for r in all_rounds
        )
        if human_input:
            current_context += f"\n\nHuman input / new direction:\n{human_input}"
            print(f"  Injecting human input: {human_input[:120]}")
    else:
        session_id    = uuid.uuid4().hex[:8]
        session_start = datetime.now()
        all_rounds    = []
        start_round   = 1
        current_context = ""

    session_data = {
        "session_id": session_id,
        "timestamp":  session_start.isoformat(),
        "question":   question,
        "title":      title,
        "rounds":     all_rounds,
        "final_synthesis": resume_data.get("final_synthesis", "") if resume_data else "",
    }

    print(f"\n{'='*70}")
    action = "RESUMING" if resume_data else "STARTING"
    print(f"  QUANTUM GRAVITY THINK TANK  |  {action} Session {session_id}")
    print(f"{'='*70}")
    print(f"\nQuestion: {question}")
    if resume_data:
        print(f"Continuing from round {start_round} (previous rounds: {start_round-1})")
    print()

    end_round = start_round + n_rounds - 1

    for round_num in range(start_round, end_round + 1):
        print(f"\n{'-'*70}")
        print(f"  ROUND {round_num}  (session {session_id})")
        print(f"{'-'*70}\n")

        if selected_agents:
            agents_this_round = selected_agents
        else:
            idx = (round_num - 1) % len(DEFAULT_ROUND_AGENTS)
            agents_this_round = DEFAULT_ROUND_AGENTS[idx]

        agent_responses = {}

        for agent_key in agents_this_round:
            if agent_key not in AGENT_REGISTRY:
                print(f"  Unknown agent: {agent_key}, skipping.")
                continue

            name, fn = AGENT_REGISTRY[agent_key]
            print(f"  [{round_num}] Consulting {name}...")

            try:
                response = fn(question, context=current_context)
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

        print(f"  Synthesizing round {round_num}...")
        synthesis = orchestrator.orchestrate(question, agent_responses, round_num)

        round_data = {
            "round":     round_num,
            "agents":    list(agent_responses.keys()),
            "responses": agent_responses,
            "synthesis": synthesis,
        }
        all_rounds.append(round_data)
        session_data["rounds"] = all_rounds

        if verbose:
            print(f"\n  [SYNTHESIS — Round {round_num}]\n  {'='*40}")
            preview = synthesis[:800] + ("..." if len(synthesis) > 800 else "")
            for line in preview.split("\n"):
                print(f"  {line}")
            print()

        # Checkpoint: save JSON + write/compile LaTeX for this round
        _save_round_checkpoint(session_data, round_data, produce_latex)
        print(f"  Checkpoint saved (round {round_num}).")

        current_context = "\n\n".join(
            f"Round {r['round']} synthesis:\n{r['synthesis']}"
            for r in all_rounds
        )

    # ── Final synthesis ──────────────────────────────────────────────────────
    print(f"\n{'='*70}")
    print(f"  FINAL SYNTHESIS")
    print(f"{'='*70}\n")
    final = orchestrator.final_synthesis(question, all_rounds, title)
    session_data["final_synthesis"] = final

    if verbose:
        print(final)

    if produce_latex:
        print(f"\n  Writing final paper LaTeX...")
        try:
            result = latex_formatter.format_final(final, title, session_id, all_rounds)
            session_data["final_latex"] = result
        except Exception as e:
            print(f"  Final LaTeX failed: {e}")

    save_session(session_data)

    print(f"\n{'='*70}")
    print(f"  DONE  |  Session {session_id}")
    out_dir = Path(OUTPUT_DIR) / session_id
    print(f"  Output: {out_dir}")
    print(f"  Session JSON: {_session_path(session_id)}")
    print(f"{'='*70}\n")

    return session_data


# ─── Interactive & CLI ────────────────────────────────────────────────────────

def interactive_mode() -> None:
    print("\nQuantum Gravity Think Tank")
    print("Type your research question (Enter for default):\n")
    q = input("> ").strip() or DEFAULT_QUESTION
    title = input("Paper title (Enter for default): ").strip() or "Towards a Plausible Theory of Quantum Gravity"
    rounds_str = input("Number of rounds this run [4]: ").strip()
    n_rounds = int(rounds_str) if rounds_str.isdigit() else 4
    run_session(q, n_rounds=n_rounds, title=title)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Quantum Gravity Agent Think Tank")
    parser.add_argument("--question",  "-q", type=str)
    parser.add_argument("--title",     "-t", type=str, default="Towards a Plausible Theory of Quantum Gravity")
    parser.add_argument("--rounds",    "-r", type=int, default=MAX_ROUNDS)
    parser.add_argument("--agents",    "-a", nargs="+", choices=sorted(AGENT_REGISTRY.keys()))
    parser.add_argument("--no-latex",  action="store_true")
    parser.add_argument("--quiet",     action="store_true")
    parser.add_argument("--interactive", "-i", action="store_true")
    parser.add_argument("--resume",    metavar="SESSION_ID",
                        help="Resume a previous session by its 8-char ID")
    parser.add_argument("--input",     metavar="TEXT",
                        help="Human input / new direction injected when resuming")
    parser.add_argument("--list-sessions", action="store_true",
                        help="List all previous sessions")
    args = parser.parse_args()

    if args.list_sessions:
        print_sessions()
    elif args.resume:
        data = load_session(args.resume)
        run_session(
            question=data["question"],
            n_rounds=args.rounds,
            selected_agents=args.agents,
            title=data.get("title", args.title),
            produce_latex=not args.no_latex,
            verbose=not args.quiet,
            resume_data=data,
            human_input=args.input or "",
        )
    elif args.interactive or not args.question:
        interactive_mode()
    else:
        run_session(
            question=args.question,
            n_rounds=args.rounds,
            selected_agents=args.agents,
            title=args.title,
            produce_latex=not args.no_latex,
            verbose=not args.quiet,
        )
