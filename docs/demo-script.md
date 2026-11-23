# Five-minute demo: follow the value, then change the decision

## Before presenting

Run the demo from the repository root using the committed evidence and a live local engine:

```bash
uv sync --frozen --extra dev --extra research
npm ci --prefix web
npm run build --prefix web
.venv/bin/qubityield serve
```

Open <http://127.0.0.1:8000>. The default server listens on the local machine. It does not connect to a QPU or require an API key. The built dashboard is served by the Python API, so scenario controls work without running a second server.

Start from the Case baseline preset and click Run analysis if any inputs have changed. The five screens are Decision desk, Experiment lab, Assumptions, Strategy tools and History. The static preview can load eight exact saved scenarios and the baseline strategy evidence. The live engine is required for arbitrary new calculations and persistent experiment history.

The full reproduction commands are in [validation.md](validation.md). Do not spend presentation time waiting for dependency installation or rebuilding evidence.

## 0:00-0:40 | Investigate the customer decision

Open Decision desk.

Say:

> The customer is considering a $5M contract for more useful computing capacity. We can deliver one upgrade first: faster calibration, better two-qubit gates, or cheaper controls. I initially thought eight hours of daily calibration made automation the obvious choice. This workbench asks whether each technical improvement actually changes the customer's economics.

Point to the current recommendation and the four headline metrics. Explain that the displayed NPV is a conditional model result. The case is fictional, and the evidence is simulated.

## 0:40-1:20 | Show why saved time can be worth zero

Stay on Decision desk and show Where the day actually goes.

Say:

> Eight hours of calibration leaves sixteen hours available. The case says seventy percent of available time is booked, so current demand is only 11.2 hours a day. Our default reading of seventy percent faster is 1.7 times the rate, or a 41.2 percent time reduction. After explicitly assumed eligibility, scale transfer and useful-window overlap, calibration saves about 1.50 physical hours a day. But it creates no new bookings at the stated demand.

Point out the difference between recovered time and booked time. Do not call recovered overnight time revenue. The demand slider allows a backlog scenario, but the baseline case does not establish one.

## 1:20-2:10 | Show the quantum experiment

Switch to Experiment lab.

Say:

> I used a twenty-qubit Clifford mirror. It runs a circuit and its inverse, so we know that the correct ideal output is all zero. There are two hundred two-qubit gates across twenty parallel layers. The two proposals run the same circuit. We propagate stochastic Pauli faults through the circuit, rather than simply multiplying reported gate fidelities.

Show the evidence ledger, shot counts and sampling intervals. At the recorded default seed, 7, with 8,192 shots per arm:

| Quantity | Current gates | Proposed pulses |
| --- | ---: | ---: |
| All-zero return | 772 / 8,192, or 9.42% | 2,468 / 8,192, or 30.13% |
| Two-qubit duration | 300 ns | 420 ns |
| Modeled shot cycle | 106 us | 108.4 us |

Say:

> The longer pulses cost time, but the return improvement is larger. With the assumed fixed shot overhead, the useful-shot rate is about 3.13 times the baseline. This is a benchmark result, not proof of application correctness or quantum advantage. The same channels were independently checked with Qiskit Aer. No quantum hardware was used.

Use the depth chart to show that the project evaluates a circuit family, and open Inspect metadata to show the seed and reproducibility fingerprints. Do not describe the confidence interval as confidence in a business forecast.

## 2:10-3:20 | Make the $5M decision reverse

Return to Decision desk. Under Commercial controls, show What creates value?. It starts at More useful output.

Say:

> The most consequential assumption is what the customer actually gets paid for. If it can use more useful output in the same booked time, a throughput ratio R creates B times R minus one in additional baseline-equivalent capacity. With our explicit assumptions of a thousand dollars per valued hour and thirty-five percent realization, that produces a positive $1.95M customer NPV at the proposed price.

Change What creates value? to Same work, less time and click Run analysis. Wait for the completed result. The previous result stays visible with a stale-result notice while inputs are unapplied or an analysis is running.

Say:

> Now keep the physics and the dollar assumptions exactly the same, but suppose the customer only wants to do its existing work faster. The time saved is B times one minus one over R. That is a different, much smaller quantity. Customer NPV falls to about negative $2.10M, and the zero-NPV price ceiling falls from about $7.43M to $2.38M. Better gates remain the technical priority, but the proposed $5M purchase no longer pays back in this interpretation.

Use the recommendation's Renegotiate verdict and the comparison table to make the distinction clear. A zero-NPV ceiling is a limit under assumptions, not a recommended quote. Fixed-output time savings also need genuinely avoidable costs or valuable redeployment to become money.

## 3:20-4:10 | Open the assumptions

Switch to Assumptions. Select Model assumptions, then search for realization or demand.

Say:

> Every input has a provenance label. The eight calibration hours and one-percent gate error come from the fictional case. The hourly value, commercial realization, overnight overlap, deployment delay and transfer from ten to a hundred qubits are assumptions. The case reports an automated-task count, so treating thirty-five percent of tasks as thirty-five percent of time also needs validation.

Point to the noise interpretation and the sunk-cost explanation.

Say:

> I treat reported gate error as total error by default, so I do not add the same in-gate coherence loss again. There is a control-only sensitivity mode. For cheaper controls, the advertised hardware discount is $600K but customer integration costs $450K. That leaves at most $150K on a purchase that was already required. If the existing system does not need replacement, its $2M purchase price is sunk and the new system creates $1.85M of outlay.

## 4:10-5:00 | Recommend the next commercial experiment

Return to Decision desk. Keep the fixed-output result visible, or save both scenarios and compare them.

Say:

> I would prioritize a gated pulse-optimization pilot, not commit the full contract on a headline gate-error claim. First confirm that the proposed half-percent error is measured at 420 nanoseconds. Then replay the customer's actual workload at matched wall-clock budgets, including readout, reset, drift and outages. At the same time, agree whether value means selling more output or reducing the cost of existing work. That distinction changed the decision more than the headline technical metric did.

> The deliverable is a reproducible decision process: a quantum experiment, a commercial model, an assumptions ledger, an executable notebook and a memo. The next milestone is evidence that the customer can convert a technical gain into value.

Finish by using Export to download the evidence JSON or comparison CSV. The executive memo is available at <http://127.0.0.1:8000/artifacts/decision_memo.pdf>; it describes the generated baseline analysis, not an automatically updated report for whichever scenario is currently on screen. Use Print decision report or export the current JSON to preserve the edited scenario.

## Optional two-minute workbench extension

Open Strategy tools and show the stress envelope. Explain that an option's win
coverage is the fraction of the entered grid it wins, not a chance of commercial
success. Compare maximin and minimax regret to show that decision rules can disagree
even when they use the same evidence. The ratio-sampling envelope is conditional on
the simulated circuit and is shown separately from commercial assumption ranges.

Switch to Pricing. The default vendor cost assumptions require a $2.375M nominal
fee to reach 60% margin. A 30% share of modeled pulse value gives about $2.229M,
which is too low. With a live engine, change the share to 35% and rerun: the target
becomes about $2.600M and satisfies the modeled constraints. Those vendor costs
are assumptions, and a feasible interval does not establish a market price.

Open History after running an experiment. Reopen its saved evidence, edit the
label or notes, and rerun the original inputs. Queued work can be cancelled;
running work is allowed to finish. Export a result and import it again to show
the portability of inputs and provenance. History requires the local server.

## If a judge asks

**Is this quantum advantage?** No. Clifford circuits with these noise channels are efficiently classically simulable. The purpose is to compare hardware proposals under an auditable model.

**Why not just use the reported error rates?** Average gate infidelity is not an application success probability. The mirror experiment propagates and cancels specific faults through a specified circuit. It still needs validation on customer workloads.

**Why is the revenue estimate conditional?** Neither an application value nor a price is supplied in the case. The model exposes the assumption instead of hiding it, and the valuation switch demonstrates its importance.

**What would change the choice?** A failed matched-time pulse improvement, credible unmet demand for recovered calibration windows, or a genuinely required controls procurement with better verified economics. The pilot gates and scenario controls make those falsifiers concrete.
