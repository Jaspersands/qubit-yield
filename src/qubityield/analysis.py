"""Connect independently testable physics and economics, with explicit provenance."""

from __future__ import annotations

import copy
import hashlib
import importlib.metadata
import json
from datetime import datetime, timezone
from functools import lru_cache
from pathlib import Path
from typing import Any

from scipy.stats import beta

from qubityield import __version__
from qubityield.economics import evaluate_economics
from qubityield.models import Scenario
from qubityield.paths import project_root
from qubityield.quantum import run_benchmark

PHYSICAL_FIELDS = (
    "n_qubits", "layers", "shots", "seed", "baseline_gate_error", "pulse_gate_error",
    "baseline_gate_ns", "pulse_duration_increase", "t1_us", "t2_us", "noise_mode",
    "readout_error", "fixed_overhead_us",
)


def canonical_hash(value: Any) -> str:
    return hashlib.sha256(
        json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False).encode()
    ).hexdigest()


def physical_key(scenario: Scenario) -> tuple:
    return tuple(getattr(scenario, field) for field in PHYSICAL_FIELDS)


def _binomial_interval(successes: int, shots: int, alpha: float = 0.025) -> tuple:
    """Exact Clopper-Pearson bounds; 97.5% per arm gives a Bonferroni 95% pair."""
    low = 0.0 if successes == 0 else float(beta.ppf(alpha / 2, successes, shots - successes + 1))
    high = 1.0 if successes == shots else float(beta.ppf(1 - alpha / 2, successes + 1, shots - successes))
    return low, high


def _compute_benchmark(key: tuple) -> dict:
    physical = dict(zip(PHYSICAL_FIELDS, key, strict=True))
    shared = {
        name: physical[name]
        for name in ("n_qubits", "layers", "shots", "seed", "t1_us", "t2_us", "noise_mode", "readout_error")
    }
    baseline_duration = physical["baseline_gate_ns"]
    pulse_duration = baseline_duration * (1 + physical["pulse_duration_increase"])
    baseline = run_benchmark(**shared, gate_error=physical["baseline_gate_error"], gate_duration_ns=baseline_duration)
    pulse = run_benchmark(**shared, gate_error=physical["pulse_gate_error"], gate_duration_ns=pulse_duration)
    baseline_cycle = physical["fixed_overhead_us"] + shared["layers"] * baseline_duration / 1000
    pulse_cycle = physical["fixed_overhead_us"] + shared["layers"] * pulse_duration / 1000
    if baseline["p_success"] == 0:
        raise ValueError("No baseline successes were observed. Increase shots or reduce workload/noise before normalizing capacity.")
    if min(baseline_cycle, pulse_cycle) <= 0:
        raise ValueError("A shot cycle must have positive duration.")
    time_ratio = baseline_cycle / pulse_cycle
    base_low, base_high = _binomial_interval(baseline["successes"], baseline["shots"])
    pulse_low, pulse_high = _binomial_interval(pulse["successes"], pulse["shots"])
    return {
        "baseline": baseline,
        "pulse": pulse,
        "baseline_cycle_us": baseline_cycle,
        "pulse_cycle_us": pulse_cycle,
        "throughput_ratio": pulse["p_success"] / baseline["p_success"] * time_ratio,
        "throughput_ratio_ci_low": pulse_low / base_high * time_ratio,
        "throughput_ratio_ci_high": pulse_high / base_low * time_ratio if base_low > 0 else None,
        "ratio_interval_label": "Conservative 95% sampling bounds from simultaneous Clopper-Pearson intervals. Excludes model uncertainty.",
        "duration_model": "Parallel entangling layers plus explicit reset/readout/scheduling/local-gate overhead per shot.",
        "physical_fingerprint": canonical_hash(physical),
    }


@lru_cache(maxsize=32)
def _cached_benchmark(key: tuple) -> dict:
    return _compute_benchmark(key)


@lru_cache(maxsize=32)
def _cached_depth_curve(key: tuple) -> tuple[dict, ...]:
    physical = dict(zip(PHYSICAL_FIELDS, key, strict=True))
    depths = sorted(set((4, 8, 12, 16, 20, 28, 40, 60, physical["layers"])))
    shared = {
        name: physical[name]
        for name in ("n_qubits", "seed", "t1_us", "t2_us", "noise_mode", "readout_error")
    }
    shared["shots"] = min(physical["shots"], 4096)
    rows = []
    for layers in depths:
        base = run_benchmark(**shared, layers=layers, gate_error=physical["baseline_gate_error"], gate_duration_ns=physical["baseline_gate_ns"])
        pulse = run_benchmark(**shared, layers=layers, gate_error=physical["pulse_gate_error"], gate_duration_ns=physical["baseline_gate_ns"] * (1 + physical["pulse_duration_increase"]))
        rows.append({
            "layers": layers,
            "baseline": base["p_success"], "pulse": pulse["p_success"],
            "baseline_low": base["ci_low"], "baseline_high": base["ci_high"],
            "pulse_low": pulse["ci_low"], "pulse_high": pulse["ci_high"],
            "shots": shared["shots"], "seed": shared["seed"],
        })
    return tuple(rows)


def evaluate(scenario: Scenario, *, refresh: bool = False, include_depth: bool = True) -> dict:
    """Evaluate an immutable scenario; cached evidence always matches all physical inputs."""
    key = physical_key(scenario)
    benchmark = copy.deepcopy(_compute_benchmark(key) if refresh else _cached_benchmark(key))
    result = evaluate_economics(scenario, benchmark)
    result["scenario"] = scenario.model_dump(mode="json")
    # Preserve original raw counts and provenance, even if economics normalizes its own copy.
    result["benchmark"] = benchmark
    result["depth_curve"] = list(copy.deepcopy(_cached_depth_curve(key))) if include_depth else []
    result.setdefault("warnings", [])
    if scenario.noise_mode == "reported_total":
        for label, arm in (("Baseline", benchmark["baseline"]), ("Pulse", benchmark["pulse"])):
            if arm["gate_error"] < arm["twirled_relaxation_infidelity"]:
                result["warnings"].append(
                    f"{label}: reported total gate error is below the relaxation floor implied by the entered T1, T2 and gate duration. Validate those inputs together."
                )
    result["warnings"].append(
        "Mirror return is a benchmark proxy. A gain here does not establish customer application accuracy, billable demand, or quantum advantage."
    )
    facts_path = project_root() / "data" / "case_facts.json"
    case_hash = hashlib.sha256(facts_path.read_bytes()).hexdigest() if facts_path.exists() else None
    source_digest = hashlib.sha256()
    # QUBITYIELD_ROOT selects data/assets, not the Python implementation.
    # Hash the package actually executing, including in non-editable installs.
    for source in sorted(Path(__file__).resolve().parent.glob("*.py")):
        source_digest.update(source.name.encode())
        source_digest.update(source.read_bytes())
    evidence = {
        "experiment_id": "qy-" + canonical_hash(result["scenario"])[:12],
        "seed": scenario.seed,
        "shots": scenario.shots,
        "source": "simulated",
        "generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "model_version": __version__,
        "source_code_sha256": source_digest.hexdigest(),
        "case_facts_sha256": case_hash,
        "physical_fingerprint": benchmark["physical_fingerprint"],
        "scenario_sha256": canonical_hash(result["scenario"]),
        "versions": {p: importlib.metadata.version(p) for p in ("numpy", "scipy", "pydantic")},
        "backend": "NumPy Pauli-frame Clifford simulator",
        "hardware_executed": False,
        "uncertainty_scope": "Shot intervals are conditional on the selected circuit and noise model. Commercial ranges are assumptions, not calibrated probabilities.",
    }
    result["evidence"] = evidence
    # Reject NaNs/Infinity before exporting or serving results.
    json.dumps(result, allow_nan=False)
    return result


def save_analysis(result: dict, path) -> None:
    """Write human-reviewable JSON with no nonstandard numeric values."""
    from pathlib import Path

    destination = Path(path)
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(json.dumps(result, indent=2, allow_nan=False) + "\n", encoding="utf-8")

