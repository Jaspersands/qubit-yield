"""Seeded, noisy Clifford mirror benchmarks for the calibration decision.

This is a Pauli-frame simulator, not a product-of-fidelities proxy.  Every
trajectory propagates actual Pauli faults through a Clifford circuit and its
inverse.  The final ideal state is |0...0>, so a trajectory succeeds exactly
when its final X-error frame is zero.  Cancellation and propagation of faults
are therefore included.

The default interpretation of ``gate_error`` is *total average gate
infidelity*.  T1/T2 are not applied a second time.  ``control_only`` is an
explicit alternative interpretation with Pauli-twirled relaxation added.
See docs/quantum-method.md for assumptions, equations, and limitations.
"""

from __future__ import annotations

import math
from collections.abc import Iterable
from dataclasses import dataclass
from numbers import Integral, Real
from typing import Literal

import numpy as np

NoiseMode = Literal["reported_total", "control_only"]
NOISE_MODES = ("reported_total", "control_only")
MAX_TRAJECTORY_GATE_UPDATES = 150_000_000


@dataclass(frozen=True, slots=True)
class Gate:
    """A Clifford gate; qubit indices use little-endian convention."""

    name: str
    qubits: tuple[int, ...]

    def inverse(self) -> Gate:
        if self.name == "s":
            return Gate("sdg", self.qubits)
        if self.name == "sdg":
            return Gate("s", self.qubits)
        return self


def _integer(value: int, name: str, minimum: int, maximum: int) -> int:
    if isinstance(value, bool) or not isinstance(value, Integral):
        raise ValueError(f"{name} must be an integer")  # noqa: TRY004 - uniform public validation errors
    value = int(value)
    if not minimum <= value <= maximum:
        raise ValueError(f"{name} must be between {minimum} and {maximum}")
    return value


def _real(value: float, name: str, minimum: float, maximum: float) -> float:
    if isinstance(value, bool) or not isinstance(value, Real):
        raise ValueError(f"{name} must be a finite number")  # noqa: TRY004 - uniform public validation errors
    value = float(value)
    if not math.isfinite(value) or not minimum <= value <= maximum:
        raise ValueError(f"{name} must be between {minimum} and {maximum}")
    return value


def _circuit_inputs(n_qubits: int, layers: int, seed: int) -> tuple[int, int, int]:
    n_qubits = _integer(n_qubits, "n_qubits", 2, 100)
    layers = _integer(layers, "layers", 0, 400)
    seed = _integer(seed, "seed", 0, 2**32 - 1)
    if n_qubits % 2:
        raise ValueError("n_qubits must be even for disjoint perfect matchings")
    if layers % 2:
        raise ValueError("layers must be even for a forward/inverse mirror")
    return n_qubits, layers, seed


def build_mirror_circuit(n_qubits: int = 20, layers: int = 20, seed: int = 7) -> tuple[Gate, ...]:
    """Build randomized local Cliffords and ring-matching CXs, then invert.

    ``layers`` counts *all* entangling layers, including the inverse.  Each
    layer contains n_qubits/2 CX gates on disjoint pairs.  Alternating nearest
    neighbor matchings on a ring avoid an all-to-all connectivity assumption.
    Local gates are sampled from six H/S words, not uniformly from the full
    Clifford group.  Their inverses are retained; algebraic cancellation by a
    transpiler would destroy this intended hardware benchmark.
    """
    n_qubits, layers, seed = _circuit_inputs(n_qubits, layers, seed)
    rng = np.random.default_rng(np.random.SeedSequence([seed, 0xC1AC017]))
    words = ((), ("h",), ("s",), ("h", "s"), ("s", "h"), ("h", "s", "h"))
    forward: list[Gate] = []
    for layer in range(layers // 2):
        for qubit, choice in enumerate(rng.integers(0, len(words), n_qubits)):
            forward.extend(Gate(name, (qubit,)) for name in words[int(choice)])
        offset = layer % 2
        for pair in range(n_qubits // 2):
            q0 = (2 * pair + offset) % n_qubits
            q1 = (q0 + 1) % n_qubits
            if rng.integers(0, 2):
                q0, q1 = q1, q0
            forward.append(Gate("cx", (q0, q1)))
    return tuple(forward + [gate.inverse() for gate in reversed(forward)])


def pauli_error_probability(gate_error: float) -> float:
    """Convert 2-qubit average infidelity r to nonidentity-Pauli rate 5r/4.

    For dimension d=4, F_avg=(d*p_identity+1)/(d+1).  The channel is CPTP
    for r in [0, 0.8]; r=0.75 gives complete depolarization.
    """
    return 1.25 * _real(gate_error, "gate_error", 0.0, 0.8)


def relaxation_pauli_probabilities(
    gate_duration_ns: float, t1_us: float, t2_us: float
) -> tuple[float, float, float, float]:
    """Pauli twirl of thermal relaxation, returned in I, X, Y, Z order.

    This preserves Bloch contraction but drops amplitude damping's affine
    shift towards |0>.  It is deliberately an approximation, not an exact
    amplitude-damping channel.
    """
    duration = _real(gate_duration_ns, "gate_duration_ns", 0.0, 1_000_000.0)
    t1 = _real(t1_us, "t1_us", 0.001, 1_000_000.0)
    t2 = _real(t2_us, "t2_us", 0.001, 1_000_000.0)
    if t2 > 2.0 * t1:
        raise ValueError("Physical coherence times require t2_us <= 2*t1_us")
    a = math.exp(-duration / (1000.0 * t1))
    b = math.exp(-duration / (1000.0 * t2))
    probabilities = ((1 + 2 * b + a) / 4, (1 - a) / 4, (1 - a) / 4, (1 - 2 * b + a) / 4)
    return tuple(max(0.0, float(p)) for p in probabilities)


def effective_gate_infidelity(
    gate_error: float,
    gate_duration_ns: float = 300,
    t1_us: float = 120,
    t2_us: float = 120,
    noise_mode: NoiseMode = "reported_total",
) -> float:
    """Average infidelity after the explicitly selected channel composition."""
    q = pauli_error_probability(gate_error)
    p_identity = relaxation_pauli_probabilities(gate_duration_ns, t1_us, t2_us)[0]
    if noise_mode not in NOISE_MODES:
        raise ValueError(f"noise_mode must be one of {NOISE_MODES}")
    if noise_mode == "reported_total":
        return float(gate_error)
    thermal_identity = p_identity**2
    combined_identity = (1 - q) * thermal_identity + (q / 15) * (1 - thermal_identity)
    return 0.8 * (1 - combined_identity)


def wilson_interval(
    successes: int, shots: int, z: float = 1.959963984540054
) -> tuple[float, float]:
    """Two-sided Wilson binomial interval (95% by default)."""
    shots = _integer(shots, "shots", 1, 2**53)
    successes = _integer(successes, "successes", 0, shots)
    z = _real(z, "z", 0.0, 20.0)
    p = successes / shots
    denominator = 1 + z * z / shots
    center = (p + z * z / (2 * shots)) / denominator
    radius = z / denominator * math.sqrt(p * (1 - p) / shots + z * z / (4 * shots**2))
    low = 0.0 if successes == 0 else max(0.0, center - radius)
    high = 1.0 if successes == shots else min(1.0, center + radius)
    return low, high


def _apply_two_qubit_pauli(
    x: np.ndarray,
    z: np.ndarray,
    q0: int,
    q1: int,
    probability: float,
    rng: np.random.Generator,
) -> None:
    # Fixed-size random draws keep common randomness aligned when comparing
    # different gate-error rates on the same seed.  Codes 1..15 enumerate all
    # nonidentity two-qubit Paulis; phases do not change a measurement.
    hits = rng.random(len(x)) < probability
    codes = rng.integers(1, 16, len(x), dtype=np.uint8)
    rows = np.flatnonzero(hits)
    codes = codes[rows]
    x[rows, q0] ^= (codes & 1) != 0
    z[rows, q0] ^= (codes & 2) != 0
    x[rows, q1] ^= (codes & 4) != 0
    z[rows, q1] ^= (codes & 8) != 0


def _apply_relaxation_twirl(
    x: np.ndarray,
    z: np.ndarray,
    qubit: int,
    probabilities: tuple[float, float, float, float],
    rng: np.random.Generator,
) -> None:
    # I, X, Y, Z have (x,z) = (0,0), (1,0), (1,1), (0,1).
    codes = np.searchsorted(np.cumsum(probabilities), rng.random(len(x)), side="right")
    x[:, qubit] ^= (codes == 1) | (codes == 2)
    z[:, qubit] ^= (codes == 2) | (codes == 3)


def run_benchmark(
    n_qubits: int = 20,
    layers: int = 20,
    shots: int = 8192,
    seed: int = 7,
    gate_error: float = 0.01,
    gate_duration_ns: float = 300,
    t1_us: float = 120,
    t2_us: float = 120,
    noise_mode: NoiseMode = "reported_total",
    readout_error: float = 0.0,
) -> dict:
    """Run a genuine noisy mirror circuit and return JSON-serializable evidence.

    Every shot starts in |0...0>.  Randomness is reproducible for a fixed seed
    and supported NumPy version.  The reported confidence interval quantifies
    shot noise for this circuit, not uncertainty about a customer workload.
    T1/T2 affect the channel only in ``control_only`` mode.  In the default
    mode, duration affects separately modeled throughput and is recorded here.
    """
    n_qubits, layers, seed = _circuit_inputs(n_qubits, layers, seed)
    shots = _integer(shots, "shots", 1, 262_144)
    readout_error = _real(readout_error, "readout_error", 0.0, 1.0)
    gate_count = n_qubits * layers // 2
    if shots * max(1, gate_count) > MAX_TRAJECTORY_GATE_UPDATES:
        raise ValueError("Requested simulation is too large; reduce shots, layers, or qubits")
    q = pauli_error_probability(gate_error)
    thermal = relaxation_pauli_probabilities(gate_duration_ns, t1_us, t2_us)
    effective_error = effective_gate_infidelity(
        gate_error, gate_duration_ns, t1_us, t2_us, noise_mode
    )
    circuit = build_mirror_circuit(n_qubits, layers, seed)
    rng = np.random.default_rng(np.random.SeedSequence([seed, 0x5A07]))
    x = np.zeros((shots, n_qubits), dtype=np.bool_)
    z = np.zeros_like(x)
    for gate in circuit:
        if gate.name == "h":
            qubit = gate.qubits[0]
            temporary = x[:, qubit].copy()
            x[:, qubit] = z[:, qubit]
            z[:, qubit] = temporary
        elif gate.name in ("s", "sdg"):
            qubit = gate.qubits[0]
            z[:, qubit] ^= x[:, qubit]
        else:
            control, target = gate.qubits
            x[:, target] ^= x[:, control]
            z[:, control] ^= z[:, target]
            _apply_two_qubit_pauli(x, z, control, target, q, rng)
            if noise_mode == "control_only":
                _apply_relaxation_twirl(x, z, control, thermal, rng)
                _apply_relaxation_twirl(x, z, target, thermal, rng)
    if readout_error:
        x ^= rng.random(x.shape) < readout_error
    successes = int(np.count_nonzero(~np.any(x, axis=1)))
    low, high = wilson_interval(successes, shots)
    return {
        "p_success": successes / shots,
        "successes": successes,
        "shots": shots,
        "ci_low": low,
        "ci_high": high,
        "gate_count": gate_count,
        "layers": layers,
        "n_qubits": n_qubits,
        "seed": seed,
        "gate_error": float(gate_error),
        "effective_gate_error": effective_error,
        "gate_duration_ns": float(gate_duration_ns),
        "entangling_duration_us": layers * float(gate_duration_ns) / 1000,
        "t1_us": float(t1_us),
        "t2_us": float(t2_us),
        "noise_mode": noise_mode,
        "readout_error": readout_error,
        "twirled_relaxation_infidelity": 0.8 * (1 - thermal[0] ** 2),
        "metric": "all-zero return probability of the specified Clifford mirror",
        "interval": "95% Wilson interval; shot noise conditional on this circuit",
        "model": "Pauli-frame Monte Carlo on a ring-connected Clifford mirror",
    }


def compare_benchmarks(
    seeds: Iterable[int] = (7, 17, 29, 43, 71),
    n_qubits: int = 20,
    layers: int = 20,
    shots: int = 8192,
    baseline_error: float = 0.01,
    optimized_error: float = 0.005,
    baseline_duration_ns: float = 300,
    optimized_duration_ns: float = 420,
    t1_us: float = 120,
    t2_us: float = 120,
    noise_mode: NoiseMode = "reported_total",
    readout_error: float = 0.0,
) -> dict:
    """Compare both proposals on the exact same predeclared circuit seeds.

    Mean/range across circuits are reported separately from per-circuit shot
    intervals.  No claim about a general workload distribution is made.
    """
    seeds = tuple(_integer(seed, "seed", 0, 2**32 - 1) for seed in seeds)
    if not 1 <= len(seeds) <= 64 or len(set(seeds)) != len(seeds):
        raise ValueError("Provide between 1 and 64 distinct circuit seeds")
    output: dict = {"seeds": list(seeds), "noise_mode": noise_mode}
    for name, error, duration in (
        ("baseline", baseline_error, baseline_duration_ns),
        ("optimized", optimized_error, optimized_duration_ns),
    ):
        runs = [
            run_benchmark(
                n_qubits=n_qubits,
                layers=layers,
                shots=shots,
                seed=seed,
                gate_error=error,
                gate_duration_ns=duration,
                t1_us=t1_us,
                t2_us=t2_us,
                noise_mode=noise_mode,
                readout_error=readout_error,
            )
            for seed in seeds
        ]
        probabilities = np.array([run["p_success"] for run in runs])
        output[name] = {
            "runs": runs,
            "mean_success": float(np.mean(probabilities)),
            "min_success": float(np.min(probabilities)),
            "max_success": float(np.max(probabilities)),
            "circuit_standard_deviation": float(np.std(probabilities, ddof=1))
            if len(runs) > 1
            else 0.0,
            "total_shots": shots * len(runs),
            "total_successes": sum(run["successes"] for run in runs),
        }
    baseline = output["baseline"]["mean_success"]
    optimized = output["optimized"]["mean_success"]
    output["success_ratio"] = optimized / baseline if baseline > 0 else None
    output["interpretation"] = (
        "Specified mirror workload only. Per-run Wilson intervals cover shot noise; "
        "circuit ranges expose variation across the chosen seeds. Neither establishes "
        "a customer application success probability."
    )
    return output


def depth_sweep(
    depths: Iterable[int] = (4, 8, 12, 16, 20, 28, 40, 60),
    shots: int = 4096,
    seed: int = 7,
    n_qubits: int = 20,
    noise_mode: NoiseMode = "reported_total",
    baseline_error: float = 0.01,
    optimized_error: float = 0.005,
    baseline_duration_ns: float = 300,
    optimized_duration_ns: float = 420,
    t1_us: float = 120,
    t2_us: float = 120,
) -> list[dict]:
    """Depth scaling for one fixed seed per depth; includes each shot interval."""
    depths = tuple(depths)
    if not 1 <= len(depths) <= 64:
        raise ValueError("Provide between 1 and 64 depths")
    rows = []
    for layers in depths:
        row: dict = {"layers": int(layers)}
        for name, error, duration in (
            ("baseline", baseline_error, baseline_duration_ns),
            ("optimized", optimized_error, optimized_duration_ns),
        ):
            result = run_benchmark(
                n_qubits=n_qubits,
                layers=layers,
                shots=shots,
                seed=seed,
                gate_error=error,
                gate_duration_ns=duration,
                t1_us=t1_us,
                t2_us=t2_us,
                noise_mode=noise_mode,
            )
            row[name] = result
        rows.append(row)
    return rows
