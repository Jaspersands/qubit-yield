# Decision tools

Two tools extend the core decision model without adding speculative physics. The stress tool asks how a recommendation changes across explicit business assumptions. The pricing tool asks whether a customer-supported price can also cover a vendor's assumed delivery costs. Both call the same `evaluate_economics` implementation used by the main dashboard.

The challenge, hardware specification and business case are fictional. The benchmark is a noisy simulation of a mirror circuit. These tools do not establish application correctness, willingness to pay, market size or hardware performance.

## Entry points

The public Python interface is:

```python
from qubityield.analysis import evaluate
from qubityield.decision_tools import (
    PricingRequest,
    StressRequest,
    evaluate_pricing,
    evaluate_stress,
)
from qubityield.models import Scenario

scenario = Scenario()
benchmark = evaluate(scenario, include_depth=False)["benchmark"]
stress = evaluate_stress(StressRequest(scenario=scenario), benchmark)
pricing = evaluate_pricing(PricingRequest(scenario=scenario), benchmark)
```

The two calculation functions are deterministic and do not mutate their inputs, draw samples, write files or access hardware. Each accepts its Pydantic request model or an equivalent dictionary. Public functions revalidate models, including models constructed through Pydantic's validation-bypassing `model_copy(update=...)` method.

The API routes are `POST /api/stress` and `POST /api/pricing`. They accept the JSON requests below, obtain one matching benchmark under the shared compute budget and attach evidence provenance to the result. Callers cannot submit substitute quantum evidence to these endpoints. Python callers supplying a benchmark must use the matching scenario. Any supplied physical metadata and cycle timing are checked for consistency. Changing fixed overhead while reusing old cycle-based sampling bounds is rejected even if the gate-error probabilities are unchanged.

The CLI accepts the same request JSON:

```sh
.venv/bin/qubityield stress --request stress-request.json --output artifacts/stress.json
.venv/bin/qubityield pricing --request pricing-request.json --output artifacts/pricing.json
```

Omitting `--request` uses the stated defaults. CLI and API wrappers add the benchmark and provenance; the pure functions return `physical_fingerprint` when it is present in the input evidence.

## Stress envelope

### Request

```json
{
  "scenario": {},
  "value_low": 250,
  "value_high": 2000,
  "realization_low": 0.1,
  "realization_high": 0.75,
  "contract_low": 3000000,
  "contract_high": 7000000,
  "grid_points": 5
}
```

An empty scenario uses the documented case defaults. A complete scenario, including `value_mode`, can be supplied instead. Only three commercial variables change inside the grid: the illustrative value per productive hour, the realization fraction, and the total nominal contract fee. Demand, scheduling, discounting, the valuation mode and the physical benchmark remain fixed. `grid_points` is an integer from 3 to 9. Each nonconstant axis is evenly spaced and includes both endpoints; a constant range contributes one unique value. The maximum is 9 × 9 × 9 = 729 cells, not 729 quantum simulations.

Value per hour is bounded from 0 to $1,000,000, realization from 0 to 1 and total contract price from 0 to $1 billion. Reversed bounds, nonfinite values, numeric strings, booleans in numeric fields and unknown fields are rejected. All monetary output must be finite JSON numbers.

### What the outputs mean

Each cell contains all four customer NPVs and the option with the highest NPV. The unchanged baseline is included at zero incremental NPV. Exact ties favor keeping the current system, then calibration, pulse and controls. This makes a zero-value tie an explicit no-purchase result.

Each option reports:

| Field | Meaning |
| --- | --- |
| `worst_npv_usd`, `best_npv_usd` | Minimum and maximum over the requested discrete grid |
| `base_npv_usd` | NPV under the supplied scenario's original assumptions |
| `win_count`, `win_coverage` | Count and fraction of cells won under the stated tie rule |
| `positive_npv_count`, `positive_npv_coverage` | Count and fraction with strictly positive customer NPV |
| `max_regret_usd` | Largest amount of NPV forgone relative to the best option in the same cell |
| `always_nonnegative` | Whether every grid NPV is at least zero |
| `dominated_by` | Options at least as good in every grid cell and strictly better in at least one |

Win coverage is a description of the chosen grid, not a probability or a confidence level. Equally spaced cells do not imply that business outcomes are uniformly distributed. Moving the ranges or their spacing can change the coverage.

The response distinguishes two decision rules. `recommendation.maximin_option` maximizes the worst customer NPV. `recommendation.minimax_regret_option` minimizes the largest forgone NPV. These rules can disagree. `base_validation_priority` retains the main model's technical validation priority, which is a different question from committing to a contract.

The original scenario can lie outside the requested ranges. In that case `base_inside_ranges` is false and the base NPV can be outside the displayed worst-to-best range. The response includes a warning rather than silently expanding the requested grid.

### Sampling uncertainty is separate

If matching evidence supplies finite lower and upper throughput-ratio sampling bounds, `sampling_envelope` propagates those bounds through the same economic equations. Each option reports base NPV bounds and the combined extremes across ratio endpoints and the commercial grid. The economic response is monotone in the pulse ratio for nonnegative value assumptions, so endpoint propagation gives the conditional extrema for that interval.

These are conditional financial bounds under this circuit, noise model and range of assumptions. They are not confidence intervals for future revenue or application performance. The tool does not infer a distribution for demand, value, vendor costs, calibration benefits or real hardware errors. If bounds are missing, it reports them unavailable. A zero lower throughput bound in `fixed_output_savings` mode means the same work could take unbounded time. Where any base or grid scenario has monetized exposure within the contract horizon, the tool explicitly reports an unbounded lower result instead of fabricating a finite dollar bound. If every scenario has zero exposure, such as zero booked work or rollout after the contract ends, the monetary limit is constant and is marked `zero_bound_value_neutral`.

The internal ratio propagation constructs algebraically consistent placeholder probabilities to reuse the economic evaluator. Those placeholders are never returned as measured counts or evidence.

### Response contract

The top-level response has `kind: "stress_envelope"`, `scenario`, `ranges`, `grid_points`, `axes`, `cell_count`, `base_inside_ranges`, `options`, `cells`, `recommendation`, `sampling_envelope`, `interpretation`, `tie_rule`, `warnings` and `physical_fingerprint`.

Each cell has `value_per_hour`, `realization`, `contract_total`, `winner`, `best_npv_usd` and `npv_by_option`. Option identifiers are `baseline`, `calibration`, `pulse` and `control`. A sampling result has `available`, `ratio_low`, `ratio_high`, `scope` and `options`; unavailable results also explain the reason. Available option bounds are `base_low_npv_usd`, `base_high_npv_usd`, `stress_low_npv_usd` and `stress_high_npv_usd`.

## Two-sided pricing

### Request

```json
{
  "scenario": {},
  "implementation_cost": 500000,
  "annual_support_cost": 150000,
  "target_gross_margin": 0.6,
  "customer_value_share": 0.3
}
```

These are analyst assumptions, not vendor facts from the challenge. The same hypothetical cost structure is applied to each proposal so the assumptions are visible. `implementation_cost` is paid at time zero and must include all supplied hardware and implementation costs borne by the vendor. `annual_support_cost` is paid at each contract-year end, including rollout years. Each cost is bounded from zero to $1 billion. Target margin is at least zero and strictly below one; the value share is between zero and one.

Despite its API name, `customer_value_share` is the fraction of gross customer value charged by the vendor. A share of 0.30 charges 30% and leaves 70% with the customer before other unmodeled costs. The UI labels it "Vendor share of customer value".

### Money and timing

Let `T` be the contract length, `r` the discount rate, `I` the upfront vendor cost, `S` yearly support cost and `m` target gross margin. Define the annuity factor `A = sum(1 / (1 + r)^year)` over years 1 through T. The core model's `fee_pv_factor = A / T` converts a nominal total fee into its present value under equal year-end installments.

The calculations keep nominal money separate from discounted money:

| Quantity | Calculation |
| --- | --- |
| Nominal vendor cost | `I + T * S` |
| Vendor cost PV | `I + S * A` |
| Nominal margin floor | `nominal_cost / (1 - m)` |
| Cash break-even floor, expressed as nominal total fee | `vendor_cost_PV / fee_pv_factor` |
| Binding vendor floor | Maximum of the two floors |
| Customer zero-NPV cap, nominal total fee | `gross_customer_value_PV / fee_pv_factor`, when gross value is positive |
| Selected value-share target | `customer_cap * customer_value_share` |

Margin means `(revenue - delivery_cost) / revenue`, not a markup on cost. Positive nominal margin does not guarantee positive NPV when implementation is paid up front and fees arrive later. The separate cash floor prevents that mistake.

The customer cap is taken directly from the existing economics, including rollout, demand, the chosen valuation mode and the treatment of installed controls. The controls contract includes hardware. Its quoted standalone purchase price is not a manufacturing-cost estimate, and the customer's integration expense is not a vendor expense. Those amounts are not counted twice.

### Feasible prices and refusals

`full_surplus_interval` is the intersection of the binding vendor floor and the customer zero-NPV cap. It is null if no positive contract can satisfy both. `share_policy_interval` further limits the price to the selected vendor share of customer value. A recommendation is made only if this narrower interval exists. `recommended_price_usd` is its upper endpoint, the requested share target; it is not a market-clearing price forecast.

A proposal can have positive joint surplus while failing the selected share policy. That result is reported as `share_target_below_vendor_floor`, with no recommended fee. The tool then shows the minimum vendor share required, so a user can negotiate the share, reduce cost or reject the proposal. It never silently increases the share to make a deal appear feasible.

The response also evaluates the scenario's existing quote independently. `quote_is_jointly_feasible` checks customer NPV, the target nominal margin and vendor cash break-even. It does not require that the existing quote satisfy the separate value-share policy. A high quoted vendor margin can coexist with negative customer NPV.

Zero customer value does not support a positive contract, even when vendor cost is zero. Gross margin for a zero-price offer is undefined and reported as null. A negative gross customer value cannot be repaired merely by clamping the price cap to zero.

### Valuation mode matters

With baseline booked hours `B` and useful-shot rate ratio `R`, the main model values `B * (R - 1)` additional productive hours in `additional_output` mode. This assumes the extra useful output can create value at the stated realization fraction. In `fixed_output_savings` mode it instead values `B * (1 - 1 / R)` hours saved while doing the same work. A slower pulse can have negative value. Calibration receives no added-bookings value in the fixed-output mode. The pricing tool preserves these distinctions; it does not convert a rate gain into an equal percentage cost saving.

### Response contract

The top level has `kind: "pricing_feasibility"`, `scenario`, `inputs`, `nominal_vendor_cost_usd`, `vendor_cost_pv_usd`, `nominal_margin_floor_usd`, `discounted_break_even_floor_usd`, `vendor_floor_usd`, `fee_pv_factor`, `vendor_npv_at_floor_usd`, `options`, `recommendation`, `assumptions`, `warnings` and `physical_fingerprint`.

There are three `options`, for calibration, pulse and controls. Each includes its customer cap, share target, binding floor, both feasibility flags and intervals, `recommended_price_usd`, `minimum_value_share`, customer and vendor NPVs at the share target and existing quote, margins, the gap to the share target and a status label. Interval objects have `min_usd` and `max_usd`. Unavailable intervals and recommended prices are null, not zero.

`recommendation.option_id` is the feasible proposal with the largest customer cap, or the largest-cap negotiable proposal if the share policy blocks every deal. It is null when no positive joint-surplus interval exists. `recommendation.deal_feasible` is true only when the selected share policy is feasible. Status identifiers are `no_positive_customer_value`, `customer_cap_below_vendor_floor`, `share_target_below_vendor_floor` and `feasible_at_share_target`.

## Reproducible examples

These examples use the saved default benchmark from `artifacts/analysis.json`: 772 baseline successful shots and 2,468 pulse successful shots out of 8,192 per arm, giving a useful-shot rate ratio of about 3.1261 after cycle timing. They are conditional model outputs, not hardware or customer evidence. Monetary figures below are rounded; the JSON retains precision.

### Default assumption grid

The default 5 × 5 × 5 grid contains 125 cells. Keeping the current system wins 46 cells, or 36.8%; pulse optimization wins 79, or 63.2%. No purchase has the highest worst-case customer NPV, zero. Pulse minimizes maximum regret, about $5.18 million, while its grid NPV ranges from about -$5.18 million to +$23.09 million. The base pulse NPV is +$1.95 million. These figures illustrate why a majority of chosen cells winning is not the same thing as a robust purchase decision.

### Example 1: A plausible opportunity that fails the share policy

Under the default additional-output valuation, the pulse customer cap is about $7.43 million. Assumed vendor delivery cost is $950,000 nominal over three years. A 60% target margin requires a $2.375 million nominal fee. The discounted cash break-even floor is lower, about $1.075 million, so the margin floor binds. Charging 30% of customer value gives about $2.229 million and a 57.38% nominal margin, below the target. A joint-surplus interval exists, but the requested share policy does not. The tool returns no recommended fee. The minimum feasible vendor share is about 31.97%.

### Example 2: A different negotiated share makes the interval feasible

Change only `customer_value_share` to 0.35. The pulse target becomes about $2.600 million. It exceeds both vendor floors and stays below the customer cap. Nominal vendor margin is about 63.47%, vendor NPV is about $1.222 million and customer NPV is about $3.866 million. The recommended nominal total is the selected share target, paid in equal year-end installments. This demonstrates a mathematical negotiation range under assumed costs; a real offer still requires validated costs and customer value.

Changing the scenario to `fixed_output_savings` is a stronger counter-case. The same physical evidence then supports a customer cap of only about $2.377 million, leaving a very narrow full-surplus interval at the 60% margin floor and no feasible 30% share target. The existing $5 million quote has negative customer NPV despite a high nominal vendor margin.

## Validation scope

`tests/test_decision_tools.py` exercises bounded grid size, reversed and degenerate ranges, finite serialization, strict numeric request types, stable tie handling, coverage arithmetic, direct agreement with the economic model, dominance, regret, base scenarios outside the grid, monotonicity, missing and invalid sampling bounds, unbounded fixed-output runtime, stale physical evidence, and input immutability. Pricing checks include margin versus markup, deferred revenue versus upfront cost, nominal versus discounted floors, zero value, zero costs, undefined zero-price margins, share-policy conflicts, negative customer NPV, control replacement and subnormal inputs.

Run the focused validation with:

```sh
.venv/bin/python -m pytest tests/test_decision_tools.py -q
.venv/bin/python -m ruff check src/qubityield/decision_tools.py tests/test_decision_tools.py
```

API resource bounds, persistence and concurrent-job behavior are tested separately. No result here establishes performance on a QPU or a real chemistry, materials or optimization workload.
