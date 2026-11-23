import { describe, expect, it } from "vitest";
import { parseImport, MAX_IMPORT_BYTES } from "./imports";
import { scenarioCatalog } from "./catalog";
const data = scenarioCatalog.case_default;

describe("untrusted JSON import", () => {
  it("accepts all eight actual evidence exports without altering them", () => {
    for (const result of Object.values(scenarioCatalog)) {
      expect(parseImport(JSON.stringify(result), data.scenario)).toEqual({
        kind: "evidence",
        result,
      });
    }
  });
  it("merges validated partial inputs into explicit defaults", () => {
    const result = parseImport(
      '{"value_mode":"fixed_output_savings","value_realization":0.2}',
      data.scenario,
    );
    expect(result.kind).toBe("scenario");
    if (result.kind === "scenario") {
      expect(result.scenario.value_mode).toBe("fixed_output_savings");
      expect(result.scenario.n_qubits).toBe(data.scenario.n_qubits);
    }
  });
  it.each([
    '{"value_realization":1.1}',
    '{"n_qubits":21}',
    '{"layers":3}',
    '{"shots":2}',
    '{"t1_us":1,"t2_us":10}',
    '{"baseline_gate_ns":1000000,"pulse_duration_increase":1}',
    '{"n_qubits":100,"layers":100,"shots":65536}',
    '{"value_realization":"0.5"}',
    '{"replacement_due":"yes"}',
    '{"shots":1e999}',
    '{"value_mode":"magic"}',
    '{"toString":3}',
    '{"bogus":true}',
  ])("rejects invalid inputs %s", (text) => {
    expect(() => parseImport(text, data.scenario)).toThrow();
  });
  it.each([
    '{"__proto__":{"polluted":true}}',
    '{"scenario":{"constructor":{"prototype":{"polluted":true}}}}',
  ])("rejects prototype injection at every depth", (text) => {
    expect(() => parseImport(text, data.scenario)).toThrow(/Unsafe/);
    expect(({} as Record<string, unknown>).polluted).toBeUndefined();
  });
  it("enforces the UTF-8 byte limit before JSON parsing", () => {
    expect(() =>
      parseImport(" ".repeat(MAX_IMPORT_BYTES + 1), data.scenario),
    ).toThrow(/1 MB/);
    expect(() =>
      parseImport("é".repeat(MAX_IMPORT_BYTES / 2 + 1), data.scenario),
    ).toThrow(/1 MB/);
  });
  it("rejects malformed or incomplete evidence", () => {
    expect(() => parseImport('{"benchmark":{}}', data.scenario)).toThrow();
    const bad = structuredClone(data);
    bad.benchmark.pulse.p_success = 2;
    expect(() => parseImport(JSON.stringify(bad), data.scenario)).toThrow();
  });
  it("rejects duplicated proposals and reversed probability intervals", () => {
    const bad = structuredClone(data);
    bad.options[0].id = bad.options[1].id;
    expect(() => parseImport(JSON.stringify(bad), data.scenario)).toThrow(
      /four options/,
    );
    const inverted = structuredClone(data);
    inverted.benchmark.baseline.ci_low = 0.99;
    expect(() => parseImport(JSON.stringify(inverted), data.scenario)).toThrow(
      /interval/,
    );
  });
  it("treats markup as inert text and does not execute it", () => {
    const supplied = structuredClone(data);
    supplied.recommendation.title = "<img src=x onerror=alert(1)>";
    const parsed = parseImport(JSON.stringify(supplied), data.scenario);
    expect(parsed.kind).toBe("evidence");
  });
  it("rejects non-string IDs and unknown sensitivity targets before rendering", () => {
    const unknown = structuredClone(data) as unknown as Record<string, any>;
    unknown.sensitivities[0].option_id = "not-an-option";
    expect(() => parseImport(JSON.stringify(unknown), data.scenario)).toThrow(
      /sensitivity option/,
    );
    const coercion = structuredClone(data) as unknown as Record<string, any>;
    coercion.options[0].id = ["baseline"];
    expect(() => parseImport(JSON.stringify(coercion), data.scenario)).toThrow(
      /option id/,
    );
  });
});
