"""
Modified Gravity / Dark Matter Think Tank — focused agent session.

Goal: find a covariant modified gravity theory compatible at ALL scales:
  - Solar system (GR recovery, PPN constraints)
  - Galaxies (RAR, rotation curves, baryonic Tully-Fisher)
  - Galaxy clusters (Bullet Cluster, X-ray mass)
  - CMB (acoustic peaks, matter power spectrum)
  - Large-scale structure

No quantum framework. Classical field theory only.
Key references: Milgrom, Bekenstein, Skordis, Famaey, Bruneton & Esposito-Farese.

By default the session runs without downloading papers. Use --download-papers to fetch
the curated arXiv set and preprocess first.

Usage:
    py -3 modified_gravity_project.py
    py -3 modified_gravity_project.py --rounds 5
    py -3 modified_gravity_project.py --no-latex
    py -3 modified_gravity_project.py --resume SESSION_ID
    py -3 modified_gravity_project.py --download-papers
    py -3 modified_gravity_project.py --download-only
    py -3 modified_gravity_project.py --dry-run-papers
    py -3 modified_gravity_project.py --list-sessions
"""

import os
import sys
import io
import json
import time
import argparse
import uuid
from datetime import datetime
from pathlib import Path

# Pacing between Anthropic calls (back-to-back agent + orchestrator + LaTeX hits rate limits)
SLEEP_AFTER_AGENT_SEC = 8.0
SLEEP_AFTER_ORCHESTRATE_SEC = 5.0
SLEEP_AFTER_CHECKPOINT_SEC = 3.0
SLEEP_AFTER_ROUND_SEC = 4.0
SLEEP_BEFORE_FINAL_SYNTHESIS_SEC = 6.0

# Force UTF-8 output on Windows
if sys.stdout.encoding.lower() != "utf-8":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8", errors="replace")

from config import ANTHROPIC_API_KEY, SESSIONS_DIR, OUTPUT_DIR

if not ANTHROPIC_API_KEY:
    print("ERROR: Set ANTHROPIC_API_KEY in the environment or .claude/settings.json (env.ANTHROPIC_API_KEY).")
    sys.exit(1)

from agents import gr_expert, math_expert, physical_meaning, devil_advocate
from agents import wild_theorist, equation_verifier, literature_reviewer
from agents import orchestrator, latex_formatter

TOPIC = "modified-gravity"

DEFAULT_QUESTION = (
    "We want to construct a covariant modified gravity theory that reproduces the "
    "successes of MOND at galactic scales while remaining compatible with ALL other "
    "observational scales: "
    "(1) SOLAR SYSTEM: recover GR to PPN precision (gamma, beta ~1), no fifth-force "
    "anomalies, correct perihelion precession. "
    "(2) GALAXIES: reproduce the Radial Acceleration Relation (RAR/MDAR), baryonic "
    "Tully-Fisher relation (v^4 ~ G M a0), flat rotation curves, with a0 ~ 1.2e-10 m/s^2. "
    "(3) GALAXY CLUSTERS: explain cluster mass discrepancy without invoking CDM — "
    "or if sterile neutrino dark matter is needed, explain why and at what scale. "
    "(4) CMB: reproduce the acoustic peak positions and heights, and the matter power "
    "spectrum P(k), without CDM — or specify precisely what supplementary matter component "
    "is required and what are its properties. "
    "(5) LARGE-SCALE STRUCTURE: correct growth rate of structure, BAO scale, Hubble tension. "
    "The theory must be relativistically covariant. Candidate frameworks include: "
    "TeVeS (Bekenstein 2004), RMOND/AMOND (Skordis-Zlosnik 2021), "
    "bimetric MOND (Milgrom 2009), dipolar dark matter (Blanchet), "
    "emergent gravity (Verlinde), covariant MOND action theories "
    "(Bruneton & Esposito-Farese 2007). "
    "Identify the strongest candidate, write its covariant action, derive its field "
    "equations, check each scale, and propose what additional ingredient (if any) is "
    "needed to pass all tests simultaneously."
)

DEFAULT_TITLE = (
    "Covariant Modified Gravity at All Scales: "
    "From Solar System to CMB"
)

# Rounds: no QM, no LQG, no BH specialist; Wild Theorist every round for speculative angles
DEFAULT_ROUND_AGENTS = [
    ["gr", "math", "wild"],
    ["meaning", "devil", "wild"],
    ["wild", "verifier"],
    ["gr", "devil", "lit", "wild"],
]

AGENT_REGISTRY = {
    "gr":       ("GR Expert",           gr_expert.consult),
    "math":     ("Math Expert",         math_expert.consult),
    "meaning":  ("Physical Meaning",    physical_meaning.interrogate),
    "devil":    ("Devil's Advocate",    devil_advocate.critique),
    "wild":     ("Wild Theorist",       wild_theorist.propose),
    "verifier": ("Equation Verifier",   equation_verifier.verify),
    "lit":      ("Literature Reviewer", literature_reviewer.review),
}

# ─── Curated paper list ───────────────────────────────────────────────────────
MODIFIED_GRAVITY_PAPERS = [
    "astro-ph/0112528",
    "astro-ph/0207231",
    "0911.5464",
    "1212.2152",
    "2303.04368",
    "astro-ph/0403694",
    "astro-ph/0512011",
    "astro-ph/0601099",
    "astro-ph/0502222",
    "astro-ph/0511591",
    "0801.1985",
    "2109.13287",
    "1907.09003",
    "2303.05023",
    "gr-qc/0602051",
    "0807.1567",
    "1007.2483",
    "1112.3960",
    "1609.05917",
    "1703.10309",
    "2109.04781",
    "astro-ph/0506582",
    "astro-ph/0608407",
    "astro-ph/0606216",
    "0803.3089",
    "1611.02269",
    "1809.00840",
    "astro-ph/0607246",
    "1105.5815",
    "1909.09218",
    "2112.15218",
    "gr-qc/0510072",
]


def download_modified_gravity_papers(dry_run: bool, download_pdfs: bool) -> None:
    """Download curated modified gravity / MOND paper library."""
    print(f"\n  Downloading {len(MODIFIED_GRAVITY_PAPERS)} modified gravity papers...")
    print("  (Bekenstein, Milgrom, Skordis, Famaey, Bruneton & Esposito-Farese, ...)\n")

    if dry_run:
        for pid in MODIFIED_GRAVITY_PAPERS:
            print(f"    {pid}")
        print("  (dry run — not downloading)")
        return

    try:
        from paper_tools.arxiv_downloader import download_by_id

        download_by_id(MODIFIED_GRAVITY_PAPERS, download_pdfs)
    except Exception as e:
        print(f"  Download error: {e}")


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
        session_id = resume_data["session_id"]
        session_start = datetime.fromisoformat(resume_data["timestamp"])
        all_rounds = resume_data.get("rounds", [])
        title = resume_data.get("title", title)
        question = resume_data.get("question", question)
        start_round = len(all_rounds) + 1
        current_context = "\n\n".join(
            f"Round {r['round']} synthesis:\n{r['synthesis']}" for r in all_rounds
        )
        if human_input:
            current_context += f"\n\nHuman input / new direction:\n{human_input}"
            print(f"  Injecting human input: {human_input[:120]}")
    else:
        session_id = uuid.uuid4().hex[:8]
        session_start = datetime.now()
        all_rounds = []
        start_round = 1
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
    print(f"  MODIFIED GRAVITY THINK TANK  |  {action} Session {session_id}")
    print(f"{'='*70}")
    print(f"\nQuestion: {question[:300]}...")
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

            time.sleep(SLEEP_AFTER_AGENT_SEC)

        print(f"  Synthesizing round {round_num}...")
        synthesis = orchestrator.orchestrate(question, agent_responses, round_num)
        time.sleep(SLEEP_AFTER_ORCHESTRATE_SEC)

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
        time.sleep(SLEEP_AFTER_CHECKPOINT_SEC)

        current_context = "\n\n".join(
            f"Round {r['round']} synthesis:\n{r['synthesis']}" for r in all_rounds
        )
        time.sleep(SLEEP_AFTER_ROUND_SEC)

    print(f"\n{'='*70}")
    print(f"  FINAL SYNTHESIS")
    print(f"{'='*70}\n")
    time.sleep(SLEEP_BEFORE_FINAL_SYNTHESIS_SEC)
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
        time.sleep(SLEEP_AFTER_CHECKPOINT_SEC)

    save_session(session_data)

    print(f"\n{'='*70}")
    print(f"  DONE  |  Session {session_id}")
    print(f"  Output: {Path(OUTPUT_DIR) / session_id}")
    print(f"  Session JSON: {_session_path(session_id)}")
    print(f"{'='*70}\n")

    return session_data


# ─── CLI ──────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Modified Gravity / Covariant MOND Think Tank",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    parser.add_argument("--question",        "-q", type=str, default=DEFAULT_QUESTION)
    parser.add_argument("--title",           "-t", type=str, default=DEFAULT_TITLE)
    parser.add_argument("--rounds",          "-r", type=int, default=4)
    parser.add_argument("--agents",          "-a", nargs="+", choices=sorted(AGENT_REGISTRY.keys()))
    parser.add_argument("--no-latex",        action="store_true")
    parser.add_argument("--quiet",           action="store_true")
    parser.add_argument("--resume",          metavar="SESSION_ID")
    parser.add_argument("--input",           metavar="TEXT",
                        help="Human input injected when resuming")
    parser.add_argument("--list-sessions",   action="store_true")
    parser.add_argument(
        "--download-papers",
        action="store_true",
        help="Before a new session, download curated arXiv papers and preprocess (ignored with --resume)",
    )
    parser.add_argument("--download-only",   action="store_true",
                        help="Only download papers and preprocess; do not run a session")
    parser.add_argument("--dry-run-papers",  action="store_true",
                        help="List papers that would be downloaded")
    parser.add_argument(
        "--pdf",
        action="store_true",
        help="With --download-papers / --download-only: also fetch PDFs (default: abstracts only)",
    )
    args = parser.parse_args()

    if args.list_sessions:
        list_sessions()
        sys.exit(0)

    if args.dry_run_papers:
        download_modified_gravity_papers(dry_run=True, download_pdfs=args.pdf)
        sys.exit(0)

    def _maybe_download_and_preprocess() -> None:
        download_modified_gravity_papers(dry_run=False, download_pdfs=args.pdf)
        print("\n  Preprocessing new papers...")
        try:
            from paper_tools.preprocess_papers import process_all

            process_all(force=False)
        except Exception as e:
            print(f"  Preprocessing error: {e}")

    if args.download_only:
        _maybe_download_and_preprocess()
        print("Download complete.")
        sys.exit(0)

    if args.download_papers and not args.resume:
        _maybe_download_and_preprocess()

    if args.resume:
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
