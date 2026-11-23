/** Live contract smoke. Run only against a disposable local test engine. */
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { build } from "esbuild";

const base = process.argv[2];
if (!base || !/^http:\/\/(127\.0\.0\.1|localhost):\d+$/.test(base))
  throw new Error(
    "Pass a disposable localhost engine URL, e.g. http://127.0.0.1:8766",
  );
const nativeFetch = globalThis.fetch;
globalThis.fetch = (path, options) => nativeFetch(new URL(path, base), options);
const output = await build({
  entryPoints: [new URL("../src/workbench-api.ts", import.meta.url).pathname],
  bundle: true,
  format: "esm",
  platform: "node",
  write: false,
});
const { queueScenario, resourceRequest } = await import(
  `data:text/javascript;base64,${Buffer.from(output.outputFiles[0].text).toString("base64")}`
);
const scenario = {
  ...JSON.parse(
    readFileSync(new URL("../public/demo.json", import.meta.url), "utf8"),
  ).scenario,
  n_qubits: 4,
  layers: 4,
  shots: 256,
  seed: 42,
};
const states = [];
let lastJob;
const result = await queueScenario(
  scenario,
  "Browser client contract smoke",
  (job) => {
    states.push(job.status);
    lastJob = job;
  },
);
assert.deepEqual(result.scenario, scenario);
assert.ok(states.includes("completed"));
const { experiments } = await resourceRequest("/api/experiments");
const record = experiments.find((item) => item.id === lastJob.experiment_id);
assert.ok(record);
await resourceRequest(`/api/experiments/${record.id}`, "PATCH", {
  label: "Verified smoke record",
  notes: "Actual TS client, Python engine, durable ledger.",
  tags: ["smoke"],
});
const full = await resourceRequest(`/api/experiments/${record.id}`);
assert.deepEqual(full.result, result);
assert.equal(full.notes, "Actual TS client, Python engine, durable ledger.");
const stress = await resourceRequest("/api/stress", "POST", {
  scenario,
  grid_points: 3,
});
assert.equal(stress.cell_count, 27);
assert.equal(stress.kind, "stress_envelope");
assert.match(stress.interpretation, /NOT a probability/);
const pricing = await resourceRequest("/api/pricing", "POST", {
  scenario,
  customer_value_share: 0.35,
});
assert.equal(pricing.kind, "pricing_feasibility");
assert.equal(pricing.inputs.customer_value_share, 0.35);
await resourceRequest(`/api/experiments/${record.id}`, "DELETE");
const deleted = await resourceRequest(`/api/jobs/${lastJob.id}`);
assert.equal(deleted.result_deleted, true);
assert.deepEqual(deleted.scenario, scenario);
console.log(
  JSON.stringify({
    status: "passed",
    job_states: states,
    metadata_patch: true,
    exact_result_load: true,
    stress_cells: stress.cell_count,
    pricing: true,
    delete: true,
    deleted_job_inputs_preserved: true,
  }),
);
