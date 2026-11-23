import {
  cleanup,
  fireEvent,
  render,
  screen,
  waitFor,
  within,
} from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import History from "./History";
import { scenarioCatalog } from "./catalog";
const data = scenarioCatalog.case_default;
const base = {
  id: "record-1",
  label: "Baseline trial",
  notes: "Initial result",
  tags: ["pilot"],
  created_at: "2026-11-20T00:00:00Z",
  updated_at: "2026-11-20T00:00:00Z",
  scenario_hash: "abc",
  summary: {
    recommended: "pulse",
    verdict: "Conditional",
    customer_npv_usd: 1945000,
  },
};
const jobs = [
  {
    id: "queued-1",
    label: "Waiting trial",
    status: "queued",
    created_at: base.created_at,
  },
  {
    id: "running-1",
    label: "Active trial",
    status: "running",
    created_at: base.created_at,
  },
  {
    id: "failed-1",
    label: "Failed trial",
    status: "failed",
    created_at: base.created_at,
    error: "Test failure",
  },
];
let fetchMock: ReturnType<typeof vi.fn>;
beforeEach(() => {
  fetchMock = vi.fn(async (path: string, init?: RequestInit) => {
    let payload: unknown = {};
    if (path === "/api/jobs" && !init?.body) payload = { jobs };
    else if (path === "/api/experiments") payload = { experiments: [base] };
    else if (path === "/api/experiments/record-1")
      payload = { ...base, result: data };
    else if (path === "/api/jobs/failed-1")
      payload = {
        ...jobs[2],
        scenario: scenarioCatalog.same_work_savings.scenario,
        include_depth: false,
      };
    return {
      ok: true,
      status: init?.method === "DELETE" ? 204 : 200,
      json: async () => payload,
    };
  });
  vi.stubGlobal("fetch", fetchMock);
});
afterEach(() => {
  cleanup();
  vi.unstubAllGlobals();
});
const open = (props: Partial<React.ComponentProps<typeof History>> = {}) =>
  render(
    <History
      scenario={data.scenario}
      offline={false}
      onLoad={vi.fn()}
      onCompare={vi.fn()}
      {...props}
    />,
  );
describe("persistent history", () => {
  it("has an honest offline boundary and never requests history", () => {
    open({ offline: true });
    expect(
      screen.getByText("History lives with your local engine."),
    ).toBeInTheDocument();
    expect(fetchMock).not.toHaveBeenCalled();
  });
  it("cancels only queued jobs and retries the original failed inputs", async () => {
    open();
    await screen.findByText("Waiting trial");
    expect(screen.getAllByText("Cancel queued job")).toHaveLength(1);
    expect(screen.getByText("Running jobs finish safely")).toBeInTheDocument();
    fireEvent.click(screen.getByText("Cancel queued job"));
    await waitFor(() =>
      expect(
        fetchMock.mock.calls.some(
          ([path]) => path === "/api/jobs/queued-1/cancel",
        ),
      ).toBe(true),
    );
    await waitFor(() =>
      expect(screen.getByText("Retry original inputs")).toBeEnabled(),
    );
    fireEvent.click(screen.getByText("Retry original inputs"));
    await waitFor(() =>
      expect(
        fetchMock.mock.calls.some(
          ([path, init]) => path === "/api/jobs" && init?.method === "POST",
        ),
      ).toBe(true),
    );
    const call = fetchMock.mock.calls.find(
      ([path, init]) => path === "/api/jobs" && init?.method === "POST",
    );
    expect(JSON.parse(String(call?.[1]?.body)).scenario).toEqual(
      scenarioCatalog.same_work_savings.scenario,
    );
  });
  it("loads or compares the full recorded result", async () => {
    const onLoad = vi.fn(),
      onCompare = vi.fn();
    open({ onLoad, onCompare });
    await screen.findByText("Baseline trial");
    fireEvent.click(screen.getByRole("button", { name: "Open" }));
    await waitFor(() =>
      expect(onLoad).toHaveBeenCalledWith(data, "Baseline trial"),
    );
    await waitFor(() =>
      expect(screen.getByRole("button", { name: "Compare" })).toBeEnabled(),
    );
    fireEvent.click(screen.getByRole("button", { name: "Compare" }));
    await waitFor(() =>
      expect(onCompare).toHaveBeenCalledWith(data, "Baseline trial"),
    );
  });
  it("patches cleaned metadata and requires explicit deletion", async () => {
    open();
    await screen.findByText("Baseline trial");
    fireEvent.click(screen.getByText("Edit notes"));
    const modal = screen.getByRole("dialog");
    fireEvent.change(within(modal).getByRole("textbox", { name: "Label" }), {
      target: { value: "  Revised trial  " },
    });
    fireEvent.change(within(modal).getByRole("textbox", { name: /Tags/ }), {
      target: { value: "pilot, reviewed, pilot," },
    });
    fireEvent.click(within(modal).getByText("Save metadata"));
    await waitFor(() =>
      expect(screen.queryByRole("dialog")).not.toBeInTheDocument(),
    );
    const patch = fetchMock.mock.calls.find(
      ([, init]) => init?.method === "PATCH",
    );
    expect(JSON.parse(String(patch?.[1]?.body))).toEqual({
      label: "Revised trial",
      notes: "Initial result",
      tags: ["pilot", "reviewed"],
    });
    fireEvent.click(screen.getByLabelText("Delete Baseline trial"));
    expect(
      fetchMock.mock.calls.some(([, init]) => init?.method === "DELETE"),
    ).toBe(false);
    expect(screen.getByText("Keep record")).toHaveFocus();
    fireEvent.click(screen.getByText("Delete record"));
    await waitFor(() =>
      expect(
        fetchMock.mock.calls.some(([, init]) => init?.method === "DELETE"),
      ).toBe(true),
    );
  });
});
