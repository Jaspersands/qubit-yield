# Phase 1: Investigate

The role is product strategy lead for a quantum control company. The decision is which
single product to deliver first, how to price it, and what the customer must verify before
signing a $5 million, three-year agreement. The contract must buy useful customer outcomes.

## Working hypothesis

Prioritize AI calibration. Eight hours of daily downtime initially appears to be the
largest recoverable loss. This is a hypothesis to test, not an endorsement of the pilot
claim or an assumption that extra hours will be sold.

The most important uncertainty is the conversion from a laboratory improvement to
valuable customer work. For calibration, that requires usable windows with unmet demand.
For pulses, it requires customer workload improvement after the longer gates and all
shot overhead. The case provides neither a dollar value for better outcomes nor a
duration-weighted calibration inventory.

## Predeclared comparison

Compare keeping the system, AI calibration, pulse optimization, and lower-cost controls.
Use the supplied 20-qubit, 20-layer workload shape for a synthetic Clifford mirror.
Evaluate the same circuit and noise draws at 1.0% and 0.5% average two-qubit gate
infidelity. Then change circuit seed, noise interpretation, demand, overhead, rollout,
value realization, and the interpretation of the AI speed claim.

The default circuit seed is 7. The robustness seeds are 7, 17, 29, 43, and 71. Every seed
is reported, with no best-seed selection. The default is 8,192 shots per proposal per seed.
An independent Qiskit Aer implementation checks both exact small systems and sampled
20-qubit systems. The simulators never connect to a real quantum processor.

## Evidence that changes the decision

- Automation loses priority if saved time does not change bookings or valuable internal work.
- Pulse optimization loses priority if matched-wall-clock application outcomes fail to improve.
- The contract loses commercial support if validated dollar value is below its break-even level.
- Cheaper controls become interesting only if a replacement was already planned, integration
  is paid for, and reliable operation is demonstrated. Historical purchase cost is not cash saved.

Every number from the case is a claim. `data/case_facts.json` records those claims;
the assumptions ledger records the additional interpretations needed to calculate a result.

