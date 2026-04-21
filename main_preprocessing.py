"""Backward-compatible entry: full library pipeline lives in paper_tools.main_preprocessing."""

import runpy

if __name__ == "__main__":
    runpy.run_module("paper_tools.main_preprocessing", run_name="__main__")
