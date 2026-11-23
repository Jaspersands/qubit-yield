import { useEffect, useRef, useState } from "react";
import {
  Activity,
  ArrowDownToLine,
  ArrowRight,
  ArrowUpRight,
  Atom,
  BadgeCheck,
  BarChart3,
  BookOpen,
  Check,
  ChevronDown,
  CircleHelp,
  ClipboardList,
  Clock3,
  Copy,
  Cpu,
  FileJson,
  FlaskConical,
  GitCompareArrows,
  Layers3,
  LayoutDashboard,
  Menu,
  Play,
  Plus,
  Search,
  ShieldCheck,
  TrendingUp,
  X,
  Zap,
  Database,
  Scale,
  Share2,
  Upload,
} from "lucide-react";
import Controls from "./Controls";
import {
  CashflowChart,
  DepthChart,
  Heatmap,
  Schedule,
  Tornado,
  ValueChart,
} from "./charts";
import type { AnalysisResponse, Scenario, Snapshot } from "./types";
import bundledEvidence from "../public/demo.json";
import { catalogEntries, scenarioCatalog } from "./catalog";
import {
  analysisCsv,
  apiRequest,
  applyPreset,
  downloadFile,
  money,
  number,
  optionColors,
  optionNames,
  percent,
  physicsChanged,
} from "./utils";
import History from "./History";
import Strategy from "./Strategy";
import ImportDialog from "./ImportDialog";
import Modal from "./Modal";
import { readShareState, shareHash } from "./share";
import type { ViewId } from "./share";
import { queueScenario } from "./workbench-api";
import type { Job } from "./workbench-api";
import { validateEvidence } from "./imports";
import type { ImportedData } from "./imports";

type View = ViewId;
const views = [
  { id: "decision" as const, label: "Decision desk", icon: LayoutDashboard },
  { id: "experiment" as const, label: "Experiment lab", icon: FlaskConical },
  { id: "strategy" as const, label: "Strategy tools", icon: Scale },
  { id: "history" as const, label: "History", icon: Database },
  { id: "assumptions" as const, label: "Assumptions", icon: ClipboardList },
];
const pageCopy: Record<View, [string, string]> = {
  decision: [
    "The calibration decision.",
    "Three proposals. One first-year bet. A decision you can defend.",
  ],
  experiment: [
    "Show your working.",
    "A reproducible test of the upgrade that matters.",
  ],
  assumptions: [
    "Question every number.",
    "Know what came from the case and what came from the model.",
  ],
  history: [
    "Build an evidence trail.",
    "Queue experiments, annotate findings, and revisit decisions.",
  ],
  strategy: [
    "Make the deal make sense.",
    "Test the downside, price the upside, and expose the assumptions.",
  ],
};
const updateHash = (view: View, scenario?: string) => {
  window.history.replaceState(null, "", shareHash(view, scenario));
};

function isAnalysis(data: unknown): data is AnalysisResponse {
  return (
    !!data &&
    typeof data === "object" &&
    "scenario" in data &&
    "benchmark" in data &&
    "recommendation" in data &&
    "options" in data
  );
}

function PanelHeader({
  eyebrow,
  title,
  right,
}: {
  eyebrow?: string;
  title: string;
  right?: React.ReactNode;
}) {
  return (
    <div className="panel-heading">
      <div>
        {eyebrow && <p className="eyebrow">{eyebrow}</p>}
        <h2>{title}</h2>
      </div>
      {right}
    </div>
  );
}

function Metric({
  label,
  value,
  note,
  icon,
  accent,
}: {
  label: string;
  value: string;
  note: string;
  icon: React.ReactNode;
  accent?: boolean;
}) {
  return (
    <div className={`metric ${accent ? "metric-accent" : ""}`}>
      <div className="metric-top">
        <span>{label}</span>
        {icon}
      </div>
      <strong>{value}</strong>
      <p>{note}</p>
    </div>
  );
}

function DecisionDesk({
  data,
  onExperiment,
  onAssumptions,
}: {
  data: AnalysisResponse;
  onExperiment: () => void;
  onAssumptions: () => void;
}) {
  const selected =
    data.options.find((option) => option.id === data.recommendation.id) ||
    data.options.find((option) => option.id === "pulse");
  const gain = (data.benchmark.throughput_ratio - 1) * 100;
  const calibration = data.options.find(
    (option) => option.id === "calibration",
  );
  return (
    <>
      <section className="decision-hero">
        <div className="hero-topline">
          <span>
            <span className="live-dot" />
            THE CURRENT CALL
          </span>
          <span>01 / 03</span>
        </div>
        <div className="hero-wave" aria-hidden="true">
          <svg viewBox="0 0 350 180">
            <path d="M0 90H50l10-12 10 24 12-48 15 78 18-116 20 145 18-129 16 98 15-74 13 52 10-32 10 17h58" />
            <path
              className="wave-echo"
              d="M0 90H50l10-12 10 24 12-48 15 78 18-116 20 145 18-129 16 98 15-74 13 52 10-32 10 17h58"
            />
          </svg>
        </div>
        <h2>{data.recommendation.title || "Prioritize the right upgrade."}</h2>
        <p className="hero-summary">{data.recommendation.summary}</p>
        <div className="hero-bottom">
          <div>
            <span className="hero-contract-label">CONTRACT DECISION</span>
            <span className="contract-verdict">
              <span />
              {data.recommendation.contract_verdict}
            </span>
          </div>
          <button onClick={onExperiment}>
            Inspect the evidence <ArrowUpRight size={17} />
          </button>
        </div>
      </section>
      <div className="metrics-grid">
        <Metric
          label="Pulse useful-shot rate"
          value={`${data.benchmark.throughput_ratio.toFixed(2)}×`}
          note={`${gain >= 0 ? "+" : ""}${gain.toFixed(0)}% vs. the current gates`}
          icon={<Activity size={17} />}
          accent
        />
        <Metric
          label="Customer NPV"
          value={money(selected?.customer_npv_usd)}
          note="After the proposed contract"
          icon={<TrendingUp size={17} />}
        />
        <Metric
          label="Break-even hour"
          value={money(selected?.break_even_value_per_hour_usd)}
          note="Required productive-hour value"
          icon={<Clock3 size={17} />}
        />
        <Metric
          label="Value-based ceiling"
          value={money(data.recommendation.price_ceiling_usd)}
          note="Total contract, same pay schedule"
          icon={<ShieldCheck size={17} />}
        />
      </div>
      <section className="panel comparison-panel">
        <PanelHeader
          eyebrow="THE COMMERCIAL COMPARISON"
          title="Better hardware. Which better business?"
          right={
            <span className="subtle-pill">
              {data.scenario.contract_years}-year horizon
            </span>
          }
        />
        <div className="comparison-chart-row">
          <ValueChart data={data} />
          <div className="chart-context">
            <span className="context-label">READ THIS FIRST</span>
            <h3>A technical win needs a paying workload.</h3>
            <p>
              Faster or cleaner execution creates potential capacity. The
              customer only captures value when demand and willingness to pay
              are there.
            </p>
            <button className="text-button" onClick={onAssumptions}>
              See what we assumed <ArrowRight size={14} />
            </button>
          </div>
        </div>
        <div className="table-scroll">
          <table className="options-table">
            <thead>
              <tr>
                <th>Proposal</th>
                <th>Annual value</th>
                <th>Value before fee, PV</th>
                <th>Customer NPV</th>
              </tr>
            </thead>
            <tbody>
              {data.options
                .filter((option) => option.id !== "baseline")
                .map((option) => (
                  <tr
                    key={option.id}
                    className={
                      option.id === data.recommendation.id
                        ? "selected-option"
                        : ""
                    }
                  >
                    <td>
                      <i style={{ background: optionColors[option.id] }} />
                      <span>{optionNames[option.id]}</span>
                      {option.id === data.recommendation.id && (
                        <span className="row-tag">Priority</span>
                      )}
                    </td>
                    <td>{money(option.annual_benefit_usd)}</td>
                    <td>{money(option.gross_value_pv_usd)}</td>
                    <td
                      className={
                        option.customer_npv_usd < 0 ? "negative" : "positive"
                      }
                    >
                      {money(option.customer_npv_usd)}
                    </td>
                  </tr>
                ))}
            </tbody>
          </table>
        </div>
        <div className="mobile-results" aria-label="Proposal comparison cards">
          {data.options
            .filter((option) => option.id !== "baseline")
            .map((option) => (
              <article className="mobile-result-card" key={option.id}>
                <h3>{optionNames[option.id]}</h3>
                <dl>
                  <div>
                    <dt>Annual value</dt>
                    <dd>{money(option.annual_benefit_usd)}</dd>
                  </div>
                  <div>
                    <dt>Value before fee, PV</dt>
                    <dd>{money(option.gross_value_pv_usd)}</dd>
                  </div>
                  <div>
                    <dt>Customer NPV</dt>
                    <dd>{money(option.customer_npv_usd)}</dd>
                  </div>
                </dl>
              </article>
            ))}
        </div>
        <p className="panel-note">
          Contract value includes the supplied product. Controls only avoid the
          existing system's purchase price when replacement is already due. All
          dollar values depend on stated assumptions.
        </p>
      </section>
      <div className="two-column-panels">
        <section className="panel">
          <PanelHeader
            eyebrow="CAPACITY IS NOT DEMAND"
            title="Where the day actually goes"
            right={<Clock3 size={17} className="muted-icon" />}
          />
          <Schedule data={data} />
          <div className="insight-strip">
            <span className="insight-number">
              {(calibration?.recovered_hours_day ?? 0).toFixed(2)}h
            </span>
            <p>
              Calibration time recovered per day.
              <br />
              Only useful overlap and unmet demand can turn it into bookings.
            </p>
          </div>
        </section>
        <section className="panel">
          <PanelHeader
            eyebrow="THE PRICE OF A CLEANER CIRCUIT"
            title="The quality gain"
            right={
              <button
                className="icon-button"
                aria-label="Open experiment lab"
                onClick={onExperiment}
              >
                <ArrowUpRight size={18} />
              </button>
            }
          />
          <div className="success-comparison">
            <div>
              <span>Current gates</span>
              <strong>{percent(data.benchmark.baseline.p_success)}</strong>
              <p>{data.scenario.baseline_gate_ns} ns / gate</p>
            </div>
            <ArrowRight size={23} />
            <div className="success-optimized">
              <span>Optimized gates</span>
              <strong>{percent(data.benchmark.pulse.p_success)}</strong>
              <p>
                {Math.round(
                  data.scenario.baseline_gate_ns *
                    (1 + data.scenario.pulse_duration_increase),
                )}{" "}
                ns / gate
              </p>
            </div>
          </div>
          <div className="mini-progress">
            <span
              style={{
                width: percent(data.benchmark.baseline.p_success),
                background: "#a0ada3",
              }}
            />
            <span
              style={{
                width: percent(data.benchmark.pulse.p_success),
                background: "#b3d46d",
              }}
            />
          </div>
          <p className="panel-note">
            Probability of an all-zero return in the mirror benchmark. A
            controlled diagnostic, not a universal application success rate.
          </p>
        </section>
      </div>
      <div className="two-column-panels">
        <section className="panel">
          <PanelHeader
            eyebrow="FIND THE SWITCHING POINT"
            title="When does the contract work?"
          />
          <Heatmap data={data} />
        </section>
        <section className="panel">
          <PanelHeader eyebrow="TIME MATTERS" title="Cashflow, year by year" />
          <CashflowChart data={data} />
          <p className="panel-note">
            Incremental customer cashflow, including rollout timing and contract
            payments. NPV also accounts for the discount rate.
          </p>
        </section>
      </div>
      {data.sensitivities?.length > 0 && (
        <section className="panel">
          <PanelHeader
            eyebrow="WHAT COULD CHANGE THE ANSWER"
            title="Stress-test the decision"
          />
          <Tornado data={data} />
        </section>
      )}
      <section className="hypothesis-panel">
        <div className="hypothesis-icon">
          <BookOpen size={22} />
        </div>
        <div>
          <span className="eyebrow">CLOSE THE INVESTIGATION LOOP</span>
          <h3>
            {data.recommendation.survived
              ? "The initial hypothesis survived."
              : "The experiment changed the initial hypothesis."}
          </h3>
          <p>{data.recommendation.initial_hypothesis}</p>
        </div>
        <span
          className={`hypothesis-status ${data.recommendation.survived ? "yes" : ""}`}
        >
          {data.recommendation.survived ? (
            <Check size={16} />
          ) : (
            <ArrowRight size={16} />
          )}
          {data.recommendation.survived ? "Supported" : "Updated"}
        </span>
      </section>
    </>
  );
}

function CircuitSchematic() {
  return (
    <div className="circuit-figure">
      <svg
        viewBox="0 0 670 225"
        role="img"
        aria-label="Schematic of a mirror circuit: local Clifford gates and entanglers followed by their inverse. Eight representative wires shown."
      >
        <defs>
          <linearGradient id="circuitFade">
            <stop offset="0%" stopColor="#f1f4e8" />
            <stop offset="100%" stopColor="#e2eacb" />
          </linearGradient>
        </defs>
        <rect x="78" y="15" width="253" height="195" rx="10" fill="#edf0e6" />
        <rect
          x="343"
          y="15"
          width="253"
          height="195"
          rx="10"
          fill="url(#circuitFade)"
        />
        {Array.from({ length: 8 }, (_, i) => (
          <g key={i}>
            <text
              x="16"
              y={40 + i * 22}
              fontSize="11"
              fill="#81907e"
              fontFamily="monospace"
            >
              q{i}
            </text>
            <line
              x1="52"
              x2="632"
              y1={36 + i * 22}
              y2={36 + i * 22}
              stroke="#cad5bf"
            />
            {[100, 175, 250, 367, 442, 517].map((x, j) => (
              <g key={x}>
                <rect
                  x={x}
                  y={27 + i * 22}
                  width="23"
                  height="18"
                  rx="4"
                  fill={j > 2 ? "#d5e6b3" : "#fbfcf7"}
                  stroke={j > 2 ? "#b3ce8e" : "#d3dacb"}
                />
                <text
                  x={x + 11.5}
                  y={40 + i * 22}
                  textAnchor="middle"
                  fontSize="9"
                  fill="#576c46"
                  fontFamily="monospace"
                >
                  {j > 2 ? "U†" : i % 2 ? "S" : "H"}
                </text>
              </g>
            ))}
          </g>
        ))}
        {[145, 220, 295, 412, 487, 562].map((x, j) =>
          [0, 2, 4, 6].map((i) => (
            <g key={`${x}-${i}`}>
              <line
                x1={x}
                x2={x}
                y1={36 + i * 22}
                y2={58 + i * 22}
                stroke="#667d50"
                strokeWidth="1.5"
              />
              <circle cx={x} cy={36 + i * 22} r="3.5" fill="#667d50" />
              <circle
                cx={x}
                cy={58 + i * 22}
                r="6"
                fill="#f8fbf3"
                stroke="#667d50"
                strokeWidth="1.4"
              />
              <path
                d={`M${x - 4},${58 + i * 22}h8 M${x},${54 + i * 22}v8`}
                stroke="#667d50"
                strokeWidth="1.2"
              />
              {j === 0 && i === 0 && (
                <title>Disjoint CNOT entangling pairs</title>
              )}
            </g>
          )),
        )}
        <text x="203" y="225" textAnchor="middle" fontSize="11" fill="#6b7b63">
          Randomized forward circuit
        </text>
        <text x="468" y="225" textAnchor="middle" fontSize="11" fill="#6b7b63">
          Exact inverse
        </text>
      </svg>
      <p>
        Illustrative circuit schematic. The actual experiment uses all
        configured qubits and layers.
      </p>
    </div>
  );
}

function ExperimentLab({
  data,
  onRun,
  busy,
  offline,
}: {
  data: AnalysisResponse;
  onRun: () => void;
  busy: boolean;
  offline: boolean;
}) {
  const [showEvidence, setShowEvidence] = useState(false);
  return (
    <>
      <div className="lab-intro">
        <div className="lab-intro-symbol">
          <Atom size={35} strokeWidth={1.2} />
        </div>
        <div>
          <span className="eyebrow">REPRODUCIBLE QUANTUM EVIDENCE</span>
          <h2>The same circuit. Two gate proposals.</h2>
          <p>
            A seeded Clifford mirror benchmark isolates the trade-off between
            lower gate error and longer execution time.
          </p>
        </div>
        <button
          className="outlined-button"
          onClick={onRun}
          disabled={busy || offline}
          title={
            offline
              ? "Start the local engine to rerun the experiment"
              : undefined
          }
        >
          <Play size={14} />
          {busy ? "Running..." : "Rerun experiment"}
        </button>
      </div>
      <div className="experiment-facts">
        <div>
          <Cpu size={17} />
          <span>Qubits</span>
          <strong>{data.scenario.n_qubits}</strong>
        </div>
        <div>
          <Layers3 size={17} />
          <span>Entangling layers</span>
          <strong>{data.scenario.layers}</strong>
        </div>
        <div>
          <Zap size={17} />
          <span>Two-qubit gates</span>
          <strong>{number(data.benchmark.baseline.gate_count)}</strong>
        </div>
        <div>
          <Copy size={17} />
          <span>Shots / circuit</span>
          <strong>{number(data.benchmark.baseline.shots)}</strong>
        </div>
      </div>
      <section className="panel">
        <PanelHeader
          eyebrow="01 / PREPARE AND UNCOMPUTE"
          title="An answer we can check"
          right={<span className="subtle-pill">Seed {data.scenario.seed}</span>}
        />
        <CircuitSchematic />
        <div className="method-three">
          <div>
            <span>01</span>
            <h3>Prepare</h3>
            <p>
              Random local Clifford rotations and disjoint two-qubit layers
              create a reproducible forward circuit.
            </p>
          </div>
          <div>
            <span>02</span>
            <h3>Add realistic noise</h3>
            <p>
              Pauli-frame trajectories sample a declared gate-noise model at
              every entangling operation.
            </p>
          </div>
          <div>
            <span>03</span>
            <h3>Check the return</h3>
            <p>
              The ideal inverse returns every qubit to zero. Noise changes the
              observed return probability.
            </p>
          </div>
        </div>
      </section>
      <div className="two-column-panels">
        <section className="panel">
          <PanelHeader
            eyebrow="02 / COMPARE ACROSS DEPTH"
            title="Does the advantage survive?"
          />
          <div className="legend-row chart-legend">
            <span>
              <i className="dot" style={{ background: "#769d42" }} />
              Optimized gates
            </span>
            <span>
              <i className="dot" style={{ background: "#899a93" }} />
              Current gates
            </span>
          </div>
          <DepthChart data={data} />
          <p className="panel-note">
            Depth-sweep evidence comes from the saved experiment suite. The
            table shows the currently selected circuit run.
          </p>
        </section>
        <section className="panel">
          <PanelHeader
            eyebrow="03 / COUNT THE WHOLE SHOT"
            title="Quality per unit of time"
          />
          <div className="throughput-hero">
            <strong>
              {data.benchmark.throughput_ratio.toFixed(2)}
              <small>×</small>
            </strong>
            <span>useful-shot throughput ratio</span>
          </div>
          <div className="cycle-row">
            <span>Current shot cycle</span>
            <strong>{data.benchmark.baseline_cycle_us.toFixed(1)} µs</strong>
          </div>
          <div className="cycle-row">
            <span>Optimized shot cycle</span>
            <strong>{data.benchmark.pulse_cycle_us.toFixed(1)} µs</strong>
          </div>
          <div className="formula">
            (P<sub>optimized</sub> / T<sub>optimized</sub>) ÷ (P
            <sub>current</sub> / T<sub>current</sub>)
          </div>
          <p className="panel-note">
            The cycle includes fixed initialization and readout overhead.
            Parallel gates count toward layer time, not sequentially toward
            every gate.
          </p>
        </section>
      </div>
      <section className="panel evidence-ledger">
        <PanelHeader
          eyebrow="RESULTS, NOT JUST A HEADLINE"
          title="The evidence ledger"
          right={
            <button
              className="text-button"
              onClick={() => setShowEvidence((value) => !value)}
            >
              <FileJson size={14} />
              {showEvidence ? "Hide metadata" : "Inspect metadata"}
            </button>
          }
        />
        <div className="table-scroll">
          <table className="evidence-table">
            <thead>
              <tr>
                <th>Configuration</th>
                <th>Return probability</th>
                <th>95% Wilson interval</th>
                <th>Gate infidelity</th>
                <th>Gate duration</th>
              </tr>
            </thead>
            <tbody>
              {(["baseline", "pulse"] as const).map((key) => (
                <tr key={key}>
                  <td>
                    <i style={{ background: optionColors[key] }} />
                    {key === "baseline" ? "Current gates" : "Optimized gates"}
                  </td>
                  <td>{percent(data.benchmark[key].p_success, 2)}</td>
                  <td>
                    {percent(data.benchmark[key].ci_low, 2)} to{" "}
                    {percent(data.benchmark[key].ci_high, 2)}
                  </td>
                  <td>
                    {percent(
                      key === "baseline"
                        ? data.scenario.baseline_gate_error
                        : data.scenario.pulse_gate_error,
                      2,
                    )}
                  </td>
                  <td>
                    {key === "baseline"
                      ? data.scenario.baseline_gate_ns
                      : Math.round(
                          data.scenario.baseline_gate_ns *
                            (1 + data.scenario.pulse_duration_increase),
                        )}{" "}
                    ns
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
        <div className="mobile-results" aria-label="Gate evidence cards">
          {(["baseline", "pulse"] as const).map((key) => (
            <article className="mobile-result-card" key={key}>
              <h3>
                {key === "baseline" ? "Current gates" : "Optimized gates"}
              </h3>
              <dl>
                <div>
                  <dt>Return probability</dt>
                  <dd>{percent(data.benchmark[key].p_success, 2)}</dd>
                </div>
                <div>
                  <dt>95% Wilson interval</dt>
                  <dd>
                    {percent(data.benchmark[key].ci_low, 2)} to{" "}
                    {percent(data.benchmark[key].ci_high, 2)}
                  </dd>
                </div>
                <div>
                  <dt>Gate infidelity</dt>
                  <dd>
                    {percent(
                      key === "baseline"
                        ? data.scenario.baseline_gate_error
                        : data.scenario.pulse_gate_error,
                      2,
                    )}
                  </dd>
                </div>
                <div>
                  <dt>Gate duration</dt>
                  <dd>
                    {key === "baseline"
                      ? data.scenario.baseline_gate_ns
                      : Math.round(
                          data.scenario.baseline_gate_ns *
                            (1 + data.scenario.pulse_duration_increase),
                        )}{" "}
                    ns
                  </dd>
                </div>
              </dl>
            </article>
          ))}
        </div>
        {showEvidence && (
          <pre className="evidence-json">
            {JSON.stringify(data.evidence, null, 2)}
          </pre>
        )}
        <p className="panel-note">
          Intervals cover shot sampling for this circuit and noise model. They
          do not cover uncertainty in hardware claims, drift, leakage or the
          commercial assumptions.
        </p>
      </section>
      <div className="model-limits">
        <CircleHelp size={23} />
        <div>
          <h3>A deliberately bounded experiment</h3>
          <p>
            This benchmark is efficiently classically simulable. It tests a
            hardware decision, not quantum advantage. Reported total gate
            infidelity includes decoherence; applying T1/T2 noise again would
            double-count it. The alternative control-only interpretation uses
            Pauli-twirled relaxation and cannot represent nonunital relaxation,
            coherent crosstalk or leakage.
          </p>
        </div>
      </div>
    </>
  );
}

function Assumptions({ data }: { data: AnalysisResponse }) {
  const [filter, setFilter] = useState("all");
  const [search, setSearch] = useState("");
  const assumptions = (data.assumptions || []).filter(
    (item) =>
      (filter === "all" ||
        (filter === "case" ? item.kind === "case" : item.kind !== "case")) &&
      `${item.label} ${item.rationale}`
        .toLowerCase()
        .includes(search.toLowerCase()),
  );
  const printable = (value: unknown) =>
    typeof value === "boolean"
      ? value
        ? "Yes"
        : "No"
      : typeof value === "object"
        ? JSON.stringify(value)
        : String(value);
  return (
    <>
      <section className="assumptions-intro">
        <span className="eyebrow">THE MODEL IS ONLY AS GOOD AS ITS INPUTS</span>
        <h2>
          Every claim has a place.
          <br />
          Every assumption has a label.
        </h2>
        <p>
          The case is fictional. Its numbers are claims to investigate, not
          measurements to trust without qualification. This ledger keeps the
          decision auditable.
        </p>
      </section>
      <div className="assumption-callouts">
        <div>
          <span>01</span>
          <h3>“Faster” has two meanings</h3>
          <p>
            A 70% speed increase reduces duration by 41.2%. A 70% time reduction
            is a much bigger claim. Change the reading and compare.
          </p>
        </div>
        <div>
          <span>02</span>
          <h3>Hours are not revenue</h3>
          <p>
            Most calibration happens overnight, 30% of available capacity is
            unbooked, and a pilot is not a full-device rollout.
          </p>
        </div>
        <div>
          <span>03</span>
          <h3>Installed cost is sunk</h3>
          <p>
            The cheaper controller saves procurement costs only when a purchase
            is due. Integration still uses real engineering time.
          </p>
        </div>
      </div>
      <section className="panel ledger-panel">
        <PanelHeader
          eyebrow="PROVENANCE LEDGER"
          title="Open the assumptions"
          right={
            <span className="subtle-pill">
              {data.assumptions.length} entries
            </span>
          }
        />
        <div className="ledger-tools">
          <div
            className="ledger-filters"
            role="tablist"
            aria-label="Assumption categories"
          >
            {[
              ["all", "All inputs"],
              ["case", "Case claims"],
              ["assumption", "Model assumptions"],
            ].map(([id, label]) => (
              <button
                key={id}
                role="tab"
                aria-selected={filter === id}
                className={filter === id ? "active" : ""}
                onClick={() => setFilter(id)}
              >
                {label}
              </button>
            ))}
          </div>
          <label className="search-field">
            <Search size={15} />
            <input
              aria-label="Search assumptions"
              placeholder="Find an assumption"
              value={search}
              onChange={(event) => setSearch(event.target.value)}
            />
          </label>
        </div>
        <div className="assumption-list">
          {assumptions.map((item) => (
            <div className="assumption-row" key={item.key}>
              <div>
                <span
                  className={`source-tag ${item.kind === "case" ? "case" : ""}`}
                >
                  {item.kind === "case" ? "CASE CLAIM" : "ASSUMPTION"}
                </span>
                <h3>{item.label}</h3>
                <p>{item.rationale}</p>
              </div>
              <span className="assumption-value">{printable(item.value)}</span>
            </div>
          ))}
          {assumptions.length === 0 && (
            <div className="empty-assumptions">
              No assumptions match this search.
            </div>
          )}
        </div>
      </section>
      {data.warnings?.length > 0 && (
        <section className="panel">
          <PanelHeader
            eyebrow="BOUNDARIES OF THIS SCENARIO"
            title="What the decision-maker should know"
          />
          <div className="warning-list">
            {data.warnings.map((warning, i) => (
              <div key={i}>
                <CircleHelp size={17} />
                <p>{warning}</p>
              </div>
            ))}
          </div>
        </section>
      )}
      <section className="panel source-panel">
        <PanelHeader
          eyebrow="TECHNICAL REFERENCES"
          title="Trace the model back to its sources"
        />
        <a
          href="https://qiskit.github.io/qiskit-aer/stubs/qiskit_aer.noise.depolarizing_error.html"
          target="_blank"
          rel="noreferrer"
        >
          <div>
            <span>QISKIT AER DOCUMENTATION</span>
            <h3>Depolarizing quantum error channels</h3>
            <p>
              The channel definition used to map average gate infidelity into
              stochastic Pauli errors.
            </p>
          </div>
          <ArrowUpRight size={18} />
        </a>
        <a
          href="https://qiskit.github.io/qiskit-aer/tutorials/2_device_noise_simulation"
          target="_blank"
          rel="noreferrer"
        >
          <div>
            <span>QISKIT AER DOCUMENTATION</span>
            <h3>Device noise simulation and total gate error</h3>
            <p>
              Why the total gate error already accounts for a thermal-relaxation
              contribution.
            </p>
          </div>
          <ArrowUpRight size={18} />
        </a>
        <div className="case-source">
          <BookOpen size={18} />
          <p>
            Case data: Lab-to-Market Hackathon, Challenge 04, “The Calibration
            Contract”, page 5. Columbia COMS 4995W, Session 11, November 19,
            2026.
          </p>
        </div>
      </section>
    </>
  );
}

function CompareDrawer({
  snapshots,
  current,
  onClose,
  onLoad,
  onDelete,
}: {
  snapshots: Snapshot[];
  current: AnalysisResponse;
  onClose: () => void;
  onLoad: (result: AnalysisResponse, name: string) => void;
  onDelete: (id: string) => void;
}) {
  return (
    <Modal
      onClose={onClose}
      labelledBy="compare-title"
      className="compare-drawer"
    >
      <div className="drawer-heading">
        <div>
          <span className="eyebrow">DECISIONS SIDE BY SIDE</span>
          <h2 id="compare-title">Compare scenarios</h2>
        </div>
        <button
          className="icon-button"
          onClick={onClose}
          aria-label="Close scenario comparison"
        >
          <X size={20} />
        </button>
      </div>
      <p className="drawer-description">
        Snapshots preserve the inputs and results from a completed run. Opening
        one restores its exact saved evidence. No new calculation is performed.
      </p>
      <div className="snapshot-grid">
        {[
          { id: "current", name: "Current result", data: current },
          ...snapshots,
        ].map((snapshot) => {
          const picked =
            snapshot.data.options.find(
              (option) => option.id === snapshot.data.recommendation.id,
            ) || snapshot.data.options.find((option) => option.id === "pulse");
          return (
            <article
              className={`snapshot-card ${snapshot.id === "current" ? "current" : ""}`}
              key={snapshot.id}
            >
              <div className="snapshot-name">
                <h3>{snapshot.name}</h3>
                {snapshot.id !== "current" && (
                  <button
                    className="icon-button"
                    aria-label={`Delete ${snapshot.name}`}
                    onClick={() => onDelete(snapshot.id)}
                  >
                    <X size={15} />
                  </button>
                )}
              </div>
              <span className="snapshot-priority">
                {optionNames[snapshot.data.recommendation.id]}
              </span>
              <strong>{money(picked?.customer_npv_usd)}</strong>
              <span className="snapshot-metric-label">customer NPV</span>
              <dl>
                <div>
                  <dt>Productive-hour value</dt>
                  <dd>
                    {money(
                      snapshot.data.scenario.value_per_productive_hour,
                      false,
                    )}
                  </dd>
                </div>
                <div>
                  <dt>Value realization</dt>
                  <dd>
                    {percent(snapshot.data.scenario.value_realization, 0)}
                  </dd>
                </div>
                <div>
                  <dt>Daily demand</dt>
                  <dd>
                    {snapshot.data.scenario.demand_hours_per_day.toFixed(1)}h
                  </dd>
                </div>
                <div>
                  <dt>Useful throughput</dt>
                  <dd>
                    {snapshot.data.benchmark.throughput_ratio.toFixed(2)}×
                  </dd>
                </div>
              </dl>
              <p>{snapshot.data.recommendation.contract_verdict}</p>
              {snapshot.id !== "current" && (
                <button
                  className="outlined-button"
                  onClick={() => {
                    onLoad(snapshot.data, snapshot.name);
                    onClose();
                  }}
                >
                  Open saved result <ArrowRight size={14} />
                </button>
              )}
            </article>
          );
        })}
      </div>
      {snapshots.length === 0 && (
        <div className="snapshot-empty">
          <GitCompareArrows size={30} />
          <h3>Save a scenario to compare it here.</h3>
          <p>
            Try a conservative buyer or a higher-value workload, then save the
            result.
          </p>
        </div>
      )}
    </Modal>
  );
}

export default function App() {
  const [data, setData] = useState<AnalysisResponse | null>(null);
  const [draft, setDraft] = useState<Scenario | null>(null);
  const [defaults, setDefaults] = useState<Scenario | null>(null);
  const [view, setView] = useState<View>(
    () =>
      readShareState(
        window.location.hash,
        catalogEntries.map((item) => item.id),
      ).view,
  );
  const [origin, setOrigin] = useState<
    "engine" | "catalog" | "history" | "imported" | "snapshot"
  >("engine");
  const [resultLabel, setResultLabel] = useState("");
  const [importOpen, setImportOpen] = useState(false);
  const [shareText, setShareText] = useState("");
  const [activeJob, setActiveJob] = useState<Job | null>(null);
  const [offline, setOffline] = useState(false);
  const [savedScenarioId, setSavedScenarioId] = useState("case_default");
  const [loading, setLoading] = useState(true);
  const [busy, setBusy] = useState(false);
  const [runningQuantum, setRunningQuantum] = useState(false);
  const [error, setError] = useState("");
  const [toast, setToast] = useState("");
  const [exportOpen, setExportOpen] = useState(false);
  const [compareOpen, setCompareOpen] = useState(false);
  const [mobileNav, setMobileNav] = useState(false);
  const [snapshots, setSnapshots] = useState<Snapshot[]>([]);
  const mainRef = useRef<HTMLElement>(null);
  const loadVersion = useRef(0);
  const viewRef = useRef(view);
  viewRef.current = view;
  const exportRef = useRef<HTMLDivElement>(null);
  useEffect(() => {
    let active = true;
    async function load() {
      try {
        let result: AnalysisResponse;
        let saved = false;
        if (
          window.location.protocol === "file:" ||
          import.meta.env.VITE_STANDALONE === "true"
        ) {
          result = bundledEvidence as unknown as AnalysisResponse;
          saved = true;
        } else {
          try {
            result = await apiRequest<AnalysisResponse>("/api/demo");
            if (!isAnalysis(result)) throw new Error("Invalid engine response");
          } catch {
            try {
              result = await apiRequest<AnalysisResponse>("/demo.json");
              if (!isAnalysis(result))
                throw new Error("Invalid saved experiment");
            } catch {
              result = bundledEvidence as unknown as AnalysisResponse;
            }
            saved = true;
          }
        }
        if (!isAnalysis(result))
          throw new Error(
            "The saved experiment is missing or invalid. Start the Python engine to generate a result.",
          );
        if (active) {
          const shared = readShareState(
            window.location.hash,
            catalogEntries.map((item) => item.id),
          );
          const initial = shared.scenario
            ? scenarioCatalog[shared.scenario]
            : result;
          setData(initial);
          setDraft(initial.scenario);
          setDefaults(result.scenario);
          setOffline(saved);
          setOrigin(shared.scenario || saved ? "catalog" : "engine");
          setSavedScenarioId(shared.scenario || (saved ? "case_default" : ""));
          setResultLabel(
            catalogEntries.find((item) => item.id === shared.scenario)?.label ||
              "",
          );
          setView(shared.view);
        }
        if (!saved) {
          try {
            const original = await apiRequest<Scenario>("/api/defaults");
            if (active && original.calibration_hours !== undefined)
              setDefaults(original);
          } catch {
            /* The successful result already contains valid defaults. */
          }
        }
      } catch (err) {
        if (active)
          setError(
            err instanceof Error
              ? err.message
              : "Could not load the experiment.",
          );
      } finally {
        if (active) setLoading(false);
      }
    }
    void load();
    try {
      const stored = JSON.parse(
        localStorage.getItem("qubityield-scenarios-v1") || "[]",
      ) as Snapshot[];
      if (Array.isArray(stored))
        setSnapshots(
          stored.slice(0, 3).filter((item) => {
            try {
              return (
                typeof item?.id === "string" &&
                typeof item?.name === "string" &&
                !!validateEvidence(item.data)
              );
            } catch {
              return false;
            }
          }),
        );
    } catch {
      /* A damaged local snapshot must not block the application. */
    }
    return () => {
      active = false;
    };
  }, []);
  useEffect(() => {
    const follow = () => {
      if (window.location.hash === "#main") return;
      const shared = readShareState(
        window.location.hash,
        catalogEntries.map((item) => item.id),
      );
      setView(shared.view);
      if (shared.scenario) {
        loadVersion.current++;
        const result = scenarioCatalog[shared.scenario];
        setData(result);
        setDraft({ ...result.scenario });
        setSavedScenarioId(shared.scenario);
        setOrigin("catalog");
        setResultLabel(
          catalogEntries.find((item) => item.id === shared.scenario)?.label ||
            "",
        );
      }
    };
    window.addEventListener("hashchange", follow);
    return () => window.removeEventListener("hashchange", follow);
  }, []);
  useEffect(() => {
    if (!toast) return;
    const timer = setTimeout(() => setToast(""), 4000);
    return () => clearTimeout(timer);
  }, [toast]);
  useEffect(() => {
    const close = (event: MouseEvent) => {
      if (
        exportRef.current &&
        !exportRef.current.contains(event.target as Node)
      )
        setExportOpen(false);
    };
    const escape = (event: KeyboardEvent) => {
      if (event.key === "Escape") {
        setCompareOpen(false);
        setExportOpen(false);
        setMobileNav(false);
      }
    };
    document.addEventListener("mousedown", close);
    document.addEventListener("keydown", escape);
    return () => {
      document.removeEventListener("mousedown", close);
      document.removeEventListener("keydown", escape);
    };
  }, []);
  const dirty =
    !!data &&
    !!draft &&
    JSON.stringify(data.scenario) !== JSON.stringify(draft);
  const physicsDirty =
    !!data && !!draft && physicsChanged(data.scenario, draft);
  const selectedSavedScenario = catalogEntries.find(
    (entry) => entry.id === savedScenarioId,
  );
  const loadSavedScenario = (id: string) => {
    const result = scenarioCatalog[id];
    if (!result || !isAnalysis(result)) return;
    loadVersion.current++;
    setData(result);
    setDraft({ ...result.scenario });
    setSavedScenarioId(id);
    setOrigin("catalog");
    setResultLabel(catalogEntries.find((item) => item.id === id)?.label || "");
    updateHash(view, id);
    setError("");
    setToast(
      "Loaded a precomputed result and its exact inputs. No new analysis was run.",
    );
  };
  const changeView = (newView: View) => {
    setView(newView);
    updateHash(newView, savedScenarioId || undefined);
    setMobileNav(false);
    window.scrollTo({ top: 0, behavior: "smooth" });
  };
  const run = async (forcePhysics = false) => {
    if (!draft || busy) return;
    if (offline) {
      setError(
        "This is a saved experiment. Start the local Python engine, then reload to evaluate your own inputs.",
      );
      return;
    }
    const submitted = { ...draft };
    const version = loadVersion.current;
    setRunningQuantum(forcePhysics || physicsDirty);
    setBusy(true);
    setError("");
    setActiveJob(null);
    try {
      const result =
        forcePhysics || physicsDirty
          ? await queueScenario(
              submitted,
              "Workspace quantum benchmark",
              setActiveJob,
            )
          : await apiRequest<AnalysisResponse>("/api/evaluate", submitted);
      if (!isAnalysis(result))
        throw new Error("The engine returned an invalid result.");
      if (version !== loadVersion.current) {
        setToast(
          "Background run completed. Your newly loaded evidence is preserved. Queued results are available in History.",
        );
        return;
      }
      setData(result);
      setDraft((current) =>
        JSON.stringify(current) === JSON.stringify(submitted)
          ? result.scenario
          : current,
      );
      setOrigin("engine");
      setSavedScenarioId("");
      setResultLabel("");
      updateHash(viewRef.current);
      setToast(
        forcePhysics || physicsDirty
          ? "Quantum benchmark complete. Decision updated."
          : "Analysis complete. Decision updated.",
      );
    } catch (err) {
      setError(
        err instanceof Error
          ? err.message
          : "Analysis failed. Your previous result is preserved.",
      );
    } finally {
      setBusy(false);
    }
  };
  const saveSnapshots = (next: Snapshot[]) => {
    setSnapshots(next);
    try {
      localStorage.setItem("qubityield-scenarios-v1", JSON.stringify(next));
      return true;
    } catch {
      return false;
    }
  };
  const saveScenario = () => {
    if (!data) return;
    if (dirty) {
      setToast("Run the changed inputs before saving the new scenario.");
      return;
    }
    const id = Date.now().toString();
    const name =
      resultLabel ||
      (origin === "catalog" && selectedSavedScenario
        ? selectedSavedScenario.label
        : `Scenario ${snapshots.length + 1} · ${money(data.scenario.value_per_productive_hour)}/h`);
    const persisted = saveSnapshots(
      [{ id, name, data }, ...snapshots].slice(0, 3),
    );
    setToast(
      persisted
        ? "Result saved. Compare up to three saved scenarios."
        : "Saved for this session. Browser storage is unavailable.",
    );
  };
  const loadEvidence = (
    result: AnalysisResponse,
    label: string,
    source: "history" | "snapshot" | "imported",
  ) => {
    loadVersion.current++;
    setData(result);
    setDraft({ ...result.scenario });
    setSavedScenarioId("");
    setOrigin(source);
    setResultLabel(label);
    setError("");
    setView("decision");
    updateHash("decision");
    setToast("Loaded completed evidence and its exact inputs.");
  };
  const imported = (payload: ImportedData) => {
    if (payload.kind === "scenario") {
      setDraft({ ...payload.scenario });
      setToast("Validated inputs loaded. Run analysis to calculate a result.");
    } else loadEvidence(payload.result, "Imported evidence", "imported");
  };
  const compareEvidence = (result: AnalysisResponse, label: string) => {
    saveSnapshots(
      [
        { id: `history-${Date.now()}`, name: label, data: result },
        ...snapshots,
      ].slice(0, 3),
    );
    setCompareOpen(true);
  };
  const share = async () => {
    if (!savedScenarioId || dirty) return;
    const hash = shareHash(view, savedScenarioId);
    const link =
      window.location.protocol === "file:"
        ? hash
        : `${window.location.origin}${window.location.pathname}${hash}`;
    try {
      await navigator.clipboard.writeText(link);
      setToast(
        "Precomputed scenario link copied. Draft inputs are not included.",
      );
    } catch {
      setShareText(link);
    }
  };
  const exportData = (format: "json" | "csv") => {
    if (!data) return;
    downloadFile(
      `qubityield-${String(data.evidence.experiment_id || "analysis")
        .replace(/[^a-zA-Z0-9._-]/g, "_")
        .slice(0, 120)}.${format}`,
      format === "json" ? JSON.stringify(data, null, 2) : analysisCsv(data),
      format === "json" ? "application/json" : "text/csv",
    );
    setExportOpen(false);
    setToast(`${format.toUpperCase()} exported with the evaluated inputs.`);
  };
  return (
    <div className="app-shell">
      <a className="skip-link" href="#main">
        Skip to analysis
      </a>
      <aside className={`sidebar ${mobileNav ? "mobile-open" : ""}`}>
        <a
          className="brand"
          href="#"
          onClick={(event) => {
            event.preventDefault();
            changeView("decision");
          }}
          aria-label="QubitYield decision desk"
        >
          <span className="brand-mark">
            <i />
            <b />
          </span>
          <span>
            Qubit<span className="brand-light">Yield</span>
            <sup>™</sup>
          </span>
        </a>
        <div className="sidebar-project">
          <span className="micro-label">ACTIVE CASE</span>
          <div>
            <span className="project-number">04</span>
            <div>
              <strong>
                The calibration
                <br />
                contract
              </strong>
              <span>Lab-to-Market Hackathon</span>
            </div>
          </div>
        </div>
        <div className="nav-label">WORKSPACE</div>
        <nav aria-label="Main navigation">
          {views.map((item) => (
            <button
              key={item.id}
              className={`nav-item ${view === item.id ? "active" : ""}`}
              aria-current={view === item.id ? "page" : undefined}
              onClick={() => changeView(item.id)}
            >
              <item.icon size={19} strokeWidth={1.7} />
              <span>{item.label}</span>
              {item.id === "assumptions" && data && (
                <span className="nav-count">{data.assumptions.length}</span>
              )}
              {view === item.id && <span className="nav-active-dot" />}
            </button>
          ))}
          <button
            className="nav-item"
            onClick={() => setCompareOpen(true)}
            disabled={!data}
          >
            <GitCompareArrows size={19} strokeWidth={1.7} />
            <span>Compare scenarios</span>
            {snapshots.length > 0 && (
              <span className="nav-count">{snapshots.length}</span>
            )}
          </button>
        </nav>
        <div className="sidebar-divider" />
        <div className="nav-label">THE INVESTIGATION</div>
        <ol className="phase-list">
          <li>
            <span>01</span>
            <div>
              <strong>Investigate</strong>
              <small>Question the claim</small>
            </div>
            <Check size={13} />
          </li>
          <li>
            <span>02</span>
            <div>
              <strong>Experiment</strong>
              <small>Make it reproducible</small>
            </div>
            <Check size={13} />
          </li>
          <li>
            <span>03</span>
            <div>
              <strong>Recommend</strong>
              <small>Decide with evidence</small>
            </div>
            <Check size={13} />
          </li>
        </ol>
        <div className="sidebar-bottom">
          <div className="device-visual" aria-hidden="true">
            {Array.from({ length: 30 }, (_, i) => (
              <i key={i} className={(i * 7) % 11 > 7 ? "bright" : ""} />
            ))}
          </div>
          <div className="device-caption">
            <span>
              <Cpu size={15} />
              100-qubit processor
            </span>
            <small>Fictional case · simulated evidence</small>
          </div>
          <div className="sidebar-credit">
            <span className="avatar">JS</span>
            <div>
              <strong>Jasper Sands</strong>
              <span>Product strategy</span>
            </div>
            <span className="credit-dot" />
          </div>
        </div>
      </aside>
      {mobileNav && (
        <button
          className="mobile-scrim"
          onClick={() => setMobileNav(false)}
          aria-label="Close navigation"
        />
      )}
      <main id="main" tabIndex={-1} className="main-shell" ref={mainRef}>
        <header className="topbar">
          <div className="breadcrumb">
            <button
              className="mobile-menu icon-button"
              aria-label="Open navigation"
              onClick={() => setMobileNav(true)}
            >
              <Menu size={21} />
            </button>
            <span>WORKSPACE</span>
            <span className="breadcrumb-slash">/</span>
            <strong>{views.find((item) => item.id === view)?.label}</strong>
          </div>
          <div className="topbar-right">
            <span className={`engine-status ${offline ? "saved" : ""}`}>
              <i />
              {offline
                ? "Saved experiment"
                : loading
                  ? "Connecting engine"
                  : "Local simulation engine"}
            </span>
            <span className="case-chip">CHALLENGE 04</span>
          </div>
        </header>
        <div className="page-content">
          <div className="page-title-row">
            <div>
              <p className="eyebrow">
                FROM QUANTUM PERFORMANCE TO COMMERCIAL VALUE
              </p>
              <h1>{pageCopy[view][0]}</h1>
              <p className="page-subtitle">{pageCopy[view][1]}</p>
            </div>
            <div className="page-actions">
              <button
                className="outlined-button"
                onClick={() => setImportOpen(true)}
                disabled={!defaults || busy}
                aria-label="Import JSON"
              >
                <Upload size={15} />
                <span>Import</span>
              </button>
              <button
                className="outlined-button share-action"
                onClick={() => void share()}
                disabled={!savedScenarioId || dirty}
                title="Share a precomputed scenario and current view"
                aria-label="Share precomputed scenario"
              >
                <Share2 size={15} />
              </button>
              <button
                className="outlined-button save-button"
                onClick={saveScenario}
                disabled={!data || busy}
              >
                <Plus size={16} />
                <span>Save scenario</span>
              </button>
              <div className="export-wrap" ref={exportRef}>
                <button
                  className="export-button"
                  disabled={!data}
                  aria-expanded={exportOpen}
                  aria-haspopup="menu"
                  onClick={() => setExportOpen(!exportOpen)}
                >
                  <ArrowDownToLine size={16} />
                  <span>Export</span>
                  <ChevronDown size={13} />
                </button>
                {exportOpen && (
                  <div className="export-menu" role="menu">
                    <button role="menuitem" onClick={() => exportData("json")}>
                      <FileJson size={16} />
                      <span>Full evidence JSON</span>
                    </button>
                    <button role="menuitem" onClick={() => exportData("csv")}>
                      <BarChart3 size={16} />
                      <span>Comparison CSV</span>
                    </button>
                    <button
                      role="menuitem"
                      onClick={() => {
                        setExportOpen(false);
                        window.print();
                      }}
                    >
                      <BookOpen size={16} />
                      <span>Print decision report</span>
                    </button>
                  </div>
                )}
              </div>
            </div>
          </div>
          {(offline || origin === "catalog") && (
            <>
              <div className="saved-banner">
                <BookOpen size={16} />
                <span>
                  You are viewing saved, reproducible results. Explore the
                  precomputed scenarios below, or run the local engine to
                  evaluate your own inputs.
                </span>
              </div>
              <section
                className="saved-scenario-explorer"
                aria-label="Precomputed scenario explorer"
              >
                <div className="saved-scenario-heading">
                  <div>
                    <span className="eyebrow">
                      {catalogEntries.length} PRECOMPUTED RESULTS
                    </span>
                    <h2>Explore saved scenarios</h2>
                  </div>
                  <span className="saved-source-pill">
                    <BadgeCheck size={13} />
                    Python-generated evidence
                  </span>
                </div>
                <div className="saved-scenario-body">
                  <div className="saved-scenario-picker">
                    <label htmlFor="saved-scenario-select">
                      Load a completed analysis
                    </label>
                    <div className="select-shell">
                      <select
                        id="saved-scenario-select"
                        value={savedScenarioId}
                        onChange={(event) =>
                          loadSavedScenario(event.target.value)
                        }
                      >
                        {!savedScenarioId && (
                          <option value="" disabled>
                            Choose a precomputed scenario
                          </option>
                        )}
                        {catalogEntries.map((entry) => (
                          <option key={entry.id} value={entry.id}>
                            {entry.label}
                          </option>
                        ))}
                      </select>
                      <ChevronDown size={15} />
                    </div>
                  </div>
                  <div className="saved-scenario-explanation">
                    <h3>{selectedSavedScenario?.label}</h3>
                    <p>{selectedSavedScenario?.description}</p>
                    <span>
                      Full result + matching inputs · no recalculation
                    </span>
                  </div>
                </div>
                <p className="saved-scenario-help">
                  Each selection loads an actual completed run from the
                  experiment catalog. Editing the controls only changes draft
                  inputs; it does not update these saved results. Save any
                  loaded result to compare it with another.
                </p>
              </section>
            </>
          )}
          {(origin === "imported" || origin === "snapshot") && (
            <div className="imported-banner">
              <Upload size={16} />
              <span>
                {resultLabel || "Loaded evidence"}: supplied evidence,
                structurally validated but not independently verified. The
                original provenance is retained in the export.
              </span>
            </div>
          )}
          {origin === "history" && (
            <div className="saved-banner">
              <Database size={16} />
              <span>
                Loaded server record: {resultLabel}. The result is from its
                recorded run; edited inputs require a new calculation.
              </span>
            </div>
          )}
          {error && (
            <div className="error-banner" role="alert">
              <CircleHelp size={18} />
              <span>{error}</span>
              <button
                className="icon-button"
                aria-label="Dismiss error"
                onClick={() => setError("")}
              >
                <X size={16} />
              </button>
            </div>
          )}
          {loading ? (
            <div className="loading-state">
              <span className="large-spinner" />
              <h2>Opening the evidence desk</h2>
              <p>Loading the case, experiment and commercial model.</p>
            </div>
          ) : !data || !draft ? (
            <section className="getting-started">
              <Atom size={38} />
              <h2>Connect the local decision engine.</h2>
              <p>
                Start the project server to load the baseline case and
                reproducible benchmark.
              </p>
              <code>qubityield serve</code>
              <button
                className="primary-button"
                onClick={() => window.location.reload()}
              >
                Reconnect <ArrowRight size={16} />
              </button>
            </section>
          ) : (
            <div className="workspace-grid">
              <div
                className={`workspace-main ${busy && (view === "decision" || view === "experiment") ? "is-calculating" : ""}`}
                aria-busy={busy}
              >
                {dirty && view !== "strategy" && view !== "history" && (
                  <div className="stale-banner">
                    <span className="status-dot unsaved" />
                    <span>
                      {offline
                        ? "Showing the saved result. Draft edits are not recalculated offline."
                        : "Showing the last completed result. Run analysis to apply your changes."}
                    </span>
                    {offline && (
                      <button
                        className="text-button"
                        onClick={() => setDraft({ ...data.scenario })}
                      >
                        Restore saved inputs
                      </button>
                    )}
                  </div>
                )}
                {view === "decision" && (
                  <DecisionDesk
                    data={data}
                    onExperiment={() => changeView("experiment")}
                    onAssumptions={() => changeView("assumptions")}
                  />
                )}
                {view === "experiment" && (
                  <ExperimentLab
                    data={data}
                    busy={busy}
                    offline={offline}
                    onRun={() => void run(true)}
                  />
                )}
                {view === "assumptions" && <Assumptions data={data} />}
                {view === "history" && (
                  <History
                    scenario={draft}
                    offline={offline}
                    onLoad={(result, label) =>
                      loadEvidence(result, label, "history")
                    }
                    onCompare={compareEvidence}
                  />
                )}{" "}
                {view === "strategy" && (
                  <Strategy scenario={draft} offline={offline} />
                )}{" "}
              </div>
              <Controls
                scenario={draft}
                onChange={(key, value) => setDraft({ ...draft, [key]: value })}
                onPreset={(preset) => {
                  if (defaults)
                    setDraft(
                      preset === "base"
                        ? { ...defaults }
                        : applyPreset({ ...defaults }, preset),
                    );
                }}
                onReset={() => {
                  if (defaults) setDraft({ ...defaults });
                }}
                onRun={() => void run()}
                busy={busy}
                dirty={dirty}
                physicsDirty={physicsDirty}
                offline={offline}
              />
            </div>
          )}
          <footer className="page-footer">
            <span>
              <BadgeCheck size={14} />
              Reproducible by design. Assumptions in the open.
            </span>
            <span>QubitYield / Lab-to-Market 2026</span>
          </footer>
        </div>
      </main>
      {toast && (
        <div className="toast" role="status">
          <Check size={17} />
          {toast}
        </div>
      )}
      {busy && (
        <div className="running-indicator" role="status">
          <span className="spinner" />
          <div>
            <strong>
              {runningQuantum
                ? activeJob?.status === "queued"
                  ? "Experiment queued"
                  : "Propagating quantum trajectories"
                : "Evaluating the commercial case"}
            </strong>
            <span>
              Your previous result stays visible until this run completes.
            </span>
          </div>
        </div>
      )}
      {importOpen && defaults && (
        <ImportDialog
          defaults={defaults}
          onImport={imported}
          onClose={() => setImportOpen(false)}
        />
      )}
      {shareText && (
        <Modal labelledBy="share-title" onClose={() => setShareText("")}>
          <div className="drawer-heading">
            <h2 id="share-title">Share this precomputed scenario</h2>
            <button
              className="icon-button"
              aria-label="Close share dialog"
              onClick={() => setShareText("")}
            >
              <X size={18} />
            </button>
          </div>
          <p className="drawer-description">
            This link opens the exact saved scenario and view. Local files share
            a URL fragment that can be appended to another copy of the preview.
            Draft edits are not shared.
          </p>
          <label className="workbench-field">
            <span>Scenario link</span>
            <input
              data-autofocus
              readOnly
              value={shareText}
              onFocus={(event) => event.target.select()}
            />
          </label>
        </Modal>
      )}
      {compareOpen && data && (
        <CompareDrawer
          snapshots={snapshots}
          current={data}
          onClose={() => setCompareOpen(false)}
          onLoad={(result, name) => loadEvidence(result, name, "snapshot")}
          onDelete={(id) =>
            saveSnapshots(snapshots.filter((snapshot) => snapshot.id !== id))
          }
        />
      )}
    </div>
  );
}
