import {
  fireEvent,
  render,
  screen,
  waitFor,
  cleanup,
} from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import App from "./App";
import demo from "../public/demo.json";
import type { AnalysisResponse } from "./types";
import { scenarioCatalog } from "./catalog";

vi.mock("./charts", () => ({
  CashflowChart: () => <div>Cashflow chart</div>,
  DepthChart: () => <div>Depth chart</div>,
  Heatmap: () => <div>Heatmap</div>,
  Schedule: () => <div>Schedule chart</div>,
  Tornado: () => <div>Sensitivity chart</div>,
  ValueChart: () => <div>Value chart</div>,
}));

const data = demo as unknown as AnalysisResponse;
let fetchMock: ReturnType<typeof vi.fn>;

beforeEach(() => {
  localStorage.clear();
  window.history.replaceState(null, "", "/");
  vi.stubGlobal("scrollTo", vi.fn());
  let submittedScenario = data.scenario;
  fetchMock = vi
    .fn()
    .mockImplementation(async (path: string, init?: RequestInit) => {
      if (path === "/api/jobs" && init?.method === "POST") {
        submittedScenario = JSON.parse(String(init.body)).scenario;
        return {
          ok: true,
          status: 202,
          json: async () => ({ id: "test-job", status: "queued" }),
        };
      }
      if (path === "/api/jobs/test-job")
        return {
          ok: true,
          json: async () => ({
            id: "test-job",
            status: "completed",
            result: { ...data, scenario: submittedScenario },
          }),
        };
      if (path === "/api/jobs")
        return { ok: true, json: async () => ({ jobs: [] }) };
      if (path === "/api/experiments")
        return { ok: true, json: async () => ({ experiments: [] }) };
      if (path === "/api/defaults")
        return { ok: true, json: async () => data.scenario };
      const result = init?.body
        ? { ...data, scenario: JSON.parse(String(init.body)) }
        : data;
      return { ok: true, json: async () => result };
    });
  vi.stubGlobal("fetch", fetchMock);
});
afterEach(() => {
  cleanup();
  vi.unstubAllGlobals();
});

async function open() {
  render(<App />);
  await screen.findByText("Prioritize pulse optimization");
}

describe("decision workflow", () => {
  it("loads evidence, switches sections and filters assumptions", async () => {
    await open();
    fireEvent.click(screen.getByRole("button", { name: /^Assumptions/ }));
    expect(screen.getByText(/Every claim has a place/)).toBeInTheDocument();
    fireEvent.change(
      screen.getByRole("textbox", { name: "Search assumptions" }),
      { target: { value: "a phrase that will not match" } },
    );
    expect(
      screen.getByText("No assumptions match this search."),
    ).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "Experiment lab" }));
    expect(
      screen.getByText("The same circuit. Two gate proposals."),
    ).toBeInTheDocument();
  });
  it("sends commercial edits to evaluate and preserves the old result until completion", async () => {
    await open();
    fireEvent.change(
      screen.getByRole("spinbutton", { name: "Value per productive hour" }),
      { target: { value: 1500 } },
    );
    expect(
      screen.getByText(/Showing the last completed result/),
    ).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "Run analysis" }));
    await waitFor(() =>
      expect(
        fetchMock.mock.calls.some(([path]) => path === "/api/evaluate"),
      ).toBe(true),
    );
    await screen.findByText("Analysis complete. Decision updated.");
    const call = fetchMock.mock.calls.find(
      ([path]) => path === "/api/evaluate",
    );
    expect(JSON.parse(String(call?.[1]?.body)).value_per_productive_hour).toBe(
      1500,
    );
  });
  it("reruns physical evidence after a gate-error change", async () => {
    await open();
    fireEvent.click(screen.getByRole("tab", { name: "Hardware" }));
    expect(screen.getByRole("spinbutton", { name: "T1" })).toHaveAttribute(
      "id",
      "input-t1",
    );
    expect(screen.getByRole("spinbutton", { name: "T2" })).toHaveAttribute(
      "id",
      "input-t2",
    );
    fireEvent.change(
      screen.getByRole("slider", { name: "Optimized gate error" }),
      { target: { value: "0.004" } },
    );
    fireEvent.click(
      screen.getByRole("button", { name: "Run quantum benchmark" }),
    );
    await waitFor(() =>
      expect(fetchMock.mock.calls.some(([path]) => path === "/api/jobs")).toBe(
        true,
      ),
    );
    await screen.findByText("Quantum benchmark complete. Decision updated.");
  });
  it("saves completed evidence and compares it without pretending draft edits were evaluated", async () => {
    await open();
    fireEvent.click(screen.getByRole("button", { name: "Save scenario" }));
    expect(
      JSON.parse(localStorage.getItem("qubityield-scenarios-v1") || "[]"),
    ).toHaveLength(1);
    fireEvent.click(screen.getByRole("button", { name: /^Compare scenarios/ }));
    expect(screen.getByRole("dialog")).toBeInTheDocument();
    expect(screen.getByText("Current result")).toBeInTheDocument();
    fireEvent.click(
      screen.getByRole("button", { name: "Close scenario comparison" }),
    );
    fireEvent.change(
      screen.getByRole("spinbutton", { name: "Value per productive hour" }),
      { target: { value: 700 } },
    );
    fireEvent.click(screen.getByRole("button", { name: "Save scenario" }));
    expect(
      JSON.parse(localStorage.getItem("qubityield-scenarios-v1") || "[]"),
    ).toHaveLength(1);
    expect(
      screen.getByText(
        "Run the changed inputs before saving the new scenario.",
      ),
    ).toBeInTheDocument();
  });
  it("labels saved evidence and disables new analysis if the API is unavailable", async () => {
    fetchMock.mockImplementation(async (path: string) => {
      if (path.startsWith("/api/")) throw new Error("Engine unavailable");
      return { ok: true, json: async () => data };
    });
    await open();
    expect(screen.getByText("Saved experiment")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Run analysis" })).toBeDisabled();
  });
  it("loads the embedded real experiment when neither API nor static files can be fetched", async () => {
    fetchMock.mockRejectedValue(new Error("Offline"));
    await open();
    expect(screen.getByText("Saved experiment")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Run analysis" })).toBeDisabled();
    fireEvent.click(screen.getByRole("button", { name: "Experiment lab" }));
    expect(
      screen.getByText("The same circuit. Two gate proposals."),
    ).toBeInTheDocument();
    expect(
      screen.getByRole("button", { name: "Rerun experiment" }),
    ).toBeDisabled();
    fireEvent.click(screen.getByRole("button", { name: "Save scenario" }));
    expect(
      JSON.parse(localStorage.getItem("qubityield-scenarios-v1") || "[]"),
    ).toHaveLength(1);
    fireEvent.click(screen.getByRole("button", { name: /^Compare scenarios/ }));
    expect(screen.getByRole("dialog")).toBeInTheDocument();
  });
  it("loads the exact saved same-work scenario offline without claiming a new computation", async () => {
    fetchMock.mockRejectedValue(new Error("Offline"));
    await open();
    const requestsBeforeSelection = fetchMock.mock.calls.length;
    fireEvent.change(
      screen.getByRole("combobox", { name: "Load a completed analysis" }),
      { target: { value: "same_work_savings" } },
    );
    expect(
      screen.getByRole("combobox", { name: "What creates value?" }),
    ).toHaveValue("fixed_output_savings");
    expect(
      screen.getByText(
        "Loaded a precomputed result and its exact inputs. No new analysis was run.",
      ),
    ).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Run analysis" })).toBeDisabled();
    fireEvent.click(screen.getByRole("button", { name: "Save scenario" }));
    const saved = JSON.parse(
      localStorage.getItem("qubityield-scenarios-v1") || "[]",
    );
    expect(saved[0].name).toBe("Same work, less time");
    expect(saved[0].data).toEqual(scenarioCatalog.same_work_savings);
    expect(fetchMock.mock.calls.length).toBe(requestsBeforeSelection);
  });
  it("keeps saved evidence unchanged after offline draft edits and restores exact saved inputs", async () => {
    fetchMock.mockRejectedValue(new Error("Offline"));
    await open();
    fireEvent.change(
      screen.getByRole("combobox", { name: "Load a completed analysis" }),
      { target: { value: "same_work_savings" } },
    );
    fireEvent.change(
      screen.getByRole("spinbutton", { name: "Value per productive hour" }),
      { target: { value: 700 } },
    );
    expect(
      screen.getByText(
        "Showing the saved result. Draft edits are not recalculated offline.",
      ),
    ).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Run analysis" })).toBeDisabled();
    fireEvent.click(screen.getByRole("button", { name: "Save scenario" }));
    expect(localStorage.getItem("qubityield-scenarios-v1")).toBeNull();
    fireEvent.click(
      screen.getByRole("button", { name: "Restore saved inputs" }),
    );
    expect(
      screen.getByRole("spinbutton", { name: "Value per productive hour" }),
    ).toHaveValue(
      scenarioCatalog.same_work_savings.scenario.value_per_productive_hour,
    );
    expect(
      screen.getByRole("combobox", { name: "What creates value?" }),
    ).toHaveValue("fixed_output_savings");
    expect(
      screen.queryByText(
        "Showing the saved result. Draft edits are not recalculated offline.",
      ),
    ).not.toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "Save scenario" }));
    expect(
      JSON.parse(localStorage.getItem("qubityield-scenarios-v1") || "[]")[0]
        .data,
    ).toEqual(scenarioCatalog.same_work_savings);
  });
  it("does not offer the offline catalog while the live analysis engine is connected", async () => {
    await open();
    expect(
      screen.queryByRole("combobox", { name: "Load a completed analysis" }),
    ).not.toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Run analysis" })).toBeEnabled();
  });
  it("imports partial inputs without replacing the previous result", async () => {
    await open();
    const trigger = screen.getByRole("button", { name: "Import JSON" });
    trigger.focus();
    fireEvent.click(trigger);
    fireEvent.change(screen.getByRole("textbox", { name: "Or paste JSON" }), {
      target: {
        value:
          '{"value_per_productive_hour":250,"value_mode":"fixed_output_savings"}',
      },
    });
    fireEvent.click(screen.getByText("Validate and import"));
    expect(screen.queryByRole("dialog")).not.toBeInTheDocument();
    expect(trigger).toHaveFocus();
    expect(
      screen.getByRole("spinbutton", { name: "Value per productive hour" }),
    ).toHaveValue(250);
    expect(
      screen.getByText(/Showing the last completed result/),
    ).toBeInTheDocument();
    expect(
      screen.getByText("Prioritize pulse optimization"),
    ).toBeInTheDocument();
  });
  it("labels imported evidence as supplied and preserves its exact data", async () => {
    await open();
    fireEvent.click(screen.getByRole("button", { name: "Import JSON" }));
    fireEvent.change(screen.getByRole("textbox", { name: "Or paste JSON" }), {
      target: { value: JSON.stringify(scenarioCatalog.same_work_savings) },
    });
    fireEvent.click(screen.getByText("Validate and import"));
    expect(
      screen.getByText(/supplied evidence, structurally validated/),
    ).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "Save scenario" }));
    expect(
      JSON.parse(localStorage.getItem("qubityield-scenarios-v1") || "[]")[0]
        .data,
    ).toEqual(scenarioCatalog.same_work_savings);
  });
  it("opens a shared precomputed scenario and view without implying live recalculation", async () => {
    window.history.replaceState(
      null,
      "",
      "/#view=experiment&scenario=same_work_savings",
    );
    render(<App />);
    await screen.findByText("The same circuit. Two gate proposals.");
    expect(
      screen.getByRole("combobox", { name: "What creates value?" }),
    ).toHaveValue("fixed_output_savings");
    expect(
      screen.getByRole("combobox", { name: "Load a completed analysis" }),
    ).toHaveValue("same_work_savings");
    expect(
      screen.getByRole("button", { name: "Share precomputed scenario" }),
    ).toBeEnabled();
    fireEvent.change(
      screen.getByRole("spinbutton", { name: "Value per productive hour" }),
      { target: { value: 300 } },
    );
    expect(
      screen.getByRole("button", { name: "Share precomputed scenario" }),
    ).toBeDisabled();
  });

  it("preserves newer draft edits when a pending calculation completes", async () => {
    await open();
    let finish: (value: unknown) => void = () => {};
    const original = fetchMock.getMockImplementation()!;
    fetchMock.mockImplementation((path: string, init?: RequestInit) =>
      path === "/api/evaluate"
        ? new Promise((resolve) => {
            finish = resolve;
          })
        : original(path, init),
    );
    fireEvent.change(
      screen.getByRole("spinbutton", { name: "Value per productive hour" }),
      { target: { value: 1500 } },
    );
    fireEvent.click(screen.getByRole("button", { name: "Run analysis" }));
    fireEvent.change(
      screen.getByRole("spinbutton", { name: "Value per productive hour" }),
      { target: { value: 2000 } },
    );
    finish({
      ok: true,
      json: async () => ({
        ...data,
        scenario: { ...data.scenario, value_per_productive_hour: 1500 },
      }),
    });
    await screen.findByText("Analysis complete. Decision updated.");
    expect(
      screen.getByRole("spinbutton", { name: "Value per productive hour" }),
    ).toHaveValue(2000);
    expect(
      screen.getByText(/Showing the last completed result/),
    ).toBeInTheDocument();
  });
});
