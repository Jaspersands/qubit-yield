"""Adversarial pricing and deterministic stress-envelope contracts."""

import copy
import json

import pytest
from pydantic import ValidationError

from qubityield.decision_tools import (
    PricingRequest,
    StressRequest,
    evaluate_pricing,
    evaluate_stress,
)
from qubityield.economics import evaluate_economics
from qubityield.models import Scenario


BENCHMARK = {
    "baseline": {"p_success": .1}, "pulse": {"p_success": .3},
    "throughput_ratio_ci_low": 2.5, "throughput_ratio_ci_high": 3.5,
    "physical_fingerprint": "specified-test-evidence",
}


def option(result, identifier="pulse"):
    return next(row for row in result["options"] if row["id"] == identifier)


@pytest.mark.parametrize("changes", [
    {"value_low": 1000, "value_high": 500},
    {"realization_low": .9, "realization_high": .1},
    {"contract_low": 9_000_000, "contract_high": 1_000_000},
    {"value_low": -1}, {"value_high": 1_000_001},
    {"realization_low": -.01}, {"realization_high": 1.01},
    {"contract_low": -1}, {"contract_high": 1_000_000_001},
    {"grid_points": 2}, {"grid_points": 10}, {"grid_points": 3.5},
    {"value_high": float("nan")}, {"contract_high": float("inf")},
    {"realization_high": float("-inf")}, {"unknown": 1},
    {"grid_points": "5"}, {"grid_points": 5.0},
    {"value_low": False}, {"contract_low": "1000"},
])
def test_stress_rejects_invalid_and_unbounded_requests(changes):
    with pytest.raises(ValidationError):
        StressRequest(**changes)


@pytest.mark.parametrize("changes", [
    {"implementation_cost": -1}, {"annual_support_cost": -1},
    {"target_gross_margin": 1}, {"target_gross_margin": 1.1},
    {"target_gross_margin": -.1}, {"customer_value_share": -1},
    {"customer_value_share": 1.1}, {"implementation_cost": float("nan")},
    {"annual_support_cost": float("inf")}, {"target_gross_margin": float("-inf")},
    {"customer_value_share": float("nan")}, {"unknown": 1},
    {"implementation_cost": True}, {"annual_support_cost": "150000"},
])
def test_pricing_rejects_invalid_costs_margins_and_nonfinite_values(changes):
    with pytest.raises(ValidationError):
        PricingRequest(**changes)


def test_unsafe_model_copy_cannot_bypass_public_function_budgets():
    unsafe = StressRequest().model_copy(update={"grid_points": 1000})
    with pytest.raises(ValidationError):
        evaluate_stress(unsafe, BENCHMARK)
    unsafe_price = PricingRequest().model_copy(update={"target_gross_margin": 1})
    with pytest.raises(ValidationError):
        evaluate_pricing(unsafe_price, BENCHMARK)


def test_maximum_stress_request_has_729_cells_and_finite_output():
    result = evaluate_stress(StressRequest(grid_points=9), BENCHMARK)
    assert result["cell_count"] == 729
    assert len(result["cells"]) == 729
    assert sum(row["win_count"] for row in result["options"]) == 729
    assert sum(row["win_coverage"] for row in result["options"]) == pytest.approx(1)
    assert "NOT a probability" in result["interpretation"]
    json.dumps(result, allow_nan=False)


def test_duplicate_axis_values_are_not_counted_as_independent_cells():
    result = evaluate_stress(StressRequest(value_low=1000, value_high=1000,
                                         realization_low=.35, realization_high=.35,
                                         contract_low=5_000_000, contract_high=5_000_000,
                                         grid_points=9), BENCHMARK)
    assert result["cell_count"] == 1
    for row in result["options"]:
        assert row["worst_npv_usd"] == row["base_npv_usd"] == row["best_npv_usd"]


def test_grid_cells_match_economic_model_and_do_not_mutate_evidence():
    evidence = copy.deepcopy(BENCHMARK)
    request = StressRequest(grid_points=3)
    result = evaluate_stress(request, evidence)
    for cell in result["cells"]:
        scenario = Scenario(value_per_productive_hour=cell["value_per_hour"],
                            value_realization=cell["realization"], contract_total=cell["contract_total"])
        direct = evaluate_economics(scenario, BENCHMARK, include_sensitivity=False)
        assert cell["npv_by_option"] == {row["id"]: row["customer_npv_usd"] for row in direct["options"]}
        assert cell["best_npv_usd"] == max(cell["npv_by_option"].values())
    assert evidence == BENCHMARK
    assert result == evaluate_stress(request, BENCHMARK)


def test_coverage_handles_ties_and_includes_the_no_purchase_option():
    request = StressRequest(scenario=Scenario(demand_hours_per_day=0, control_engineers=0),
                            value_low=0, value_high=0, realization_low=0, realization_high=0,
                            contract_low=0, contract_high=0)
    result = evaluate_stress(request, BENCHMARK)
    assert result["cells"][0]["winner"] == "baseline"
    assert option(result, "baseline")["win_coverage"] == 1
    assert option(result, "pulse")["win_coverage"] == 0
    assert option(result, "pulse")["positive_npv_coverage"] == 0


def test_worst_case_and_regret_are_distinct_and_calculated_from_same_grid():
    result = evaluate_stress(StressRequest(), BENCHMARK)
    assert result["recommendation"]["maximin_option"] == "baseline"
    assert result["recommendation"]["minimax_regret_option"] == "pulse"
    for row in result["options"]:
        expected = max(cell["best_npv_usd"] - cell["npv_by_option"][row["id"]] for cell in result["cells"])
        assert row["max_regret_usd"] == expected
    assert "baseline" in option(result, "calibration")["dominated_by"]


def test_base_outside_requested_ranges_is_explicit():
    result = evaluate_stress(StressRequest(value_low=0, value_high=1,
                                         realization_low=0, realization_high=.01), BENCHMARK)
    assert result["base_inside_ranges"] is False
    assert option(result)["base_npv_usd"] > option(result)["best_npv_usd"]
    assert any("outside" in warning for warning in result["warnings"])


def test_more_value_and_lower_price_improve_npv_when_physical_gain_is_positive():
    result = evaluate_stress(StressRequest(grid_points=3), BENCHMARK)
    def find(value, realization, contract):
        return next(cell["npv_by_option"]["pulse"] for cell in result["cells"]
                    if cell["value_per_hour"] == value and cell["realization"] == realization
                    and cell["contract_total"] == contract)
    assert find(2000, .75, 3_000_000) > find(250, .75, 3_000_000)
    assert find(2000, .75, 3_000_000) > find(2000, .1, 3_000_000)
    assert find(2000, .75, 3_000_000) > find(2000, .75, 7_000_000)


def test_sampling_bounds_are_separate_and_cover_base_point():
    result = evaluate_stress(StressRequest(grid_points=3), BENCHMARK)
    sampling = result["sampling_envelope"]
    assert sampling["available"] is True
    for bound in sampling["options"]:
        point = option(result, bound["id"])
        assert bound["base_low_npv_usd"] <= point["base_npv_usd"] <= bound["base_high_npv_usd"]
        assert bound["stress_low_npv_usd"] <= point["worst_npv_usd"]
        assert bound["stress_high_npv_usd"] >= point["best_npv_usd"]
    assert "not a confidence interval for commercial" in sampling["scope"]


def test_large_ratio_bound_does_not_create_invalid_probability_or_fake_counts():
    evidence = {**BENCHMARK, "throughput_ratio_ci_high": 100}
    result = evaluate_stress(StressRequest(grid_points=3), evidence)
    sampling = result["sampling_envelope"]
    assert sampling["available"] is True
    assert sampling["ratio_high"] == 100
    assert all("p_success" not in row and "successes" not in row for row in sampling["options"])
    json.dumps(result, allow_nan=False)


def test_absent_sampling_interval_is_not_invented():
    evidence = {"baseline": {"p_success": .1}, "pulse": {"p_success": .3}}
    result = evaluate_stress(StressRequest(grid_points=3), evidence)
    assert result["sampling_envelope"]["available"] is False
    assert result["sampling_envelope"]["options"] == []


def test_zero_ratio_lower_bound_is_explicitly_unbounded_for_fixed_output():
    evidence = {**BENCHMARK, "throughput_ratio_ci_low": 0}
    result = evaluate_stress(StressRequest(scenario=Scenario(value_mode="fixed_output_savings"), grid_points=3), evidence)
    assert result["sampling_envelope"]["available"] is False
    assert result["sampling_envelope"]["lower_bound_unbounded"] is True


@pytest.mark.parametrize("changes", [{"demand_hours_per_day": 0}, {"rollout_months": 120}])
def test_zero_ratio_bound_does_not_invent_monetary_exposure_without_any_value(changes):
    evidence = {**BENCHMARK, "throughput_ratio_ci_low": 0}
    scenario = Scenario(value_mode="fixed_output_savings", **changes)
    result = evaluate_stress(StressRequest(scenario=scenario, grid_points=3), evidence)
    envelope = result["sampling_envelope"]
    assert envelope["available"] and envelope["zero_bound_value_neutral"]
    for row in envelope["options"]:
        assert row["base_low_npv_usd"] == row["base_high_npv_usd"]


@pytest.mark.parametrize("bounds", [
    {"throughput_ratio_ci_low": 4, "throughput_ratio_ci_high": 3},
    {"throughput_ratio_ci_low": -1}, {"throughput_ratio_ci_high": 1},
    {"throughput_ratio_ci_high": float("inf")},
    {"throughput_ratio_ci_low": None, "throughput_ratio_ci_high": False},
])
def test_invalid_sampling_bounds_cannot_generate_a_financial_envelope(bounds):
    with pytest.raises(ValueError):
        evaluate_stress(StressRequest(grid_points=3), {**BENCHMARK, **bounds})


@pytest.mark.parametrize("function,tool_request", [
    (evaluate_stress, StressRequest()), (evaluate_pricing, PricingRequest()),
])
def test_stale_physical_evidence_is_rejected(function, tool_request):
    evidence = copy.deepcopy(BENCHMARK)
    evidence["baseline"]["n_qubits"] = 4
    with pytest.raises(ValueError, match="does not match"):
        function(tool_request, evidence)


@pytest.mark.parametrize("function,model", [(evaluate_stress, StressRequest), (evaluate_pricing, PricingRequest)])
def test_old_cycle_timing_cannot_reuse_a_stale_ratio_interval(function, model):
    evidence = {**BENCHMARK, "baseline_cycle_us": 106, "pulse_cycle_us": 108.4}
    function(model(), evidence)
    changed = Scenario(fixed_overhead_us=200)
    with pytest.raises(ValueError, match="cycle.*does not match"):
        function(model(scenario=changed), evidence)


@pytest.mark.parametrize("value", [None, False, "106", float("nan"), float("inf")])
def test_supplied_cycle_metadata_must_be_finite_numeric(value):
    with pytest.raises(ValueError, match="cycle.*does not match"):
        evaluate_stress(StressRequest(), {**BENCHMARK, "baseline_cycle_us": value})


def test_nominal_cost_floor_uses_revenue_margin_not_markup():
    result = evaluate_pricing(PricingRequest(), BENCHMARK)
    assert result["nominal_vendor_cost_usd"] == 950_000
    assert result["nominal_margin_floor_usd"] == 2_375_000
    assert result["vendor_floor_usd"] == 2_375_000
    assert result["nominal_margin_floor_usd"] != 950_000 * 1.6


def test_deferred_revenue_cannot_hide_a_negative_vendor_npv():
    scenario = Scenario(contract_years=2, discount_rate=.20)
    result = evaluate_pricing(PricingRequest(scenario=scenario, target_gross_margin=0), BENCHMARK)
    assert result["nominal_margin_floor_usd"] == 800_000
    expected_pv_cost = 500_000 + 150_000 / 1.2 + 150_000 / 1.2**2
    assert result["vendor_cost_pv_usd"] == pytest.approx(expected_pv_cost)
    expected_nominal_break_even = expected_pv_cost / ((1 / 1.2 + 1 / 1.2**2) / 2)
    assert result["discounted_break_even_floor_usd"] == pytest.approx(expected_nominal_break_even)
    assert result["vendor_floor_usd"] > result["nominal_margin_floor_usd"]
    assert result["vendor_npv_at_floor_usd"] == pytest.approx(0, abs=1e-8)


def test_share_policy_can_fail_even_when_full_joint_surplus_exists():
    result = evaluate_pricing(PricingRequest(customer_value_share=.3), BENCHMARK)
    pulse = option(result)
    assert pulse["full_surplus_feasible"] is True
    assert pulse["share_policy_feasible"] is False
    assert pulse["recommended_price_usd"] is None
    assert pulse["gap_to_share_target_usd"] > 0
    assert pulse["status"] == "share_target_below_vendor_floor"


def test_feasible_price_meets_margin_and_both_party_npvs():
    req = PricingRequest(customer_value_share=.5)
    result = evaluate_pricing(req, BENCHMARK)
    pulse = option(result)
    assert result["recommendation"]["deal_feasible"] is True
    assert pulse["share_policy_feasible"] is True
    assert pulse["recommended_price_usd"] == pulse["customer_share_target_usd"]
    assert pulse["margin_at_share_target"] >= req.target_gross_margin
    assert pulse["customer_npv_at_share_target_usd"] >= 0
    assert pulse["vendor_npv_at_share_target_usd"] >= 0
    interval = pulse["share_policy_interval"]
    assert interval["min_usd"] <= pulse["recommended_price_usd"] <= interval["max_usd"]


def test_value_share_is_converted_on_same_nominal_payment_schedule():
    req = PricingRequest(customer_value_share=.5)
    result = evaluate_pricing(req, BENCHMARK)
    direct = evaluate_economics(req.scenario, BENCHMARK, include_sensitivity=False)
    gross_pv = option(direct)["gross_value_pv_usd"]
    pulse = option(result)
    assert pulse["customer_share_target_usd"] * result["fee_pv_factor"] == pytest.approx(.5 * gross_pv)
    assert pulse["customer_npv_at_share_target_usd"] == pytest.approx(.5 * gross_pv)


def test_customer_ceiling_not_nominal_profit_determines_quote_acceptability():
    result = evaluate_pricing(PricingRequest(scenario=Scenario(value_mode="fixed_output_savings")), BENCHMARK)
    pulse = option(result)
    assert pulse["quote_vendor_margin"] > .6
    assert pulse["quote_customer_npv_usd"] < 0
    assert pulse["quote_is_jointly_feasible"] is False


def test_zero_cost_is_allowed_but_zero_price_does_not_have_a_gross_margin():
    result = evaluate_pricing(PricingRequest(implementation_cost=0, annual_support_cost=0,
                                            customer_value_share=0), BENCHMARK)
    pulse = option(result)
    assert result["nominal_vendor_cost_usd"] == result["vendor_floor_usd"] == 0
    assert pulse["margin_at_share_target"] is None
    assert pulse["share_policy_feasible"] is False
    assert pulse["recommended_price_usd"] is None
    json.dumps(result, allow_nan=False)


def test_zero_customer_ceiling_cannot_be_called_a_feasible_contract_even_if_costs_zero():
    result = evaluate_pricing(PricingRequest(scenario=Scenario(demand_hours_per_day=0),
                                            implementation_cost=0, annual_support_cost=0), BENCHMARK)
    assert result["recommendation"]["deal_feasible"] is False
    for row in result["options"]:
        assert row["customer_zero_npv_cap_usd"] == 0
        assert row["full_surplus_feasible"] is False
        assert row["recommended_price_usd"] is None
        assert row["minimum_value_share"] is None


def test_zero_quote_cannot_meet_a_margin_target_even_when_vendor_cost_is_zero():
    result = evaluate_pricing(PricingRequest(scenario=Scenario(contract_total=0),
                                           implementation_cost=0, annual_support_cost=0), BENCHMARK)
    assert option(result)["quote_vendor_margin"] is None
    assert option(result)["quote_is_jointly_feasible"] is False


def test_controls_vendor_cost_is_distinct_from_customer_integration_cost():
    req = PricingRequest(scenario=Scenario(value_per_productive_hour=0, replacement_due=True),
                         implementation_cost=100_000, annual_support_cost=10_000)
    result = evaluate_pricing(req, BENCHMARK)
    assert result["nominal_vendor_cost_usd"] == 130_000
    assert result["recommendation"]["option_id"] == "control"
    assert option(result, "control")["share_policy_feasible"] is True


def test_more_customer_value_improves_cap_while_vendor_cost_floor_stays_fixed():
    low = evaluate_pricing(PricingRequest(scenario=Scenario(value_per_productive_hour=500)), BENCHMARK)
    high = evaluate_pricing(PricingRequest(scenario=Scenario(value_per_productive_hour=2000)), BENCHMARK)
    assert high["vendor_floor_usd"] == low["vendor_floor_usd"]
    assert option(high)["customer_zero_npv_cap_usd"] > option(low)["customer_zero_npv_cap_usd"]
    assert option(high)["minimum_value_share"] < option(low)["minimum_value_share"]


def test_more_cost_or_higher_margin_cannot_reduce_required_price():
    base = evaluate_pricing(PricingRequest(), BENCHMARK)
    cost = evaluate_pricing(PricingRequest(implementation_cost=1_000_000), BENCHMARK)
    margin = evaluate_pricing(PricingRequest(target_gross_margin=.8), BENCHMARK)
    assert cost["vendor_floor_usd"] >= base["vendor_floor_usd"]
    assert margin["vendor_floor_usd"] >= base["vendor_floor_usd"]


def test_subnormal_share_cannot_leak_infinity_into_json():
    result = evaluate_pricing(PricingRequest(customer_value_share=5e-324), BENCHMARK)
    assert option(result)["recommended_price_usd"] is None
    json.dumps(result, allow_nan=False)


def test_request_and_evidence_are_unchanged_after_pricing():
    req = PricingRequest()
    req_before = req.model_dump()
    evidence = copy.deepcopy(BENCHMARK)
    first = evaluate_pricing(req, evidence)
    assert req.model_dump() == req_before
    assert evidence == BENCHMARK
    assert first == evaluate_pricing(req, evidence)
