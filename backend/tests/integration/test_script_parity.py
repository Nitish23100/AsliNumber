"""Structural test: every Makefile target has a corresponding .ps1 script.

Per Requirement 15.1/15.2: Windows developers need a PowerShell
equivalent of every Makefile target. This is a structural/string check
(does the file exist, does it perform the same underlying command),
not a full execution test, since CI runners for this check are
Windows-optional per the design's Testing Strategy.
"""

import re
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parents[3]
_MAKEFILE_PATH = _REPO_ROOT / "Makefile"
_SCRIPTS_DIR = _REPO_ROOT / "scripts"

_TARGET_PATTERN = re.compile(r"^([a-zA-Z0-9_-]+):", re.MULTILINE)


def _makefile_targets() -> list[str]:
    content = _MAKEFILE_PATH.read_text(encoding="utf-8")
    return [t for t in _TARGET_PATTERN.findall(content) if t != ".PHONY"]


def test_every_makefile_target_has_a_ps1_script() -> None:
    for target in _makefile_targets():
        ps1_path = _SCRIPTS_DIR / f"{target}.ps1"
        assert ps1_path.exists(), f"Missing scripts/{target}.ps1 for Makefile target '{target}'"


def test_every_makefile_target_has_a_sh_script() -> None:
    for target in _makefile_targets():
        sh_path = _SCRIPTS_DIR / f"{target}.sh"
        assert sh_path.exists(), f"Missing scripts/{target}.sh for Makefile target '{target}'"


def test_ps1_and_sh_scripts_invoke_the_same_underlying_commands() -> None:
    # A lightweight structural check: for each script pair, confirm they
    # share at least one meaningful command token (e.g. "pytest", "ruff",
    # "npm", "docker compose", "app.cli") rather than asserting byte-for-byte
    # equivalence, since the two shells have different syntax for the same
    # operation.
    meaningful_tokens = ["pytest", "ruff", "npm", "docker compose", "app.cli", "pip install"]
    for target in _makefile_targets():
        ps1_content = (_SCRIPTS_DIR / f"{target}.ps1").read_text(encoding="utf-8")
        sh_content = (_SCRIPTS_DIR / f"{target}.sh").read_text(encoding="utf-8")
        ps1_tokens = {tok for tok in meaningful_tokens if tok in ps1_content}
        sh_tokens = {tok for tok in meaningful_tokens if tok in sh_content}
        assert ps1_tokens == sh_tokens, (
            f"scripts/{target}.ps1 and scripts/{target}.sh reference different "
            f"commands: {ps1_tokens} vs {sh_tokens}"
        )
