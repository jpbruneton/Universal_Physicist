"""
Legacy archive — older modified-gravity / MOND think tank (use modified_gravity_project.py).

Goal: find a covariant modified gravity theory compatible at ALL scales:
  - Solar system (GR recovery, PPN constraints)
  - Galaxies (RAR, rotation curves, baryonic Tully-Fisher)
  - Galaxy clusters (Bullet Cluster, X-ray mass)
  - CMB (acoustic peaks, matter power spectrum)
  - Large-scale structure

No quantum framework. Classical field theory only.
Key references: Milgrom, Bekenstein, Skordis, Famaey, Bruneton & Esposito-Farese.

Usage:
    py -3 modified_gravity_legacy_project.py
    py -3 modified_gravity_legacy_project.py --rounds 5
    py -3 modified_gravity_legacy_project.py --no-latex
    py -3 modified_gravity_legacy_project.py --resume SESSION_ID
    py -3 modified_gravity_legacy_project.py --skip-download
    py -3 modified_gravity_legacy_project.py --list-sessions
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

#if not os.environ.get("ANTHROPIC_API_KEY"):
#    print("ERROR: Set ANTHROPIC_API_KEY environment variable first.")
#    sys.exit(1)

from config import SESSIONS_DIR, OUTPUT_DIR
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
    "(3) GALAXY CLUSTERS: explain cluster mass discrepancy without invoking CDM ÔÇö "
    "or if sterile neutrino dark matter is needed, explain why and at what scale. "
    "(4) CMB: reproduce the acoustic peak positions and heights, and the matter power "
    "spectrum P(k), without CDM ÔÇö or specify precisely what supplementary matter component "
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

# Rounds: no QM, no LQG, no BH specialist
# Round 1: GR + Math ÔÇö lay out the covariant frameworks, field equations, actions
# Round 2: Meaning + Devil ÔÇö multi-scale constraints, what passes/fails
# Round 3: Wild + Verifier ÔÇö bold proposals + equation checks
# Round 4: GR + Devil + Lit ÔÇö sharpen, observational predictions, literature grounding
DEFAULT_ROUND_AGENTS = [
    ["gr", "math"],                    # Round 1: covariant actions, field equations
    ["meaning", "devil"],              # Round 2: scale-by-scale stress test
    ["wild", "verifier"],              # Round 3: novel proposals + rigor check
    ["gr", "devil", "lit"],            # Round 4: synthesis + literature grounding
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

# ÔöÇÔöÇÔöÇ Curated paper list ÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇ
# Key papers for modified gravity / covariant MOND literature
MODIFIED_GRAVITY_PAPERS = [
    # --- MOND foundations ---
    "astro-ph/0112528",   # Milgrom 2001 ÔÇö MOND review (Acta Astronomica)
    "astro-ph/0207231",   # Milgrom 2002 ÔÇö MOND: the predictions
    "0911.5464",          # Milgrom 2009 ÔÇö Bimetric MOND gravity
    "1212.2152",          # Milgrom 2012 ÔÇö MOND laws of galactic dynamics
    "2303.04368",         # Milgrom 2023 ÔÇö MOND vs dark matter in galaxy groups

    # --- TeVeS (Bekenstein) ---
    "astro-ph/0403694",   # Bekenstein 2004 ÔÇö Relativistic MOND (TeVeS)
    "astro-ph/0512011",   # Bekenstein & Sagi 2008 ÔÇö New TeVeS and gravitational lensing
    "astro-ph/0601099",   # Sanders 2006 ÔÇö TeVeS and galaxy clusters
    "astro-ph/0502222",   # Sanders 2005 ÔÇö TeVeS and CMB
    "astro-ph/0511591",   # Skordis et al. 2006 ÔÇö CMB power spectrum in TeVeS
    "0801.1985",          # Skordis 2008 ÔÇö TeVeS cosmology

    # --- RMOND / AMOND (Skordis & Zlosnik) ---
    "2109.13287",         # Skordis & Zlosnik 2021 ÔÇö Relativistic MOND (RMOND)
    "1907.09003",         # Skordis & Zlosnik 2019 ÔÇö RMOND precursor
    "2303.05023",         # Skordis 2023 ÔÇö AMOND extension

    # --- Bruneton & Esposito-Farese ---
    "gr-qc/0602051",      # Bruneton & Esposito-Farese 2007 ÔÇö field-theoretical selfgravitation
    "0807.1567",          # Bruneton et al. 2009 ÔÇö viable covariant MOND models
    "1007.2483",          # Esposito-Farese 2011 ÔÇö comparing MOND and dark matter

    # --- Famaey & McGaugh review ---
    "1112.3960",          # Famaey & McGaugh 2012 ÔÇö Living Reviews: MOND

    # --- Radial Acceleration Relation ---
    "1609.05917",         # McGaugh, Lelli, Schombert 2016 ÔÇö RAR discovery
    "1703.10309",         # Lelli et al. 2017 ÔÇö RAR with SPARC sample
    "2109.04781",         # Chae et al. 2021 ÔÇö RAR in ellipticals

    # --- Baryonic Tully-Fisher ---
    "astro-ph/0506582",   # McGaugh 2005 ÔÇö baryonic Tully-Fisher

    # --- Galaxy clusters / Bullet Cluster problem ---
    "astro-ph/0608407",   # Clowe et al. 2006 ÔÇö Bullet Cluster direct evidence CDM
    "astro-ph/0606216",   # Angus, Famaey, Buote 2008 ÔÇö clusters in MOND
    "0803.3089",          # Angus et al. 2008 ÔÇö CMB and MOND with sterile neutrinos

    # --- Emergent gravity (Verlinde) ---
    "1611.02269",         # Verlinde 2016 ÔÇö emergent gravity and dark matter
    "1809.00840",         # Hossenfelder & Mistele 2018 ÔÇö covariant emergent gravity

    # --- Dipolar dark matter (Blanchet) ---
    "astro-ph/0607246",   # Blanchet 2007 ÔÇö dipolar dark matter and MOND
    "1105.5815",          # Blanchet & Heully 2012 ÔÇö gravitational polarization

    # --- MOND and large-scale structure / Hubble ---
    "1909.09218",         # Kroupa et al. 2019 ÔÇö MOND cosmological simulations
    "2112.15218",         # Banik & Zhao 2021 ÔÇö MOND review (confrontation with data)

    # --- PPN / Solar system constraints ---
    "gr-qc/0510072",      # Will 2006 ÔÇö confrontation of GR with experiment (PPN)
]


def download_modified_gravity_papers(dry_run: bool = False) -> None:
    """Download curated modified gravity / MOND paper library."""
    print(f"\n  Downloading {len(MODIFIED_GRAVITY_PAPERS)} modified gravity papers...")
    print("  (Bekenstein, Milgrom, Skordis, Famaey, Bruneton & Esposito-Farese, ...)\n")

    if dry_run:
        for pid in MODIFIED_GRAVITY_PAPERS:
            print(f"    {pid}")
        print("  (dry run ÔÇö not downloading)")
        return

    try:
        from paper_tools.arxiv_downloader import download_by_id
        download_by_id(MODIFIED_GRAVITY_PAPERS, download_pdfs=False)
    except Exception as e:
        print(f"  Download error: {e}")


# ÔöÇÔöÇÔöÇ Session persistence ÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇ

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


# ÔöÇÔöÇÔöÇ Round checkpoint ÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇ

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


# ÔöÇÔöÇÔöÇ Core runner ÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇ

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
        session_id      = resume_data["session_id"]
        session_start   = datetime.fromisoformat(resume_data["timestamp"])
        all_rounds      = resume_data.get("rounds", [])
        title           = resume_data.get("title", title)
        question        = resume_data.get("question", question)
        start_round     = len(all_rounds) + 1
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

    # ÔöÇÔöÇ Final synthesis ÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇ
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


# ÔöÇÔöÇÔöÇ CLI ÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇ

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
    parser.add_argument("--skip-download",   action="store_true",
                        help="Skip paper download step")
    parser.add_argument("--download-only",   action="store_true",
                        help="Only download papers, do not run session")
    parser.add_argument("--dry-run-papers",  action="store_true",
                        help="List papers that would be downloaded")
    args = parser.parse_args()

    if args.list_sessions:
        list_sessions()
        sys.exit(0)

    if args.dry_run_papers:
        download_modified_gravity_papers(dry_run=True)
        sys.exit(0)

    # Download papers first (unless skipped or resuming)
    if not args.skip_download and not args.resume:
        download_modified_gravity_papers(dry_run=False)
        print("\n  Preprocessing new papers...")
        try:
            from paper_tools.preprocess_papers import process_all
            process_all(force=False)
        except Exception as e:
            print(f"  Preprocessing error: {e}")

    if args.download_only:
        print("Download complete.")
        sys.exit(0)

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
