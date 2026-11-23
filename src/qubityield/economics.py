"""Capacity, pricing and investment decisions with an explicit value bridge.

The model ranks conditional commercial opportunities, not hardware vendors.
It does not equate a simulated mirror-circuit success with application utility.
An explicit realization fraction and value assumption bridge that gap, and the
output keeps a test priority separate from a commitment to the proposed fee.
"""

from __future__ import annotations

import math
from collections.abc import Mapping
from typing import Any

from .models import Scenario, coerce_scenario


CASE_SOURCE = "Lab-to-Market Hackathon, Challenge 04, p. 5 (fictional case)"
OPTION_LABELS = {
    "baseline": "Keep current system",
    "calibration": "AI calibration",
    "pulse": "Pulse optimization",
    "control": "Lower-cost controls",
}


def calibration_time_reduction(speed_claim: float, interpretation: str) -> float:
    """Translate an ambiguous percentage into a fractional time reduction."""

    if not math.isfinite(speed_claim) or not 0 <= speed_claim <= 1:
        raise ValueError("speed_claim must be finite and between zero and one")
    if interpretation == "rate_increase":
        return speed_claim / (1 + speed_claim)
    if interpretation == "time_reduction":
        return speed_claim
    raise ValueError("Unknown AI speed interpretation")


def active_fraction(year: int, rollout_months: float) -> float:
    """Fraction of a particular contract year in which benefits are available."""

    return max(0.0, min(1.0, (12 * year - rollout_months) / 12))


def _finite_number(value: Any, label: str) -> float:
    try:
        number = float(value)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"{label} must be a finite number") from exc
    if not math.isfinite(number):
        raise ValueError(f"{label} must be a finite number")
    return number


def normalize_benchmark(scenario: Scenario, benchmark: Mapping[str, Any]) -> dict[str, Any]:
    """Compute the useful-shot rate ratio from evidence and current shot timing.

    A physical run estimates success probability. Reset/readout/host overhead is
    an economic scenario input, so cycle times are always recalculated here.
    Entangling gates within one layer are parallel; timing uses *layers*, not
    the total gate count. Local gates are ideal and take zero time in this
    deliberately controlled benchmark.
    """

    if not isinstance(benchmark, Mapping):
        raise ValueError("benchmark must contain baseline and pulse evidence")
    baseline = dict(benchmark.get("baseline", {}))
    pulse = dict(benchmark.get("pulse", {}))
    p0 = _finite_number(baseline.get("p_success"), "baseline p_success")
    p1 = _finite_number(pulse.get("p_success"), "pulse p_success")
    if not 0 < p0 <= 1:
        raise ValueError("baseline p_success must be positive and at most one; increase shots if zero successes were observed")
    if not 0 <= p1 <= 1:
        raise ValueError("pulse p_success must be between zero and one")
    baseline_cycle = scenario.fixed_overhead_us + scenario.layers * scenario.baseline_gate_ns / 1000
    pulse_cycle = scenario.fixed_overhead_us + scenario.layers * scenario.baseline_gate_ns * (1 + scenario.pulse_duration_increase) / 1000
    ratio = (p1 / pulse_cycle) / (p0 / baseline_cycle)
    return {
        **dict(benchmark),
        "baseline": baseline,
        "pulse": pulse,
        "throughput_ratio": ratio,
        "baseline_cycle_us": baseline_cycle,
        "pulse_cycle_us": pulse_cycle,
        "baseline_successful_shots_per_second": p0 * 1_000_000 / baseline_cycle,
        "pulse_successful_shots_per_second": p1 * 1_000_000 / pulse_cycle,
        "quantity_label": "simulated mirror-circuit successes per second",
    }


def _core(s: Scenario, benchmark: Mapping[str, Any]) -> dict[str, Any]:
    """Pure, inexpensive economics for one already-simulated physical case."""

    bench = normalize_benchmark(s, benchmark)
    rate_ratio = bench["throughput_ratio"]
    if s.value_mode == "fixed_output_savings" and rate_ratio <= 0:
        raise ValueError("Fixed-output savings requires positive pulse throughput; the same output cannot be delivered at zero successful-shot rate")
    available = 24 - s.calibration_hours
    booked = min(s.demand_hours_per_day, available)
    time_reduction = calibration_time_reduction(s.ai_speed_claim, s.ai_speed_interpretation)
    saved = s.calibration_hours * (1 - s.already_automated) * time_reduction * s.scale_realization
    usable_saved = saved * s.monetizable_overlap
    ai_available = min(24.0, available + usable_saved)
    ai_booked = min(s.demand_hours_per_day, ai_available)
    baseline_hours = booked * s.operating_days
    ai_hours = ai_booked * s.operating_days
    pulse_hours = baseline_hours * rate_ratio

    annual_fee = s.contract_total / s.contract_years
    discount_weights = [1 / (1 + s.discount_rate) ** y for y in range(1, s.contract_years + 1)]
    fee_pv_factor = sum(discount_weights) / s.contract_years
    benefit_pv_factor = sum(
        active_fraction(y, s.rollout_months) * weight
        for y, weight in enumerate(discount_weights, start=1)
    )
    fee_pv = s.contract_total * fee_pv_factor
    integration_cost = s.control_engineers * s.control_integration_months / 12 * s.engineer_annual_cost
    control_hardware_quote = s.control_cost * (1 - s.control_saving)
    avoided_procurement = s.control_cost if s.replacement_due else 0.0
    control_upfront_benefit = avoided_procurement - integration_cost
    standalone_controls_net = avoided_procurement - control_hardware_quote - integration_cost

    def option(identifier: str, new_hours: float, new_available: float, new_booked: float, upfront: float = 0.0) -> dict[str, Any]:
        incremental = new_hours - baseline_hours
        if s.value_mode == "fixed_output_savings":
            value_hours = baseline_hours * (1 - 1 / rate_ratio) if identifier == "pulse" else 0.0
        else:
            value_hours = incremental
        annual_benefit = value_hours * s.value_per_productive_hour * s.value_realization
        gross_pv = upfront + annual_benefit * benefit_pv_factor
        is_baseline = identifier == "baseline"
        net = 0.0 if is_baseline else gross_pv - fee_pv
        denominator = value_hours * s.value_realization * benefit_pv_factor
        break_even = max(0.0, (fee_pv - upfront) / denominator) if denominator > 0 else None
        price_ceiling = max(0.0, gross_pv / fee_pv_factor) if not is_baseline else 0.0
        return {
            "id": identifier,
            "label": OPTION_LABELS[identifier],
            "available_hours_day": new_available,
            "booked_hours_day": new_booked,
            "recovered_hours_day": saved if identifier == "calibration" else 0.0,
            "usable_recovered_hours_day": usable_saved if identifier == "calibration" else 0.0,
            "useful_hours_year": new_hours,
            "incremental_useful_hours_year": incremental,
            "value_hours_year": value_hours,
            "annual_benefit_usd": annual_benefit,
            "upfront_benefit_usd": upfront,
            "customer_npv_usd": net,
            "gross_value_pv_usd": gross_pv,
            "contract_fee_pv_usd": 0.0 if is_baseline else fee_pv,
            "break_even_value_per_hour_usd": break_even,
            "price_ceiling_usd": price_ceiling,
            "price_ceiling_feasible": gross_pv >= 0,
        }

    options = [
        option("baseline", baseline_hours, available, booked),
        option("calibration", ai_hours, ai_available, ai_booked),
        option("pulse", pulse_hours, available, booked),
        option("control", baseline_hours, available, booked, control_upfront_benefit),
    ]
    by_id = {o["id"]: o for o in options}
    preferred = max(options, key=lambda o: (o["gross_value_pv_usd"], o["id"] == "baseline"))
    best_at_quote = max(options, key=lambda o: (o["customer_npv_usd"], o["id"] == "baseline"))
    cashflows = [{"year": 0, "calibration": 0.0, "pulse": 0.0, "control": control_upfront_benefit}]
    for year in range(1, s.contract_years + 1):
        cashflows.append({
            "year": year,
            **{
                identifier: by_id[identifier]["annual_benefit_usd"] * active_fraction(year, s.rollout_months) - annual_fee
                for identifier in ("calibration", "pulse", "control")
            },
        })

    return {
        "benchmark": bench,
        "options": options,
        "schedule": {
            "baseline": {"calibration": s.calibration_hours, "booked": booked, "idle": 24 - s.calibration_hours - booked},
            "calibration": {"calibration": s.calibration_hours - saved, "booked": ai_booked, "idle": 24 - (s.calibration_hours - saved) - ai_booked},
        },
        "cashflows": cashflows,
        "financial_basis": {
            "currency": "USD",
            "basis": "incremental customer contribution or avoided cost, not vendor revenue",
            "value_mode": s.value_mode,
            "value_quantity_definition": (
                "baseline booked hours avoided while delivering the same expected mirror-benchmark output; only the pulse option accelerates existing work"
                if s.value_mode == "fixed_output_savings"
                else "additional useful benchmark output expressed in baseline-equivalent productive hours"
            ),
            "fee_timing": "equal end-of-year installments",
            "annual_contract_fee_usd": annual_fee,
            "contract_fee_pv_usd": fee_pv,
            "fee_pv_factor": fee_pv_factor,
            "benefit_pv_factor": benefit_pv_factor,
            "control_integration_cost_usd": integration_cost,
            "control_hardware_quote_usd": control_hardware_quote,
            "control_avoided_procurement_usd": avoided_procurement,
            "standalone_controls_net_usd": standalone_controls_net,
            "control_contract_includes_hardware": True,
            "calibration_time_reduction": time_reduction,
            "unserved_demand_hours_day": max(0.0, s.demand_hours_per_day - available),
            "best_at_current_quote": best_at_quote["id"],
            "preferred_validation_target": preferred["id"],
            "useful_hours_definition": "annual mirror-benchmark capacity expressed in hours at the baseline successful-shot rate; not wall-clock hours or guaranteed application utility",
        },
    }


def assumptions_ledger(s: Scenario) -> list[dict[str, Any]]:
    """Return input provenance alongside assumptions that the case cannot answer."""

    observations = [
        ("calibration_hours", "Daily calibration", 8.0, "Nominal processor unavailability, before any overnight or demand adjustment."),
        ("booking_utilization", "Observed bookings / available time", 0.70, "Case observation. Default demand is 0.70 x (24 - 8) = 11.2 hours/day; the explicit demand field controls a scenario."),
        ("already_automated", "Calibration tasks already automated", 0.35, "The case reports a fraction of tasks, not a time share. Treating it as a time share is an explicit approximation."),
        ("ai_speed_claim", "AI calibration speed claim", 0.70, "The wording is 70% faster. It does not unambiguously mean 70% less time."),
        ("baseline_gate_error", "Current two-qubit average gate infidelity", 0.01, "Interpreted as full reported gate error in reported_total mode; mapping to an independent depolarizing channel is a modeling assumption."),
        ("pulse_gate_error", "Proposed two-qubit average gate infidelity", 0.005, "A proposed improvement in the fictional case, not independently measured evidence."),
        ("baseline_gate_ns", "Current two-qubit duration (ns)", 300.0, "Disjoint two-qubit gates run in parallel within a layer."),
        ("pulse_duration_increase", "Pulse duration increase", 0.40, "420 ns at the case's 300 ns baseline."),
        ("t1_us", "Median T1 (us)", 120.0, "A median is not a device-wide distribution. Reported-total mode does not add this loss twice."),
        ("t2_us", "Median T2 (us)", 120.0, "Used for the alternate control-only noise interpretation, with T2 <= 2 T1."),
        ("n_qubits", "Representative workload qubits", 20, "The device has 100 qubits; the representative workload uses 20. The benchmark does not simulate the whole processor."),
        ("layers", "Entangling layers", 20, "Even mirror-circuit depth; at 20 qubits this yields 200 two-qubit gates."),
        ("contract_total", "Proposed total contract", 5_000_000.0, "Assumed to include the selected product and, for controls, the supplied hardware. Do not add the hardware quote to this fee."),
        ("contract_years", "Contract horizon (years)", 3, "No terminal value, renewal, or residual hardware value is assumed."),
        ("control_cost", "Conventional control procurement", 2_000_000.0, "Only avoidable when an equivalent new procurement was already required. Installed purchase costs are sunk."),
        ("control_saving", "Advertised hardware discount", 0.30, "Standalone hardware quote is $1.4M at the case inputs, separate from the target total-contract analysis."),
        ("control_engineers", "Customer engineers for integration", 3, "Customer cost; vendor engineering cost is not provided."),
        ("control_integration_months", "Control integration (months)", 6.0, "3 engineers x 6/12 year x $300K = $450K."),
        ("engineer_annual_cost", "Customer cost per engineer-year", 300_000.0, "No extra, unsupported engineering salary assumptions are added."),
    ]
    rows: list[dict[str, Any]] = []
    for key, label, original, rationale in observations:
        value = getattr(s, key)
        overridden = value != original
        rows.append({
            "key": key, "label": label, "value": value,
            "kind": "assumption" if overridden else "case", "source": CASE_SOURCE,
            "original_value": original,
            "rationale": ("Scenario override of the case observation. " if overridden else "") + rationale,
        })
    assumptions = [
        ("ai_speed_interpretation", "Meaning of faster", "rate_increase uses time / 1.7, a 41.18% reduction; time_reduction tests the alternative 70% reduction reading."),
        ("scale_realization", "10-to-100-qubit transfer", "Assumed fraction of pilot time-saving that survives full-device deployment. This is not a success probability."),
        ("monetizable_overlap", "Freed time in usable windows", "Assumed fraction of saved calibration time reachable by customer demand. The case only says most calibration runs overnight."),
        ("demand_hours_per_day", "Daily demand scenario", "Fixed workload-hour demand; extra availability creates bookings only after the existing 16 hours are filled. No automatic demand growth is assumed."),
        ("fixed_overhead_us", "Reset, readout and host overhead per shot", "Illustrative fixed time per shot. It dilutes the relative penalty of longer entangling gates. Local Clifford-gate time is omitted."),
        ("value_per_productive_hour", "Value per baseline-equivalent productive hour", "Illustrative marginal contribution or avoided cost, not a known rental price or vendor revenue."),
        ("value_realization", "Commercial value realization", "Fraction of the selected extra-output or fixed-output saved-time quantity that translates into monetizable application benefit. Explicitly unvalidated, not a probability or margin estimate."),
        ("value_mode", "What creates financial value", "additional_output values B*(R-1), which needs demand for more useful output. fixed_output_savings values B*(1-1/R), the booked time avoided for the same benchmark output; only genuinely avoidable costs can be monetized. Calibration has no same-output speedup and earns zero capacity value in that mode."),
        ("operating_days", "Operating days per year", "Assumed service calendar; maintenance and other fixed overhead are represented only to the extent captured by the case's booked time."),
        ("discount_rate", "Annual discount rate", "Illustrative time-value/risk hurdle. It does not validate the business or replace uncertainty analysis."),
        ("rollout_months", "Delay before recurring benefits", "Assumed deployment delay shared by capacity improvements. Fees remain payable at each year end; a delay beyond the horizon produces no recurring benefit."),
        ("replacement_due", "Equivalent new controls purchase required", "False means the existing $2M system is sunk. True credits avoidable $2M procurement. Integration cost is conservatively recognized at time zero."),
        ("noise_mode", "Noise interpretation", "reported_total uses reported full gate infidelities without adding in-gate T1/T2 loss again; control_only treats the reported errors as control errors and adds Pauli-twirled relaxation."),
        ("readout_error", "Independent bit-readout error", "Not supplied in the case. Zero isolates the proposed two-qubit-gate improvement; it is not a claim of perfect hardware readout."),
        ("shots", "Monte Carlo trajectories per circuit", "A computational budget. Binomial intervals reflect sampling error within this assumed model, not uncertainty about real hardware."),
        ("seed", "Reproducibility seed", "Reproduce the circuit and simulated error trajectories using the exported scenario and software version."),
    ]
    for key, label, rationale in assumptions:
        rows.append({"key": key, "label": label, "value": getattr(s, key), "kind": "assumption", "source": "Explicit analyst assumption", "rationale": rationale})
    return rows


def _recommendation(s: Scenario, result: dict[str, Any]) -> dict[str, Any]:
    preferred_id = result["financial_basis"]["preferred_validation_target"]
    preferred = next(o for o in result["options"] if o["id"] == preferred_id)
    initial = "Prioritize AI calibration because eight hours of daily downtime appears to be the largest capacity opportunity."
    if preferred_id == "baseline":
        title = "Keep the current system"
        verdict = "Reject at the current evidence level"
        summary = "None of the modeled upgrades creates positive gross customer value under these assumptions. Validate demand and application value before purchasing capacity."
    else:
        title = f"Prioritize {OPTION_LABELS[preferred_id].lower()}"
        verdict = "Conditional go after validation" if preferred["customer_npv_usd"] > 0 else "Renegotiate"
        if preferred_id == "pulse":
            mechanism = "Better gates increase simulated successful-shot throughput even after accounting for their longer duration."
        elif preferred_id == "calibration":
            mechanism = "Demand exceeds current available capacity, so some recovered calibration time produces additional bookings."
        else:
            mechanism = "An already-required procurement makes the avoided control-system purchase the largest modeled source of value."
        summary = mechanism + " The price ceiling depends on the assumed application-value conversion and is a zero-NPV ceiling, not a recommended price or validated willingness to pay."
    return {
        "id": preferred_id,
        "title": title,
        "summary": summary,
        "contract_verdict": verdict,
        "price_ceiling_usd": preferred["price_ceiling_usd"],
        "price_ceiling_basis": "maximum nonnegative total of equal annual installments; where gross value is positive it sets modeled customer NPV to zero. Zero may mean that no nonnegative fee can break even.",
        "initial_hypothesis": initial,
        "survived": preferred_id == "calibration",
        "best_at_current_quote": result["financial_basis"]["best_at_current_quote"],
        "validation_gates": [
            "Replay representative customer applications at matched wall-clock budgets, including reset, readout, leakage and drift.",
            "Measure booked demand by time of day and identify which saved calibration windows could actually be sold or used.",
            "Obtain an agreed dollar value for application outcomes before converting benchmark gains into a contract price.",
        ],
    }


def _warnings(s: Scenario, result: dict[str, Any]) -> list[str]:
    notes = [
        "All case inputs are fictional. The benchmark is simulated; no QPU, customer or vendor has validated these results.",
        "Mirror-circuit success is a controlled benchmark, not application correctness. The dollar conversion requires customer validation.",
        "The 35% already-automated task count is assumed to represent 35% of calibration time; a task-duration audit could change the result.",
        "The 10-qubit AI pilot does not establish performance on the customer's 100-qubit processor.",
        "The target contract includes the selected product. For controls it includes hardware, so the separate $1.4M hardware quote is not charged again.",
        "Lower-cost controls are assumed to preserve current performance; that parity must be tested. Vendor delivery costs are unknown, so vendor profit is not estimated.",
        "Baseline-equivalent productive hours can exceed wall-clock hours; they express benchmark throughput relative to the baseline.",
    ]
    if s.demand_hours_per_day <= 24 - s.calibration_hours:
        notes.append("Current demand fits inside existing availability. Faster calibration produces no additional booked hours in this fungible-demand model.")
    if not s.replacement_due:
        notes.append("The installed $2M controls are treated as a sunk cost. A cheaper new control system does not create savings without a replacement need.")
    if s.noise_mode == "reported_total":
        notes.append("Reported gate error is interpreted as total average infidelity. Adding in-gate coherence decay again would double count it.")
    else:
        notes.append("Control-only mode is an alternate interpretation and uses Pauli-twirled thermal noise, not a full nonunital amplitude-damping model.")
    if s.fixed_overhead_us == 0:
        notes.append("Zero reset/readout/host overhead is an optimistic gate-only timing limit.")
    if s.value_mode == "fixed_output_savings":
        notes.append("This scenario values fixed-output saved booked hours, B*(1-1/R), rather than extra capacity B*(R-1). Saved time is worth money only if costs are avoidable or the time is redeployed; calibration creates no same-output execution speedup.")
        baseline = next(o for o in result["options"] if o["id"] == "baseline")
        if baseline["booked_hours_day"] / result["benchmark"]["throughput_ratio"] > baseline["available_hours_day"]:
            notes.append("At the proposed pulse throughput, the same expected workload cannot fit into currently available hours. The fixed-output case would require extra runtime beyond the modeled daily capacity.")
    else:
        notes.append("This scenario values additional useful output B*(R-1), not the smaller fixed-output saved-time quantity B*(1-1/R). Extra-output demand and willingness to pay must be established.")
    if s.rollout_months >= s.contract_years * 12:
        notes.append("Deployment occurs after the modeled contract horizon, so no recurring capacity benefit is recognized.")
    if abs(s.demand_hours_per_day - s.booking_utilization * (24 - s.calibration_hours)) > 1e-9:
        notes.append("Demand is a scenario override of the case's observed utilization; the explicit daily-demand field controls bookings.")
    if result["benchmark"]["baseline"]["p_success"] < 0.01:
        notes.append("The baseline success probability is very small. Ratios may be unstable; increase shots and inspect uncertainty before valuing a gain.")
    return notes


def evaluate_economics(scenario: Scenario | dict, benchmark: Mapping[str, Any], *, include_sensitivity: bool = True) -> dict[str, Any]:
    """Evaluate four choices and explain the commercial assumptions.

    Reuses physical evidence for economic sweeps; it never silently simulates
    new hardware settings. The caller must supply evidence matching physical
    inputs. Pure economic edits, including shot overhead, need no new shots.
    """

    s = coerce_scenario(scenario)
    result = _core(s, benchmark)
    result["scenario"] = s.model_dump()
    result["recommendation"] = _recommendation(s, result)
    result["assumptions"] = assumptions_ledger(s)
    result["warnings"] = _warnings(s, result)
    result["sensitivities"] = []
    result["heatmap"] = []
    if not include_sensitivity:
        return result

    preferred_id = result["recommendation"]["id"]
    target_id = preferred_id if preferred_id != "baseline" else "pulse"
    sweeps = [
        ("value_per_productive_hour", "Value per productive hour", 250.0, 2500.0),
        ("value_realization", "Commercial value realization", 0.10, 0.80),
        ("demand_hours_per_day", "Demand hours per day", 8.0, 22.0),
        ("rollout_months", "Deployment delay (months)", 3.0, 18.0),
        ("discount_rate", "Annual discount rate", 0.05, 0.25),
        ("monetizable_overlap", "Saved time in usable windows", 0.0, 1.0),
        ("scale_realization", "AI pilot transfer fraction", 0.30, 1.0),
    ]
    for field, label, low, high in sweeps:
        bounds = []
        for value in (low, high):
            changed = Scenario.model_validate({**s.model_dump(), field: value})
            evaluated = _core(changed, benchmark)
            target = next(o for o in evaluated["options"] if o["id"] == target_id)
            bounds.append(target["customer_npv_usd"])
        result["sensitivities"].append({"parameter": field, "label": label, "low": low, "high": high, "low_npv": bounds[0], "high_npv": bounds[1], "option_id": target_id})
    result["sensitivities"].sort(key=lambda x: abs(x["high_npv"] - x["low_npv"]), reverse=True)

    for value in (0, 250, 500, 1000, 1500, 2000, 3000):
        for realization in (0.10, 0.25, 0.35, 0.50, 0.75, 1.0):
            changed = Scenario.model_validate({**s.model_dump(), "value_per_productive_hour": value, "value_realization": realization})
            evaluated = _core(changed, benchmark)
            winner = max(evaluated["options"], key=lambda o: (o["customer_npv_usd"], o["id"] == "baseline"))
            result["heatmap"].append({"value_per_hour": value, "realization": realization, "winner": winner["id"], "npv": winner["customer_npv_usd"]})
    return result
