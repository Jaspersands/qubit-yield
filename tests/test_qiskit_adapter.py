"""Optional independent Aer checks; core tests still run without Qiskit."""

import math

import numpy as np
import pytest

pytest.importorskip("qiskit_aer", reason="Install .[research] for independent Aer validation")

from qiskit.quantum_info import Operator

from qubityield.qiskit_adapter import (
    exact_aer_probability,
    run_aer_benchmark,
    to_qiskit_circuit,
)
from qubityield.quantum import run_benchmark


def test_export_preserves_compiled_gate_count():
    circuit = to_qiskit_circuit()
    assert circuit.num_qubits == 20
    assert circuit.count_ops()["cx"] == 200
    assert circuit.count_ops()["measure"] == 20


def test_export_preserves_parallel_entangling_layers():
    circuit = to_qiskit_circuit()
    assert circuit.depth(lambda instruction: instruction.operation.name == "cx") == 20
    occupied = set()
    layer_gate_counts = []
    for instruction in circuit.data:
        if instruction.operation.name == "cx":
            qubits = {circuit.find_bit(bit).index for bit in instruction.qubits}
            assert not (occupied & qubits)
            occupied |= qubits
        elif instruction.operation.name == "barrier" and occupied:
            layer_gate_counts.append(len(occupied) // 2)
            occupied = set()
    assert layer_gate_counts == [10] * 20


def test_qiskit_mirror_is_identity():
    circuit = to_qiskit_circuit(4, 10, 7, measure=False)
    np.testing.assert_allclose(Operator(circuit).data, np.eye(16), atol=1e-12)


@pytest.mark.parametrize(
    "n,mode", [(2, "reported_total"), (4, "reported_total"), (4, "control_only")]
)
def test_primary_matches_exact_aer_density_matrix(n, mode):
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
    exact = exact_aer_probability(**params)
    primary = run_benchmark(shots=32768, **params)
    tolerance = 6 * math.sqrt(exact * (1 - exact) / primary["shots"]) + 1e-4
    assert abs(primary["p_success"] - exact) < tolerance


def test_aer_stabilizer_with_two_qubit_complete_depolarization():
    result = run_aer_benchmark(n_qubits=2, layers=2, shots=8192, gate_error=0.75)
    assert abs(result["p_success"] - 0.25) < 0.02
    assert result["hardware_execution"] is False


def test_duration_has_no_extra_noise_in_reported_total_mode():
    a = exact_aer_probability(gate_error=0.01, gate_duration_ns=300)
    b = exact_aer_probability(gate_error=0.01, gate_duration_ns=420)
    assert a == pytest.approx(b, abs=1e-12)


def test_exact_reference_is_bounded():
    with pytest.raises(ValueError):
        exact_aer_probability(n_qubits=20)
