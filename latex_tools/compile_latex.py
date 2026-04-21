"""
LaTeX compilation utility. Tries latexmk first, falls back to two pdflatex passes
(needed for cross-references and bibliography).

Returns (success: bool, pdf_path: str | None, log: str).
"""

import os
import subprocess
import shutil
from pathlib import Path


def _find_compiler():
    """Return the best available LaTeX compiler, or None."""
    for cmd in ("latexmk", "pdflatex"):
        if shutil.which(cmd):
            return cmd
    return None


def compile(tex_path: str, clean: bool = True) -> tuple:
    """
    Compile tex_path to PDF.
    Returns (success, pdf_path_or_None, log_text).
    """
    tex_path = Path(tex_path).resolve()
    tex_dir  = str(tex_path.parent)
    tex_name = tex_path.name
    pdf_path = tex_path.with_suffix(".pdf")

    compiler = _find_compiler()
    if compiler is None:
        return False, None, (
            "No LaTeX compiler found. Install MiKTeX (https://miktex.org) or "
            "TeX Live and ensure pdflatex/latexmk is on PATH."
        )

    if compiler == "latexmk":
        cmd = ["latexmk", "-pdf", "-interaction=nonstopmode", "-halt-on-error", tex_name]
    else:
        # pdflatex needs two passes for \ref / bibliography
        cmd = ["pdflatex", "-interaction=nonstopmode", "-halt-on-error", tex_name]

    try:
        # First pass
        r1 = subprocess.run(cmd, cwd=tex_dir, capture_output=True, text=True, timeout=90)
        if compiler == "pdflatex" and r1.returncode == 0:
            # Second pass to resolve references
            subprocess.run(cmd, cwd=tex_dir, capture_output=True, text=True, timeout=90)

        log = r1.stdout + r1.stderr
        success = r1.returncode == 0 and pdf_path.exists()

        if clean and compiler == "latexmk":
            # latexmk can clean auxiliary files
            subprocess.run(
                ["latexmk", "-c", tex_name],
                cwd=tex_dir, capture_output=True, timeout=30
            )
        elif clean:
            for ext in (".aux", ".log", ".out", ".toc", ".fls", ".fdb_latexmk"):
                aux = tex_path.with_suffix(ext)
                if aux.exists():
                    aux.unlink()

        return success, str(pdf_path) if success else None, log

    except FileNotFoundError:
        return False, None, f"{compiler} not found on PATH."
    except subprocess.TimeoutExpired:
        return False, None, "LaTeX compilation timed out (>90s)."
    except Exception as e:
        return False, None, str(e)


def is_available() -> bool:
    return _find_compiler() is not None


if __name__ == "__main__":
    ok = is_available()
    print("latex_tools.compile_latex: LaTeX compiler on PATH:", "yes" if ok else "no")
