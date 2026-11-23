import {
  cleanup,
  fireEvent,
  render,
  screen,
  waitFor,
} from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import Strategy from "./Strategy";
import { scenarioCatalog } from "./catalog";
import tools from "../public/tools.json";
afterEach(() => {
  cleanup();
  vi.unstubAllGlobals();
});
describe("stress and pricing tools", () => {
  it("explores actual precomputed results offline and distinguishes coverage from probability", () => {
    const fetch = vi.fn();
    vi.stubGlobal("fetch", fetch);
    render(
      <Strategy scenario={scenarioCatalog.case_default.scenario} offline />,
    );
    expect(screen.getByText("Coverage, not probability")).toBeInTheDocument();
    expect(screen.getByText(/125 GRID CELLS/)).toBeInTheDocument();
    expect(screen.getByText("Run stress grid")).toBeDisabled();
    fireEvent.click(screen.getByRole("tab", { name: "Pricing feasibility" }));
    expect(
      screen.getByText("Is there a price both sides can accept?"),
    ).toBeInTheDocument();
    expect(screen.getByText("Evaluate pricing")).toBeDisabled();
    expect(screen.getAllByText("No feasible offer").length).toBeGreaterThan(0);
    expect(fetch).not.toHaveBeenCalled();
  });
  it("keeps original tool results visibly stale when assumptions change", () => {
    render(
      <Strategy scenario={scenarioCatalog.case_default.scenario} offline />,
    );
    fireEvent.change(
      screen.getByRole("spinbutton", {
        name: "High productive-hour value (USD)",
      }),
      { target: { value: 3000 } },
    );
    expect(
      screen.getByText(/Showing the last completed tool result/),
    ).toBeInTheDocument();
    expect(screen.getByText(/125 GRID CELLS/)).toBeInTheDocument();
  });
  it("submits pricing assumptions to Python without doing browser financial math", async () => {
    const fetch = vi.fn(async () => ({
      ok: true,
      status: 200,
      json: async () => ({
        ...tools.pricing,
        inputs: { ...tools.pricing.inputs, customer_value_share: 0.35 },
      }),
    }));
    vi.stubGlobal("fetch", fetch);
    render(
      <Strategy
        scenario={scenarioCatalog.same_work_savings.scenario}
        offline={false}
      />,
    );
    fireEvent.click(screen.getByRole("tab", { name: "Pricing feasibility" }));
    fireEvent.change(
      screen.getByRole("spinbutton", {
        name: "Vendor share of customer value",
      }),
      { target: { value: 0.35 } },
    );
    fireEvent.click(screen.getByText("Evaluate pricing"));
    await waitFor(() => expect(fetch).toHaveBeenCalled());
    const [path, init] = fetch.mock.calls[0] as unknown as [
      string,
      RequestInit,
    ];
    expect(path).toBe("/api/pricing");
    expect(JSON.parse(String(init.body))).toMatchObject({
      customer_value_share: 0.35,
      scenario: { value_mode: "fixed_output_savings" },
    });
    await screen.findByText("Computed by local engine");
  });
  it("preserves prior results when the engine rejects a stress range", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn(async () => ({
        ok: false,
        status: 422,
        json: async () => ({ detail: "Low value must not exceed high value" }),
      })),
    );
    render(
      <Strategy
        scenario={scenarioCatalog.case_default.scenario}
        offline={false}
      />,
    );
    fireEvent.click(screen.getByText("Run stress grid"));
    await screen.findByRole("alert");
    expect(
      screen.getByText("Low value must not exceed high value"),
    ).toBeInTheDocument();
    expect(screen.getByText(/125 GRID CELLS/)).toBeInTheDocument();
  });
});
