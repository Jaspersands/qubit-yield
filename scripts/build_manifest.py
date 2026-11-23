"""Hash submission artifacts, case inputs and source files for reviewable provenance."""

from __future__ import annotations

import hashlib
import json
import platform
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def main() -> None:
    paths = []
    for directory in ("src", "tests", "scripts", "data", "docs", "artifacts", "notebooks", "web/src", "web/public", "web/scripts"):
        paths.extend((ROOT / directory).rglob("*"))
    paths.extend(ROOT / name for name in (
        "pyproject.toml", "uv.lock", "web/package-lock.json", "README.md", "Makefile",
        "Dockerfile", ".github/workflows/ci.yml", "web/preview/index.html",
        "LICENSE", "CHANGELOG.md", ".gitignore", ".dockerignore", ".python-version", "web/package.json",
        "web/index.html", "web/tsconfig.json", "web/vite.config.ts", "web/vite.preview.config.ts",
    ))
    hashes = {}
    for path in sorted(set(paths)):
        if not path.is_file() or "__pycache__" in path.parts or path.name == "manifest.json":
            continue
        relative = path.relative_to(ROOT).as_posix()
        hashes[relative] = {"sha256": hashlib.sha256(path.read_bytes()).hexdigest(), "bytes": path.stat().st_size}
    output = ROOT / "artifacts" / "manifest.json"
    output.write_text(json.dumps({
        "schema_version": 1,
        "python": platform.python_version(),
        "algorithm": "SHA-256",
        "note": "Integrity manifest. Timestamps and PDF metadata can change on regeneration; scientific counts are seeded.",
        "files": hashes,
    }, indent=2) + "\n")
    print(f"Hashed {len(hashes)} files: {output}")


if __name__ == "__main__":
    main()

