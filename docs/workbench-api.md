# Workbench API contract

The local server keeps the existing synchronous evaluation routes compatible.
Direct evaluation does not automatically save experiments. The offline preview
cannot use the live queue or persistent ledger.

## Jobs

- `POST /api/jobs`: `{scenario: Scenario, label: string, include_depth: boolean}`.
  Defaults: default scenario, `Experiment`, false. Returns 202 and a job.
- `GET /api/jobs`: `{jobs: [job, ...]}`, newest first. `limit`: 1-200, default 100.
- `GET /api/jobs/{id}`: job plus original `scenario` and `include_depth` in
  every state, with `result` when completed.
- `POST /api/jobs/{id}/cancel`: queued work only; running/finished work returns 409.

A job has `id`, `status`, `created_at`, `started_at`, `finished_at`, `label`,
`error`, and `experiment_id`. Status is queued, running, completed, failed, or
cancelled. UTC ISO timestamps and unavailable values are null where appropriate.
Completed work atomically creates an experiment after checking its normalized
scenario matches the submitted job. If that experiment is later
deleted, job detail returns `result: null` and `result_deleted: true`.

Two compute slots are shared by all live numerical routes. The queue holds at
most eight pending jobs; overflow returns 429 with Retry-After. SQLite persists
job metadata and results. Interrupted jobs become explicitly failed on restart,
without silent reruns. Graceful shutdown cancels queued work and waits for running work.

## Experiments

- `GET /api/experiments`: `{experiments: [metadata, ...]}`, newest first;
  `limit`: 1-200, default 100; `offset`: 0 or higher.
- `GET /api/experiments/{id}`: metadata plus full analysis `result`.
- `PATCH /api/experiments/{id}`: one or more of `{label, notes, tags}`; returns metadata.
- `DELETE /api/experiments/{id}`: 204; later reads return 404.

Metadata includes `id`, `label`, `notes`, `tags`, `created_at`, `updated_at`,
`scenario_hash`, and `summary: {recommended, verdict, customer_npv_usd}`.
IDs are UUIDs. Labels are trimmed, 1-120 characters; notes at most 4000;
tags at most eight unique trimmed strings, each 1-40 characters. Text must be
valid UTF-8. Labels/tags reject control characters; notes permit tab/newline.
Null values and unknown fields are rejected; empty notes or tags clear them.

`QUBITYIELD_DATA_DIR` selects storage; the default is user-writable local data
outside the checkout. Results have corruption-detection checksums, not signatures.
One server owns a data directory at a time. No route accepts a filesystem path.

## Decision tools

`POST /api/stress` accepts `StressRequest`: scenario, hourly-value/realization/
contract-price ranges, and grid_points 3-9. `POST /api/pricing` accepts
`PricingRequest`: scenario, implementation cost, annual support cost, target
gross margin, and customer-value share. Each evaluates a single matched physical
benchmark. Cost/value ranges are assumptions, not probabilities or case facts.

Malformed/nonfinite/overly nested/invalid-UTF8 JSON: 400. Duplicate object keys
are rejected rather than silently taking the last value. UTF-8 with an optional
BOM is supported; UTF-16 and UTF-32 request bodies are rejected. Body over
64 KiB: 413. A nonempty body with a non-JSON media type returns 415. JSON media
types include `application/json`, `application/*+json`, and an omitted header.
Invalid schema or UUID: 422. Missing record: 404. Invalid transition: 409.
Busy/full: 429. Storage failure or corrupted evidence: 503.

The server is a local research tool without authentication or tenant isolation;
localhost is the default. A public repository is not a hosted account service.
