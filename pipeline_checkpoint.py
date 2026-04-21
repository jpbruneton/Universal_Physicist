"""
Per-prompt pipeline checkpoints for main.py: resume after interruption, detect completed runs.

State lives under pipeline_state/<fp_prefix>/state.json (gitignored).
Fingerprint = SHA-256 of canonical JSON (mode, phrase/instructions, skip flags, etc.).
"""

from __future__ import annotations

import hashlib
import json
import shutil
from pathlib import Path
from typing import Any

STATE_DIR_NAME = "pipeline_state"
STATE_FILENAME = "state.json"
SCHEMA_VERSION = 1


def pipeline_fully_done(state: dict[str, Any], output_dir: Path) -> bool:
    """True if checkpoint says completed and, when LaTeX is on, final_paper.tex exists."""
    if state.get("step") != "completed":
        return False
    if state.get("no_latex"):
        return True
    sid = state.get("session_id")
    if not sid:
        return True
    return (output_dir / sid / "final_paper.tex").is_file()


def canonical_fingerprint_inputs(
    session_mode: str,
    phrase_for_project: str,
    use_instructions: bool,
    skip_papers: bool,
    skip_preprocess: bool,
    max_papers: int | None,
    rounds: int | None,
    no_latex: bool,
    pdf_flag: bool,
    no_pdf_flag: bool,
    session_name_raw: str,
) -> dict[str, Any]:
    return {
        "v": SCHEMA_VERSION,
        "session_mode": session_mode,
        "phrase_for_project": phrase_for_project.strip(),
        "use_instructions": use_instructions,
        "skip_papers": skip_papers,
        "skip_preprocess": skip_preprocess,
        "max_papers_override": max_papers,
        "rounds_override": rounds,
        "no_latex": no_latex,
        "pdf_flag": pdf_flag,
        "no_pdf_flag": no_pdf_flag,
        "session_name": session_name_raw.strip(),
    }


def fingerprint_hex(inputs: dict[str, Any]) -> str:
    payload = json.dumps(inputs, sort_keys=True, ensure_ascii=False)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def state_dir_for_fingerprint(project_root: Path, fp_hex: str) -> Path:
    return project_root / STATE_DIR_NAME / fp_hex[:16]


def state_json_path(project_root: Path, fp_hex: str) -> Path:
    return state_dir_for_fingerprint(project_root, fp_hex) / STATE_FILENAME


def load_state(project_root: Path, fp_hex: str) -> dict[str, Any] | None:
    p = state_json_path(project_root, fp_hex)
    if not p.is_file():
        return None
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None


def save_state(project_root: Path, fp_hex: str, data: dict[str, Any]) -> None:
    d = state_dir_for_fingerprint(project_root, fp_hex)
    d.mkdir(parents=True, exist_ok=True)
    path = d / STATE_FILENAME
    tmp = path.with_suffix(".tmp")
    payload = json.dumps(data, indent=2, ensure_ascii=False, default=str)
    tmp.write_text(payload, encoding="utf-8")
    tmp.replace(path)


def delete_state(project_root: Path, fp_hex: str) -> None:
    d = state_dir_for_fingerprint(project_root, fp_hex)
    if d.is_dir():
        shutil.rmtree(d, ignore_errors=True)


