import type { AnalysisResponse, Scenario } from "./types";

export const MAX_IMPORT_BYTES = 1_000_000;
type NumericRule = [number, number, boolean?];
const numericRules: Record<string, NumericRule> = {
  calibration_hours: [0, 24],
  booking_utilization: [0, 1],
  already_automated: [0, 1],
  ai_speed_claim: [0, 1],
  scale_realization: [0, 1],
  monetizable_overlap: [0, 1],
  demand_hours_per_day: [0, 24],
  value_per_productive_hour: [0, 1e6],
  value_realization: [0, 1],
  operating_days: [1, 366, true],
  discount_rate: [0, 1],
  contract_years: [1, 10, true],
  contract_total: [0, 1e9],
  rollout_months: [0, 120],
  control_cost: [0, 1e9],
  control_saving: [0, 1],
  control_engineers: [0, 100, true],
  control_integration_months: [0, 120],
  engineer_annual_cost: [0, 1e7],
  n_qubits: [2, 100, true],
  layers: [2, 100, true],
  shots: [256, 65536, true],
  seed: [0, 4294967295, true],
  baseline_gate_error: [0, 0.2],
  pulse_gate_error: [0, 0.2],
  baseline_gate_ns: [Number.MIN_VALUE, 1e6],
  pulse_duration_increase: [0, 4],
  fixed_overhead_us: [0, 1e6],
  t1_us: [0.001, 1e6],
  t2_us: [0.001, 1e6],
  readout_error: [0, 0.5],
};
const enumRules: Record<string, string[]> = {
  ai_speed_interpretation: ["rate_increase", "time_reduction"],
  value_mode: ["additional_output", "fixed_output_savings"],
  noise_mode: ["reported_total", "control_only"],
};
const ids = ["baseline", "calibration", "pulse", "control"];
function fail(message: string): never {
  throw new Error(message);
}
function record(value: unknown, name: string): Record<string, unknown> {
  if (!value || typeof value !== "object" || Array.isArray(value))
    fail(`${name} must be an object.`);
  return value as Record<string, unknown>;
}
function finite(value: unknown, name: string, min = -1e15, max = 1e15): number {
  if (
    typeof value !== "number" ||
    !Number.isFinite(value) ||
    value < min ||
    value > max
  )
    fail(`${name} must be a finite number between ${min} and ${max}.`);
  return value;
}
function string(value: unknown, name: string, max = 6000): string {
  if (typeof value !== "string" || value.length > max)
    fail(`${name} must be text with at most ${max} characters.`);
  return value;
}
function list(value: unknown, name: string, max: number): unknown[] {
  if (!Array.isArray(value) || value.length > max)
    fail(`${name} must be an array with at most ${max} entries.`);
  return value;
}
function inspectTree(value: unknown, depth = 0, count = { value: 0 }) {
  if (++count.value > 50000 || depth > 25)
    fail(
      "The import is too complex. Use a normal scenario or evidence export.",
    );
  if (typeof value === "number" && !Number.isFinite(value))
    fail("All imported numbers must be finite.");
  if (typeof value === "string" && value.length > 12000)
    fail("An imported text field is too long.");
  if (value && typeof value === "object")
    for (const [key, child] of Object.entries(value)) {
      if (["__proto__", "prototype", "constructor"].includes(key))
        fail(`Unsafe property name: ${key}.`);
      inspectTree(child, depth + 1, count);
    }
}

export function validateScenario(
  input: unknown,
  defaults?: Scenario,
): Scenario {
  const value = record(input, "Scenario");
  if (!Object.keys(value).length)
    fail("The scenario must contain at least one input.");
  for (const [key, child] of Object.entries(value)) {
    if (Object.hasOwn(numericRules, key)) {
      const [min, max, integer] = numericRules[key];
      const n = finite(child, key, min, max);
      if (integer && !Number.isInteger(n)) fail(`${key} must be an integer.`);
    } else if (Object.hasOwn(enumRules, key)) {
      if (typeof child !== "string" || !enumRules[key].includes(child))
        fail(`${key} has an unsupported value.`);
    } else if (key === "replacement_due") {
      if (typeof child !== "boolean")
        fail("replacement_due must be true or false.");
    } else fail(`Unknown scenario input: ${key}.`);
  }
  const full = { ...(defaults || {}), ...value } as Scenario;
  for (const key of [
    ...Object.keys(numericRules),
    ...Object.keys(enumRules),
    "replacement_due",
  ])
    if (full[key] === undefined) fail(`Missing scenario input: ${key}.`);
  if (full.n_qubits % 2 || full.layers % 2)
    fail("Qubits and layers must both be even.");
  if (full.t2_us > 2 * full.t1_us) fail("T2 cannot exceed twice T1.");
  if (full.baseline_gate_ns * (1 + full.pulse_duration_increase) > 1e6)
    fail("Optimized gate duration exceeds the engine limit.");
  if ((full.shots * full.n_qubits * full.layers) / 2 > 150_000_000)
    fail(
      "Simulation exceeds the engine work limit. Reduce shots, qubits or layers.",
    );
  return full;
}

export function validateEvidence(input: unknown): AnalysisResponse {
  const value = record(input, "Evidence");
  validateScenario(value.scenario);
  const benchmark = record(value.benchmark, "benchmark");
  for (const key of ["baseline", "pulse"]) {
    const result = record(benchmark[key], `benchmark.${key}`);
    for (const field of ["p_success", "ci_low", "ci_high"])
      finite(result[field], `${key}.${field}`, 0, 1);
    if (
      Number(result.ci_low) > Number(result.p_success) ||
      Number(result.p_success) > Number(result.ci_high)
    )
      fail("Probability must lie within its reported interval.");
    finite(result.shots, `${key}.shots`, 1, 1e9);
    finite(result.gate_count, `${key}.gate_count`, 0, 1e6);
  }
  finite(benchmark.throughput_ratio, "throughput_ratio", 0, 1e12);
  finite(
    benchmark.baseline_cycle_us,
    "baseline_cycle_us",
    Number.MIN_VALUE,
    1e12,
  );
  finite(benchmark.pulse_cycle_us, "pulse_cycle_us", Number.MIN_VALUE, 1e12);
  const options = list(value.options, "options", 4);
  if (
    options.length !== 4 ||
    new Set(options.map((option) => record(option, "option").id)).size !== 4
  )
    fail("Evidence must contain each of the four options exactly once.");
  for (const option of options) {
    const row = record(option, "option");
    if (typeof row.id !== "string" || !ids.includes(row.id))
      fail("Unknown option id.");
    string(row.label, "option label", 200);
    for (const key of [
      "available_hours_day",
      "booked_hours_day",
      "recovered_hours_day",
    ])
      finite(row[key], key, 0, 24);
    for (const key of [
      "useful_hours_year",
      "incremental_useful_hours_year",
      "annual_benefit_usd",
      "upfront_benefit_usd",
      "customer_npv_usd",
      "gross_value_pv_usd",
    ])
      finite(row[key], key);
    if (row.break_even_value_per_hour_usd !== null)
      finite(row.break_even_value_per_hour_usd, "break-even value", 0);
  }
  const recommendation = record(value.recommendation, "recommendation");
  if (typeof recommendation.id !== "string" || !ids.includes(recommendation.id))
    fail("Unknown recommended option.");
  for (const key of [
    "title",
    "summary",
    "contract_verdict",
    "initial_hypothesis",
  ])
    string(recommendation[key], key);
  finite(recommendation.price_ceiling_usd, "price ceiling", 0);
  if (typeof recommendation.survived !== "boolean")
    fail("survived must be boolean.");
  const schedule = record(value.schedule, "schedule");
  for (const key of ["baseline", "calibration"]) {
    const day = record(schedule[key], "schedule day");
    for (const field of ["calibration", "booked", "idle"])
      finite(day[field], field, 0, 24);
  }
  for (const row of list(value.cashflows, "cashflows", 12)) {
    const item = record(row, "cashflow");
    for (const key of ["year", "calibration", "pulse", "control"])
      finite(item[key], key);
  }
  for (const row of list(value.sensitivities, "sensitivities", 50)) {
    const item = record(row, "sensitivity");
    if (
      item.option_id !== undefined &&
      (typeof item.option_id !== "string" || !ids.includes(item.option_id))
    )
      fail("Unknown sensitivity option.");
    string(item.parameter, "parameter", 200);
    string(item.label, "label", 300);
    for (const key of ["low", "high", "low_npv", "high_npv"])
      finite(item[key], key);
  }
  const heatmap = list(value.heatmap, "heatmap", 400).map((row) =>
    record(row, "heatmap cell"),
  );
  for (const item of heatmap) {
    finite(item.value_per_hour, "value per hour", 0);
    finite(item.realization, "realization", 0, 1);
    finite(item.npv, "npv");
    if (
      typeof item.winner !== "string" ||
      ![...ids, "none"].includes(item.winner)
    )
      fail("Unknown heatmap winner.");
  }
  if (
    new Set(heatmap.map((item) => item.value_per_hour)).size *
      new Set(heatmap.map((item) => item.realization)).size >
    400
  )
    fail("The heatmap has too many distinct axes.");
  for (const row of list(value.depth_curve, "depth_curve", 100)) {
    const item = record(row, "depth row");
    finite(item.layers, "depth", 0, 1e6);
    for (const key of [
      "baseline",
      "pulse",
      "baseline_low",
      "baseline_high",
      "pulse_low",
      "pulse_high",
    ])
      finite(item[key], key, 0, 1);
  }
  for (const row of list(value.assumptions, "assumptions", 150)) {
    const item = record(row, "assumption");
    for (const key of ["key", "label", "kind", "rationale"])
      string(item[key], key);
  }
  for (const warning of list(value.warnings, "warnings", 100))
    string(warning, "warning");
  const evidence = record(value.evidence, "evidence metadata");
  for (const key of ["experiment_id", "source", "generated_at"])
    string(evidence[key], key, 300);
  finite(evidence.seed, "seed", 0, 4294967295);
  finite(evidence.shots, "shots", 1, 1e9);
  return value as unknown as AnalysisResponse;
}

export type ImportedData =
  | { kind: "scenario"; scenario: Scenario }
  | { kind: "evidence"; result: AnalysisResponse };
export function parseImport(text: string, defaults: Scenario): ImportedData {
  if (new TextEncoder().encode(text).byteLength > MAX_IMPORT_BYTES)
    fail("Import must be no larger than 1 MB.");
  let data: unknown;
  try {
    data = JSON.parse(text);
  } catch {
    fail("This file is not valid JSON.");
  }
  inspectTree(data);
  const value = record(data, "Import");
  if ("benchmark" in value || "options" in value || "evidence" in value)
    return { kind: "evidence", result: validateEvidence(value) };
  if ("scenario" in value) {
    if (Object.keys(value).some((key) => key !== "scenario"))
      fail("Use a full evidence export or a scenario-only object.");
    return {
      kind: "scenario",
      scenario: validateScenario(value.scenario, defaults),
    };
  }
  return { kind: "scenario", scenario: validateScenario(value, defaults) };
}
