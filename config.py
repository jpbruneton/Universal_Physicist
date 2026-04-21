import os
import sys
import json

ANTHROPIC_API_KEY = os.environ.get("ANTHROPIC_API_KEY")

# If not in environment, try loading from .claude/settings.json
if not ANTHROPIC_API_KEY:
    settings_path = os.path.join(os.path.dirname(__file__), ".claude", "settings.json")
    if os.path.exists(settings_path):
        try:
            with open(settings_path) as f:
                settings = json.load(f)
                ANTHROPIC_API_KEY = settings.get("env", {}).get("ANTHROPIC_API_KEY")
        except (json.JSONDecodeError, IOError):
            pass

# So entrypoints that only read os.environ (and child processes) see the key from settings.json.
if ANTHROPIC_API_KEY and not os.environ.get("ANTHROPIC_API_KEY"):
    os.environ["ANTHROPIC_API_KEY"] = ANTHROPIC_API_KEY

if not ANTHROPIC_API_KEY:
    print(
        "WARNING: ANTHROPIC_API_KEY not set — use the environment or .claude/settings.json (env.ANTHROPIC_API_KEY).",
        file=sys.stderr,
    )

# Model for all agents — Sonnet 4.6 is the default; swap to opus for deeper reasoning
AGENT_MODEL = "claude-sonnet-4-6"

# Bound prompt size (characters) per call site. Long sessions otherwise send huge
# cumulative context and spike tokens-per-minute (429 risk). Truncation keeps the tail.
MAX_EXPERT_CONTEXT_CHARS = 45000
MAX_ORCHESTRATOR_AGENT_RESPONSE_CHARS = 14000
MAX_FINAL_ROUND_SYNTHESIS_CHARS = 16000
MAX_FINAL_ALL_ROUNDS_CHARS = 90000
# Warn once per call_agent when estimated input exceeds this (characters, rough).
LARGE_REQUEST_WARN_INPUT_CHARS = 120000

# How many rounds of debate the orchestrator runs before synthesizing
MAX_ROUNDS = 3

# Papers directory
PAPERS_DIR = os.path.join(os.path.dirname(__file__), "papers")
OUTPUT_DIR = os.path.join(os.path.dirname(__file__), "output")
SESSIONS_DIR = os.path.join(os.path.dirname(__file__), "sessions")

# ArXiv categories relevant to quantum gravity
ARXIV_CATEGORIES = ["gr-qc", "hep-th", "quant-ph", "math-ph"]

# Keywords that mark a paper as excluded (string theory heavy, not relevant to our QG approach).
# A paper is excluded only if it matches >=2 exclude keywords AND zero safelist keywords.
EXCLUDE_KEYWORDS = [
    "string compactification", "flux compactification", "Calabi-Yau",
    "moduli stabilization", "KKLT", "landscape of string vacua",
    "supersymmetry breaking", "brane inflation", "D-brane phenomenology",
    "Type IIA phenomenology", "Type IIB phenomenology",
]

# If ANY of these appear, the paper is KEPT regardless of exclude matches.
EXCLUDE_SAFELIST = [
    "AdS/CFT", "Anti-de Sitter", "holograph", "black hole entropy",
    "Bekenstein", "entanglement entropy", "Ryu-Takayanagi",
    "ER=EPR", "firewall", "information paradox", "holographic entanglement",
    "spacetime emergence", "quantum information",
]

ARXIV_SEARCH_TERMS = [
    "quantum gravity",
    "loop quantum gravity",
    "spin foam",
    "black hole",
    "white hole",
    "Hawking radiation",
    "information loss",
    "holography",
    "AdS/CFT",
    "entanglement entropy",
    "spacetime emergence",
    "entropic gravity",
    "causal sets",
    "causal dynamical triangulations",
    "asymptotic safety",
    "generalized uncertainty principle",
    "quantum cosmology",
    "relational quantum mechanics",
    "quantum reference frames",
    "wormhole",
    "minimum length",
    "Planck scale",
]
