"""Bounded JSON input, portable comparisons and reviewable integrity checks."""

from __future__ import annotations

import csv
import hashlib
import json
import math
import re
from pathlib import Path, PurePosixPath
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, field_validator

from qubityield.analysis import evaluate
from qubityield.models import Scenario

MAX_INPUT_BYTES = 1_048_576


def _unique_object(pairs: list[tuple[str, Any]]) -> dict:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise ValueError(f"Duplicate JSON key: {key}")
        result[key] = value
    return result


def _finite_float(value: str) -> float:
    number = float(value)
    if not math.isfinite(number):
        raise ValueError("JSON numbers must be finite")
    return number


def _reject_constant(value: str) -> None:
    raise ValueError(f"Nonstandard JSON number: {value}")


def read_json(path: Path, *, max_bytes: int = MAX_INPUT_BYTES) -> Any:
    """Read bounded UTF-8 JSON without duplicate keys, NaN or infinity."""
    with path.open("rb") as source:
        data = source.read(max_bytes + 1)
    if len(data) > max_bytes:
        raise ValueError(f"{path} exceeds the {max_bytes:,}-byte input limit")
    try:
        parsed = json.loads(data.decode("utf-8-sig"), object_pairs_hook=_unique_object,
                            parse_float=_finite_float, parse_constant=_reject_constant)
        pending = [(parsed, 0)]
        while pending:
            value, depth = pending.pop()
            if depth > 32:
                raise ValueError("JSON nesting exceeds the 32-level input limit")
            if isinstance(value, dict):
                pending.extend((child, depth + 1) for child in value.values())
            elif isinstance(value, list):
                pending.extend((child, depth + 1) for child in value)
        return parsed
    except (UnicodeError, RecursionError) as exc:
        raise ValueError("Input must be reasonably nested UTF-8 JSON") from exc


class NamedScenario(BaseModel):
    model_config = ConfigDict(extra="forbid")
    name: str = Field(min_length=1, max_length=120)
    scenario: Scenario

    @field_validator("name")
    @classmethod
    def meaningful_name(cls, value: str) -> str:
        if not value.strip() or any(ord(char) < 32 for char in value):
            raise ValueError("Scenario names must contain visible text and no control characters")
        return value.strip()


def compare_scenarios(values: Any) -> dict:
    """Validate every item before computing a bounded batch of named scenarios."""
    if not isinstance(values, list) or not 1 <= len(values) <= 16:
        raise ValueError("A comparison must be a JSON list of 1 to 16 named scenarios")
    scenarios = [NamedScenario.model_validate(value) for value in values]
    names = [item.name for item in scenarios]
    if len(set(names)) != len(names):
        raise ValueError("Comparison scenario names must be unique")
    rows, analyses = [], []
    for item in scenarios:
        result = evaluate(item.scenario, include_depth=False)
        options = {option["id"]: option for option in result["options"]}
        # Baseline is deliberately first, so exact ties choose no purchase.
        winner = max(options.values(), key=lambda option: (option["customer_npv_usd"], option["id"] == "baseline"))
        rows.append({
            "name": item.name,
            "scenario_sha256": result["evidence"]["scenario_sha256"],
            "physical_fingerprint": result["evidence"]["physical_fingerprint"],
            "value_mode": item.scenario.value_mode,
            "validation_priority": result["recommendation"]["id"],
            "best_option_after_fees": winner["id"],
            "best_customer_npv_usd": winner["customer_npv_usd"],
            "throughput_ratio": result["benchmark"]["throughput_ratio"],
            "calibration_npv_usd": options["calibration"]["customer_npv_usd"],
            "pulse_npv_usd": options["pulse"]["customer_npv_usd"],
            "controls_npv_usd": options["control"]["customer_npv_usd"],
        })
        analyses.append({"name": item.name, "result": result})
    return {
        "schema_version": 1, "kind": "batch_comparison", "count": len(rows),
        "comparison": rows, "analyses": analyses,
        "interpretation": "Named assumption scenarios, not random draws or probabilities. Validation priority can differ from the best purchase after fees. Each saved analysis preserves its exact inputs and provenance.",
    }


def safe_csv_cell(value: Any) -> Any:
    """Keep untrusted text inert in spreadsheet applications; retain numeric types."""
    if isinstance(value, str) and value.lstrip(" \t\r\n").startswith(("=", "+", "-", "@")):
        return "'" + value
    return value


def write_comparison_csv(result: dict, path: Path) -> None:
    rows = result["comparison"]
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as target:
        writer = csv.DictWriter(target, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows({key: safe_csv_cell(value) for key, value in row.items()} for row in rows)


def _resolved_path(path: Path) -> Path:
    try:
        return path.resolve()
    except (OSError, RuntimeError) as exc:
        raise ValueError(f"Cannot resolve path safely: {path}") from exc


def require_distinct_outputs(first: Path, second: Path) -> None:
    """Prevent a CSV export from overwriting its JSON evidence through an alias."""
    if _resolved_path(first) == _resolved_path(second) or (
        first.exists() and second.exists() and first.samefile(second)
    ):
        raise ValueError("JSON and CSV output destinations must be different files")


def verify_manifest(manifest: dict, root: Path) -> dict:
    """Check only declared project files, rejecting paths outside the given root.

    This detects accidental modification. It is not a signature and does not
    establish trust in a manifest received with untrusted files.
    """
    if not isinstance(manifest, dict) or manifest.get("schema_version") != 1 or manifest.get("algorithm") != "SHA-256":
        raise ValueError("Expected a schema-version-1 SHA-256 manifest")
    files = manifest.get("files")
    if not isinstance(files, dict) or not 1 <= len(files) <= 10_000:
        raise ValueError("Manifest must contain 1 to 10,000 file entries")
    base = _resolved_path(root)
    if not base.is_dir():
        raise ValueError("Manifest root must be a directory")
    # Validate the whole manifest before touching any declared file.
    validated = []
    for name, expected in files.items():
        if not isinstance(name, str) or not name or "\\" in name:
            raise ValueError("Manifest paths must be nonempty relative POSIX paths")
        relative = PurePosixPath(name)
        if relative.is_absolute() or any(part in ("", ".", "..") for part in name.split("/")):
            raise ValueError(f"Unsafe manifest path: {name}")
        if not isinstance(expected, dict) or not isinstance(expected.get("sha256"), str) or not re.fullmatch(r"[0-9a-f]{64}", expected["sha256"]):
            raise ValueError(f"Invalid SHA-256 entry: {name}")
        size = expected.get("bytes")
        if isinstance(size, bool) or not isinstance(size, int) or size < 0:
            raise ValueError(f"Invalid byte count: {name}")
        destination = base.joinpath(*relative.parts)
        if not _resolved_path(destination).is_relative_to(base):
            raise ValueError(f"Manifest path leaves the project root: {name}")
        validated.append((name, destination, expected))
    failures, verified = [], 0
    for name, destination, expected in validated:
        if not destination.is_file():
            failures.append({"path": name, "reason": "missing or not a regular file"})
            continue
        digest, size = hashlib.sha256(), 0
        with destination.open("rb") as source:
            while chunk := source.read(1_048_576):
                digest.update(chunk)
                size += len(chunk)
        if size != expected["bytes"] or digest.hexdigest() != expected["sha256"]:
            failures.append({"path": name, "reason": "content or size changed"})
        else:
            verified += 1
    return {"valid": not failures, "checked": len(validated), "verified": verified,
            "failures": failures, "scope": "Declared files only. This integrity check is not a cryptographic signature and does not report unlisted files."}
