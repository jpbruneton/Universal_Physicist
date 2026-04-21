"""
Session project generated from `main.py` (frozen plan + improved research prompt).

Original phrase:
{"query": "Find a covariant modified gravity theory compatible at ALL scales: solar system (PPN), galaxies (RAR, BTFR, flat rotation curves, a0~1.2e-10 m/s^2), galaxy clusters (Bullet Cluster, X-ray mass), CMB (acoustic peaks, matter power spectrum), and large-scale structure. The theory must be relativistically covariant, reproduce MOND phenomenology in the weak-field non-relativistic limit, and either explain or specify what additional matter component (sterile neutrinos?) handles clusters and CMB. Evaluate: TeVeS (Bekenstein), RMOND/AMOND (Skordis-Zlosnik), bimetric MOND (Milgrom), dipolar dark matter (Blanchet), covariant k-mouflage and DHOST theories (Bruneton, Esposito-Farese), chameleon/symmetron screening (Khoury), gravitational polarization (Blanchet, Le Tiec). Write the covariant action of the strongest candidate, derive its field equations, check each observational scale, and identify what additional ingredient if any is needed.", "keywords": ["MOND", "modified Newtonian dynamics", "TeVeS", "relativistic MOND", "RMOND", "AMOND", "radial acceleration relation", "baryonic Tully-Fisher", "covariant modified gravity", "bimetric MOND", "dipolar dark matter", "gravitational polarization", "k-mouflage", "DHOST", "chameleon screening", "symmetron", "emergent gravity Verlinde", "MOND CMB", "sterile neutrino dark matter", "modified gravity clusters"], "authors": ["Milgrom", "Bekenstein", "Skordis", "Famaey", "Bruneton", "Esposito-Farese", "Blanchet", "Le Tiec", "Khoury", "Sanders", "McGaugh", "Verlinde", "Hossenfelder", "Angus", "Lelli"], "exclude_keywords": ["supersymmetry", "string compactification", "loop quantum gravity", "spin foam"], "exclude_authors": [], "mode": "researcher", "session_name": "mond_theories"}

Run from the repository root, for example:
  py -3 written_projects/covariant_modified_gravity_across_all_scales_from_project.py
  py -3 written_projects/covariant_modified_gravity_across_all_scales_from_project.py --fetch-papers
  py -3 written_projects/covariant_modified_gravity_across_all_scales_from_project.py --rounds 3 --quiet

This file embeds the planner output (refined question, title, arXiv query, dynamic agents,
and round roster). Re-running it repeats the expert discussion without calling the planner.

Generated at: 2026-04-21T16:08:33Z
"""

import argparse
import io
import json
import sys
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parent.parent
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

if sys.stdout.encoding.lower() != "utf-8":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8", errors="replace")

from config import ANTHROPIC_API_KEY, PAPERS_ARXIV_PDF, get_papers_dir, set_papers_project
from topic_project_writer import slugify_papers_subdir

if not ANTHROPIC_API_KEY:
    print(
        "ERROR: Set ANTHROPIC_API_KEY in the environment or .claude/settings.json "
        "(env.ANTHROPIC_API_KEY)."
    )
    sys.exit(1)

from main import (
    SLEEP_BEFORE_EXPERT_SESSION_SEC,
    _pacing_sleep,
    build_merged_registry,
    run_pipeline_session,
)

PLAN = json.loads('{"session_title": "Covariant Modified Gravity Across All Scales: From MOND Phenomenology to CMB and Clusters", "refined_research_question": "Can a single relativistically covariant modified gravity theory — with action S = S_gravity[g_{mu nu}] + S_scalar[phi, g_{mu nu}] + S_matter[psi, tilde{g}_{mu nu}] where tilde{g}_{mu nu} is a MOND-modified metric — simultaneously satisfy: (1) PPN constraints (gamma, beta within 10^{-4} of GR) in the solar system; (2) the radial acceleration relation g_obs = g_bar / (1 - e^{-sqrt(g_bar/a_0)}) with a_0 ~ 1.2e-10 m/s^2 and the baryonic Tully-Fisher relation v_f^4 = G M_bar a_0 for galaxies; (3) flat rotation curves; (4) Bullet Cluster and X-ray mass constraints for galaxy clusters; (5) CMB acoustic peaks and matter power spectrum P(k)? Specifically: evaluate TeVeS (Bekenstein), RMOND/AMOND (Skordis-Zlosnik), bimetric MOND (Milgrom), dipolar dark matter / gravitational polarization (Blanchet, Le Tiec), covariant k-mouflage and DHOST theories (Bruneton, Esposito-Farese), chameleon/symmetron screening (Khoury), and emergent gravity (Verlinde); write the covariant action of the strongest surviving candidate; derive its full field equations and weak-field non-relativistic limit; and determine whether an additional matter component (e.g. sterile neutrino dark matter, ~11 eV, Angus) is necessary and sufficient to close the cluster and CMB gaps.", "arxiv_search_query": "(((abs:MOND OR abs:\\"modified Newtonian dynamics\\" OR abs:TeVeS OR abs:\\"relativistic MOND\\" OR abs:RMOND OR abs:AMOND OR abs:\\"radial acceleration relation\\" OR abs:\\"baryonic Tully-Fisher\\" OR abs:\\"covariant modified gravity\\" OR abs:\\"bimetric MOND\\" OR abs:\\"dipolar dark matter\\" OR abs:\\"gravitational polarization\\" OR abs:k-mouflage OR abs:DHOST OR abs:\\"chameleon screening\\" OR abs:symmetron OR abs:\\"emergent gravity\\" OR abs:Verlinde OR abs:\\"MOND CMB\\" OR abs:\\"sterile neutrino dark matter\\" OR abs:\\"modified gravity clusters\\") AND (au:Milgrom OR au:Bekenstein OR au:Skordis OR au:Famaey OR au:Bruneton OR au:Esposito-Farese OR au:Blanchet OR au:\\"Le Tiec\\" OR au:Khoury OR au:Sanders OR au:McGaugh OR au:Verlinde OR au:Hossenfelder OR au:Angus OR au:Lelli) ANDNOT (abs:supersymmetry OR abs:\\"string compactification\\" OR abs:\\"loop quantum gravity\\" OR abs:\\"spin foam\\")) AND (all:MOND OR all:\\"modified Newtonian dynamics\\" OR all:TeVeS OR all:\\"relativistic MOND\\" OR all:RMOND OR all:AMOND OR all:\\"radial acceleration relation\\" OR all:\\"baryonic Tully-Fisher\\" OR all:\\"covariant modified gravity\\" OR all:\\"bimetric MOND\\" OR all:\\"dipolar dark matter\\" OR all:\\"gravitational polarization\\" OR all:k-mouflage OR all:DHOST OR all:\\"chameleon screening\\" OR all:symmetron OR all:\\"emergent gravity Verlinde\\" OR all:\\"MOND CMB\\" OR all:\\"sterile neutrino dark matter\\" OR all:\\"modified gravity clusters\\") AND (au:Milgrom OR au:Bekenstein OR au:Skordis OR au:Famaey OR au:Bruneton OR au:Esposito-Farese OR au:Blanchet OR au:\\"Le Tiec\\" OR au:Khoury OR au:Sanders OR au:McGaugh OR au:Verlinde OR au:Hossenfelder OR au:Angus OR au:Lelli)) ANDNOT all:supersymmetry ANDNOT all:\\"string compactification\\" ANDNOT all:\\"loop quantum gravity\\" ANDNOT all:\\"spin foam\\"", "arxiv_categories": ["gr-qc", "hep-th", "astro-ph"], "max_papers": 80, "dynamic_agent_specs": [{"id": "mond_galactic", "display_name": "MOND & Galactic Dynamics Expert", "system_prompt": "You are an expert in Modified Newtonian Dynamics (MOND) and galactic-scale phenomenology. You have deep knowledge of the radial acceleration relation (RAR), baryonic Tully-Fisher relation (BTFR), flat rotation curves, and the critical acceleration a_0 ~ 1.2e-10 m/s^2. You are familiar with the works of Milgrom, McGaugh, Famaey, Lelli, and Sanders. You can derive the MOND interpolating function mu(x) where x = g/a_0, analyze its limiting behaviors (deep-MOND: g ~ sqrt(g_N a_0) and Newtonian: g ~ g_N), and evaluate how different covariant theories reproduce these limits. You assess galaxy rotation curve fits quantitatively and know the observational scatter and systematic uncertainties in the RAR. You understand the distinction between AQUAL, QUMOND, and their relativistic extensions. You critically evaluate whether a given covariant action reproduces correct galactic phenomenology in its weak-field non-relativistic limit. You connect galactic observations to the free functions appearing in modified gravity Lagrangians."}, {"id": "cluster_cosmo", "display_name": "Galaxy Clusters & Cosmological Structure Expert", "system_prompt": "You are an expert in galaxy cluster physics, large-scale structure, and CMB cosmology in the context of modified gravity and dark matter alternatives. You understand X-ray mass measurements, gravitational lensing mass reconstructions, and the Bullet Cluster constraint on self-interaction and spatial coincidence of dark matter. You are familiar with the works of Angus, Skordis, Famaey, and Sanders on cluster mass discrepancies in MOND. You know the CMB power spectrum in detail: the positions of acoustic peaks l_n, their amplitude ratios, and how the matter-to-radiation ratio and baryon loading affect them. You understand how modified gravity theories (TeVeS, RMOND, AMOND) affect the CMB and matter power spectrum P(k), including the role of the MOND scalar field as an effective dark matter surrogate. You evaluate whether sterile neutrino dark matter (~11 eV, as proposed by Angus) or other hot/warm dark matter candidates can close the cluster and CMB gaps in otherwise viable MOND theories. You quantitatively assess sigma_8 tension, S_8 parameter, and large-scale structure constraints."}, {"id": "covariant_actions", "display_name": "Covariant Modified Gravity & Field Theory Specialist", "system_prompt": "You are an expert in constructing and analyzing covariant modified gravity theories beyond GR, with specialization in tensor-scalar-vector theories, DHOST (Degenerate Higher-Order Scalar-Tensor) theories, TeVeS, bimetric theories, k-mouflage, chameleon and symmetron screening mechanisms. You are familiar with the works of Bekenstein, Skordis, Zlosnik, Bruneton, Esposito-Farese, Khoury, Blanchet, and Milgrom. You can write down covariant actions explicitly, e.g. S = (1/16 pi G) int d^4x sqrt(-g) [R + F(X, phi)] + S_matter, identify the degrees of freedom, derive field equations via variational principle, and check for ghost instabilities, gradient instabilities, and superluminality. You understand the PPN formalism and can compute gamma and beta parameters for a given scalar-tensor or vector-tensor theory. You know how DHOST theories evade Ostrogradski ghosts via degeneracy conditions and how k-mouflage restores GR locally while modifying gravity at low accelerations. You evaluate theoretical consistency including causality, unitarity, and stability of cosmological solutions."}, {"id": "screening_dipolar", "display_name": "Screening Mechanisms & Dipolar Dark Matter Expert", "system_prompt": "You are an expert in gravitational screening mechanisms (chameleon, symmetron, Vainshtein, k-mouflage) and in the dipolar dark matter / gravitational polarization framework of Blanchet and Le Tiec. You understand how screening restores GR in high-density/high-acceleration environments (solar system) while allowing MOND-like modifications at low accelerations in galactic outskirts. You can derive the chameleon field equation (Box phi = dV/dphi - beta rho / M_Pl) and the symmetron VEV condition, and assess their compatibility with fifth-force laboratory bounds. You are deeply familiar with the gravitational polarization model: the idea that a dipolar dark matter fluid with polarization P satisfying div P = rho_DM produces an effective MONDian force, and can write the covariant generalization of this action. You evaluate whether dipolar dark matter can simultaneously explain flat rotation curves, cluster lensing, and CMB without introducing screening fine-tuning. You connect these frameworks to Verlinde\'s emergent gravity and Hossenfelder\'s covariant emergent gravity (COVARIANT version of Verlinde), assessing their observational predictions quantitatively."}], "round_agent_groups": [["covariant_actions", "mond_galactic", "math"], ["cluster_cosmo", "mond_galactic", "screening_dipolar"], ["covariant_actions", "screening_dipolar", "gr", "qft"], ["cluster_cosmo", "covariant_actions", "devil"], ["lit", "mond_galactic", "cluster_cosmo", "meaning"], ["verifier", "devil", "covariant_actions", "wild"]], "session_mode": "researcher"}')
set_papers_project(slugify_papers_subdir(PLAN["session_title"]))


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Replay expert session from embedded plan (no planner call).",
    )
    parser.add_argument(
        "--fetch-papers",
        action="store_true",
        help="Run arXiv search/download and preprocess before the discussion",
    )
    parser.add_argument(
        "--skip-preprocess",
        action="store_true",
        help="With --fetch-papers: skip paper_tools.preprocess_papers",
    )
    parser.add_argument(
        "--pdf",
        action="store_true",
        help="With --fetch-papers: force arXiv PDFs (overrides config)",
    )
    parser.add_argument(
        "--no-pdf",
        action="store_true",
        help="With --fetch-papers: skip arXiv PDFs (overrides config)",
    )
    parser.add_argument(
        "--rounds",
        "-r",
        type=int,
        default=None,
        help="Max discussion rounds (default: full plan)",
    )
    parser.add_argument("--no-latex", action="store_true")
    parser.add_argument("--quiet", action="store_true")
    args = parser.parse_args()

    if args.pdf and args.no_pdf:
        parser.error("Use either --pdf or --no-pdf, not both.")

    if args.fetch_papers:
        print(f"\n  [2/4] Searching arXiv and saving abstracts...\n  → {get_papers_dir()}\n")
        from paper_tools.arxiv_downloader import search_and_download

        if args.pdf:
            download_pdfs = True
        elif args.no_pdf:
            download_pdfs = False
        else:
            download_pdfs = PAPERS_ARXIV_PDF
        search_and_download(
            query=PLAN["arxiv_search_query"],
            categories=PLAN["arxiv_categories"],
            max_results=PLAN["max_papers"],
            download_pdfs=download_pdfs,
        )
        if not args.skip_preprocess:
            print("\n  [3/4] Preprocessing paper library...\n")
            from paper_tools.preprocess_papers import process_all

            process_all(force=False)
        else:
            print("\n  [3/4] Skipped (--skip-preprocess).\n")
    else:
        print("\n  [2–3/4] Skipping papers (use --fetch-papers to run arXiv + preprocess).\n")

    round_groups = PLAN["round_agent_groups"]
    if args.rounds is not None:
        round_groups = round_groups[: max(1, args.rounds)]

    merged_registry = build_merged_registry(PLAN)

    print("\n  [4/4] Expert discussion...\n")
    _pacing_sleep(SLEEP_BEFORE_EXPERT_SESSION_SEC, "preprocessing — before expert discussion")
    run_pipeline_session(
        question=PLAN["refined_research_question"],
        title=PLAN["session_title"],
        agent_registry=merged_registry,
        round_groups=round_groups,
        planning=PLAN,
        produce_latex=not args.no_latex,
        verbose=not args.quiet,
        resume_session_data=None,
        start_round_one_based=1,
        on_pipeline_event=None,
        explicit_session_id=None,
    )


if __name__ == "__main__":
    main()
