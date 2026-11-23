# QubitYield: workbench expansion plan

Owner: Jasper Sands. Scope: the Calibration Contract challenge and a reusable local decision workbench. Public repository: Jaspersands/qubit-yield.

This plan turns the original single-experiment dashboard into a persistent, reviewable experiment workspace. The underlying quantum and financial models remain explicit and reproducible. A feature is complete only when it is connected to actual data, has a useful failure path, and passes the checks listed below.

## 1. Preserve and publish the working foundation

- Keep the scientific engine, default counts, alternative valuation, executed notebook, memo and source references reproducible.
- Publish the full source tree to the approved public GitHub repository, preserving directories and binary artifacts.
- Configure GitHub Pages to publish the standalone demo after verification succeeds.
- Verify the remote files against the local committed tree and inspect the actual hosted result.

Acceptance: the public repository contains runnable source, tests and evidence; the demo URL serves the intended build. A repository containing only a README does not count as publication.

## 2. Add a persistent experiment ledger

- Store completed analyses in SQLite under an explicit user-writable data directory.
- Preserve immutable evidence and scenario hashes while allowing labels, notes and tags to change.
- List experiments and retrieve the full saved result with stable IDs.
- Support deliberate record deletion without altering unrelated experiments.
- Keep runtime data and personal notes out of version control.

Acceptance: records survive a fresh application instance; edits do not rewrite scientific results; invalid IDs and oversized metadata are rejected predictably.

## 3. Make computation asynchronous and bounded

- Submit work as jobs with queued, running, completed, failed and cancelled states.
- Cap workers and queue capacity; share the same compute limit with synchronous routes.
- Return useful job status and failure information without exposing tracebacks.
- Cancel queued jobs honestly. Explain when an already-running calculation cannot be interrupted.
- Clean up resources on application shutdown.

Acceptance: the UI remains responsive, jobs cannot create unbounded work, cancelled queued jobs never run, and failed work does not become a completed experiment.

## 4. Expose history in the interface

- Add an experiment/history screen connected to the ledger and job API.
- Open completed runs without silently recomputing them.
- Edit labels and notes, rerun a saved scenario and cancel queued work.
- Compare selected completed results with their exact original inputs.
- Provide informative empty, offline, loading and error states.

Acceptance: every visible action calls a real endpoint or is explicitly unavailable offline; loading evidence preserves its provenance.

## 5. Add a commercial stress envelope

- Sweep bounded ranges for productive-hour value, value realization and contract total.
- Report each proposal's worst, base and best customer NPV across the entered range.
- Show which proposal wins each grid point and how often it wins within that grid.
- Label grid coverage as a sensitivity result, not a probability or forecast.
- Carry conditional throughput uncertainty into value calculations where the benchmark supports it.

Acceptance: ranges, grid size and finite values are validated; zero-width ranges work; changes in fees and customer value have the expected economic direction.

## 6. Add vendor/customer pricing feasibility

- Separate the customer's zero-NPV price ceiling from the vendor's delivery-cost floor.
- Accept explicitly assumed implementation cost, yearly support cost, target gross margin and customer-value share.
- Calculate a nominal contract cost floor and an illustrative negotiated value-share target.
- Show whether the vendor and customer have any mutually feasible price interval.
- Explain when a free contract still cannot create positive customer value.

Acceptance: nominal totals and discounted customer NPV are not mixed, margin at or above 100% is invalid, and unknown vendor costs are never presented as case facts.

## 7. Add strategy tools to the interface

- Present stress and pricing tools as decision aids with editable assumptions and meaningful charts or tables.
- Display the valuation basis alongside the result.
- Show result staleness when assumptions change.
- Keep computation in the Python model rather than duplicating financial formulas in JavaScript.
- Provide a useful offline experience using clearly labeled saved evidence where available.

Acceptance: no button silently simulates a calculation; inputs and displayed evidence stay in sync; offline limitations are visible.

## 8. Improve portability of scenarios

- Import bounded JSON scenario or evidence files with explicit validation.
- Reject malformed, nonfinite, oversized and structurally invalid imports.
- Keep imported text inert and guard against prototype pollution.
- Export reviewable JSON/CSV with safe cell handling.
- Add shareable links to saved catalog scenarios and views without sending data to a new external service.

Acceptance: import failures leave the prior result intact, a shared saved-scenario link restores the intended result, and formulas cannot execute through exported CSV labels.

## 9. Strengthen interface accessibility and reviewability

- Support keyboard operation and visible focus.
- Add Escape handling, focus containment and focus restoration to dialogs.
- Give charts readable table alternatives and meaningful labels.
- Preserve readable layouts on narrow screens and in print.
- Keep saved evidence distinct from draft controls in every view.

Acceptance: key workflows can be completed by keyboard, dialogs do not strand focus, and tables remain usable when the layout is narrow.

## 10. Extend the command line

- Add batch comparison of several named scenarios.
- Add stress and pricing commands using the same models as the API.
- Add a manifest audit that detects modified or missing evidence.
- Give invalid files and invalid arguments nonzero exit codes with useful messages.
- Document shell-independent equivalents of the Make targets.

Acceptance: CLI results match API/pure-model outputs, malformed batch input fails cleanly, and an altered file fails the integrity audit.

## 11. Preserve reproducibility and packaging

- Regenerate analysis metadata after source changes.
- Execute the notebook and refresh the saved catalog and exported report.
- Build both the local API dashboard and the standalone public demo.
- Verify installation in an isolated locked environment.
- Keep Docker inputs and CI paths consistent with the expanded frontend's data dependencies.

Acceptance: a clean environment can run the documented commands, generated evidence identifies the current implementation, and the public demo needs no external fonts, API key or backend.

## 12. Run a complete adversarial review

- Scientific: circuit size/depth invariants, independent Aer agreement, noise interpretation, extreme valid parameters and zero-success intervals.
- Financial: units, sunk costs, annual versus total fees, rollout timing, zero-value cases, zero-fee feasibility and valuation reversal.
- API: nonfinite and overflowing numbers, deep JSON, large payloads, unexpected fields, invalid IDs, saturation and race conditions.
- Persistence: restart, concurrent writes, metadata bounds, immutable evidence, failed job cleanup and cross-record isolation.
- Interface: stale results, malformed imports, stored-text injection, offline behavior, deep links, keyboard dialogs and empty states.
- Distribution: clean installation, actual public file contents, CI outcome and hosted-page behavior.

Every finding receives a severity, a reproducible case, an outcome and a regression check where appropriate. Fix release-blocking findings before marking the corresponding capability complete. Document genuine remaining limitations without weakening the stated checks.

## Delivery criteria

The final delivery is the improved public repository and hosted demo, with a concise account of what changed, what passed and anything still blocked. No unimplemented roadmap item is presented as a working feature. The audit report is evidence of checks performed, not a guarantee of hardware performance or commercial demand.

## Status

Implementation and local verification are complete. The feature-by-feature status,
executed check totals and fixed adversarial findings are recorded in
[release-audit.md](release-audit.md). Full GitHub source publication, remote CI,
hosted Pages verification and live browser visual inspection remain explicitly
blocked by the available publishing/browser access. They are not marked complete.
