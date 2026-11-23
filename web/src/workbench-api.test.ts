import { afterEach, describe, expect, it, vi } from "vitest";
import { queueScenario, resourceRequest } from "./workbench-api";
import { scenarioCatalog } from "./catalog";
afterEach(() => vi.unstubAllGlobals());
describe("background job client", () => {
  it("reports queue and completion states while returning the actual evidence", async () => {
    const data = scenarioCatalog.case_default;
    const status = vi.fn();
    const fetch = vi
      .fn()
      .mockResolvedValueOnce({
        ok: true,
        status: 202,
        json: async () => ({ id: "job-a", status: "queued" }),
      })
      .mockResolvedValueOnce({
        ok: true,
        status: 200,
        json: async () => ({ id: "job-a", status: "completed", result: data }),
      });
    vi.stubGlobal("fetch", fetch);
    expect(await queueScenario(data.scenario, "Trial", status)).toEqual(data);
    expect(status.mock.calls.map(([job]) => job.status)).toEqual([
      "queued",
      "completed",
    ]);
    expect(JSON.parse(fetch.mock.calls[0][1].body)).toEqual({
      scenario: data.scenario,
      label: "Trial",
      include_depth: false,
    });
  });
  it.each([
    ["failed", "Hardware-model validation failed"],
    ["cancelled", "cancelled"],
    ["completed", "completed job did not contain"],
  ])(
    "handles %s without returning invented results",
    async (status, message) => {
      const fetch = vi
        .fn()
        .mockResolvedValueOnce({
          ok: true,
          json: async () => ({ id: "job-a", status: "queued" }),
        })
        .mockResolvedValueOnce({
          ok: true,
          json: async () => ({
            id: "job-a",
            status,
            error: status === "failed" ? message : null,
            result: null,
            result_deleted: status === "completed",
          }),
        });
      vi.stubGlobal("fetch", fetch);
      await expect(
        queueScenario(scenarioCatalog.case_default.scenario, "Trial"),
      ).rejects.toThrow(message);
    },
  );
  it("surfaces a full queue response without entering the polling loop", async () => {
    const fetch = vi
      .fn()
      .mockResolvedValue({
        ok: false,
        status: 429,
        json: async () => ({
          detail: "The experiment queue is full. Try again later.",
        }),
      });
    vi.stubGlobal("fetch", fetch);
    await expect(
      queueScenario(scenarioCatalog.case_default.scenario, "Trial"),
    ).rejects.toThrow("queue is full");
    expect(fetch).toHaveBeenCalledTimes(1);
  });
  it("accepts a successful empty deletion response", async () => {
    const json = vi.fn();
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue({ ok: true, status: 204, json }),
    );
    expect(
      await resourceRequest("/api/experiments/test", "DELETE"),
    ).toBeUndefined();
    expect(json).not.toHaveBeenCalled();
  });
});
