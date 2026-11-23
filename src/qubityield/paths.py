"""Resolve resources without depending on a hard-coded machine path."""

import os
from pathlib import Path


def project_root() -> Path:
    """Find the source checkout; QUBITYIELD_ROOT supports an alternate deployment layout."""
    override = os.environ.get("QUBITYIELD_ROOT")
    if override:
        return Path(override).expanduser().resolve()
    source_root = Path(__file__).resolve().parents[2]
    if (source_root / "pyproject.toml").is_file():
        return source_root
    current = Path.cwd()
    if (current / "data" / "case_facts.json").is_file():
        return current
    return source_root

