import { useState } from "react";
import {
  ArrowUpRight,
  ChevronDown,
  FlaskConical,
  RotateCcw,
  SlidersHorizontal,
} from "lucide-react";
import type { Scenario } from "./types";
import { money, percent } from "./utils";

type Props = {
  scenario: Scenario;
  onChange: (key: keyof Scenario, value: number | string | boolean) => void;
  onPreset: (preset: string) => void;
  onReset: () => void;
  onRun: () => void;
  busy: boolean;
  dirty: boolean;
  physicsDirty: boolean;
  offline: boolean;
};

function Slider({
  label,
  value,
  min = 0,
  max = 1,
  step = 0.05,
  format = percent,
  onChange,
  help,
}: {
  label: string;
  value: number;
  min?: number;
  max?: number;
  step?: number;
  format?: (value: number) => string;
  onChange: (value: number) => void;
  help?: string;
}) {
  const id = `input-${label.toLowerCase().replace(/[^a-z0-9]+/g, "-")}`;
  return (
    <div className="slider-field">
      <label htmlFor={id}>
        <span>{label}</span>
        <output htmlFor={id}>{format(value)}</output>
      </label>
      <input
        id={id}
        aria-label={label}
        type="range"
        min={min}
        max={max}
        step={step}
        value={value}
        onChange={(event) => onChange(Number(event.target.value))}
        style={
          {
            "--fill": `${((value - min) / (max - min)) * 100}%`,
          } as React.CSSProperties
        }
      />
      {help && <p>{help}</p>}
    </div>
  );
}

function NumberField({
  label,
  value,
  onChange,
  min = 0,
  max,
  step = 1,
  suffix,
  help,
}: {
  label: string;
  value: number;
  onChange: (value: number) => void;
  min?: number;
  max?: number;
  step?: number;
  suffix?: string;
  help?: string;
}) {
  const id = `input-${label.toLowerCase().replace(/[^a-z0-9]+/g, "-")}`;
  return (
    <div className="number-field">
      <label htmlFor={id}>{label}</label>
      <div className="input-shell">
        <input
          id={id}
          type="number"
          value={value}
          min={min}
          max={max}
          step={step}
          onChange={(event) =>
            onChange(
              event.target.value === "" ? min : Number(event.target.value),
            )
          }
        />
        {suffix && <span>{suffix}</span>}
      </div>
      {help && <p>{help}</p>}
    </div>
  );
}

export default function Controls({
  scenario,
  onChange,
  onPreset,
  onReset,
  onRun,
  busy,
  dirty,
  physicsDirty,
  offline,
}: Props) {
  const [section, setSection] = useState<"commercial" | "hardware">(
    "commercial",
  );
  return (
    <aside className="controls-panel" aria-label="Scenario controls">
      <div className="control-heading">
        <SlidersHorizontal size={17} />
        <h2>Shape the scenario</h2>
        <button
          className="icon-button"
          aria-label="Reset all inputs to the case baseline"
          title="Reset to case baseline"
          onClick={onReset}
        >
          <RotateCcw size={15} />
        </button>
      </div>
      {!offline && (
        <>
          <label className="preset-label" htmlFor="scenario-preset">
            START FROM A PERSPECTIVE
          </label>
          <div className="select-shell">
            <select
              id="scenario-preset"
              defaultValue="base"
              onChange={(event) => {
                onPreset(event.target.value);
                event.target.value = "base";
              }}
            >
              <option value="base">Case baseline</option>
              <option value="conservative">Conservative buyer</option>
              <option value="demand">Demand-constrained growth</option>
              <option value="savings">Same work, less time</option>
              <option value="optimistic">High-value workload</option>
              <option value="procurement">Hardware replacement due</option>
            </select>
            <ChevronDown size={15} />
          </div>
        </>
      )}
      <div
        className="control-tabs"
        role="tablist"
        aria-label="Scenario control groups"
      >
        <button
          role="tab"
          aria-selected={section === "commercial"}
          className={section === "commercial" ? "active" : ""}
          onClick={() => setSection("commercial")}
        >
          Commercial
        </button>
        <button
          role="tab"
          aria-selected={section === "hardware"}
          className={section === "hardware" ? "active" : ""}
          onClick={() => setSection("hardware")}
        >
          Hardware
        </button>
      </div>
      <div className="control-content">
        {section === "commercial" ? (
          <>
            <div className="select-field value-mode-field">
              <label htmlFor="value-mode">What creates value?</label>
              <div className="select-shell">
                <select
                  id="value-mode"
                  value={scenario.value_mode || "additional_output"}
                  onChange={(event) =>
                    onChange("value_mode", event.target.value)
                  }
                >
                  <option value="additional_output">More useful output</option>
                  <option value="fixed_output_savings">
                    Same work, less time
                  </option>
                </select>
                <ChevronDown size={14} />
              </div>
              <p className="field-note">
                {scenario.value_mode === "fixed_output_savings"
                  ? "Value comes from freeing time while doing the same useful work."
                  : "Value requires a customer who can use more output in the same time."}
              </p>
            </div>
            <NumberField
              label="Value per productive hour"
              value={scenario.value_per_productive_hour}
              step={100}
              max={1000000}
              suffix="USD"
              onChange={(value) => onChange("value_per_productive_hour", value)}
              help="An assumption to test with the customer."
            />
            <Slider
              label="Value realization"
              value={scenario.value_realization}
              onChange={(value) => onChange("value_realization", value)}
              help="Share of extra useful capacity that becomes economic value."
            />
            <Slider
              label="Daily demand"
              value={scenario.demand_hours_per_day}
              max={24}
              step={0.2}
              format={(value) => `${value.toFixed(1)} h`}
              onChange={(value) => onChange("demand_hours_per_day", value)}
            />
            <div className="field-divider">
              <span>CALIBRATION CLAIM</span>
            </div>
            <Slider
              label="Scale-up realization"
              value={scenario.scale_realization}
              onChange={(value) => onChange("scale_realization", value)}
              help="How much of the 10-qubit pilot gain reaches 100 qubits."
            />
            <Slider
              label="Useful time overlap"
              value={scenario.monetizable_overlap}
              onChange={(value) => onChange("monetizable_overlap", value)}
              help="Recovered calibration time that overlaps customer demand."
            />
            <div className="select-field">
              <label htmlFor="speed-reading">
                Read “{percent(scenario.ai_speed_claim, 0)} faster” as
              </label>
              <div className="select-shell">
                <select
                  id="speed-reading"
                  value={scenario.ai_speed_interpretation}
                  onChange={(event) =>
                    onChange("ai_speed_interpretation", event.target.value)
                  }
                >
                  <option value="rate_increase">
                    {percent(scenario.ai_speed_claim, 0)} higher speed
                  </option>
                  <option value="time_reduction">
                    {percent(scenario.ai_speed_claim, 0)} less time
                  </option>
                </select>
                <ChevronDown size={14} />
              </div>
            </div>
            <details className="advanced-controls">
              <summary>
                Contract & deployment <ChevronDown size={14} />
              </summary>
              <div>
                <NumberField
                  label="Proposed contract"
                  value={scenario.contract_total}
                  step={100000}
                  max={1000000000}
                  suffix="USD"
                  onChange={(value) => onChange("contract_total", value)}
                />
                <Slider
                  label="Rollout delay"
                  value={scenario.rollout_months}
                  max={120}
                  step={1}
                  format={(value) => `${value} months`}
                  onChange={(value) => onChange("rollout_months", value)}
                />
                <Slider
                  label="Discount rate"
                  value={scenario.discount_rate}
                  max={1}
                  step={0.01}
                  onChange={(value) => onChange("discount_rate", value)}
                />
                <label className="toggle-field">
                  <input
                    type="checkbox"
                    checked={scenario.replacement_due}
                    onChange={(event) =>
                      onChange("replacement_due", event.target.checked)
                    }
                  />
                  <span className="toggle-track" />
                  <span>Control replacement already due</span>
                </label>
                <p className="field-note">
                  An installed system is a sunk cost. Savings from a replacement
                  only count when that purchase would happen anyway.
                </p>
              </div>
            </details>
          </>
        ) : (
          <>
            <div className="hardware-note">
              <FlaskConical size={17} />
              <p>
                These inputs rerun a noisy Clifford mirror-circuit simulation.
              </p>
            </div>
            <Slider
              label="Current gate error"
              value={scenario.baseline_gate_error}
              max={0.2}
              step={0.0005}
              format={(value) => percent(value, 2)}
              onChange={(value) => onChange("baseline_gate_error", value)}
            />
            <Slider
              label="Optimized gate error"
              value={scenario.pulse_gate_error}
              max={0.2}
              step={0.0005}
              format={(value) => percent(value, 2)}
              onChange={(value) => onChange("pulse_gate_error", value)}
            />
            <Slider
              label="Longer optimized gates"
              value={scenario.pulse_duration_increase}
              max={4}
              step={0.05}
              onChange={(value) => onChange("pulse_duration_increase", value)}
            />
            <NumberField
              label="Cycle overhead"
              value={scenario.fixed_overhead_us}
              max={1000000}
              step={10}
              suffix="µs"
              onChange={(value) => onChange("fixed_overhead_us", value)}
              help="Initialization, readout and other fixed shot costs."
            />
            <div className="field-divider">
              <span>EXPERIMENT</span>
            </div>
            <Slider
              label="Circuit layers"
              value={scenario.layers}
              min={2}
              max={100}
              step={2}
              format={(value) => `${value} layers`}
              onChange={(value) => onChange("layers", value)}
            />
            <div className="two-inputs">
              <NumberField
                label="Qubits"
                value={scenario.n_qubits}
                min={2}
                max={100}
                step={2}
                onChange={(value) => onChange("n_qubits", value)}
              />
              <NumberField
                label="Seed"
                value={scenario.seed}
                min={0}
                max={4294967295}
                onChange={(value) => onChange("seed", value)}
              />
            </div>
            <div className="select-field">
              <label htmlFor="shots">Shots per circuit</label>
              <div className="select-shell">
                <select
                  id="shots"
                  value={scenario.shots}
                  onChange={(event) =>
                    onChange("shots", Number(event.target.value))
                  }
                >
                  {![2048, 8192, 32768].includes(scenario.shots) && (
                    <option value={scenario.shots}>
                      {scenario.shots.toLocaleString()} · imported
                    </option>
                  )}
                  <option value={2048}>2,048 · quick</option>
                  <option value={8192}>8,192 · standard</option>
                  <option value={32768}>32,768 · precise</option>
                </select>
                <ChevronDown size={14} />
              </div>
            </div>
            <details className="advanced-controls">
              <summary>
                Noise assumptions <ChevronDown size={14} />
              </summary>
              <div>
                <div className="select-field">
                  <label htmlFor="noise-mode">Reported error means</label>
                  <div className="select-shell">
                    <select
                      id="noise-mode"
                      value={scenario.noise_mode}
                      onChange={(event) =>
                        onChange("noise_mode", event.target.value)
                      }
                    >
                      <option value="reported_total">
                        Total gate infidelity
                      </option>
                      <option value="control_only">Control error only</option>
                    </select>
                    <ChevronDown size={14} />
                  </div>
                </div>
                <p className="field-note">
                  Total infidelity already includes decoherence. The
                  control-only sensitivity adds Pauli-twirled relaxation.
                </p>
                <div className="two-inputs">
                  <NumberField
                    label="T1"
                    value={scenario.t1_us}
                    min={0.001}
                    max={1000000}
                    suffix="µs"
                    onChange={(value) => onChange("t1_us", value)}
                  />
                  <NumberField
                    label="T2"
                    value={scenario.t2_us}
                    min={0.001}
                    max={1000000}
                    suffix="µs"
                    onChange={(value) => onChange("t2_us", value)}
                  />
                </div>
                <Slider
                  label="Readout bit error"
                  value={scenario.readout_error}
                  max={0.5}
                  step={0.001}
                  format={(value) => percent(value, 2)}
                  onChange={(value) => onChange("readout_error", value)}
                />
              </div>
            </details>
          </>
        )}
      </div>
      <div className="control-run">
        <div className="input-status">
          <span className={`status-dot ${dirty ? "unsaved" : ""}`} />
          {dirty
            ? "Inputs changed. Results below are previous."
            : `Contract: ${money(scenario.contract_total)} over ${scenario.contract_years} years`}
        </div>
        <button
          className="primary-button"
          onClick={onRun}
          disabled={busy || offline}
        >
          {busy ? (
            <>
              <span className="spinner" /> Running experiment
            </>
          ) : (
            <>
              {physicsDirty ? "Run quantum benchmark" : "Run analysis"}
              <ArrowUpRight size={18} />
            </>
          )}
        </button>
        {offline && <p>Start the local engine to run a new scenario.</p>}
      </div>
    </aside>
  );
}
