"""Optional, independently implemented Qiskit Aer reference for our workload.

Install ``qubityield[research]`` to use this module. Nothing here submits a job
to quantum hardware. Barriers preserve the specified compiled workload.
"""

from __future__ import annotations

from numbers import Integral

import numpy as np

from .quantum import NOISE_MODES, build_mirror_circuit, wilson_interval


def _qiskit_imports():
    try:
        from qiskit import QuantumCircuit
        from qiskit.quantum_info import PTM
        from qiskit_aer import AerSimulator
        from qiskit_aer.noise import (
            NoiseModel,
            ReadoutError,
            depolarizing_error,
            pauli_error,
            thermal_relaxation_error,
        )
    except ImportError as exc:
        raise ImportError(
            "Install optional validation tools: pip install 'qubityield[research]'"
        ) from exc
    return (
        QuantumCircuit,
        PTM,
        AerSimulator,
        NoiseModel,
        ReadoutError,
        depolarizing_error,
        pauli_error,
        thermal_relaxation_error,
    )


def to_qiskit_circuit(n_qubits: int = 20, layers: int = 20, seed: int = 7, *, measure: bool = True):
    """Export the identical seeded gate sequence with barriers around CX layers.

    Do not transpile away the identity mirror. The question is the fidelity
    of executing the fixed gate sequence, not computing an identity cheaply.
    Barriers separate whole disjoint-pair layers, not gates inside a layer:
    the case's ten simultaneous CXs must not become ten serial CXs.
    """
    QuantumCircuit, *_ = _qiskit_imports()
    gates = build_mirror_circuit(n_qubits, layers, seed)
    circuit = QuantumCircuit(n_qubits, n_qubits if measure else 0)
    entangling_count = 0
    gates_per_layer = n_qubits // 2
    for gate in gates:
        if gate.name == "cx" and entangling_count % gates_per_layer == 0:
            if not circuit.data or circuit.data[-1].operation.name != "barrier":
                circuit.barrier()
        getattr(circuit, gate.name)(*gate.qubits)
        if gate.name == "cx":
            entangling_count += 1
            if entangling_count % gates_per_layer == 0:
                circuit.barrier()
    if measure:
        circuit.measure(range(n_qubits), range(n_qubits))
    return circuit


def qiskit_noise_model(
    gate_error: float = 0.01,
    gate_duration_ns: float = 300,
    t1_us: float = 120,
    t2_us: float = 120,
    noise_mode: str = "reported_total",
    readout_error: float = 0.0,
):
    """Construct the reference channel without using our fault-rate helper.

    Control noise uses Aer depolarization, lambda=4r/3. In control_only mode,
    Qiskit's own thermal channel is converted to a Pauli transfer matrix and
    twirled by keeping its diagonal, rather than reusing our thermal formula.
    """
    (
        _,
        PTM,
        _,
        NoiseModel,
        ReadoutError,
        depolarizing_error,
        pauli_error,
        thermal_relaxation_error,
    ) = _qiskit_imports()
    if noise_mode not in NOISE_MODES:
        raise ValueError(f"noise_mode must be one of {NOISE_MODES}")
    values = (gate_error, gate_duration_ns, t1_us, t2_us, readout_error)
    if not all(np.isfinite(value) for value in values):
        raise ValueError("Noise parameters must be finite")
    if not 0 <= gate_error <= 0.8 or not 0 <= readout_error <= 1:
        raise ValueError("Gate infidelity must be in [0,0.8] and readout error in [0,1]")
    if gate_duration_ns < 0 or min(t1_us, t2_us) <= 0 or t2_us > 2 * t1_us:
        raise ValueError("Require nonnegative duration, positive T1/T2, and T2 <= 2*T1")
    channel = depolarizing_error(4 * gate_error / 3, 2)
    if noise_mode == "control_only":
        thermal = thermal_relaxation_error(t1_us * 1000, t2_us * 1000, gate_duration_ns)
        _, lx, ly, lz = np.diag(PTM(thermal).data).real
        probabilities = (
            np.array(
                [
                    1 + lx + ly + lz,
                    1 + lx - ly - lz,
                    1 - lx + ly - lz,
                    1 - lx - ly + lz,
                ]
            )
            / 4
        )
        probabilities = np.clip(probabilities, 0, 1)
        probabilities /= probabilities.sum()
        twirl = pauli_error(list(zip(("I", "X", "Y", "Z"), probabilities)))
        channel = channel.compose(twirl.tensor(twirl))
    model = NoiseModel()
    model.add_all_qubit_quantum_error(channel, ["cx"])
    if readout_error:
        model.add_all_qubit_readout_error(
            ReadoutError(
                [
                    [1 - readout_error, readout_error],
                    [readout_error, 1 - readout_error],
                ]
            )
        )
    return model


def run_aer_benchmark(
    n_qubits: int = 20,
    layers: int = 20,
    shots: int = 8192,
    seed: int = 7,
    gate_error: float = 0.01,
    gate_duration_ns: float = 300,
    t1_us: float = 120,
    t2_us: float = 120,
    noise_mode: str = "reported_total",
    readout_error: float = 0.0,
) -> dict:
    """Run Aer stabilizer simulation; this is not a QPU execution."""
    if isinstance(shots, bool) or not isinstance(shots, Integral) or not 1 <= shots <= 262144:
        raise ValueError("shots must be an integer between 1 and 262144")
    _, _, AerSimulator, *_ = _qiskit_imports()
    circuit = to_qiskit_circuit(n_qubits, layers, seed)
    model = qiskit_noise_model(
        gate_error, gate_duration_ns, t1_us, t2_us, noise_mode, readout_error
    )
    simulator = AerSimulator(
        method="stabilizer",
        noise_model=model,
        fusion_enable=False,
        enable_truncation=False,
        max_parallel_threads=2,
    )
    counts = simulator.run(circuit, shots=int(shots), seed_simulator=seed).result().get_counts()
    successes = int(counts.get("0" * n_qubits, 0))
    low, high = wilson_interval(successes, int(shots))
    return {
        "p_success": successes / shots,
        "successes": successes,
        "shots": int(shots),
        "ci_low": low,
        "ci_high": high,
        "n_qubits": n_qubits,
        "layers": layers,
        "gate_count": int(circuit.count_ops().get("cx", 0)),
        "entangling_depth": circuit.depth(lambda instruction: instruction.operation.name == "cx"),
        "seed": seed,
        "gate_error": gate_error,
        "gate_duration_ns": gate_duration_ns,
        "noise_mode": noise_mode,
        "readout_error": readout_error,
        "backend": "Qiskit Aer stabilizer simulator",
        "hardware_execution": False,
    }


def exact_aer_probability(
    n_qubits: int = 4,
    layers: int = 6,
    seed: int = 7,
    gate_error: float = 0.01,
    gate_duration_ns: float = 300,
    t1_us: float = 120,
    t2_us: float = 120,
    noise_mode: str = "reported_total",
    readout_error: float = 0.0,
) -> float:
    """Exact small-circuit density matrix followed by classical readout noise."""
    if not 2 <= n_qubits <= 8:
        raise ValueError("Exact density-matrix checks are restricted to 2-8 qubits")
    _, _, AerSimulator, *_ = _qiskit_imports()
    circuit = to_qiskit_circuit(n_qubits, layers, seed, measure=False)
    circuit.save_density_matrix()
    # Readout is applied exactly below, since no sampled measurements occur.
    model = qiskit_noise_model(gate_error, gate_duration_ns, t1_us, t2_us, noise_mode, 0)
    simulator = AerSimulator(
        method="density_matrix",
        noise_model=model,
        fusion_enable=False,
        enable_truncation=False,
        max_parallel_threads=2,
    )
    density = np.asarray(simulator.run(circuit, shots=1).result().data(0)["density_matrix"])
    if not 0 <= readout_error <= 1 or not np.isfinite(readout_error):
        raise ValueError("readout_error must be finite and in [0,1]")
    weights = np.array(
        [
            readout_error ** state.bit_count()
            * (1 - readout_error) ** (n_qubits - state.bit_count())
            for state in range(2**n_qubits)
        ]
    )
    return float(np.dot(density.diagonal().real, weights))
