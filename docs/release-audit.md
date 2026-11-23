# QubitYield 0.2 release audit

Recorded 22 November 2026. This report separates implemented features, executed
checks and externally blocked delivery steps. It is a bounded engineering review,
not proof that every possible defect has been eliminated.

## Result

The expanded local workbench is implemented and verified. Its Python package,
five-screen dashboard, standalone preview, ten-cell executed notebook, evidence
exports and two-page memo are ready together. The seeded baseline still returns
772 and 2,468 successes out of 8,192 shots. All scientific results are simulated.

Public delivery is not complete. The public repository
`https://github.com/Jaspersands/qubit-yield` was created, but the verified remote
README remains the initial two-line placeholder. The GitHub integration rejected
write calls with `403 Resource not accessible by integration`; the browser's file
picker displayed `Access to local files on your machine is disabled by your administrator`.
No source push, remote CI success or live Pages deployment is claimed. These are
access blockers, not failures of the local numerical or application checks.

The available browser also could not reach the executor's local application
server. The final dashboard has functional DOM and real-client/API coverage, but
no completed visual check in that browser. The PDF was visually checked separately.

## Roadmap completion

| Workstream | Implemented result | Verification status |
| --- | --- | --- |
| Foundation and publication | Reproducible source/evidence, public repo initialized, Pages workflow prepared | Local ready; full remote publication blocked |
| Experiment ledger | SQLite history, immutable scientific evidence, editable labels/notes/tags, deletion | Passed persistence, restart, corruption and isolation checks |
| Background computation | Two shared compute slots, eight pending jobs, queued cancellation | Passed saturation, races, shutdown and startup-failure checks |
| History interface | Open, compare, edit, rerun, cancel and delete flows | Component tests and actual TypeScript-client integration passed |
| Stress envelope | Up to 729 grid cells, extrema, regret, dominance and conditional sampling bounds | Financial and adversarial numerical tests passed |
| Pricing | Nominal margin floor, discounted cash floor, customer ceiling and value-share policy | Boundary, timing and feasibility tests passed |
| Strategy interface | Live calculations plus exact saved baseline evidence offline | Component and production-bundle checks passed |
| Portable scenarios | Validated imports, JSON/CSV exports and saved-scenario links | Malformed-input, injection, bounds and stale-state tests passed |
| Accessibility and responsive structure | Focus trapping/restoration, Escape, inert backgrounds, mobile evidence/comparison cards | Behavior tested; live visual inspection blocked |
| CLI | Evaluate, compare, stress, pricing, reproduce, serve and manifest verification | Valid/invalid input, evidence preservation and failure exits passed |
| Reproducibility and packaging | Locked environment, regenerated evidence, notebook, memo and both frontend builds | Local gates passed; Docker execution and remote CI not run |
| Adversarial review | Independent cross-reviews with reproduced failures and regressions | Findings below fixed and included in the final checks |

## Executed checks

| Gate | Recorded outcome |
| --- | --- |
| Python environment | Python 3.12.14; locked installation with system site packages disabled |
| Python lint | Ruff passed for source, tests and scripts |
| Full backend suite | 344 passed, plus 17 parameter subtests |
| Frontend suite | 62 passed across 9 test files |
| Independent quantum reference | 16 Aer comparisons passed, including exact small systems and sampled 20-qubit circuits |
| Notebook | All 10 code cells executed with genuine outputs; no error outputs |
| Production dashboard | TypeScript check and Vite production build passed |
| Standalone production bundle | All 8 exact saved scenarios, 5 screens, strategy, imports, hashes and dialogs passed; zero fetches and runtime errors |
| Actual TypeScript client and Python server | Queued/running/completed job, exact result loading, metadata editing, 27-cell stress, pricing and deletion passed |
| Independent concurrency probe | 32 submitted, 16 cancelled, 16 completed; no orphaned evidence; deleting one preserved the other 15 |
| Publication helper | 22 mocked-command checks passed; no remote command executed by those tests |
| Executive memo | Two pages rendered and visually inspected; visible text uses embedded DejaVu fonts |
| Source provenance | Generated analysis hash matches the actual current Python source files |

The backend run reported one upstream TestClient deprecation warning. It did not
fail a check. The locked environment remains the verified dependency resolution.

The final standalone preview is 1,307,926 bytes with SHA-256
`7b2b163df64cd90ddff4a91c6a2d1f0f8adbefc0be80766e32f4741c83ece134`.
The generated manifest supplies hashes for the full declared release contents.
It is an integrity record, not an author signature.

## Adversarial findings and fixes

Severity describes the effect within this local research application. Each listed
failure was reproduced or exposed by an executable boundary check before its fix.

| ID | Severity | Reproduction or failure | Fix and regression |
| --- | --- | --- | --- |
| A01 | High | Send non-JSON byte bodies to typed POST routes; validation could produce HTTP 500 | Unsupported non-JSON bodies now return 415; raw byte and media-type cases covered |
| A02 | Medium | UTF-16/UTF-32 or duplicate-key JSON could bypass the advertised UTF-8/unambiguous-input contract | Explicit UTF-8 decoding and duplicate rejection; 400 regressions |
| A03 | High | Complete a queued job with a valid analysis for a different scenario | Compare normalized requested/returned scenarios inside the completion transaction; zero records on mismatch |
| A04 | Medium | Fail while starting the second worker after the first starts | Stop and join started workers before releasing the directory lock |
| A05 | Medium | Corrupt saved JSON or insert a nonfinite stored value | Checksum/structure/finite-value checks yield a clear storage error instead of response serialization failure |
| A06 | High | Set comparison JSON and CSV outputs to the same path, symlink or hardlink | Reject aliases before computation or writes; preserve existing bytes |
| A07 | Medium | Verify a manifest entry whose symlink points to itself | Convert path-resolution failure into a controlled validation error and nonzero CLI exit |
| A08 | High | Reuse a benchmark's ratio interval after changing fixed shot overhead | Validate supplied cycle timing against the scenario; stale timing evidence rejected |
| A09 | Medium | Zero vendor cost and zero quote could be called margin-qualified | Require a positive quote; zero-price margin remains undefined |
| A10 | Medium | A zero throughput lower bound could imply monetary exposure even with no work/value | Distinguish unbounded fixed-output exposure from value-neutral zero-demand/zero-benefit cases |
| A11 | High | Background completion races with newer draft edits or a newly loaded result | Preserve later workspace changes and apply completion only to the intended run state |
| A12 | Medium | Import unknown option IDs, array-coerced IDs, nonfinite values or prototype payloads | Strict structural, identifier, type and bounded-value validation before rendering; imported evidence explicitly unverified |
| A13 | High | Generate reports into a custom folder, then execute a notebook that loads the old default figure | Notebook renders its own result in a temporary directory; regression runs without any default artifacts folder |
| A14 | High | Source files change while publication authentication/clone occurs | Verify copied checkout against the original validated manifest before staging; copy that validated manifest canonically |
| A15 | High | Remote symlinks/directories redirect publication, or GH_HOST changes the destination | Reject path collisions, protect Git control paths, pin github.com and verify the pushed commit; never force-push |

The commercial design also checks vendor cash timing separately from nominal
margin. A deferred-payment contract can pass a margin target while failing
discounted cash break-even. Grid win coverage is not represented as a probability.

## How to repeat the checks

```sh
uv sync --frozen --extra dev --extra research
npm ci --prefix web
uv run --frozen ruff check src tests scripts
uv run --frozen pytest -q
npm test --prefix web
uv run --frozen qubityield reproduce
uv run --frozen python scripts/validate_qiskit.py
uv run --frozen python scripts/execute_notebook.py
npm run build --prefix web
npm run build:preview --prefix web
npm run test:preview --prefix web
uv run --frozen python scripts/build_manifest.py
uv run --frozen qubityield verify-manifest
```

For the actual-client smoke, start a disposable local server with an empty
`QUBITYIELD_DATA_DIR`, then run
`node web/scripts/smoke-engine.mjs http://127.0.0.1:8766`. The CI workflow contains
the complete temporary-server sequence. Do not point this test at a valuable
existing ledger: it creates and deletes its own test experiment.

## Publication continuation

`scripts/publish_existing.py` supports the already-created public repository.
Without `--push` it prints a verified local plan and makes no network request.
With `--push`, an already authenticated official GitHub CLI must have the required
repository and workflow write access. The helper clones the current default branch,
preserves unrelated remote files/history, overlays verified release files, makes
one normal commit, pushes without force and verifies the remote commit. It does
not create credentials or expand access. CI/Pages success still needs inspection
after the source reaches GitHub.

## Remaining limits

This is an unauthenticated local prototype, not a public multi-tenant service.
The public preview is static; fresh calculations and persistent history require
the Python engine. Running jobs cannot be interrupted safely, and interrupted
jobs fail explicitly after restart. SQLite data needs an appropriate backup and
retention policy for long-term use.

No actual QPU, vendor pulse, customer workload, customer willingness to pay or
vendor cost estimate was validated. The Clifford/Pauli model is efficiently
classically simulable and does not demonstrate quantum advantage. Passing the
software checks does not validate the fictional case's commercial assumptions.
