import { describe, expect, it, vi, afterEach } from "vitest";
import {
  analysisCsv,
  apiRequest,
  applyPreset,
  money,
  physicsChanged,
} from "./utils";
import demo from "../public/demo.json";
import type { AnalysisResponse } from "./types";

const data = demo as unknown as AnalysisResponse;
afterEach(() => vi.unstubAllGlobals());

describe("scenario routing and presets", () => {
  it("reuses the physical evidence only for commercial edits", () => {
    expect(
      physicsChanged(data.scenario, {
        ...data.scenario,
        value_per_productive_hour: 2000,
      }),
    ).toBe(false);
    expect(
      physicsChanged(data.scenario, {
        ...data.scenario,
        pulse_gate_error: 0.004,
      }),
    ).toBe(true);
    expect(physicsChanged(data.scenario, { ...data.scenario, seed: 23 })).toBe(
      true,
    );
    expect(
      physicsChanged(data.scenario, {
        ...data.scenario,
        noise_mode: "control_only",
      }),
    ).toBe(true);
  });
  it("preserves physical settings when applying a commercial preset", () => {
    const conservative = applyPreset(data.scenario, "conservative");
    expect(conservative.value_realization).toBe(0.15);
    expect(conservative.value_per_productive_hour).toBe(500);
    expect(physicsChanged(data.scenario, conservative)).toBe(false);
    expect(data.scenario.value_realization).toBe(0.35);
  });
  it("switches the economic interpretation without changing the quantum evidence", () => {
    const savings = applyPreset(data.scenario, "savings");
    expect(savings.value_mode).toBe("fixed_output_savings");
    expect(physicsChanged(data.scenario, savings)).toBe(false);
  });
});

describe("reviewable exports", () => {
  it("quotes fields and preserves full numeric precision in CSV", () => {
    const changed = {
      ...data,
      options: [
        {
          ...data.options[0],
          label: 'Test, "quoted" option',
          customer_npv_usd: -1234.56789,
        },
      ],
    };
    const csv = analysisCsv(changed);
    expect(csv).toContain('"Test, ""quoted"" option"');
    expect(csv).toContain('"-1234.56789"');
    expect(csv.split("\n")).toHaveLength(2);
  });
  it("neutralizes spreadsheet formulas in untrusted labels while preserving numeric losses", () => {
    const changed = {
      ...data,
      options: [
        {
          ...data.options[0],
          label: '=HYPERLINK("https://evil.test")',
          customer_npv_usd: -200,
        },
      ],
    };
    const csv = analysisCsv(changed);
    expect(csv).toContain("' =".replace(" ", ""));
    expect(csv).toContain('"-200"');
  });
  it("does not turn an unattainable break-even value into a zero price", () => {
    expect(money(null)).toBe("Not reached");
    expect(money(Number.POSITIVE_INFINITY)).toBe("Not reached");
    expect(money(0)).toBe("$0");
    expect(money(-1_500_000)).toBe("−$1.50M");
  });
});

describe("engine errors", () => {
  it("shows validated field errors from the API instead of discarding them", async () => {
    vi.stubGlobal(
      "fetch",
      vi
        .fn()
        .mockResolvedValue({
          ok: false,
          status: 422,
          json: async () => ({
            detail: [
              {
                loc: ["body", "t2_us"],
                msg: "T2 must be no greater than twice T1",
              },
            ],
          }),
        }),
    );
    await expect(apiRequest("/api/benchmark", data.scenario)).rejects.toThrow(
      "t2_us: T2 must be no greater than twice T1",
    );
  });
  it("sends scenarios as JSON without mutating the submitted result", async () => {
    const fetchMock = vi
      .fn()
      .mockResolvedValue({ ok: true, json: async () => data });
    vi.stubGlobal("fetch", fetchMock);
    await apiRequest("/api/evaluate", data.scenario);
    const request = fetchMock.mock.calls[0][1];
    expect(request.method).toBe("POST");
    expect(JSON.parse(request.body)).toEqual(data.scenario);
    expect(request.headers["Content-Type"]).toBe("application/json");
  });
});
