"""Independent density-matrix checks and physical invariants of the simulator."""

import json
import math
import unittest

import numpy as np

from qubityield.quantum import (
    build_mirror_circuit,
    compare_benchmarks,
    effective_gate_infidelity,
    pauli_error_probability,
    relaxation_pauli_probabilities,
    run_benchmark,
    wilson_interval,
)

IDENTITY = np.eye(2, dtype=complex)
X = np.array([[0, 1], [1, 0]], dtype=complex)
Y = np.array([[0, -1j], [1j, 0]], dtype=complex)
Z = np.diag([1, -1]).astype(complex)
H = np.array([[1, 1], [1, -1]], dtype=complex) / np.sqrt(2)
S = np.diag([1, 1j]).astype(complex)


def one_qubit_operator(matrix, qubit, n):
    """Independent dense operator with qubit 0 as the least significant bit."""
    result = np.ones((1, 1), dtype=complex)
    for q in reversed(range(n)):
        result = np.kron(result, matrix if q == qubit else IDENTITY)
    return result


def gate_operator(gate, n):
    if gate.name != "cx":
        matrix = {"h": H, "s": S, "sdg": S.conj().T}[gate.name]
        return one_qubit_operator(matrix, gate.qubits[0], n)
    control, target = gate.qubits
    result = np.zeros((2**n, 2**n), dtype=complex)
    for state in range(2**n):
        result[state ^ (1 << target) if state & (1 << control) else state, state] = 1
    return result


def density_matrix_reference(n, layers, seed, error, duration, t1, t2, mode, readout=0):
    """Small-system Kraus channel oracle, separate from Pauli-frame propagation."""
    rho = np.zeros((2**n, 2**n), dtype=complex)
    rho[0, 0] = 1
    # Use the depolarizing parameter lambda and all 16 Paulis, rather than the
    # simulator's nonidentity-fault formulation.  This catches a factor error.
    lam = 4 * error / 3
    paulis = (IDENTITY, X, Y, Z)
    thermal = relaxation_pauli_probabilities(duration, t1, t2)
    for gate in build_mirror_circuit(n, layers, seed):
        operator = gate_operator(gate, n)
        rho = operator @ rho @ operator.conj().T
        if gate.name == "cx":
            q0, q1 = gate.qubits
            mixed = np.zeros_like(rho)
            for p0 in paulis:
                for p1 in paulis:
                    operator = one_qubit_operator(p0, q0, n) @ one_qubit_operator(p1, q1, n)
                    mixed += operator @ rho @ operator.conj().T / 16
            rho = (1 - lam) * rho + lam * mixed
            if mode == "control_only":
                for qubit in (q0, q1):
                    rho = sum(
                        probability
                        * (
                            one_qubit_operator(pauli, qubit, n)
                            @ rho
                            @ one_qubit_operator(pauli, qubit, n).conj().T
                        )
                        for probability, pauli in zip(thermal, paulis)
                    )
    weights = np.array(
        [
            readout ** state.bit_count() * (1 - readout) ** (n - state.bit_count())
            for state in range(2**n)
        ]
    )
    return float(np.dot(np.diag(rho).real, weights))


class QuantumBenchmarkTests(unittest.TestCase):
    def test_mirror_is_identity_on_an_arbitrary_state(self):
        rng = np.random.default_rng(56)
        for n in (2, 4):
            initial = rng.normal(size=2**n) + 1j * rng.normal(size=2**n)
            initial /= np.linalg.norm(initial)
            state = initial.copy()
            for gate in build_mirror_circuit(n, 10, 19):
                state = gate_operator(gate, n) @ state
            np.testing.assert_allclose(state, initial, atol=1e-12)

    def test_case_workload_gate_count(self):
        circuit = build_mirror_circuit()
        self.assertEqual(sum(g.name == "cx" for g in circuit), 200)
        self.assertEqual(run_benchmark(shots=100)["gate_count"], 200)

    def test_ring_connections_only(self):
        for gate in build_mirror_circuit(20, 20, 7):
            if gate.name == "cx":
                difference = abs(gate.qubits[0] - gate.qubits[1])
                self.assertIn(difference, (1, 19))

    def test_each_layer_is_a_disjoint_complete_matching(self):
        for n in (2, 4, 20):
            gates = [gate for gate in build_mirror_circuit(n, 20, 7) if gate.name == "cx"]
            for start in range(0, len(gates), n // 2):
                layer = gates[start : start + n // 2]
                qubits = [qubit for gate in layer for qubit in gate.qubits]
                self.assertEqual(sorted(qubits), list(range(n)))

    def test_noiseless_is_certain_even_with_nontrivial_inverse(self):
        for n in (2, 4, 20):
            result = run_benchmark(n_qubits=n, gate_error=0, shots=512)
            self.assertEqual(result["successes"], 512)
            self.assertEqual(result["p_success"], 1)

    def test_no_double_counting_coherence(self):
        a = run_benchmark(shots=1024, gate_duration_ns=300, noise_mode="reported_total")
        b = run_benchmark(shots=1024, gate_duration_ns=420, noise_mode="reported_total")
        self.assertEqual(a["successes"], b["successes"])
        self.assertEqual(a["effective_gate_error"], 0.01)

    def test_average_infidelity_conversion_from_kraus_trace_formula(self):
        for r in (0, 0.005, 0.01, 0.2, 0.75, 0.8):
            q = pauli_error_probability(r)
            # Only identity Kraus operator has nonzero trace. d=4.
            average_fidelity = (16 * (1 - q) + 4) / 20
            self.assertAlmostEqual(1 - average_fidelity, r)

    def test_matches_independent_density_matrix(self):
        cases = [
            (2, 6, 13, 0.06, 300, 120, 120, "reported_total", 0),
            (4, 6, 17, 0.04, 300, 120, 120, "reported_total", 0.015),
            (4, 4, 29, 0.02, 420, 8, 12, "control_only", 0),
        ]
        for n, layers, seed, error, duration, t1, t2, mode, readout in cases:
            with self.subTest(mode=mode, n=n):
                expected = density_matrix_reference(
                    n, layers, seed, error, duration, t1, t2, mode, readout
                )
                result = run_benchmark(
                    n_qubits=n,
                    layers=layers,
                    seed=seed,
                    gate_error=error,
                    gate_duration_ns=duration,
                    t1_us=t1,
                    t2_us=t2,
                    noise_mode=mode,
                    readout_error=readout,
                    shots=65536,
                )
                sampling_tolerance = (
                    6 * math.sqrt(expected * (1 - expected) / result["shots"]) + 1e-4
                )
                self.assertLess(abs(result["p_success"] - expected), sampling_tolerance)

    def test_complete_two_qubit_depolarization_returns_uniform_distribution(self):
        result = run_benchmark(n_qubits=2, layers=2, gate_error=0.75, shots=65536)
        self.assertLess(abs(result["p_success"] - 0.25), 0.01)

    def test_readout_channel(self):
        self.assertEqual(
            run_benchmark(n_qubits=2, layers=0, shots=256, gate_error=0, readout_error=1)[
                "p_success"
            ],
            0,
        )
        result = run_benchmark(n_qubits=2, layers=0, shots=65536, gate_error=0, readout_error=0.5)
        self.assertLess(abs(result["p_success"] - 0.25), 0.01)

    def test_relaxation_probabilities_and_composition(self):
        p = relaxation_pauli_probabilities(420, 120, 120)
        self.assertAlmostEqual(sum(p), 1)
        self.assertTrue(all(value >= 0 for value in p))
        self.assertGreater(effective_gate_infidelity(0.005, 420, noise_mode="control_only"), 0.005)
        self.assertEqual(effective_gate_infidelity(0.005, 420), 0.005)
        self.assertAlmostEqual(
            effective_gate_infidelity(0.005, 0, noise_mode="control_only"), 0.005
        )
        self.assertAlmostEqual(
            effective_gate_infidelity(0.75, 420, noise_mode="control_only"), 0.75
        )

    def test_deterministic_and_json_serializable(self):
        a = run_benchmark(shots=512)
        self.assertEqual(a, run_benchmark(shots=512))
        json.dumps(a, allow_nan=False)

    def test_pulse_improves_measured_case_benchmark(self):
        result = compare_benchmarks(seeds=(7, 17), shots=2048)
        self.assertGreater(result["success_ratio"], 1.5)
        self.assertEqual(result["baseline"]["total_shots"], 4096)
        json.dumps(result, allow_nan=False)

    def test_wilson_boundary_values(self):
        low, high = wilson_interval(0, 100)
        self.assertEqual(low, 0)
        self.assertGreater(high, 0)
        low, high = wilson_interval(100, 100)
        self.assertLess(low, 1)
        self.assertAlmostEqual(high, 1)

    def test_invalid_inputs_fail_explicitly(self):
        invalid = [
            {"n_qubits": 3},
            {"layers": 3},
            {"shots": 0},
            {"seed": -1},
            {"gate_error": -0.01},
            {"gate_error": 0.81},
            {"gate_error": float("nan")},
            {"t1_us": 120, "t2_us": 250},
            {"t1_us": 0},
            {"readout_error": 1.01},
            {"noise_mode": "assume-magic"},
            {"n_qubits": True},
            {"shots": 10.0},
            {"n_qubits": 100, "layers": 400, "shots": 262144},
        ]
        for arguments in invalid:
            with self.subTest(arguments=arguments), self.assertRaises(ValueError):
                run_benchmark(**arguments)


if __name__ == "__main__":
    unittest.main()
