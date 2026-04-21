import json
import os
import re
import sys

_PROJECT_ROOT = os.path.dirname(os.path.abspath(__file__))
_DEFAULT_YAML = os.path.join(_PROJECT_ROOT, "config.default.yaml")
_LOCAL_YAML = os.path.join(_PROJECT_ROOT, "config.yaml")


def _deep_merge(base: dict, override: dict) -> dict:
    out = dict(base)
    for key, val in override.items():
        if (
            key in out
            and isinstance(out[key], dict)
            and isinstance(val, dict)
        ):
            out[key] = _deep_merge(out[key], val)
        else:
            out[key] = val
    return out


def _load_yaml_config() -> dict:
    try:
        import yaml
    except ImportError:
        return {}
    data: dict = {}
    if os.path.isfile(_DEFAULT_YAML):
        try:
            with open(_DEFAULT_YAML, encoding="utf-8") as f:
                loaded = yaml.safe_load(f)
                if isinstance(loaded, dict):
                    data = loaded
        except (OSError, yaml.YAMLError):
            pass
    if os.path.isfile(_LOCAL_YAML):
        try:
            with open(_LOCAL_YAML, encoding="utf-8") as f:
                local = yaml.safe_load(f)
                if isinstance(local, dict):
                    data = _deep_merge(data, local)
        except (OSError, yaml.YAMLError):
            pass
    return data


_YAML = _load_yaml_config()


def _y(*keys, default=None):
    d = _YAML
    for k in keys:
        if not isinstance(d, dict) or k not in d:
            return default
        d = d[k]
    return d


def _as_bool(val, default: bool) -> bool:
    """YAML booleans; treat missing as default."""
    if val is None:
        return default
    if isinstance(val, bool):
        return val
    if isinstance(val, str):
        return val.strip().lower() in ("1", "true", "yes", "on")
    return bool(val)


ANTHROPIC_API_KEY = os.environ.get("ANTHROPIC_API_KEY")

# If not in environment, try loading from .claude/settings.json
if not ANTHROPIC_API_KEY:
    settings_path = os.path.join(_PROJECT_ROOT, ".claude", "settings.json")
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

AGENT_MODEL = _y("agent", "model", default="claude-sonnet-4-6")

MIN_ARXIV_PAPERS = int(_y("arxiv", "min_papers", default=8))
MAX_ARXIV_PAPERS = int(_y("arxiv", "max_papers", default=120))

MAX_EXPERT_CONTEXT_CHARS = int(_y("context", "max_expert_chars", default=45000))
MAX_ORCHESTRATOR_AGENT_RESPONSE_CHARS = int(
    _y("context", "max_orchestrator_agent_response_chars", default=14000)
)
MAX_FINAL_ROUND_SYNTHESIS_CHARS = int(
    _y("context", "max_final_round_synthesis_chars", default=16000)
)
MAX_FINAL_ALL_ROUNDS_CHARS = int(_y("context", "max_final_all_rounds_chars", default=90000))
LARGE_REQUEST_WARN_INPUT_CHARS = int(
    _y("context", "large_request_warn_input_chars", default=120000)
)
# Paper library can grow to thousands of entries; LaTeX / selector agents only need a candidate subset.
MAX_PAPER_CATALOGUE_ENTRIES = int(_y("context", "max_paper_catalogue_entries", default=150))
# Bound synthesis length sent to LaTeX formatter (full text stays in session JSON).
MAX_LATEX_SYNTHESIS_CHARS = int(_y("context", "max_latex_synthesis_chars", default=24000))

MAX_ROUNDS = int(_y("session", "max_rounds", default=3))

_papers_rel = _y("paths", "papers", default="papers")
_output_rel = _y("paths", "output", default="output")
_sessions_rel = _y("paths", "sessions", default="sessions")
_papers_base = os.path.join(_PROJECT_ROOT, _papers_rel)
# Active project subfolder under papers/ (see set_papers_project).
_papers_project_slug = "default"
OUTPUT_DIR = os.path.join(_PROJECT_ROOT, _output_rel)
SESSIONS_DIR = os.path.join(_PROJECT_ROOT, _sessions_rel)


def _sanitize_papers_slug(slug: str) -> str:
    s = slug.lower().strip()
    s = re.sub(r"[^a-z0-9_]+", "_", s)
    s = s.strip("_")
    if len(s) > 50:
        s = s[:50].rstrip("_")
    return s or "default"


def get_papers_dir() -> str:
    """Current paper library directory: papers/<project_slug>/."""
    return os.path.join(_papers_base, _papers_project_slug)


def set_papers_project(slug: str) -> None:
    """Route downloads, index.json, and preprocess to papers/<slug>/."""
    global _papers_project_slug
    _papers_project_slug = _sanitize_papers_slug(slug)
    os.makedirs(get_papers_dir(), exist_ok=True)

# Default arXiv category filter / search terms for paper_tools (not in YAML — edit here if needed).
ARXIV_CATEGORIES = [
    "gr-qc",
    "hep-th",
    "quant-ph",
    "math-ph",
]

# String-theory-heavy paper filter in preprocess_papers (not in YAML).
EXCLUDE_KEYWORDS = [
    "string compactification",
    "flux compactification",
    "Calabi-Yau",
    "moduli stabilization",
    "KKLT",
    "landscape of string vacua",
    "supersymmetry breaking",
    "brane inflation",
    "D-brane phenomenology",
    "Type IIA phenomenology",
    "Type IIB phenomenology",
]
EXCLUDE_SAFELIST = [
    "AdS/CFT",
    "Anti-de Sitter",
    "holograph",
    "black hole entropy",
    "Bekenstein",
    "entanglement entropy",
    "Ryu-Takayanagi",
    "ER=EPR",
    "firewall",
    "information paradox",
    "holographic entanglement",
    "spacetime emergence",
    "quantum information",
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

PAPERS_ARXIV_PDF = _as_bool(_y("papers", "arxiv_pdf"), True)
PAPERS_INSPIRE = _as_bool(_y("papers", "inspire"), True)
PAPERS_SEMANTIC_SCHOLAR = _as_bool(_y("papers", "semantic_scholar"), True)
