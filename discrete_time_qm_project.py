"""
Discrete-Time Quantum Mechanics Think Tank — focused agent session.

No literature retrieval. Agents work from first principles, focusing on:
  - Discrete-time Schrodinger/Dirac equations (step size a)
  - Unitarity under time discretization
  - Special-relativistic invariance (Lorentz covariance)
  - Dispersion relations and their continuum limit
  - Observable predictions and experimental tests

Usage:
    py -3 discrete_time_qm_project.py                         # run with default question
    py -3 discrete_time_qm_project.py --rounds 5              # more rounds
    py -3 discrete_time_qm_project.py --no-latex              # skip LaTeX output
    py -3 discrete_time_qm_project.py --resume SESSION_ID     # resume a previous session
    py -3 discrete_time_qm_project.py --input "Try finite-difference Dirac on a null lattice"
    py -3 discrete_time_qm_project.py --list-sessions
"""

import os
import sys
import io
import json
import argparse
import uuid
from datetime import datetime
from pathlib import Path

# Force UTF-8 output on Windows (avoids cp1252 crashes on checkmarks, arrows, etc.)
if sys.stdout.encoding.lower() != "utf-8":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8", errors="replace")

from config import ANTHROPIC_API_KEY, SESSIONS_DIR, OUTPUT_DIR

if not ANTHROPIC_API_KEY:
    print("ERROR: Set ANTHROPIC_API_KEY in the environment or .claude/settings.json (env.ANTHROPIC_API_KEY).")
    sys.exit(1)
from agents import qm_expert, qft_expert, math_expert
from agents import wild_theorist, equation_verifier, physical_meaning, devil_advocate
from agents import orchestrator, latex_formatter

TOPIC = "discrete-time-qm"

DEFAULT_QUESTION = (
    "We want to construct a discrete-time quantum mechanics that is internally consistent "
    "and compatible with special relativity. The continuum Schrodinger equation "
    "i hbar d/dt psi = H psi suggests a natural discretization "
    "i hbar (psi(t+a) - psi(t)) / a = H psi(t), but this is not unitary. "
    "Explore the space of discrete-time evolution equations: "
    "(1) Which schemes preserve exact unitarity? "
    "(2) Which are Lorentz covariant — i.e. treat space and time on equal footing "
    "in the discrete setting, respecting SR time dilation and length contraction? "
    "(3) What dispersion relations do they imply, and do they reduce correctly to "
    "E = hbar omega and E^2 = p^2 c^2 + m^2 c^4 in the continuum limit? "
    "(4) What new physics (deviations from standard QM/QFT) do they predict at "
    "time step a ~ Planck time, and how could these be tested?"
)

DEFAULT_TITLE = "Discrete-Time Quantum Mechanics: Unitarity, Lorentz Invariance, and Observable Predictions"

# Agent sequence: no GR (no gravity), no LQG, no BH, no literature
# Round 1: establish the mathematical landscape of discrete-time schemes
# Round 2: verify equations, extract physical meaning
# Round 3: bold proposals + devil's critique
# Round 4: final sharpening — QM expert + verifier
DEFAULT_ROUND_AGENTS = [
    ["qm", "qft", "math"],          # Round 1: formalism, SR, mathematical structures
    ["verifier", "meaning"],         # Round 2: unitarity proofs, dispersion, interpretation
    ["wild", "devil"],               # Round 3: novel discretization ideas + sharp critique
    ["qm", "verifier", "math"],     # Round 4: synthesis, consistency, predictions
]

AGENT_REGISTRY = {
    "qm":       ("QM Expert",           qm_expert.consult),
    "qft":      ("QFT Expert",          qft_expert.consult),
    "math":     ("Math Expert",         math_expert.consult),
    "wild":     ("Wild Theorist",       wild_theorist.propose),
    "verifier": ("Equation Verifier",   equation_verifier.verify),
    "meaning":  ("Physical Meaning",    physical_meaning.interrogate),
    "devil":    ("Devil's Advocate",    devil_advocate.critique),
}


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


def list_sessions() -> None:
    os.makedirs(SESSIONS_DIR, exist_ok=True)
    sessions = []
    for p in sorted(Path(SESSIONS_DIR).glob("session_*.json")):
        try:
            data = json.loads(p.read_text(encoding="utf-8"))
            sessions.append(data)
        except Exception:
            pass
    if not sessions:
        print("No sessions found.")
        return
    print(f"\n{'ID':10}  {'Date':19}  {'Rounds':6}  Question")
    print("-" * 80)
    for s in sessions:
        print(f"{s['session_id']:10}  {s['timestamp'][:19]:19}  "
              f"{len(s.get('rounds', [])):6}  {s.get('question','')[:60]}")
    print()


# ─── Round checkpoint ─────────────────────────────────────────────────────────

def _save_checkpoint(session_data: dict, round_data: dict, produce_latex: bool) -> None:
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


# ─── Core runner ──────────────────────────────────────────────────────────────

def run_session(
    question: str = DEFAULT_QUESTION,
    n_rounds: int = 4,
    selected_agents=None,
    title: str = DEFAULT_TITLE,
    produce_latex: bool = True,
    verbose: bool = True,
    resume_data: dict = None,
    human_input: str = "",
) -> dict:

    if resume_data:
        session_id    = resume_data["session_id"]
        session_start = datetime.fromisoformat(resume_data["timestamp"])
        all_rounds    = resume_data.get("rounds", [])
        title         = resume_data.get("title", title)
        question      = resume_data.get("question", question)
        start_round   = len(all_rounds) + 1
        current_context = "\n\n".join(
            f"Round {r['round']} synthesis:\n{r['synthesis']}" for r in all_rounds
        )
        if human_input:
            current_context += f"\n\nHuman input / new direction:\n{human_input}"
            print(f"  Injecting human input: {human_input[:120]}")
    else:
        session_id      = uuid.uuid4().hex[:8]
        session_start   = datetime.now()
        all_rounds      = []
        start_round     = 1
        current_context = ""

    session_data = {
        "session_id":      session_id,
        "timestamp":       session_start.isoformat(),
        "topic":           TOPIC,
        "question":        question,
        "title":           title,
        "rounds":          all_rounds,
        "final_synthesis": resume_data.get("final_synthesis", "") if resume_data else "",
    }

    print(f"\n{'='*70}")
    action = "RESUMING" if resume_data else "STARTING"
    print(f"  DISCRETE-TIME QM THINK TANK  |  {action} Session {session_id}")
    print(f"{'='*70}")
    print(f"\nQuestion: {question[:200]}...")
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
            print(f"\n  [SYNTHESIS - Round {round_num}]\n  {'='*40}")
            preview = synthesis[:800] + ("..." if len(synthesis) > 800 else "")
            for line in preview.split("\n"):
                print(f"  {line}")
            print()

        _save_checkpoint(session_data, round_data, produce_latex)
        print(f"  Checkpoint saved (round {round_num}).")

        current_context = "\n\n".join(
            f"Round {r['round']} synthesis:\n{r['synthesis']}" for r in all_rounds
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
    print(f"  Output: {Path(OUTPUT_DIR) / session_id}")
    print(f"  Session JSON: {_session_path(session_id)}")
    print(f"{'='*70}\n")

    return session_data


# ─── CLI ──────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Discrete-Time QM Agent Think Tank")
    parser.add_argument("--question",  "-q", type=str, default=DEFAULT_QUESTION)
    parser.add_argument("--title",     "-t", type=str, default=DEFAULT_TITLE)
    parser.add_argument("--rounds",    "-r", type=int, default=4)
    parser.add_argument("--agents",    "-a", nargs="+", choices=sorted(AGENT_REGISTRY.keys()))
    parser.add_argument("--no-latex",  action="store_true")
    parser.add_argument("--quiet",     action="store_true")
    parser.add_argument("--resume",    metavar="SESSION_ID")
    parser.add_argument("--input",     metavar="TEXT",
                        help="Human input injected when resuming")
    parser.add_argument("--list-sessions", action="store_true")
    args = parser.parse_args()

    if args.list_sessions:
        list_sessions()
    elif args.resume:
        data = load_session(args.resume)
        run_session(
            question=data["question"],
            n_rounds=args.rounds,
            selected_agents=args.agents,
            title=data.get("title", DEFAULT_TITLE),
            produce_latex=not args.no_latex,
            verbose=not args.quiet,
            resume_data=data,
            human_input=args.input or "",
        )
    else:
        run_session(
            question=args.question,
            n_rounds=args.rounds,
            selected_agents=args.agents,
            title=args.title,
            produce_latex=not args.no_latex,
            verbose=not args.quiet,
        )
