"""Independent simulator cross-check; run from the repository root.

Usage: python scripts/validate_qiskit.py --shots 8192 --output artifacts/qiskit_validation.json
Requires pip install -e '.[research]'. No hardware account or QPU is used.
"""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
import json
import math
from pathlib import Path
import platform

import numpy as np

from qubityield.qiskit_adapter import exact_aer_probability, run_aer_benchmark
from qubityield.quantum import run_benchmark


def comparison(label, primary, reference_probability, reference_shots=None, metadata=None):
    p = primary["p_success"]
    variance = p * (1 - p) / primary["shots"]
    if reference_shots:
        variance += reference_probability * (1 - reference_probability) / reference_shots
    tolerance = 6 * math.sqrt(variance) + 1 / primary["shots"]
    difference = abs(p - reference_probability)
    return {
        "check": label,
        "primary_probability": p,
        "reference_probability": reference_probability,
        "absolute_difference": difference,
        "tolerance": tolerance,
        "criterion": "6 combined binomial standard errors plus 1/primary_shots",
        "primary_shots": primary["shots"],
        "reference_shots": reference_shots,
        "passed": difference <= tolerance,
        **(metadata or {}),
    }


def validate(shots: int = 8192, seeds: tuple[int, ...] = (7, 17, 29)) -> dict:
    import qiskit
    import qiskit_aer

    checks = []
    for mode in ("reported_total", "control_only"):
        for n in (2, 4):
            params = dict(
                n_qubits=n,
                layers=6,
                seed=29,
                gate_error=0.04,
                gate_duration_ns=420,
                t1_us=80,
                t2_us=120,
                noise_mode=mode,
                readout_error=0.015,
            )
            primary = run_benchmark(shots=max(shots, 32768), **params)
            exact = exact_aer_probability(**params)
            checks.append(
                comparison(
                    f"exact_{n}q_{mode}",
                    primary,
                    exact,
                    metadata={"reference": "Aer exact density matrix", **params},
                )
            )
        for seed in seeds:
            for label, error, duration in (("baseline", 0.01, 300), ("pulse", 0.005, 420)):
                params = dict(
                    n_qubits=20,
                    layers=20,
                    seed=seed,
                    gate_error=error,
                    gate_duration_ns=duration,
                    noise_mode=mode,
                )
                primary = run_benchmark(shots=shots, **params)
                aer = run_aer_benchmark(shots=shots, **params)
                result = comparison(
                    f"20q_{mode}_{label}_seed{seed}",
                    primary,
                    aer["p_success"],
                    shots,
                    {"reference": aer["backend"], "gate_count": aer["gate_count"], **params},
                )
                result["gate_count_preserved"] = aer["gate_count"] == 200
                result["entangling_depth"] = aer["entangling_depth"]
                result["parallel_layers_preserved"] = aer["entangling_depth"] == 20
                result["passed"] &= (
                    result["gate_count_preserved"] and result["parallel_layers_preserved"]
                )
                checks.append(result)
    return {
        "status": "passed" if all(row["passed"] for row in checks) else "failed",
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "hardware_execution": False,
        "versions": {
            "python": platform.python_version(),
            "numpy": np.__version__,
            "qiskit": qiskit.__version__,
            "qiskit_aer": qiskit_aer.__version__,
        },
        "description": (
            "Independent Aer reference on identical fixed circuits. Shot counts need not match: "
            "the simulators use different random generators. Agreement validates numerical "
            "implementation of the chosen channels, not their realism for a customer device."
        ),
        "checks": checks,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--shots", type=int, default=8192)
    parser.add_argument("--seeds", type=int, nargs="+", default=[7, 17, 29])
    parser.add_argument("--output", type=Path, default=Path("artifacts/qiskit_validation.json"))
    args = parser.parse_args()
    report = validate(args.shots, tuple(args.seeds))
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2, allow_nan=False) + "\n")
    print(f"Qiskit validation {report['status']}: {len(report['checks'])} checks; {args.output}")
    for row in report["checks"]:
        if not row["passed"]:
            print(
                f"FAILED {row['check']}: difference {row['absolute_difference']:.6f}, tolerance {row['tolerance']:.6f}"
            )
    return 0 if report["status"] == "passed" else 1


if __name__ == "__main__":
    raise SystemExit(main())
