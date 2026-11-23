import { useState } from "react";
import {
  ArrowUpRight,
  BadgeCheck,
  CircleHelp,
  FlaskConical,
  Scale,
  X,
  ArrowDownToLine,
} from "lucide-react";
import type { Scenario } from "./types";
import { money, optionNames, percent, downloadFile } from "./utils";
import { resourceRequest } from "./workbench-api";

type StressInput = {
  value_low: number;
  value_high: number;
  realization_low: number;
  realization_high: number;
  contract_low: number;
  contract_high: number;
  grid_points: number;
};
type PricingInput = {
  implementation_cost: number;
  annual_support_cost: number;
  target_gross_margin: number;
  customer_value_share: number;
};
interface StressResult {
  kind: "stress_envelope";
  scenario: Scenario;
  cell_count: number;
  grid_points: number;
  base_inside_ranges: boolean;
  ranges: {
    value_per_productive_hour: [number, number];
    value_realization: [number, number];
    contract_total: [number, number];
  };
  options: {
    id: string;
    label: string;
    worst_npv_usd: number;
    base_npv_usd: number;
    best_npv_usd: number;
    win_count: number;
    win_coverage: number;
    positive_npv_coverage: number;
    max_regret_usd: number;
    always_nonnegative: boolean;
  }[];
  recommendation: {
    maximin_option: string;
    minimax_regret_option: string;
    summary: string;
  };
  sampling_envelope: {
    available: boolean;
    reason?: string;
    ratio_low?: number;
    ratio_high?: number;
    scope: string;
    options: {
      id: string;
      base_low_npv_usd: number;
      base_high_npv_usd: number;
      stress_low_npv_usd: number;
      stress_high_npv_usd: number;
    }[];
  };
  warnings: string[];
  interpretation: string;
}
interface PricingResult {
  kind: "pricing_feasibility";
  scenario: Scenario;
  inputs: PricingInput;
  nominal_vendor_cost_usd: number;
  vendor_cost_pv_usd: number;
  vendor_floor_usd: number;
  nominal_margin_floor_usd?: number;
  discounted_break_even_floor_usd?: number;
  options: {
    id: string;
    label: string;
    customer_zero_npv_cap_usd: number;
    customer_share_target_usd: number;
    vendor_floor_usd: number;
    full_surplus_feasible: boolean;
    share_policy_feasible: boolean;
    full_surplus_interval: { min_usd: number; max_usd: number } | null;
    share_policy_interval: { min_usd: number; max_usd: number } | null;
    recommended_price_usd: number | null;
    minimum_value_share: number | null;
    margin_at_share_target: number | null;
    vendor_profit_at_share_target_usd: number;
    customer_npv_at_share_target_usd: number;
    vendor_npv_at_share_target_usd: number;
    status: string;
    status_label?: string;
    gap_to_share_target_usd?: number;
    quote_is_jointly_feasible?: boolean;
  }[];
  recommendation: { option_id: string; summary: string };
  assumptions: {
    key: string;
    label: string;
    value: unknown;
    rationale: string;
  }[];
  warnings: string[];
}

const payloads = import.meta.glob("../public/tools.json", {
  eager: true,
  import: "default",
});
const precomputed = (Object.values(payloads)[0] || {}) as {
  stress?: StressResult;
  pricing?: PricingResult;
};
const stressDefault: StressInput = {
  value_low: 250,
  value_high: 2000,
  realization_low: 0.1,
  realization_high: 0.75,
  contract_low: 3e6,
  contract_high: 7e6,
  grid_points: 5,
};
const pricingDefault: PricingInput = {
  implementation_cost: 500000,
  annual_support_cost: 150000,
  target_gross_margin: 0.6,
  customer_value_share: 0.3,
};
const same = (a: object, b: object) =>
  JSON.stringify(Object.entries(a).sort()) ===
  JSON.stringify(Object.entries(b).sort());

function ToolNumber({
  label,
  value,
  onChange,
  min = 0,
  max = 1e9,
  step = 1,
}: {
  label: string;
  value: number;
  onChange: (n: number) => void;
  min?: number;
  max?: number;
  step?: number;
}) {
  return (
    <label className="workbench-field">
      <span>{label}</span>
      <input
        type="number"
        required
        value={value}
        min={min}
        max={max}
        step={step}
        onChange={(event) => onChange(Number(event.target.value))}
      />
    </label>
  );
}
export default function Strategy({
  scenario,
  offline,
}: {
  scenario: Scenario;
  offline: boolean;
}) {
  const [tab, setTab] = useState<"stress" | "pricing">("stress");
  const [stressInput, setStressInput] = useState<StressInput>(stressDefault);
  const [priceInput, setPriceInput] = useState<PricingInput>(
    precomputed.pricing?.inputs || pricingDefault,
  );
  const [stress, setStress] = useState<StressResult | null>(
    precomputed.stress || null,
  );
  const [pricing, setPricing] = useState<PricingResult | null>(
    precomputed.pricing || null,
  );
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [stressSource, setStressSource] = useState("Precomputed baseline");
  const [priceSource, setPriceSource] = useState("Precomputed baseline");
  const [lastStress, setLastStress] = useState<StressInput>(stressDefault);
  const [lastPrice, setLastPrice] = useState<PricingInput>(
    precomputed.pricing?.inputs || pricingDefault,
  );
  const stressStale =
    !!stress &&
    (!same(stressInput, lastStress) || !same(scenario, stress.scenario));
  const priceStale =
    !!pricing &&
    (!same(priceInput, lastPrice) || !same(scenario, pricing.scenario));
  const run = async () => {
    if (offline || busy) return;
    setBusy(true);
    setError("");
    try {
      if (tab === "stress") {
        const result = await resourceRequest<StressResult>(
          "/api/stress",
          "POST",
          { scenario, ...stressInput },
        );
        setStress(result);
        setLastStress({ ...stressInput });
        setStressSource("Computed by local engine");
      } else {
        const result = await resourceRequest<PricingResult>(
          "/api/pricing",
          "POST",
          { scenario, ...priceInput },
        );
        setPricing(result);
        setLastPrice({ ...priceInput });
        setPriceSource("Computed by local engine");
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : "Tool calculation failed.");
    } finally {
      setBusy(false);
    }
  };
  return (
    <>
      <section className="lab-intro">
        <div className="lab-intro-symbol">
          <Scale size={31} />
        </div>
        <div>
          <span className="eyebrow">FROM PERFORMANCE TO A NEGOTIABLE DEAL</span>
          <h2>Challenge the recommendation.</h2>
          <p>
            Stress assumptions, distinguish uncertainty from probability, and
            test whether the customer and vendor can both win.
          </p>
        </div>
      </section>
      <div className="tool-tabs" role="tablist" aria-label="Strategy tools">
        <button
          role="tab"
          aria-selected={tab === "stress"}
          className={tab === "stress" ? "active" : ""}
          onClick={() => setTab("stress")}
        >
          <FlaskConical size={16} />
          Stress envelope
        </button>
        <button
          role="tab"
          aria-selected={tab === "pricing"}
          className={tab === "pricing" ? "active" : ""}
          onClick={() => setTab("pricing")}
        >
          <Scale size={16} />
          Pricing feasibility
        </button>
      </div>
      {offline && (
        <div className="saved-banner">
          <BadgeCheck size={16} />
          <span>
            Saved baseline tool results, when available. The Python engine is
            required to calculate tools for edited inputs. No browser financial
            model is used.
          </span>
        </div>
      )}
      {error && (
        <div className="error-banner" role="alert">
          <span>{error}</span>
          <button
            className="icon-button"
            aria-label="Dismiss strategy error"
            onClick={() => setError("")}
          >
            <X size={15} />
          </button>
        </div>
      )}
      <section className="panel">
        <div className="panel-heading">
          <div>
            <span className="eyebrow">EXPLICIT ASSUMPTIONS</span>
            <h2>
              {tab === "stress"
                ? "Define the range of possibilities"
                : "Specify vendor costs and negotiating policy"}
            </h2>
          </div>
        </div>
        <form
          onSubmit={(event) => {
            event.preventDefault();
            void run();
          }}
        >
          <div className="tool-inputs">
            {tab === "stress" ? (
              <>
                <ToolNumber
                  label="Low productive-hour value (USD)"
                  value={stressInput.value_low}
                  max={1e6}
                  onChange={(value) =>
                    setStressInput({ ...stressInput, value_low: value })
                  }
                />
                <ToolNumber
                  label="High productive-hour value (USD)"
                  value={stressInput.value_high}
                  max={1e6}
                  onChange={(value) =>
                    setStressInput({ ...stressInput, value_high: value })
                  }
                />
                <ToolNumber
                  label="Low realization (fraction)"
                  value={stressInput.realization_low}
                  max={1}
                  step={0.05}
                  onChange={(value) =>
                    setStressInput({ ...stressInput, realization_low: value })
                  }
                />
                <ToolNumber
                  label="High realization (fraction)"
                  value={stressInput.realization_high}
                  max={1}
                  step={0.05}
                  onChange={(value) =>
                    setStressInput({ ...stressInput, realization_high: value })
                  }
                />
                <ToolNumber
                  label="Low contract price (USD)"
                  value={stressInput.contract_low}
                  step={100000}
                  onChange={(value) =>
                    setStressInput({ ...stressInput, contract_low: value })
                  }
                />
                <ToolNumber
                  label="High contract price (USD)"
                  value={stressInput.contract_high}
                  step={100000}
                  onChange={(value) =>
                    setStressInput({ ...stressInput, contract_high: value })
                  }
                />
                <ToolNumber
                  label="Grid points per dimension"
                  value={stressInput.grid_points}
                  min={3}
                  max={9}
                  onChange={(value) =>
                    setStressInput({ ...stressInput, grid_points: value })
                  }
                />
              </>
            ) : (
              <>
                <ToolNumber
                  label="Implementation cost (USD)"
                  value={priceInput.implementation_cost}
                  step={10000}
                  onChange={(value) =>
                    setPriceInput({ ...priceInput, implementation_cost: value })
                  }
                />
                <ToolNumber
                  label="Annual support cost (USD)"
                  value={priceInput.annual_support_cost}
                  step={10000}
                  onChange={(value) =>
                    setPriceInput({ ...priceInput, annual_support_cost: value })
                  }
                />
                <ToolNumber
                  label="Target vendor gross margin (fraction)"
                  value={priceInput.target_gross_margin}
                  max={0.95}
                  step={0.05}
                  onChange={(value) =>
                    setPriceInput({ ...priceInput, target_gross_margin: value })
                  }
                />
                <ToolNumber
                  label="Vendor share of customer value"
                  value={priceInput.customer_value_share}
                  max={1}
                  step={0.05}
                  onChange={(value) =>
                    setPriceInput({
                      ...priceInput,
                      customer_value_share: value,
                    })
                  }
                />
              </>
            )}
          </div>
          <div className="tool-run-row">
            <p>
              {tab === "stress"
                ? "Deterministic grid coverage is not a probability of commercial success."
                : "All vendor costs are assumptions. The fee is the vendor’s share of modeled customer gross value."}{" "}
              Runs use current workspace draft inputs.
            </p>
            <button className="primary-button" disabled={offline || busy}>
              {busy
                ? "Calculating..."
                : tab === "stress"
                  ? "Run stress grid"
                  : "Evaluate pricing"}
              <ArrowUpRight size={16} />
            </button>
          </div>
        </form>
      </section>
      {(tab === "stress" ? stressStale : priceStale) && (
        <div className="stale-banner">
          <CircleHelp size={15} />
          <span>
            Showing the last completed tool result. Its inputs differ from the
            current draft.{" "}
            {offline
              ? "Start the engine to recalculate."
              : "Run the tool to apply changes."}
          </span>
        </div>
      )}
      {tab === "stress" &&
        (stress ? (
          <>
            <section className="panel">
              <div className="panel-heading">
                <div>
                  <span className="eyebrow">
                    {stressSource} · {stress.cell_count} GRID CELLS
                  </span>
                  <h2>The decision under pressure</h2>
                </div>
                <button
                  className="outlined-button"
                  onClick={() =>
                    downloadFile(
                      "qubityield-stress.json",
                      JSON.stringify(stress, null, 2),
                      "application/json",
                    )
                  }
                >
                  <ArrowDownToLine size={13} />
                  Export stress JSON
                </button>
              </div>
              <span className="subtle-pill">Coverage, not probability</span>
              <p className="strategy-summary">
                {stress.recommendation.summary}
              </p>
              <div className="strategy-two">
                <div>
                  <span>Best worst-case outcome</span>
                  <strong>
                    {optionNames[stress.recommendation.maximin_option] ||
                      stress.recommendation.maximin_option}
                  </strong>
                </div>
                <div>
                  <span>Smallest maximum regret</span>
                  <strong>
                    {optionNames[stress.recommendation.minimax_regret_option] ||
                      stress.recommendation.minimax_regret_option}
                  </strong>
                </div>
              </div>
              <div className="stress-cards">
                {stress.options.map((option) => (
                  <article className="stress-card" key={option.id}>
                    <h3>{option.label}</h3>
                    <div className="npv-three">
                      <div>
                        <span>Worst NPV</span>
                        <strong>{money(option.worst_npv_usd)}</strong>
                      </div>
                      <div>
                        <span>Base NPV</span>
                        <strong>{money(option.base_npv_usd)}</strong>
                      </div>
                      <div>
                        <span>Best NPV</span>
                        <strong>{money(option.best_npv_usd)}</strong>
                      </div>
                    </div>
                    <div className="coverage-label">
                      <span>Winning cells</span>
                      <strong>
                        {option.win_count} / {stress.cell_count} (
                        {percent(option.win_coverage, 0)})
                      </strong>
                    </div>
                    <div className="coverage-track">
                      <span style={{ width: percent(option.win_coverage) }} />
                    </div>
                    <p>
                      Positive NPV in {percent(option.positive_npv_coverage, 0)}{" "}
                      of grid cells. Maximum regret:{" "}
                      {money(option.max_regret_usd)}.
                    </p>
                  </article>
                ))}
              </div>
              <p className="panel-note">{stress.interpretation}</p>
              {!stress.base_inside_ranges && (
                <p className="panel-note">
                  The base case lies outside at least one selected stress range.
                </p>
              )}
            </section>
            <section className="panel">
              <div className="panel-heading">
                <div>
                  <span className="eyebrow">
                    SAMPLING SENSITIVITY IS A SEPARATE LAYER
                  </span>
                  <h2>What changes across the shot interval?</h2>
                </div>
              </div>
              <p className="strategy-summary">
                {stress.sampling_envelope.scope}
              </p>
              {stress.sampling_envelope.available ? (
                <div className="sampling-cards">
                  {stress.sampling_envelope.options.map((option) => (
                    <div key={option.id}>
                      <h3>{optionNames[option.id] || option.id}</h3>
                      <p>Base-case NPV envelope</p>
                      <strong>
                        {money(option.base_low_npv_usd)} to{" "}
                        {money(option.base_high_npv_usd)}
                      </strong>
                      <p>Stress + sampling envelope</p>
                      <span>
                        {money(option.stress_low_npv_usd)} to{" "}
                        {money(option.stress_high_npv_usd)}
                      </span>
                    </div>
                  ))}
                </div>
              ) : (
                <p className="panel-note">
                  {stress.sampling_envelope.reason ||
                    "A sampling envelope is not available for this result."}
                </p>
              )}
              <p className="panel-note">
                These are sensitivity intervals under the stated shot model.
                They are not probabilities of profitable adoption.
              </p>
            </section>
            <Warnings values={stress.warnings} />
          </>
        ) : (
          <EngineToolEmpty offline={offline} />
        ))}
      {tab === "pricing" &&
        (pricing ? (
          <>
            <section className="panel">
              <div className="panel-heading">
                <div>
                  <span className="eyebrow">{priceSource}</span>
                  <h2>Is there a price both sides can accept?</h2>
                </div>
                <button
                  className="outlined-button"
                  onClick={() =>
                    downloadFile(
                      "qubityield-pricing.json",
                      JSON.stringify(pricing, null, 2),
                      "application/json",
                    )
                  }
                >
                  <ArrowDownToLine size={13} />
                  Export pricing JSON
                </button>
              </div>
              <p className="strategy-summary">
                {pricing.recommendation.summary}
              </p>
              <div className="pricing-floors">
                <div>
                  <span>Nominal delivery cost</span>
                  <strong>{money(pricing.nominal_vendor_cost_usd)}</strong>
                </div>
                <div>
                  <span>Vendor price floor</span>
                  <strong>{money(pricing.vendor_floor_usd)}</strong>
                </div>
                {pricing.nominal_margin_floor_usd !== undefined && (
                  <div>
                    <span>Margin-only floor</span>
                    <strong>{money(pricing.nominal_margin_floor_usd)}</strong>
                  </div>
                )}
                {pricing.discounted_break_even_floor_usd !== undefined && (
                  <div>
                    <span>Cash break-even fee floor</span>
                    <strong>
                      {money(pricing.discounted_break_even_floor_usd)}
                    </strong>
                  </div>
                )}
              </div>
              <div className="price-cards">
                {pricing.options.map((option) => (
                  <article className="price-card" key={option.id}>
                    <div className="price-card-heading">
                      <h3>{option.label}</h3>
                      <span
                        className={`feasibility ${option.share_policy_feasible ? "feasible" : ""}`}
                      >
                        {option.share_policy_feasible
                          ? "Feasible under policy"
                          : option.full_surplus_feasible
                            ? "Policy gap"
                            : "No customer surplus"}
                      </span>
                    </div>
                    <dl>
                      <div>
                        <dt>Vendor floor</dt>
                        <dd>{money(option.vendor_floor_usd)}</dd>
                      </div>
                      <div>
                        <dt>Customer zero-NPV ceiling</dt>
                        <dd>{money(option.customer_zero_npv_cap_usd)}</dd>
                      </div>
                      <div>
                        <dt>Value-share target price</dt>
                        <dd>{money(option.customer_share_target_usd)}</dd>
                      </div>
                      <div>
                        <dt>Full-surplus feasible interval</dt>
                        <dd>
                          {option.full_surplus_interval
                            ? `${money(option.full_surplus_interval.min_usd)} to ${money(option.full_surplus_interval.max_usd)}`
                            : "No overlap"}
                        </dd>
                      </div>
                      <div>
                        <dt>Value-share policy interval</dt>
                        <dd>
                          {option.share_policy_interval
                            ? `${money(option.share_policy_interval.min_usd)} to ${money(option.share_policy_interval.max_usd)}`
                            : "No overlap"}
                        </dd>
                      </div>
                      {option.minimum_value_share !== null && (
                        <div>
                          <dt>Minimum vendor value share</dt>
                          <dd>{percent(option.minimum_value_share, 2)}</dd>
                        </div>
                      )}
                      {option.margin_at_share_target !== null && (
                        <div>
                          <dt>Margin at share target</dt>
                          <dd>{percent(option.margin_at_share_target, 2)}</dd>
                        </div>
                      )}
                      {option.gap_to_share_target_usd !== undefined && (
                        <div>
                          <dt>Gap from share target to floor</dt>
                          <dd>{money(option.gap_to_share_target_usd)}</dd>
                        </div>
                      )}
                      <div>
                        <dt>Conditional recommended price</dt>
                        <dd>
                          {option.recommended_price_usd === null
                            ? "No feasible offer"
                            : money(option.recommended_price_usd)}
                        </dd>
                      </div>
                      <div>
                        <dt>Customer NPV at share target</dt>
                        <dd>
                          {money(option.customer_npv_at_share_target_usd)}
                        </dd>
                      </div>
                      <div>
                        <dt>Vendor NPV at share target</dt>
                        <dd>{money(option.vendor_npv_at_share_target_usd)}</dd>
                      </div>
                    </dl>
                    <p>
                      {option.status_label ||
                        option.status.replaceAll("_", " ")}
                    </p>
                  </article>
                ))}
              </div>
              <p className="panel-note">
                Prices are nominal totals paid on the scenario installment
                schedule. A zero-NPV customer ceiling is a modeled boundary, not
                a willingness-to-pay estimate. Vendor floors include the stated
                costs and cash timing.
              </p>
            </section>
            <section className="panel">
              <div className="panel-heading">
                <h2>Vendor assumptions behind the price</h2>
              </div>
              <div className="warning-list">
                {pricing.assumptions.map((item) => (
                  <div key={item.key}>
                    <CircleHelp size={16} />
                    <p>
                      <strong>{item.label}.</strong> {item.rationale}
                    </p>
                  </div>
                ))}
              </div>
            </section>
            <Warnings values={pricing.warnings} />
          </>
        ) : (
          <EngineToolEmpty offline={offline} />
        ))}
    </>
  );
}
function EngineToolEmpty({ offline }: { offline: boolean }) {
  return (
    <section className="panel workbench-empty">
      <Scale size={27} />
      <h3>
        {offline
          ? "This tool needs the local engine."
          : "Run the tool to inspect the decision."}
      </h3>
      <p>
        {offline
          ? "No precomputed payload for this tool is bundled. Start qubityield serve to calculate it."
          : "Set the assumptions above. The Python model will return the stress or pricing result."}
      </p>
    </section>
  );
}
function Warnings({ values }: { values: string[] }) {
  return values?.length ? (
    <section className="panel">
      <div className="warning-list">
        {values.map((warning, index) => (
          <div key={index}>
            <CircleHelp size={16} />
            <p>{warning}</p>
          </div>
        ))}
      </div>
    </section>
  ) : null;
}
