"""Commercial counterfactuals and accounting invariants, not snapshot tests."""

import json
import math

import pytest
from pydantic import ValidationError

from qubityield.economics import (
    active_fraction,
    calibration_time_reduction,
    evaluate_economics,
)
from qubityield.models import Scenario


BENCHMARK = {
    "baseline": {"p_success": 0.20, "ci_low": 0.19, "ci_high": 0.21},
    "pulse": {"p_success": 0.40, "ci_low": 0.39, "ci_high": 0.41},
}


def evaluated(**overrides):
    return evaluate_economics(Scenario(**overrides), BENCHMARK, include_sensitivity=False)


def opt(result, identifier):
    return next(o for o in result["options"] if o["id"] == identifier)


def test_faster_is_not_the_same_as_less_time():
    assert calibration_time_reduction(0.7, "rate_increase") == pytest.approx(7 / 17)
    assert calibration_time_reduction(0.7, "time_reduction") == pytest.approx(0.7)


def test_default_calibration_has_no_new_bookings_despite_real_time_saved():
    result = evaluated()
    ai = opt(result, "calibration")
    assert ai["recovered_hours_day"] == pytest.approx(1.4988235294117647)
    assert ai["usable_recovered_hours_day"] == pytest.approx(0.37470588235294117)
    assert ai["booked_hours_day"] == pytest.approx(11.2)
    assert ai["incremental_useful_hours_year"] == 0
    assert ai["annual_benefit_usd"] == 0
    assert ai["break_even_value_per_hour_usd"] is None


def test_new_demand_can_use_only_reachable_recovered_time():
    result = evaluated(demand_hours_per_day=24)
    baseline = opt(result, "baseline")
    ai = opt(result, "calibration")
    assert baseline["booked_hours_day"] == 16
    assert ai["booked_hours_day"] - 16 == pytest.approx(0.37470588235294117)
    assert ai["incremental_useful_hours_year"] == pytest.approx(136.76764705882353)


@pytest.mark.parametrize("demand", [0, 11.2, 16, 24])
@pytest.mark.parametrize("overlap", [0, 0.25, 1])
def test_daily_time_is_conserved_even_if_saved_hours_cannot_be_used(demand, overlap):
    result = evaluated(demand_hours_per_day=demand, monetizable_overlap=overlap)
    for schedule in result["schedule"].values():
        assert sum(schedule.values()) == pytest.approx(24)
        assert min(schedule.values()) >= 0
    assert opt(result, "calibration")["available_hours_day"] <= 24


@pytest.mark.parametrize("field", ["scale_realization", "ai_speed_claim", "monetizable_overlap"])
def test_a_broken_calibration_value_link_prevents_new_bookings(field):
    result = evaluated(demand_hours_per_day=24, **{field: 0})
    assert opt(result, "calibration")["booked_hours_day"] == 16


def test_already_automated_tasks_are_not_sold_as_new_savings():
    result = evaluated(already_automated=1, demand_hours_per_day=24)
    assert opt(result, "calibration")["recovered_hours_day"] == 0


def test_zero_demand_means_zero_capacity_value_for_both_upgrades():
    result = evaluated(demand_hours_per_day=0)
    for identifier in ("calibration", "pulse"):
        assert opt(result, identifier)["annual_benefit_usd"] == 0
        assert opt(result, identifier)["price_ceiling_usd"] == 0
    assert result["recommendation"]["id"] == "baseline"


def test_parallel_entangling_gates_use_layers_for_time_not_gate_count():
    result = evaluated()
    assert result["benchmark"]["baseline_cycle_us"] == 106
    assert result["benchmark"]["pulse_cycle_us"] == pytest.approx(108.4)
    assert result["benchmark"]["throughput_ratio"] == pytest.approx(2 * 106 / 108.4)


def test_slow_gates_pay_a_larger_penalty_when_no_fixed_overhead_exists():
    result = evaluated(fixed_overhead_us=0)
    assert result["benchmark"]["throughput_ratio"] == pytest.approx(2 / 1.4)
    assert result["benchmark"]["throughput_ratio"] < evaluated()["benchmark"]["throughput_ratio"]


def test_same_accuracy_with_slower_gates_can_destroy_value():
    benchmark = {"baseline": {"p_success": 0.4}, "pulse": {"p_success": 0.4}}
    result = evaluate_economics(Scenario(), benchmark, include_sensitivity=False)
    assert opt(result, "pulse")["annual_benefit_usd"] < 0
    assert result["recommendation"]["id"] == "baseline"


def test_zero_monetization_does_not_turn_capacity_into_revenue():
    result = evaluated(value_realization=0)
    assert opt(result, "pulse")["incremental_useful_hours_year"] > 0
    assert opt(result, "pulse")["annual_benefit_usd"] == 0
    assert opt(result, "pulse")["break_even_value_per_hour_usd"] is None


def test_fixed_output_savings_is_not_extra_output_capacity():
    extra = evaluated()
    fixed = evaluated(value_mode="fixed_output_savings")
    p_extra, p_fixed = opt(extra, "pulse"), opt(fixed, "pulse")
    ratio = fixed["benchmark"]["throughput_ratio"]
    baseline_hours = opt(fixed, "baseline")["useful_hours_year"]
    assert p_extra["incremental_useful_hours_year"] == p_fixed["incremental_useful_hours_year"]
    assert p_extra["value_hours_year"] == pytest.approx(baseline_hours * (ratio - 1))
    assert p_fixed["value_hours_year"] == pytest.approx(baseline_hours * (1 - 1 / ratio))
    assert p_fixed["annual_benefit_usd"] == pytest.approx(p_extra["annual_benefit_usd"] / ratio)
    assert p_fixed["value_hours_year"] < baseline_hours


def test_calibration_extra_bookings_are_not_same_output_savings():
    fixed = evaluated(value_mode="fixed_output_savings", demand_hours_per_day=24)
    ai = opt(fixed, "calibration")
    assert ai["incremental_useful_hours_year"] > 0
    assert ai["value_hours_year"] == 0
    assert ai["annual_benefit_usd"] == 0


def test_fixed_output_price_ceiling_and_break_even_use_saved_time():
    fixed = evaluated(value_mode="fixed_output_savings")
    pulse = opt(fixed, "pulse")
    repriced = evaluated(value_mode="fixed_output_savings", contract_total=pulse["price_ceiling_usd"])
    assert opt(repriced, "pulse")["customer_npv_usd"] == pytest.approx(0, abs=1e-8)
    value_changed = evaluated(value_mode="fixed_output_savings", value_per_productive_hour=pulse["break_even_value_per_hour_usd"])
    assert opt(value_changed, "pulse")["customer_npv_usd"] == pytest.approx(0, abs=1e-8)


def test_zero_pulse_rate_cannot_deliver_fixed_output():
    benchmark = {"baseline": {"p_success": 0.4}, "pulse": {"p_success": 0}}
    with pytest.raises(ValueError, match="same output"):
        evaluate_economics(Scenario(value_mode="fixed_output_savings"), benchmark)


def test_fixed_output_slowdown_reports_unfulfillable_daily_work():
    benchmark = {"baseline": {"p_success": 0.4}, "pulse": {"p_success": 0.1}}
    result = evaluate_economics(Scenario(value_mode="fixed_output_savings"), benchmark, include_sensitivity=False)
    assert opt(result, "pulse")["value_hours_year"] < 0
    assert any("cannot fit" in warning for warning in result["warnings"])


def test_zero_price_may_still_not_offset_unavoidable_integration():
    result = evaluated(contract_total=0)
    control = opt(result, "control")
    assert control["price_ceiling_usd"] == 0
    assert control["price_ceiling_feasible"] is False
    assert control["customer_npv_usd"] == -450_000


def test_standalone_control_savings_account_for_engineering_and_sunk_costs():
    sunk = evaluated()["financial_basis"]
    replacement = evaluated(replacement_due=True)["financial_basis"]
    assert sunk["control_hardware_quote_usd"] == 1_400_000
    assert sunk["control_integration_cost_usd"] == 450_000
    assert sunk["standalone_controls_net_usd"] == -1_850_000
    assert replacement["standalone_controls_net_usd"] == 150_000


def test_target_control_contract_includes_hardware_and_does_not_charge_it_twice():
    result = evaluated(replacement_due=True, discount_rate=0)
    control = opt(result, "control")
    assert control["gross_value_pv_usd"] == 1_550_000
    assert control["customer_npv_usd"] == -3_450_000  # 2M avoided -450K integration -5M total fee
    assert result["financial_basis"]["control_contract_includes_hardware"] is True


def test_advertised_discount_is_separate_from_fixed_target_contract():
    original = evaluated(replacement_due=True)
    deeper_discount = evaluated(replacement_due=True, control_saving=0.6)
    assert deeper_discount["financial_basis"]["standalone_controls_net_usd"] > original["financial_basis"]["standalone_controls_net_usd"]
    assert opt(original, "control")["customer_npv_usd"] == opt(deeper_discount, "control")["customer_npv_usd"]


def test_cash_flows_reconcile_to_every_option_npv():
    result = evaluated()
    for identifier in ("calibration", "pulse", "control"):
        discounted = sum(row[identifier] / (1.12 ** row["year"]) for row in result["cashflows"])
        assert opt(result, identifier)["customer_npv_usd"] == pytest.approx(discounted)


def test_delayed_benefits_do_not_delay_contract_payments_without_agreement():
    result = evaluated(rollout_months=18, discount_rate=0)
    pulse = opt(result, "pulse")
    rows = result["cashflows"]
    assert rows[1]["pulse"] == pytest.approx(-5_000_000 / 3)
    assert rows[2]["pulse"] == pytest.approx(pulse["annual_benefit_usd"] / 2 - 5_000_000 / 3)
    assert rows[3]["pulse"] == pytest.approx(pulse["annual_benefit_usd"] - 5_000_000 / 3)


def test_no_recurring_benefit_after_horizon():
    result = evaluated(rollout_months=36)
    assert opt(result, "pulse")["gross_value_pv_usd"] == 0
    assert opt(result, "pulse")["customer_npv_usd"] < 0


def test_price_ceiling_is_a_nominal_installment_total_not_present_value():
    result = evaluated()
    ceiling = opt(result, "pulse")["price_ceiling_usd"]
    assert ceiling > opt(result, "pulse")["gross_value_pv_usd"]
    repriced = evaluated(contract_total=ceiling)
    assert opt(repriced, "pulse")["customer_npv_usd"] == pytest.approx(0, abs=1e-8)


def test_break_even_dollar_assumption_actually_sets_npv_to_zero():
    result = evaluated()
    breakeven = opt(result, "pulse")["break_even_value_per_hour_usd"]
    repriced_value = evaluated(value_per_productive_hour=breakeven)
    assert opt(repriced_value, "pulse")["customer_npv_usd"] == pytest.approx(0, abs=1e-8)


def test_validation_priority_is_distinct_from_buying_at_an_unaffordable_quote():
    result = evaluated(contract_total=100_000_000)
    assert result["recommendation"]["id"] == "pulse"
    assert result["recommendation"]["best_at_current_quote"] == "baseline"
    assert result["recommendation"]["contract_verdict"] == "Renegotiate"
    assert result["recommendation"]["survived"] is False


def test_derived_rate_ignores_an_untrusted_or_stale_ratio():
    bad_ratio = {**BENCHMARK, "throughput_ratio": 1000, "baseline_cycle_us": 1, "pulse_cycle_us": 1}
    result = evaluate_economics(Scenario(), bad_ratio, include_sensitivity=False)
    assert result["benchmark"]["throughput_ratio"] == pytest.approx(2 * 106 / 108.4)


@pytest.mark.parametrize("changes", [
    {"t2_us": 300}, {"n_qubits": 21}, {"layers": 21}, {"value_realization": 1.1},
    {"demand_hours_per_day": -1}, {"discount_rate": float("nan")}, {"contract_total": float("inf")},
    {"surprise": 1},
])
def test_invalid_or_nonphysical_scenarios_are_rejected(changes):
    with pytest.raises(ValidationError):
        Scenario(**changes)


@pytest.mark.parametrize("p0,p1", [(0, .1), (-.1, .1), (1.1, .2), (.1, -1), (.1, math.inf)])
def test_invalid_benchmark_cannot_create_spurious_money(p0, p1):
    with pytest.raises(ValueError):
        evaluate_economics(Scenario(), {"baseline": {"p_success": p0}, "pulse": {"p_success": p1}})


def test_results_are_finite_and_exportable_with_real_sensitivity_evaluations():
    result = evaluate_economics(Scenario(), BENCHMARK)
    json.dumps(result, allow_nan=False)
    assert len(result["heatmap"]) == 42
    assert all(cell["npv"] >= 0 for cell in result["heatmap"])
    assert any(cell["winner"] == "baseline" for cell in result["heatmap"])
    sensitivity = next(row for row in result["sensitivities"] if row["parameter"] == "value_per_productive_hour")
    independently_evaluated = evaluated(value_per_productive_hour=sensitivity["low"])
    assert sensitivity["low_npv"] == opt(independently_evaluated, sensitivity["option_id"])["customer_npv_usd"]


def test_case_override_is_marked_as_assumption():
    result = evaluated(baseline_gate_ns=250)
    row = next(a for a in result["assumptions"] if a["key"] == "baseline_gate_ns")
    assert row["kind"] == "assumption"
    assert row["original_value"] == 300


def test_benefit_fraction_boundaries():
    assert [active_fraction(y, 18) for y in range(1, 4)] == [0, .5, 1]
    assert active_fraction(1, 0) == 1
