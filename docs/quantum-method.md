# Quantum experiment: a compiled mirror workload

The experiment is a circuit-level Monte Carlo computation with propagated Pauli
faults. It does not estimate application correctness by multiplying gate
fidelities. It is designed as a transparent, reproducible proxy experiment for
the fictional 20-qubit customer workload in Challenge 4.

## Circuit and measured quantity

Each circuit has ten forward entangling layers and the exact inverse ten
layers. Every entangling layer contains ten CX gates on disjoint pairs, giving
200 two-qubit gates in all. The pairings alternate between the two perfect
matchings of a 20-qubit ring. Control/target direction and local H/S Clifford
words are seeded. The six local gate words are not a uniform sample of the
full 24-element single-qubit Clifford group. The entire circuit ideally
returns an initial `|000...0>` state to itself.

The metric is the fraction of noisy shots that return all zero. Each simulated
shot tracks a two-bit Pauli frame per qubit through H, S, S-dagger, and CX
conjugation rules. Fault propagation, harmless Z errors, and fault cancellation
are included. This computation is efficient because the chosen circuit is
Clifford. No exponential-sized 20-qubit state vector is needed, and no
quantum computational advantage is claimed.

A return probability is specific to this benchmark. It is not a universal
probability that a chemistry, optimization, or customer production job is
correct. The acceptance test must repeat the comparison on the customer's
real workload and readout protocol. The example does not assume five
20-qubit jobs can run concurrently on a 100-qubit processor: crosstalk,
connectivity, scheduling, and partitioning information are missing.

## Infidelity is not fault probability

The case gives a two-qubit gate error but no measurement definition. The main
reading treats it as average gate infidelity `r`. For a two-qubit isotropic
Pauli channel, the total probability of a nonidentity Pauli is `q = 5r/4`.
Each of the 15 nonidentity Paulis then has probability `q/15`.

Equivalently, for a four-dimensional gate, a depolarizing channel
`E(rho) = (1-lambda)rho + lambda I/4` has `lambda = 4r/3`. Its average gate
fidelity is `(4*p_identity + 1)/5`, so using `r` directly as the probability
of a Pauli fault would give the wrong channel. This conversion follows the
standard [average gate fidelity formula](https://arxiv.org/abs/quant-ph/0205035)
and the [Qiskit Aer depolarizing channel definition](https://qiskit.github.io/qiskit-aer/stubs/qiskit_aer.noise.depolarizing_error.html).

## Two explicit noise interpretations

`reported_total` is the default. The 1.0% baseline and 0.5% optimized errors
already include all error during the physical gate. We do not independently
add a T1/T2 penalty during those same gates. Their durations, 300 ns and
420 ns, still affect throughput. The
[Qiskit device-noise modeling guide](https://qiskit.github.io/qiskit-aer/tutorials/2_device_noise_simulation)
likewise adjusts depolarization to account for relaxation when matching a
reported total gate infidelity, instead of simply adding the full error twice.

`control_only` is a deliberately different reading of the claim: the stated
gate error excludes coherence loss. Each gate then receives both its control
Pauli error and independent one-qubit, Pauli-twirled thermal relaxation over
the gate duration. The one-qubit Pauli probabilities are

```
a = exp(-duration/T1)
b = exp(-duration/T2)
pI = (1 + 2b + a)/4
pX = pY = (1-a)/4
pZ = (1 - 2b + a)/4
```

Durations and coherence times are converted to consistent units. We require
`T2 <= 2*T1`, as in the
[thermal relaxation channel definition](https://qiskit.github.io/qiskit-aer/stubs/qiskit_aer.noise.thermal_relaxation_error.html).
This twirl preserves Bloch-vector contraction but removes amplitude damping's
affine shift toward the ground state. It is a sensitivity model, not an exact
simulation of nonunital amplitude damping. Coherent errors, leakage, drift,
crosstalk, and correlated errors are not in either channel.

T1 and T2 alone do not identify a full two-qubit error channel. The separately
reported `twirled_relaxation_infidelity` is a diagnostic of this assumed
independent-qubit model, not a measured device specification.

## Timing, sampling, and uncertainty

All active qubits participate in exactly one two-qubit gate in every layer.
The entangling portion therefore lasts `layers * gate_duration`, not
`gate_count * gate_duration`. Local Clifford gates are treated as ideal and
instantaneous in this first benchmark; SPAM is ideal by default. An optional
independent readout-error probability can be used in the engine. The economic
model must add explicit reset, readout, and scheduling overhead before
turning these times into throughput.

Circuit seeds and shot seeds use separate deterministic NumPy SeedSequence
streams. Equal seeds use common random numbers for the two error rates,
reducing some comparison noise without forcing monotonicity: extra faults can
occasionally cancel existing faults. Per-circuit 95% Wilson intervals reflect
shot noise only. The comparison reports a mean, range, and standard deviation
across fixed circuit seeds separately. Neither uncertainty summary covers
unknown customer workloads or uncertainty in the case claims.

## Independent checks

`tests/test_quantum.py` implements a separate small-system density-matrix
oracle using full gate matrices and Kraus mixtures. It checks noisy 2- and
4-qubit circuits, readout noise, and the alternative relaxation model against
the trajectory simulator. Other checks verify the mirror on an arbitrary
state, the infidelity conversion, exact gate counts, noiseless certainty,
complete-depolarization statistics, deterministic output, physical input
validation, and the absence of coherence double-counting.

## Optional independent Qiskit Aer validation

Install `.[research]` and run:

```sh
python scripts/validate_qiskit.py --shots 8192 --output artifacts/qiskit_validation.json
```

`qiskit_adapter.py` exports the exact same H/S/CX sequence with barriers around
whole disjoint-pair entangling layers and executes it without a transpiler
optimization pass. Barriers do not serialize the ten CX gates inside each
layer. Tests independently verify both 200 CX gates and entangling depth 20.
This is an abstract validation circuit, not a device-specific scheduled program;
real routing, native-gate decomposition, pulse durations, and idle intervals
still require a hardware backend. Aer uses its own
depolarizing channel (`lambda = 4r/3`), independent random trajectories, and
stabilizer implementation. For the alternative relaxation interpretation,
the adapter obtains the Pauli-transfer matrix of Qiskit's thermal-relaxation
channel and constructs its diagonal twirl. It does not reuse the primary
simulator's thermal probabilities. Small 2- and 4-qubit circuits are also
checked against Aer exact density matrices, including readout errors.

The validation report records dependency versions, circuit seeds, probabilities,
differences, and a stated six-standard-error comparison criterion. Its default
16 checks comprise four exact small-system comparisons and twelve sampled
20-qubit comparisons (three seeds, two proposals, two noise interpretations).
Equal shot counts from two simulators are not expected to produce identical
counts; agreement is statistical. Numerical agreement supports the software
implementation of the chosen model. It does not establish that the model
fully describes a customer device. All of these are simulator executions.

## What independent simulator agreement can and cannot exclude

The primary and Aer simulators deliberately share the seeded gate list so they
execute the same experiment. Agreement alone cannot reveal a mistake in that
shared specification. Separate invariant tests verify the full mirror is an
identity on arbitrary states, every entangling layer is a disjoint complete
matching, every coupling belongs to the stated ring, and the workload contains
exactly 200 CX gates in 20 parallel entangling layers. A separate dense-matrix
Kraus implementation and Aer provide two checks on fault propagation and
channel conversion. These checks do not validate the choice of mirror workload,
the interpretation of a vendor's gate-error number as average infidelity, or
the independence and stationarity of noise. Those remain explicit model
assumptions requiring customer measurements.
