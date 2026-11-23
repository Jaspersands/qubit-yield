# Validation and reproduction

QubitYield distinguishes three claims: the code is internally consistent, an independent simulator agrees with its stated noise model, and the model predicts something commercially useful. The first two can be checked here. The third requires customer and hardware evidence that the fictional case does not provide.

## Recorded local verification

The current verification totals, adversarial findings and publication status are recorded in [release-audit.md](release-audit.md). Counts are a snapshot, not a guarantee about later edits. Run the commands below against the exact checkout being reviewed. GitHub Actions is configured to repeat verification with the locked Python dependency resolution.

The standalone production bundle is exercised by `web/scripts/smoke-preview.mjs` in a DOM harness, including all five screens, eight saved scenarios, strategy evidence, imports and share links. `web/scripts/smoke-engine.mjs` exercises the actual TypeScript API client against a fresh local Python server. These are functional checks, not a visual browser test. A live visual browser check remains a separate delivery gate; the release audit records whether it was possible in this environment.

The executive memo is rendered and visually inspected as a two-page PDF with embedded fonts. The expanded notebook contains ten code cells, including stress and pricing analysis. `scripts/execute_notebook.py` executes ordinary Python in-process and captures rich outputs. Its figure is rendered from that notebook's own result, so a custom report output folder cannot silently load a stale default figure. No QPU execution or separate live Jupyter-kernel validation is claimed.

The saved [Qiskit validation report](../artifacts/qiskit_validation.json) separately records 16 passing comparisons. It covers two noise interpretations, exact small-system density matrices and 20-qubit stabilizer simulations. The report includes software versions, tested inputs, numerical differences and pass thresholds. This confirms agreement on the chosen circuit and channels, not realism for a customer's device.

| Layer | Checks performed | What those checks do not establish |
| --- | --- | --- |
| Quantum engine | Noiseless mirror return; Pauli channel mapping; fault propagation; physical bounds; independent exact and sampled checks; preservation of 200 CX gates and 20 entangling layers | Fidelity of real hardware, non-Clifford workload performance, leakage or coherent crosstalk |
| Economics | Demand bottlenecks; 24-hour schedule conservation; sunk costs; inclusive contract scope; discounting; deployment delay; cash-flow reconciliation; break-even prices; both valuation modes | Customer willingness to pay, incremental margins, demand growth or vendor profitability |
| Integration and API | Physical-input cache keys; response isolation; input/source provenance; timezone-aware timestamps; alternate-scenario memos; input bounds; oversized and chunked request bodies; nonfinite JSON; worker limits; PNG/SVG generation | Internet-service hardening, a production SLA or authenticated multi-tenant operation |
| Dashboard | Component interactions, scenario state, export behavior and utilities; TypeScript production build; standalone production bundle and tab switching in a DOM harness with zero fetches and zero runtime errors | Live visual browser rendering, every browser/device combination or a real production deployment |
| Submission artifacts | Two-page PDF rendered and visually inspected with embedded fonts; ten notebook code cells executed with captured rich outputs | A live Jupyter-kernel session or evidence from a QPU |

## Install the locked dependency resolution

Use Python 3.11 or newer and a supported modern Node.js version. CI currently selects Python 3.12 and Node 22. The source checkout includes `uv.lock` and `web/package-lock.json`.

From the repository root:

```bash
uv sync --frozen --extra dev --extra research
npm ci --prefix web
```

The research extra supplies Qiskit Aer, notebook execution tools and pandas. A minimal application installation without the research extra can run the NumPy engine and API, but it cannot perform the independent Qiskit or notebook checks.

If uv is unavailable, an unlocked installation can be made with the following commands. It resolves dependencies within `pyproject.toml` ranges rather than reproducing the lockfile exactly:

```bash
python3 -m venv .venv
.venv/bin/python -m pip install -e '.[dev,research]'
npm ci --prefix web
```

## Run the checks

```bash
.venv/bin/python -m ruff check src tests scripts
.venv/bin/python -m pytest
npm test --prefix web
npm run build --prefix web
```

The test suite includes adversarial regressions for a zero-demand scenario, calibration becoming the preferred validation target, changed controls economics, different contract horizons, the fixed-output valuation and the alternate noise interpretation. Generated text must agree with the entered scenario instead of silently repeating the default conclusion.

Simulation requests are bounded by their combined work, not just individual fields. A request exceeding 150 million shot-by-entangling-gate updates is rejected. The API also limits input bodies and concurrent analyses. It is intended to run locally, with the default server bound to `127.0.0.1`.

## Regenerate the evidence and notebook

```bash
.venv/bin/qubityield reproduce --output artifacts
.venv/bin/python scripts/validate_qiskit.py --output artifacts/qiskit_validation.json
.venv/bin/python scripts/execute_notebook.py
npm run build --prefix web
```

The first command regenerates the analysis JSON, comparison tables, sensitivity outputs, scenario variants, figure, executive memo and notebook. It also updates the dashboard's saved default evidence. Rebuilding the frontend afterward ensures that a static build contains the latest saved evidence.

`reproduce --quick` skips the multi-seed robustness run. It does not execute the notebook. Independent Qiskit validation and notebook execution are separate commands so their success or failure is visible. The notebook execution script uses the current Python interpreter and a shared in-process namespace, with IPython capturing rich display output and final-expression results. It fails on a cell error and writes genuine execution counts and outputs; it does not fabricate outputs or merely write an unexecuted notebook. This runner supports the project's ordinary Python cells, not notebook magics or shell escapes. It does not need kernel sockets.

The important artifacts are:

| Artifact | Purpose |
| --- | --- |
| [analysis.json](../artifacts/analysis.json) | Default inputs, raw counts, computed decision, metadata and fingerprints |
| [options.csv](../artifacts/options.csv) | Alternative-by-alternative commercial comparison |
| [cashflows.csv](../artifacts/cashflows.csv) | Upfront and annual cash flows that reconcile to NPV |
| [scenarios.json](../artifacts/scenarios.json) | Counter-cases, including fixed-output savings and the alternate noise interpretation |
| [multi_seed.json](../artifacts/multi_seed.json) | Both noise interpretations across predeclared seeds 7, 17, 29, 43 and 71 |
| [qiskit_validation.json](../artifacts/qiskit_validation.json) | Independent numerical implementation checks |
| [decision_landscape.png](../artifacts/decision_landscape.png) | Circuit-depth, economic, schedule and sensitivity figure |
| [decision_memo.pdf](../artifacts/decision_memo.pdf) | Generated executive recommendation for the baseline scenario |
| [calibration_contract.ipynb](../notebooks/calibration_contract.ipynb) | Executable investigation and recommendation |

When `--output` names a different folder, the generated report artifacts go there. The notebook and saved frontend demo remain repository resources and are updated in their normal locations. Preserve an existing working copy if you need to compare it with a previous generated version.

## Check one counter-case independently

Create `fixed_output.json` in the repository root containing:

```json
{"value_mode": "fixed_output_savings"}
```

Evaluate it without overwriting the default evidence:

```bash
.venv/bin/qubityield evaluate --scenario fixed_output.json --output artifacts/fixed_output_check.json
```

Omitted fields use validated defaults. With the recorded default seed and dependencies, changing only this valuation interpretation leaves the quantum success counts unchanged and changes the pulse case as follows:

| Quantity | Additional useful output | Fixed useful output, less time |
| --- | ---: | ---: |
| Successful-shot rate ratio | 3.1261x | 3.1261x |
| Valued-hours formula | B x (R - 1) | B x (1 - 1/R) |
| Annual conditional benefit | $3.042M | $0.973M |
| Three-year customer NPV | +$1.945M | -$2.100M |
| Nominal zero-NPV total fee | $7.430M | $2.377M |

Here B is baseline booked hours/year and R is relative benchmark throughput. Both calculations use the same illustrative $1,000 per valued hour, 35% commercial realization, six-month rollout, 12% annual discount rate and equal year-end payments totaling $5M. The price ceilings are nominal installment totals, not present values or recommended quotes.

Additional-output value needs a customer who can use and pay for more output. Fixed-output savings need actually avoidable cost or valuable reuse of released time. A fixed equipment expense does not disappear when a job finishes faster. The tool deliberately keeps the physical capacity metric separate from the quantity used to assign financial value.

## Numerical and statistical interpretation

The case's 1% and 0.5% two-qubit errors are interpreted as average gate infidelities. For a four-dimensional depolarizing channel, the simulator uses a uniform nonidentity-Pauli fault probability of `5r/4`, equivalent to Qiskit's depolarizing parameter `4r/3`. The primary engine propagates actual Pauli frames through the Clifford circuit and its inverse, including fault propagation and cancellation.

In reported-total mode, the quoted gate error already includes whatever in-gate relaxation was included in that reported number. T1/T2 loss is not added again. Control-only mode is a different interpretation that adds Pauli-twirled relaxation. That approximation preserves the Bloch contraction but not amplitude damping's shift toward the ground state. The two interpretations are sensitivity cases, not two measurements of the device.

The timing model uses parallel entangling layers, not 200 serial gates. With a separately assumed 100 us overhead, the default cycles are 106 us and 108.4 us. The Qiskit export preserves the intended gate count and entangling layer count; it is a validation circuit, not a hardware-calibrated pulse schedule.

Per-circuit probability intervals are 95% Wilson intervals. The throughput-ratio bounds use simultaneous Clopper-Pearson intervals with a conservative Bonferroni construction. They cover shot sampling conditional on a particular circuit and model. They do not cover uncertainty about hardware error definitions, drift, customer workloads or commercial assumptions. Five predeclared circuit seeds expose some circuit dependence without selecting the most favorable seed afterward.

The independent Aer comparison uses exact density matrices on small systems and sampled stabilizer simulations on the 20-qubit workload. Its recorded agreement criterion is six combined binomial standard errors plus one primary-shot resolution. Different random generators mean counts need not match exactly. The relatively generous threshold catches numerical disagreement without pretending that matching Monte Carlo samples is a requirement.

## Provenance and limits

An analysis records its scenario hash, physical-input fingerprint, case-data hash, source-code hash, package versions, UTC timestamp and `hardware_executed: false`. An economic input change can reuse identical physical evidence while still producing a different scenario fingerprint. Responses are copied before returning them so a caller cannot mutate a cached benchmark.

Reproducing raw stochastic counts requires the same code, seed, inputs and compatible numerical environment. Timestamps will differ on regeneration. A changed implementation, dependency set or scenario must not be presented as the same evidence solely because a screenshot looks similar.

The case facts are fictional. The homogeneous ring workload, ideal local gates, independent stochastic errors, reset/readout overhead, eligible calibration-time fraction, overnight overlap, scale transfer, dollar value and realization fraction all have stated limitations. The benchmark is efficiently classically simulable and makes no claim of quantum advantage. No QPU job, customer pilot, real revenue measurement, production deployment or vendor-margin validation is implied by passing these tests.

The remaining work is a real customer experiment, described in [pilot-plan.md](pilot-plan.md): establish baseline scheduling and costs, agree on the value metric, replay representative applications at matched wall-clock budgets, and release commercial commitments only when the acceptance gates hold.

## Public release checks

A separate virtual environment installs the locked dependencies with system site packages disabled. Final evidence is regenerated in that environment and records its actual package versions. The default counts (772 and 2468), throughput ratio (3.1261113129266005), and customer NPV ($1,945,361.2361530242) match the original result. Consult the release audit for the final suite totals and any unverified deployment steps.

The public-release API rejects overflowing numbers, nonfinite values in structured JSON media types, and excessive nesting with HTTP 400. The code fingerprint hashes the executing package even when the data directory is relocated. The standalone demo loads all eight saved scenarios without a backend and preserves completed evidence when controls are edited.
