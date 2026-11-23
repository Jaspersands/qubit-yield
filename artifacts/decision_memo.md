# Executive decision memo

Fictional case. Simulated evidence. AI-assisted implementation.

## Decision

Prioritize a gated pulse optimization pilot. The contract verdict is conditional go after validation. At the proposed $5.00M total fee, this option has $1.95M incremental customer NPV over 3 years. This is a conditional scenario result, not validated willingness to pay.

## Initial hypothesis and what changed

The initial calibration-first hypothesis did not survive. This scenario has 16 nominal available hours/day, 11.2 hours/day of demand and 11.2 booked hours/day. Reading the AI claim as a 70% higher rate gives a 41.18% time reduction. With 65% assumed time eligibility, 70% scale transfer and 25% useful-window overlap, automation recovers 1.499 physical hours/day and 0.375 demand-accessible hours/day. It adds 0 booked hours/year at the entered demand. The task-duration and demand assumptions need customer logs.

## Computational evidence

A seeded 20-qubit Clifford mirror contains 200 two-qubit gates across 20 parallel entangling layers. At seed 7, current gates return the known correct bitstring in 772/8,192 shots (9.42%); proposed pulses do so in 2,468/8,192 (30.13%). Including 100 microseconds of assumed overhead, cycles take 106 versus 108.4 microseconds. The proposed successful-shot rate is 3.126 times the baseline. Per-circuit intervals quantify shot sampling only. Multi-seed and independent Qiskit validation routines are provided; their saved reports identify their own tested configurations and do not automatically validate every edited scenario. No QPU was used.

## Price and alternatives

Assuming $1,000 of contribution or avoided cost per valued hour and 35% value realization gives $3.04M/year for the selected option after rollout. This scenario values additional useful output, B*(R-1), not fixed-output cost savings; it requires demand and a customer application-value mechanism. Valuing the same physical gain as runtime saved for the same output gives -$2.10M customer NPV with all other inputs unchanged. The horizon uses 12% discounting and a 6-month rollout. The break-even productive-hour value for the selected option is $673/hour at the same realization fraction. For pulse optimization, the zero-customer-NPV ceiling is $7.43M in equal annual installments over 3 years, not a price recommendation. An illustrative 30% share of verified value would imply about $2.23M on that schedule. Separately, the advertised controls quote nets $150,000 if an equivalent new purchase was already required, after $450,000 of integration cost. Without a replacement need it creates $1.85M of new outlay. The target $5.00M controls contract includes its hardware, preventing double counting.

## What the customer should validate first

First confirm whether the proposed 0.50% error is a total measured gate error at 420 ns. Run a matched wall-clock replay of the customer's actual workload, including readout, reset, single-qubit gates, leakage, drift and calibration outages. Pre-register the circuit or observable, error tolerance and useful-throughput acceptance rule; randomize comparison sessions across days and qubit regions. Record the full booking calendar. The original case's 10-qubit calibration pilot needs validation on larger subsystems before extrapolating to a 100-qubit processor.

## Commercial terms and limitations

If the validation gates justify a pilot, agree its scope and delivery-cost floor before spending; release deployment payments only after technical and application-value gates pass. Cap recurring fees at a negotiated share of verified incremental value, with rollback and reliability conditions. Vendor delivery cost is absent, so no vendor margin is claimed. The simulator uses independent stochastic faults, a homogeneous ring-connected synthetic workload and ideal local gates. The selected reported-total error budget already includes gate-time decoherence; adding a T1/T2 penalty again would double count. Mirror return is not general application correctness, and a 100-qubit device is not assumed to run five independent jobs. These are the main reasons to validate before committing.

See [references](../docs/references.md), [raw evidence](analysis.json), and [result figure](decision_landscape.png).
