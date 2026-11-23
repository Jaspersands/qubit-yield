# Sources and scope

## Case input

Instructor-provided *Lab-to-Market Hackathon: Four Commercial Decisions at the Quantum
Frontier*, COMS 4995W, Session 11, November 19, 2026, Challenge 04, page 5.
The brief explicitly describes all case data as fictional. The source PDF is not
redistributed; the relevant numerical claims are transcribed in `data/case_facts.json`.

## Scientific foundations

1. Qiskit Aer, [depolarizing_error](https://qiskit.github.io/qiskit-aer/stubs/qiskit_aer.noise.depolarizing_error.html).
   Defines the depolarizing channel. We distinguish its parameter from average gate
   infidelity and from the probability of a nonidentity Pauli fault.
2. Qiskit Aer, [Device backend noise model simulations](https://qiskit.github.io/qiskit-aer/tutorials/2_device_noise_simulation).
   Explains matching combined depolarization and relaxation to a reported gate-error
   budget. This supports avoiding an extra coherence penalty when reported error already
   includes it; it does not prove that the fictional device follows our channel model.
3. Qiskit Aer, [thermal_relaxation_error](https://qiskit.github.io/qiskit-aer/stubs/qiskit_aer.noise.thermal_relaxation_error.html).
   Defines the T1/T2 channel and the constraint T2 <= 2 T1. Our alternative fast model
   uses its Pauli twirl, not the full nonunital amplitude-damping dynamics.
4. Timothy Proctor, Stefan Seritan, Kenneth Rudinger, Erik Nielsen, Robin Blume-Kohout,
   and Kevin Young. "Scalable Randomized Benchmarking of Quantum Computers Using Mirror
   Circuits." *Physical Review Letters* 129, 150502 (2022).
   [doi:10.1103/PhysRevLett.129.150502](https://doi.org/10.1103/PhysRevLett.129.150502).
   Mirror circuits motivate an efficiently verifiable output. Our simple forward/inverse
   circuit family is not a reproduction of the paper's full randomized mirror
   benchmarking protocol and does not estimate a universal device fidelity.
5. Michael A. Nielsen. "A simple formula for the average gate fidelity of a quantum
   dynamical operation." *Physics Letters A* 303, 249-252 (2002).
   [arXiv:quant-ph/0205035](https://arxiv.org/abs/quant-ph/0205035).
   For dimension four, the relation between average and entanglement fidelity gives
   nonidentity Pauli probability q = 5r/4 for average infidelity r.

## Financial analysis

Discounted cash flows, capacity conservation, and break-even prices are derived directly
in `docs/economic-method.md` and implemented in `src/qubityield/economics.py`.
No external market price, customer willingness-to-pay estimate, or revenue forecast is
asserted. $1,000 per productive hour, 35% realization, 12% discounting and six months to
rollout are explicit illustrative assumptions, not additional case facts.

## Reproduction environment

The actual installed versions appear in `artifacts/analysis.json` and
`artifacts/qiskit_validation.json`. Python dependency resolution is recorded in `uv.lock`;
frontend resolution is recorded in `web/package-lock.json`. Pinning dependencies enables
reproducibility; it does not guarantee bit-for-bit floating-point output across platforms.

