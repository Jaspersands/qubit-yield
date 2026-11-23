"""Bounded commercial stress tests and explicit two-sided pricing constraints.

These pure functions reuse supplied, matching quantum evidence. They make no
hardware calls, draw no random samples and do not turn an assumption grid into
a probability distribution. The API owns simulation scheduling and provenance.
"""

from __future__ import annotations

import copy
import json
import math
from collections.abc import Mapping
from itertools import product
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, model_validator

from .economics import evaluate_economics
from .models import Scenario

OPTION_ORDER = ("baseline", "calibration", "pulse", "control")
MAX_STRESS_CELLS = 9**3


class StressRequest(BaseModel):
    """Three evenly spaced assumption axes, at most 729 distinct grid points."""

    model_config = ConfigDict(extra="forbid", allow_inf_nan=False, strict=True)
    scenario: Scenario = Field(default_factory=Scenario)
    value_low: float = Field(default=250.0, ge=0, le=1_000_000)
    value_high: float = Field(default=2000.0, ge=0, le=1_000_000)
    realization_low: float = Field(default=0.10, ge=0, le=1)
    realization_high: float = Field(default=0.75, ge=0, le=1)
    contract_low: float = Field(default=3_000_000.0, ge=0, le=1_000_000_000)
    contract_high: float = Field(default=7_000_000.0, ge=0, le=1_000_000_000)
    grid_points: int = Field(default=5, ge=3, le=9)

    @model_validator(mode="after")
    def ordered_ranges(self) -> StressRequest:
        for prefix in ("value", "realization", "contract"):
            if getattr(self, f"{prefix}_low") > getattr(self, f"{prefix}_high"):
                raise ValueError(f"{prefix}_low cannot exceed {prefix}_high")
        return self


class PricingRequest(BaseModel):
    """Assumed vendor delivery economics, not costs supplied by the case file.

    customer_value_share is the fraction of modeled customer gross value charged
    by the vendor, not the fraction retained by the customer.
    """

    model_config = ConfigDict(extra="forbid", allow_inf_nan=False, strict=True)
    scenario: Scenario = Field(default_factory=Scenario)
    implementation_cost: float = Field(default=500_000.0, ge=0, le=1_000_000_000)
    annual_support_cost: float = Field(default=150_000.0, ge=0, le=1_000_000_000)
    target_gross_margin: float = Field(default=0.60, ge=0, lt=1)
    customer_value_share: float = Field(default=0.30, ge=0, le=1)


def _request(model_type, value):
    # Revalidate instances too: Pydantic model_copy(update=...) bypasses validation.
    return model_type.model_validate(value.model_dump() if isinstance(value, BaseModel) else value)


def _finite_json(value):
    try:
        json.dumps(value, allow_nan=False)
    except (TypeError, ValueError, OverflowError) as exc:
        raise ValueError("Decision calculation requires finite, JSON-serializable evidence") from exc
    return value


def _checked_evidence(scenario: Scenario, benchmark: Mapping[str, Any]) -> dict:
    if not isinstance(benchmark, Mapping):
        raise ValueError("benchmark must be a mapping of baseline and pulse evidence")
    evidence = copy.deepcopy(dict(benchmark))
    # Full analysis responses may not be passed accidentally in place of their benchmark.
    for arm, error, duration in (
        ("baseline", scenario.baseline_gate_error, scenario.baseline_gate_ns),
        ("pulse", scenario.pulse_gate_error, scenario.baseline_gate_ns * (1 + scenario.pulse_duration_increase)),
    ):
        if not isinstance(evidence.get(arm), Mapping):
            raise ValueError(f"benchmark must contain {arm} evidence")
        expected = {
            "n_qubits": scenario.n_qubits, "layers": scenario.layers,
            "shots": scenario.shots, "seed": scenario.seed,
            "gate_error": error, "gate_duration_ns": duration,
            "noise_mode": scenario.noise_mode, "readout_error": scenario.readout_error,
            "t1_us": scenario.t1_us, "t2_us": scenario.t2_us,
        }
        for key, value in expected.items():
            if key in evidence[arm] and evidence[arm][key] != value:
                raise ValueError(f"{arm} benchmark {key} does not match the scenario; rerun matching physics")
    for key, duration in (
        ("baseline_cycle_us", scenario.baseline_gate_ns),
        ("pulse_cycle_us", scenario.baseline_gate_ns * (1 + scenario.pulse_duration_increase)),
    ):
        if key in evidence:
            supplied = evidence[key]
            expected_cycle = scenario.fixed_overhead_us + scenario.layers * duration / 1000
            if (isinstance(supplied, bool) or not isinstance(supplied, (int, float))
                    or not math.isfinite(supplied)
                    or not math.isclose(supplied, expected_cycle, rel_tol=1e-12, abs_tol=0)):
                raise ValueError(f"benchmark {key} does not match the scenario; rerun matching cycle timing")
    return _finite_json(evidence)


def _economics(scenario: Scenario, benchmark: Mapping[str, Any]) -> dict:
    return _finite_json(evaluate_economics(scenario, benchmark, include_sensitivity=False))


def _axis(low: float, high: float, points: int) -> list[float]:
    if low == high:
        return [float(low)]
    return [low + (high - low) * index / (points - 1) for index in range(points - 1)] + [float(high)]


def _winner(npvs: Mapping[str, float]) -> str:
    # Stable, disclosed tie rule: no purchase first, then the declared option order.
    return max(OPTION_ORDER, key=lambda key: npvs[key])


def _npvs(result: dict) -> dict[str, float]:
    return {option["id"]: option["customer_npv_usd"] for option in result["options"]}


def _ratio_evidence(scenario: Scenario, ratio: float) -> dict:
    """Represent a hypothetical rate ratio using valid probabilities.

    The returned numbers are algebraic placeholders ONLY for the economic
    evaluator. They are never exported as measured counts or probabilities.
    Choosing the smaller baseline keeps both probabilities <= 0.5 even when a
    confidence-bound ratio exceeds the largest ratio possible at observed p0.
    """
    baseline_cycle = scenario.fixed_overhead_us + scenario.layers * scenario.baseline_gate_ns / 1000
    pulse_cycle = scenario.fixed_overhead_us + scenario.layers * scenario.baseline_gate_ns * (1 + scenario.pulse_duration_increase) / 1000
    probability_ratio = ratio * pulse_cycle / baseline_cycle
    if not math.isfinite(probability_ratio):
        raise ValueError("Sampling-bound throughput ratio is too large")
    p0 = 0.5 / max(1.0, probability_ratio)
    p1 = p0 * probability_ratio
    if p0 <= 0:
        raise ValueError("Sampling-bound ratio cannot be represented safely")
    return {"baseline": {"p_success": p0}, "pulse": {"p_success": p1}}


def _sampling_envelope(scenario: Scenario, benchmark: dict, scenarios: list[Scenario]) -> dict:
    scope = (
        "Propagation of the supplied throughput-ratio sampling interval through the same "
        "economic model. Conditional on this circuit, noise model and selected assumption "
        "ranges; not a confidence interval for commercial performance."
    )
    low = benchmark.get("throughput_ratio_ci_low")
    high = benchmark.get("throughput_ratio_ci_high")
    parsed = []
    for bound in (low, high):
        if bound is None:
            parsed.append(None)
            continue
        if isinstance(bound, bool):
            raise ValueError("Sampling ratio bounds must be finite numbers")
        try:
            bound = float(bound)
        except (TypeError, ValueError) as exc:
            raise ValueError("Sampling ratio bounds must be finite numbers") from exc
        if not math.isfinite(bound) or bound < 0:
            raise ValueError("Sampling ratio bounds must be finite and nonnegative")
        parsed.append(bound)
    low, high = parsed
    if low is None or high is None:
        return {"available": False, "ratio_low": low, "ratio_high": high, "scope": scope,
                "reason": "Finite lower and upper throughput-ratio sampling bounds were not supplied.", "options": []}
    if low > high:
        raise ValueError("Sampling ratio bounds must be finite, nonnegative and ordered")
    base_result = _economics(scenario, benchmark)
    point = base_result["benchmark"]["throughput_ratio"]
    if not low <= point <= high:
        raise ValueError("Sampling ratio bounds must contain the supplied point estimate")
    zero_value_limit = False
    if scenario.value_mode == "fixed_output_savings" and low == 0:
        baseline = next(row for row in base_result["options"] if row["id"] == "baseline")
        financially_exposed = (
            baseline["booked_hours_day"] > 0
            and base_result["financial_basis"]["benefit_pv_factor"] > 0
            and any(item.value_per_productive_hour > 0 and item.value_realization > 0
                    for item in [scenario, *scenarios])
        )
        if financially_exposed:
            return {"available": False, "ratio_low": low, "ratio_high": high, "scope": scope,
                    "reason": "A zero lower throughput bound gives unbounded same-output runtime; there is no finite lower monetary bound.",
                    "lower_bound_unbounded": True, "options": []}
        zero_value_limit = True
    bounds = []
    for ratio in (low, high):
        # If no booked work or monetized benefit exists anywhere in the grid,
        # NPV is constant in R. Its R -> 0+ limit equals any positive R value.
        conditional = _ratio_evidence(scenario, 1.0 if zero_value_limit and ratio == 0 else ratio)
        base = _npvs(_economics(scenario, conditional))
        grid = [_npvs(_economics(item, conditional)) for item in scenarios]
        bounds.append((base, grid))
    return {
        "available": True, "ratio_low": low, "ratio_high": high, "scope": scope,
        "zero_bound_value_neutral": zero_value_limit,
        "options": [
            {"id": identifier,
             "base_low_npv_usd": min(bound[0][identifier] for bound in bounds),
             "base_high_npv_usd": max(bound[0][identifier] for bound in bounds),
             "stress_low_npv_usd": min(row[identifier] for _, grid in bounds for row in grid),
             "stress_high_npv_usd": max(row[identifier] for _, grid in bounds for row in grid)}
            for identifier in OPTION_ORDER
        ],
    }


def evaluate_stress(request: StressRequest | dict, benchmark: Mapping[str, Any]) -> dict:
    """Evaluate a bounded three-dimensional grid without new quantum execution."""
    req = _request(StressRequest, request)
    s = req.scenario
    evidence = _checked_evidence(s, benchmark)
    base = _economics(s, evidence)
    axes = {
        "value": _axis(req.value_low, req.value_high, req.grid_points),
        "realization": _axis(req.realization_low, req.realization_high, req.grid_points),
        "contract": _axis(req.contract_low, req.contract_high, req.grid_points),
    }
    scenarios, cells = [], []
    for value, realization, contract in product(axes["value"], axes["realization"], axes["contract"]):
        changed = Scenario.model_validate({**s.model_dump(), "value_per_productive_hour": value,
                                           "value_realization": realization, "contract_total": contract})
        scenarios.append(changed)
        npvs = _npvs(_economics(changed, evidence))
        winner = _winner(npvs)
        cells.append({"value_per_hour": value, "realization": realization,
                      "contract_total": contract, "winner": winner,
                      "best_npv_usd": npvs[winner], "npv_by_option": npvs})
    if len(cells) > MAX_STRESS_CELLS:  # Defense if input schema is edited later.
        raise ValueError("Stress grid exceeds the 729-cell budget")
    base_by_id = {option["id"]: option for option in base["options"]}
    options = []
    for identifier in OPTION_ORDER:
        values = [cell["npv_by_option"][identifier] for cell in cells]
        wins = sum(cell["winner"] == identifier for cell in cells)
        positives = sum(value > 0 for value in values)
        dominators = [
            other for other in OPTION_ORDER if other != identifier
            and all(cell["npv_by_option"][other] >= cell["npv_by_option"][identifier] for cell in cells)
            and any(cell["npv_by_option"][other] > cell["npv_by_option"][identifier] for cell in cells)
        ]
        options.append({
            "id": identifier, "label": base_by_id[identifier]["label"],
            "worst_npv_usd": min(values), "base_npv_usd": base_by_id[identifier]["customer_npv_usd"],
            "best_npv_usd": max(values), "win_count": wins, "win_coverage": wins / len(cells),
            "positive_npv_count": positives, "positive_npv_coverage": positives / len(cells),
            "max_regret_usd": max(cell["best_npv_usd"] - cell["npv_by_option"][identifier] for cell in cells),
            "always_nonnegative": min(values) >= 0, "dominated_by": dominators,
        })
    maximin = max(options, key=lambda option: option["worst_npv_usd"])
    minimax = min(options, key=lambda option: option["max_regret_usd"])
    inside = (req.value_low <= s.value_per_productive_hour <= req.value_high
              and req.realization_low <= s.value_realization <= req.realization_high
              and req.contract_low <= s.contract_total <= req.contract_high)
    sampling = _sampling_envelope(s, evidence, scenarios)
    result = {
        "kind": "stress_envelope", "scenario": s.model_dump(),
        "ranges": {"value_per_productive_hour": [req.value_low, req.value_high],
                   "value_realization": [req.realization_low, req.realization_high],
                   "contract_total": [req.contract_low, req.contract_high]},
        "grid_points": req.grid_points, "axes": axes, "cell_count": len(cells),
        "base_inside_ranges": inside, "options": options, "cells": cells,
        "recommendation": {
            "maximin_option": maximin["id"], "minimax_regret_option": minimax["id"],
            "base_validation_priority": base["recommendation"]["id"],
            "summary": f"Across {len(cells)} stated assumption combinations, {maximin['label'].lower()} "
                       f"protects the highest worst-case customer NPV; {minimax['label'].lower()} "
                       "minimizes the largest forgone NPV. These are different decision rules, not probabilities of success.",
        },
        "sampling_envelope": sampling,
        "interpretation": "Win coverage is the fraction of these equally spaced grid cells in which an option has the highest customer NPV. It is NOT a probability, forecast or confidence level. No distribution over assumptions is asserted.",
        "tie_rule": "Keep current system wins exact ties first, followed by calibration, pulse and controls.",
        "warnings": [
            "All case data are fictional. No new physics is simulated by this stress grid; it reuses the supplied matching benchmark.",
            "Worst and best results are over the stated discrete assumption grid, not all possible hardware or business conditions.",
            "Sampling bounds and assumption ranges have different meanings and are reported separately.",
        ] + ([] if inside else ["The base scenario lies outside the requested ranges; its NPV need not fall between the reported grid extremes."]),
        "physical_fingerprint": evidence.get("physical_fingerprint"),
    }
    return _finite_json(result)


def _finite_ratio(numerator: float, denominator: float) -> float | None:
    if denominator <= 0:
        return None
    result = numerator / denominator
    return result if math.isfinite(result) else None


def _margin(price: float, cost: float) -> float | None:
    fraction = _finite_ratio(cost, price)
    return None if fraction is None else 1 - fraction


def evaluate_pricing(request: PricingRequest | dict, benchmark: Mapping[str, Any]) -> dict:
    """Compare vendor price floors with customer ceilings on one payment schedule.

    Nominal margin and present value are calculated separately. The binding
    floor must meet both the nominal target margin and vendor cash-flow NPV>=0.
    A recommended price must also fit the user-selected vendor share of value.
    """
    req = _request(PricingRequest, request)
    s = req.scenario
    evidence = _checked_evidence(s, benchmark)
    base = _economics(s, evidence)
    fee_factor = base["financial_basis"]["fee_pv_factor"]
    annuity = fee_factor * s.contract_years
    nominal_cost = req.implementation_cost + req.annual_support_cost * s.contract_years
    cost_pv = req.implementation_cost + req.annual_support_cost * annuity
    margin_floor = nominal_cost / (1 - req.target_gross_margin)
    cash_floor = cost_pv / fee_factor
    binding_floor = max(margin_floor, cash_floor)
    options = []
    for option in base["options"]:
        if option["id"] == "baseline":
            continue
        ceiling = option["price_ceiling_usd"]
        target = ceiling * req.customer_value_share
        full_feasible = option["price_ceiling_feasible"] and ceiling > 0 and binding_floor <= ceiling
        share_feasible = full_feasible and target > 0 and binding_floor <= target
        if not option["price_ceiling_feasible"] or ceiling <= 0:
            status, label = "no_positive_customer_value", "No positive customer-supported contract price"
        elif not full_feasible:
            status, label = "customer_cap_below_vendor_floor", "Customer ceiling cannot cover the vendor floor"
        elif not share_feasible:
            status, label = "share_target_below_vendor_floor", "Value-share target is below the vendor floor"
        else:
            status, label = "feasible_at_share_target", "Feasible at the selected share of value"
        recommended = target if share_feasible else None
        options.append({
            "id": option["id"], "label": option["label"],
            "customer_zero_npv_cap_usd": ceiling,
            "customer_share_target_usd": target, "vendor_floor_usd": binding_floor,
            "full_surplus_feasible": full_feasible, "share_policy_feasible": share_feasible,
            "full_surplus_interval": {"min_usd": binding_floor, "max_usd": ceiling} if full_feasible else None,
            "share_policy_interval": {"min_usd": binding_floor, "max_usd": target} if share_feasible else None,
            "recommended_price_usd": recommended,
            "minimum_value_share": _finite_ratio(binding_floor, ceiling),
            "margin_at_share_target": _margin(target, nominal_cost),
            "vendor_profit_at_share_target_usd": target - nominal_cost,
            "customer_npv_at_share_target_usd": option["gross_value_pv_usd"] - target * fee_factor,
            "vendor_npv_at_share_target_usd": target * fee_factor - cost_pv,
            "quote_customer_npv_usd": option["customer_npv_usd"],
            "quote_vendor_npv_usd": s.contract_total * fee_factor - cost_pv,
            "quote_vendor_margin": _margin(s.contract_total, nominal_cost),
            "quote_is_jointly_feasible": full_feasible and s.contract_total > 0 and binding_floor <= s.contract_total <= ceiling,
            "gap_to_share_target_usd": max(0.0, binding_floor - target),
            "status": status, "status_label": label,
        })
    feasible = [option for option in options if option["share_policy_feasible"]]
    negotiable = [option for option in options if option["full_surplus_feasible"]]
    candidates = feasible or negotiable
    selected = max(candidates, key=lambda option: option["customer_zero_npv_cap_usd"]) if candidates else None
    if feasible:
        summary = f"{selected['label']} admits a price that meets the assumed vendor margin, cash-flow break-even and selected value-share policy. Validate the costs and customer benefit before treating that range as an offer."
    elif negotiable:
        summary = f"{selected['label']} has potential joint surplus, but the selected share of customer value is below the vendor floor. Raise the negotiated share or reduce delivery cost; no price is recommended under the current policy."
    else:
        summary = "No upgrade supports a positive contract price that meets the assumed vendor constraints and the modeled customer ceiling. Reduce cost, establish more customer value or decline the deal."
    inputs = req.model_dump(exclude={"scenario"})
    return _finite_json({
        "kind": "pricing_feasibility", "scenario": s.model_dump(), "inputs": inputs,
        "nominal_vendor_cost_usd": nominal_cost, "vendor_cost_pv_usd": cost_pv,
        "nominal_margin_floor_usd": margin_floor, "discounted_break_even_floor_usd": cash_floor,
        "vendor_floor_usd": binding_floor, "fee_pv_factor": fee_factor,
        "vendor_npv_at_floor_usd": binding_floor * fee_factor - cost_pv,
        "options": options,
        "recommendation": {"option_id": selected["id"] if selected else None,
                           "deal_feasible": bool(feasible), "summary": summary},
        "assumptions": [
            {"key": "implementation_cost", "label": "Vendor upfront implementation cost", "value": req.implementation_cost, "kind": "assumption", "rationale": "Paid at time zero. Must include all vendor implementation and supplied-hardware cost; the case provides no vendor cost data."},
            {"key": "annual_support_cost", "label": "Vendor yearly support cost", "value": req.annual_support_cost, "kind": "assumption", "rationale": "Paid at each contract-year end, including rollout years. Same hypothetical cost basis is applied to each proposal for comparison."},
            {"key": "target_gross_margin", "label": "Target nominal gross margin", "value": req.target_gross_margin, "kind": "assumption", "rationale": "Defined as (nominal contract revenue - nominal delivery cost) / nominal revenue. Cash timing is checked separately."},
            {"key": "customer_value_share", "label": "Vendor share of customer value", "value": req.customer_value_share, "kind": "assumption", "rationale": "Fraction of modeled gross customer value charged as the fee, on the same installment schedule. It is not the fraction retained by the customer."},
        ],
        "warnings": [
            "Vendor costs, margin target and value-share policy are analyst assumptions, not facts from the fictional case.",
            "All price floors and ceilings are nominal total fees on the same equal year-end installment schedule. Present values are labeled separately.",
            "A positive quote must satisfy both the nominal margin target and vendor cash-flow break-even. Zero-price offers have no defined gross margin and are not recommended contracts.",
            "The quoted controls hardware price is not its manufacturing cost. Enter the vendor's actual inclusive hardware and delivery cost before using this tool for that proposal.",
            "Customer value remains conditional on the workload and valuation mode; this does not establish willingness to pay, market pricing, tax treatment or a vendor valuation.",
        ],
        "physical_fingerprint": evidence.get("physical_fingerprint"),
    })
