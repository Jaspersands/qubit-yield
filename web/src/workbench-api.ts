import type { AnalysisResponse, Scenario } from "./types";

export interface Job {
  id: string;
  status: "queued" | "running" | "completed" | "failed" | "cancelled";
  created_at: string;
  started_at: string | null;
  finished_at: string | null;
  label: string;
  error: string | null;
  experiment_id: string | null;
  result?: AnalysisResponse | null;
  scenario?: Scenario;
  include_depth?: boolean;
  result_deleted?: boolean;
}
export interface Experiment {
  id: string;
  label: string;
  notes: string;
  tags: string[];
  created_at: string;
  updated_at: string;
  scenario_hash: string;
  summary: { recommended: string; verdict: string; customer_npv_usd: number };
  result?: AnalysisResponse;
}

export async function resourceRequest<T>(
  path: string,
  method = "GET",
  body?: unknown,
): Promise<T> {
  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), 120_000);
  try {
    const response = await fetch(path, {
      method,
      signal: controller.signal,
      ...(body === undefined
        ? {}
        : {
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify(body),
          }),
    });
    if (!response.ok) {
      let detail = `Request failed (${response.status}).`;
      try {
        const payload = await response.json();
        if (typeof payload.detail === "string") detail = payload.detail;
        else if (Array.isArray(payload.detail))
          detail = payload.detail
            .map((item: { msg: string }) => item.msg)
            .join("; ");
      } catch {
        /* Keep the HTTP status if no JSON body exists. */
      }
      throw new Error(detail);
    }
    return response.status === 204
      ? (undefined as T)
      : ((await response.json()) as T);
  } finally {
    clearTimeout(timer);
  }
}

export async function queueScenario(
  scenario: Scenario,
  label: string,
  onStatus?: (job: Job) => void,
): Promise<AnalysisResponse> {
  let job = await resourceRequest<Job>("/api/jobs", "POST", {
    scenario,
    label,
    include_depth: false,
  });
  onStatus?.(job);
  for (let attempt = 0; attempt < 200; attempt++) {
    job = await resourceRequest<Job>(`/api/jobs/${encodeURIComponent(job.id)}`);
    onStatus?.(job);
    if (job.status === "completed") {
      if (!job.result)
        throw new Error(
          "The completed job did not contain an analysis. Open History to inspect it.",
        );
      return job.result;
    }
    if (job.status === "failed")
      throw new Error(
        job.error ||
          "The experiment failed. Its record is available in History.",
      );
    if (job.status === "cancelled")
      throw new Error(
        "The queued experiment was cancelled. Your previous result is preserved.",
      );
    if (job.status !== "queued" && job.status !== "running")
      throw new Error("The engine returned an invalid job status.");
    await new Promise((resolve) => setTimeout(resolve, 1500));
  }
  throw new Error(
    "This job is still pending. Open History to follow its status; the server job was not cancelled.",
  );
}
