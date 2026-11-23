# A six-week pilot with a decision at every gate

This is a proposed commercial experiment, not an executed hardware study. Price the pilot
after estimating delivery cost; the case supplies no vendor cost basis.

| Timing | Customer evidence | Exit criterion | What it resolves |
| --- | --- | --- | --- |
| Week 1 | 30-day booking calendar, task duration logs, error definitions, shot timing | Agreed baseline, workload, and value metric | Unmet demand, existing automation, and whether gate error includes coherence |
| Week 2 | Randomized current/optimized pulse runs on a small subsystem | No regressions in leakage, readout, stability, or workload tolerance | Whether the quoted 0.5% at 420 ns is reproducible |
| Weeks 3-4 | Repeated matched-time trials across qubit regions and days | Predeclared lower confidence bound on useful throughput exceeds customer hurdle | Whether synthetic benchmark benefit transfers to the customer workload |
| Week 5 | Deployment and rollback rehearsal on a larger subsystem | Stable service availability and recovery within agreed limits | Integration and 10-to-100-qubit scaling risk |
| Week 6 | Jointly reviewed usage and outcome ledger | Verified incremental value supports delivery cost and negotiated price | Whether a contract creates surplus for both sides |

## Technical design

Use interleaved, randomized baseline/optimized sessions to separate drift from treatment.
Freeze circuit compilation, physical qubit assignments, shot budget, acceptance metric,
and analysis before evaluating the comparison. Use a held-out workload family and include
negative controls. Record reset, readout, scheduling, and calibration time as well as
entangling time. A lower average gate error is not enough if it produces fewer acceptable
application results per wall-clock hour.

The deployed benchmark should include full amplitude damping where appropriate, coherent
error, crosstalk, leakage, and the measured distribution of qubit quality. The included
Clifford simulator is a transparent controlled experiment, not a hardware digital twin.

## Commercial structure

A suggested negotiating structure is a fixed pilot fee covering agreed delivery cost,
followed by staged deployment and verified-value payments. A 30% share of verified value
is an illustrative bargaining starting point, not a market price estimate. Set a cap,
define the valuation baseline, avoid paying twice for existing automation, and attach
reliability and rollback conditions. The model's zero-NPV price ceiling leaves no
customer surplus and should not be used as the proposed price.

Stop if the useful-throughput improvement disappears on real workloads, if demand never
uses additional capacity, or if verified contribution cannot justify the total cost.
Keep AI calibration as a second opportunity when real demand or maintenance objectives
support it. Labor and reliability gains are possible but absent from the supplied case;
they must be measured before being added to the value estimate.

