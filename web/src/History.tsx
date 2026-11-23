import { useCallback, useEffect, useState } from "react";
import {
  Clock3,
  Play,
  RefreshCw,
  Save,
  Trash2,
  X,
  GitCompareArrows,
  ArrowUpRight,
  Database,
} from "lucide-react";
import type { AnalysisResponse, Scenario } from "./types";
import type { Experiment, Job } from "./workbench-api";
import { resourceRequest } from "./workbench-api";
import { money, optionNames } from "./utils";
import Modal from "./Modal";

type Props = {
  scenario: Scenario;
  offline: boolean;
  onLoad: (result: AnalysisResponse, label: string) => void;
  onCompare: (result: AnalysisResponse, label: string) => void;
};
const stamp = (value: string) => {
  const date = new Date(value);
  return Number.isNaN(date.getTime()) ? value : date.toLocaleString();
};

export default function History({
  scenario,
  offline,
  onLoad,
  onCompare,
}: Props) {
  const [jobs, setJobs] = useState<Job[]>([]);
  const [records, setRecords] = useState<Experiment[]>([]);
  const [error, setError] = useState("");
  const [pending, setPending] = useState("");
  const [search, setSearch] = useState("");
  const [label, setLabel] = useState("Calibration decision");
  const [edit, setEdit] = useState<Experiment | null>(null);
  const [remove, setRemove] = useState<Experiment | null>(null);
  const refresh = useCallback(async () => {
    if (offline) return;
    try {
      const [j, e] = await Promise.all([
        resourceRequest<{ jobs: Job[] }>("/api/jobs"),
        resourceRequest<{ experiments: Experiment[] }>("/api/experiments"),
      ]);
      setJobs(j.jobs);
      setRecords(e.experiments);
    } catch (err) {
      setError(
        err instanceof Error ? err.message : "Could not load server history.",
      );
    }
  }, [offline]);
  useEffect(() => {
    void refresh();
    if (offline) return;
    const interval = setInterval(() => void refresh(), 4000);
    return () => clearInterval(interval);
  }, [refresh, offline]);
  const act = async (key: string, fn: () => Promise<void>) => {
    setPending(key);
    setError("");
    try {
      await fn();
      await refresh();
    } catch (err) {
      setError(err instanceof Error ? err.message : "The action failed.");
    } finally {
      setPending("");
    }
  };
  const detail = async (record: Experiment) => {
    const full = await resourceRequest<Experiment>(
      `/api/experiments/${encodeURIComponent(record.id)}`,
    );
    if (!full.result)
      throw new Error("This record does not contain a completed analysis.");
    return full.result;
  };
  const queue = async (input: Scenario, name: string, includeDepth = false) => {
    await resourceRequest<Job>("/api/jobs", "POST", {
      scenario: input,
      label: name,
      include_depth: includeDepth,
    });
  };
  const saveEdit = () =>
    edit &&
    void act("edit", async () => {
      const tags = [
        ...new Set(edit.tags.map((tag) => tag.trim()).filter(Boolean)),
      ];
      if (tags.length > 8 || tags.some((tag) => tag.length > 40))
        throw new Error(
          "Use at most 8 tags, each no longer than 40 characters.",
        );
      await resourceRequest(
        `/api/experiments/${encodeURIComponent(edit.id)}`,
        "PATCH",
        { label: edit.label.trim(), notes: edit.notes, tags },
      );
      setEdit(null);
    });
  if (offline)
    return (
      <section className="panel engine-required">
        <Database size={34} />
        <span className="eyebrow">PERSISTENT EXPERIMENT WORKSPACE</span>
        <h2>History lives with your local engine.</h2>
        <p>
          The standalone preview does not create server records or run
          background jobs. Start the Python server to queue experiments,
          annotate results and keep a searchable SQLite history.
        </p>
        <code>qubityield serve</code>
        <p>
          Your saved browser snapshots and eight precomputed scenarios are still
          available in this preview.
        </p>
      </section>
    );
  return (
    <>
      <section className="panel history-queue">
        <div>
          <span className="eyebrow">RUN, RECORD, REVISIT</span>
          <h2>Your experiment workspace</h2>
          <p>
            Queue the current draft inputs. Completed jobs automatically become
            persistent experiment records.
          </p>
        </div>
        <form
          onSubmit={(event) => {
            event.preventDefault();
            void act("queue", () => queue(scenario, label));
          }}
        >
          <label className="workbench-field">
            <span>Experiment label</span>
            <input
              maxLength={120}
              required
              value={label}
              onChange={(event) => setLabel(event.target.value)}
            />
          </label>
          <button
            className="primary-button"
            disabled={!!pending || !label.trim()}
          >
            <Play size={14} />
            Queue current scenario
          </button>
        </form>
      </section>
      {error && (
        <div className="error-banner" role="alert">
          <span>{error}</span>
          <button
            className="icon-button"
            aria-label="Dismiss history error"
            onClick={() => setError("")}
          >
            <X size={16} />
          </button>
        </div>
      )}
      <section className="panel">
        <div className="panel-heading">
          <div>
            <p className="eyebrow">BACKGROUND WORK</p>
            <h2>Job queue</h2>
          </div>
          <button className="outlined-button" onClick={() => void refresh()}>
            <RefreshCw size={14} />
            Refresh
          </button>
        </div>
        <div className="job-list">
          {jobs.length === 0 ? (
            <p className="workbench-empty">
              No jobs yet. Queue the current scenario to create your first
              durable result.
            </p>
          ) : (
            jobs.map((job) => (
              <article className="job-row" key={job.id}>
                <span className={`job-status ${job.status}`}>
                  <i />
                  {job.status}
                </span>
                <div>
                  <h3>{job.label}</h3>
                  <p>
                    {stamp(job.created_at)}
                    {job.error && ` · ${job.error}`}
                  </p>
                  <code>{job.id.slice(0, 8)}</code>
                </div>
                {job.status === "queued" && (
                  <button
                    className="outlined-button"
                    disabled={!!pending}
                    onClick={() =>
                      void act(job.id, async () => {
                        await resourceRequest(
                          `/api/jobs/${encodeURIComponent(job.id)}/cancel`,
                          "POST",
                        );
                      })
                    }
                  >
                    Cancel queued job
                  </button>
                )}
                {job.status === "running" && (
                  <span className="job-hint">Running jobs finish safely</span>
                )}
                {job.status === "completed" && job.experiment_id && (
                  <button
                    className="outlined-button"
                    disabled={!!pending}
                    onClick={() =>
                      void act(job.id, async () => {
                        const full = await resourceRequest<Job>(
                          `/api/jobs/${encodeURIComponent(job.id)}`,
                        );
                        if (full.result) onLoad(full.result, job.label);
                        else
                          throw new Error(
                            full.result_deleted
                              ? "This result was deleted from history. Rerun the original job to produce a new record."
                              : "The result is not available yet.",
                          );
                      })
                    }
                  >
                    Open result <ArrowUpRight size={14} />
                  </button>
                )}
                {["failed", "cancelled", "completed"].includes(job.status) && (
                  <button
                    className="outlined-button"
                    disabled={!!pending}
                    onClick={() =>
                      void act(job.id, async () => {
                        const full = await resourceRequest<Job>(
                          `/api/jobs/${encodeURIComponent(job.id)}`,
                        );
                        if (!full.scenario)
                          throw new Error(
                            "The original inputs are not available for this job.",
                          );
                        await queue(
                          full.scenario,
                          `${job.label.slice(0, 110)} · retry`,
                          full.include_depth || false,
                        );
                      })
                    }
                  >
                    Retry original inputs
                  </button>
                )}
              </article>
            ))
          )}
        </div>
        <p className="panel-note">
          Queued jobs can be cancelled. Running jobs are not interrupted. The
          list refreshes while this screen is open.
        </p>
      </section>
      <section className="panel">
        <div className="panel-heading">
          <div>
            <p className="eyebrow">SAVED ON THE SERVER</p>
            <h2>
              Experiment history{" "}
              <span className="count-label">{records.length}</span>
            </h2>
          </div>
          <label className="search-field">
            <input
              aria-label="Search experiment history"
              placeholder="Search labels, notes, tags"
              value={search}
              onChange={(event) => setSearch(event.target.value)}
            />
          </label>
        </div>
        <div className="history-records">
          {records
            .filter((record) =>
              `${record.label} ${record.notes} ${record.tags.join(" ")}`
                .toLowerCase()
                .includes(search.toLowerCase()),
            )
            .map((record) => (
              <article className="history-card" key={record.id}>
                <div className="history-card-top">
                  <div>
                    <h3>{record.label}</h3>
                    <span>
                      <Clock3 size={12} />
                      {stamp(record.created_at)}
                    </span>
                  </div>
                  <strong>{money(record.summary.customer_npv_usd)}</strong>
                </div>
                <div className="history-card-decision">
                  <span>
                    {optionNames[record.summary.recommended] ||
                      record.summary.recommended}
                  </span>
                  <span>{record.summary.verdict}</span>
                </div>
                {record.notes && (
                  <p className="history-notes">{record.notes}</p>
                )}
                {record.tags.length > 0 && (
                  <div className="tag-list">
                    {record.tags.map((tag) => (
                      <span key={tag}>{tag}</span>
                    ))}
                  </div>
                )}
                <div className="history-actions">
                  <button
                    onClick={() =>
                      void act(record.id, async () =>
                        onLoad(await detail(record), record.label),
                      )
                    }
                    disabled={!!pending}
                  >
                    <ArrowUpRight size={14} />
                    Open
                  </button>
                  <button
                    onClick={() =>
                      void act(record.id, async () =>
                        onCompare(await detail(record), record.label),
                      )
                    }
                    disabled={!!pending}
                  >
                    <GitCompareArrows size={14} />
                    Compare
                  </button>
                  <button
                    onClick={() =>
                      void act(record.id, async () => {
                        const result = await detail(record);
                        await queue(
                          result.scenario,
                          `${record.label.slice(0, 110)} · rerun`,
                        );
                      })
                    }
                    disabled={!!pending}
                  >
                    <Play size={13} />
                    Rerun
                  </button>
                  <button
                    onClick={() =>
                      setEdit({ ...record, tags: [...record.tags] })
                    }
                    disabled={!!pending}
                  >
                    <Save size={13} />
                    Edit notes
                  </button>
                  <button
                    className="danger-button"
                    onClick={() => setRemove(record)}
                    disabled={!!pending}
                    aria-label={`Delete ${record.label}`}
                  >
                    <Trash2 size={13} />
                  </button>
                </div>
              </article>
            ))}
        </div>
        {records.length === 0 && (
          <p className="workbench-empty">
            Completed queued jobs appear here. Direct quick evaluations are not
            automatically added to history.
          </p>
        )}
      </section>
      {edit && (
        <Modal labelledBy="edit-experiment-title" onClose={() => setEdit(null)}>
          <div className="drawer-heading">
            <h2 id="edit-experiment-title">Annotate experiment</h2>
            <button
              className="icon-button"
              aria-label="Close experiment editor"
              onClick={() => setEdit(null)}
            >
              <X size={19} />
            </button>
          </div>
          <label className="workbench-field">
            <span>Label</span>
            <input
              data-autofocus
              value={edit.label}
              maxLength={120}
              onChange={(event) =>
                setEdit({ ...edit, label: event.target.value })
              }
            />
          </label>
          <label className="workbench-field">
            <span>Notes</span>
            <textarea
              rows={6}
              value={edit.notes}
              maxLength={4000}
              onChange={(event) =>
                setEdit({ ...edit, notes: event.target.value })
              }
            />
          </label>
          <label className="workbench-field">
            <span>Tags, separated by commas (up to 8)</span>
            <input
              value={edit.tags.join(", ")}
              maxLength={328}
              onChange={(event) =>
                setEdit({
                  ...edit,
                  tags: event.target.value.split(",").map((tag) => tag.trim()),
                })
              }
            />
          </label>
          {error && (
            <div className="error-banner" role="alert">
              {error}
            </div>
          )}
          <div className="modal-actions">
            <button className="outlined-button" onClick={() => setEdit(null)}>
              Cancel
            </button>
            <button
              className="primary-button"
              disabled={!!pending || !edit.label.trim()}
              onClick={saveEdit}
            >
              Save metadata
            </button>
          </div>
        </Modal>
      )}
      {remove && (
        <Modal
          labelledBy="delete-experiment-title"
          onClose={() => setRemove(null)}
        >
          <div className="drawer-heading">
            <h2 id="delete-experiment-title">Delete this history record?</h2>
            <button
              className="icon-button"
              aria-label="Close delete dialog"
              onClick={() => setRemove(null)}
            >
              <X size={19} />
            </button>
          </div>
          <p className="drawer-description">
            “{remove.label}” will be removed from server history. Export or save
            a browser snapshot first if you need a copy.
          </p>
          {error && (
            <div className="error-banner" role="alert">
              {error}
            </div>
          )}
          <div className="modal-actions">
            <button
              className="outlined-button"
              data-autofocus
              onClick={() => setRemove(null)}
            >
              Keep record
            </button>
            <button
              className="danger-solid"
              disabled={!!pending}
              onClick={() =>
                void act("delete", async () => {
                  await resourceRequest(
                    `/api/experiments/${encodeURIComponent(remove.id)}`,
                    "DELETE",
                  );
                  setRemove(null);
                })
              }
            >
              Delete record
            </button>
          </div>
        </Modal>
      )}
    </>
  );
}
