"""Cross-layer regressions from adversarial review of provenance and reports."""

from datetime import datetime
import json
from pathlib import Path
import tomllib

from fastapi.testclient import TestClient
import pytest

from qubityield import analysis, api
from qubityield.economics import evaluate_economics
from qubityield.models import Scenario
from qubityield.reporting import memo_sections


def test_notebook_renders_its_own_result_without_default_artifacts(tmp_path, monkeypatch):
    nbformat = pytest.importorskip("nbformat")
    display_module = pytest.importorskip("IPython.display")
    from pathlib import Path
    from qubityield import reporting

    result = analysis.evaluate(Scenario(shots=256, value_mode="fixed_output_savings"))
    notebook_path = tmp_path / "custom" / "analysis.ipynb"
    reporting.write_notebook(result, notebook_path)
    notebook = nbformat.read(notebook_path, as_version=4)
    figure_cell = next(cell for cell in notebook.cells if cell.cell_type == "code" and "figure_path" in cell.source)
    seen, displayed, temporary_paths = [], [], []
    original_plot = reporting.plot_decision

    def render(supplied_result, path):
        seen.append(supplied_result)
        temporary_paths.append(path)
        original_plot(supplied_result, path)

    monkeypatch.setattr(reporting, "plot_decision", render)
    monkeypatch.setattr(display_module, "display", displayed.append)
    # There is deliberately no default artifacts directory under this root.
    exec(figure_cell.source, {"Path": Path, "root": tmp_path, "result": result})
    assert seen == [result]
    assert len(displayed) == 1 and len(displayed[0].data) > 10_000
    assert all(not path.exists() for path in temporary_paths)


def compact_scenario(**changes):
    return Scenario(n_qubits=4, layers=6, shots=256, **changes)


def memo_result(scenario=None, pulse_success=0.4):
    scenario = scenario or Scenario()
    evidence = {
        "baseline": {"p_success": .2, "successes": 200, "shots": 1000, "gate_count": scenario.n_qubits * scenario.layers // 2},
        "pulse": {"p_success": pulse_success, "successes": int(1000 * pulse_success), "shots": 1000, "gate_count": scenario.n_qubits * scenario.layers // 2},
    }
    return evaluate_economics(scenario, evidence, include_sensitivity=False)


def test_economic_edits_reuse_the_same_physical_cache_key():
    first = compact_scenario()
    second = compact_scenario(value_mode="fixed_output_savings", value_realization=.1, demand_hours_per_day=20)
    assert analysis.physical_key(first) == analysis.physical_key(second)


@pytest.mark.parametrize("key,value", [
    ("n_qubits", 6), ("layers", 8), ("shots", 512), ("seed", 17),
    ("baseline_gate_error", .02), ("pulse_gate_error", .004),
    ("baseline_gate_ns", 320), ("pulse_duration_increase", .6),
    ("t1_us", 130), ("t2_us", 110), ("noise_mode", "control_only"),
    ("readout_error", .015), ("fixed_overhead_us", 250),
])
def test_every_physical_or_timing_input_invalidates_matching_cache_key(key, value):
    first = compact_scenario()
    second = Scenario.model_validate({**first.model_dump(), key: value})
    assert analysis.physical_key(first) != analysis.physical_key(second)


def test_mutating_a_response_cannot_poison_cached_evidence():
    scenario = compact_scenario()
    first = analysis.evaluate(scenario, include_depth=False)
    original = first["benchmark"]["baseline"]["successes"]
    first["benchmark"]["baseline"]["successes"] = -999
    first["benchmark"]["baseline"]["p_success"] = .000001
    first["options"][0]["customer_npv_usd"] = 100_000_000
    second = analysis.evaluate(scenario, include_depth=False)
    assert second["benchmark"]["baseline"]["successes"] == original
    assert second["options"][0]["customer_npv_usd"] == 0


def test_provenance_is_bound_to_inputs_and_timestamp_is_timezone_aware():
    scenario = compact_scenario()
    result = analysis.evaluate(scenario, include_depth=False)
    evidence = result["evidence"]
    assert evidence["scenario_sha256"] == analysis.canonical_hash(result["scenario"])
    assert evidence["physical_fingerprint"] == result["benchmark"]["physical_fingerprint"]
    assert evidence["hardware_executed"] is False
    assert datetime.fromisoformat(evidence["generated_at"]).utcoffset().total_seconds() == 0
    changed = analysis.evaluate(compact_scenario(value_mode="fixed_output_savings"), include_depth=False)
    assert changed["evidence"]["experiment_id"] != evidence["experiment_id"]
    assert changed["benchmark"]["baseline"]["successes"] == result["benchmark"]["baseline"]["successes"]
    json.dumps(result, allow_nan=False)


def test_sampler_ratio_bounds_contain_the_reported_point_estimate():
    result = analysis.evaluate(compact_scenario(), include_depth=False)
    benchmark = result["benchmark"]
    assert benchmark["throughput_ratio_ci_low"] <= benchmark["throughput_ratio"]
    assert benchmark["throughput_ratio_ci_high"] >= benchmark["throughput_ratio"]


def test_depth_sweep_contains_the_selected_high_depth_circuit():
    result = analysis.evaluate(Scenario(n_qubits=2, layers=80, shots=256))
    assert 80 in {row["layers"] for row in result["depth_curve"]}
    assert 60 in {row["layers"] for row in result["depth_curve"]}


def test_zero_demand_memo_does_not_recommend_pulse_or_invent_case_bookings():
    result = memo_result(Scenario(demand_hours_per_day=0))
    sections = dict(memo_sections(result))
    assert result["recommendation"]["id"] == "baseline"
    assert "Keep the current system" in sections["Decision"]
    assert "11.2 hours/day" not in sections["Initial hypothesis and what changed"]
    assert "0 booked hours/day" in sections["Initial hypothesis and what changed"]


def test_calibration_winning_memo_updates_hypothesis_fee_horizon_and_inputs():
    scenario = Scenario(demand_hours_per_day=24, contract_years=4, contract_total=2_000_000,
                        ai_speed_interpretation="time_reduction", scale_realization=1,
                        monetizable_overlap=1)
    result = memo_result(scenario, pulse_success=.2)
    sections = dict(memo_sections(result))
    assert result["recommendation"]["id"] == "calibration"
    assert "ai calibration pilot" in sections["Decision"]
    assert "$2.00M" in sections["Decision"]
    assert "4 years" in sections["Decision"]
    assert "hypothesis survived" in sections["Initial hypothesis and what changed"]
    assert "70% less time" in sections["Initial hypothesis and what changed"]
    assert "24 hours/day of demand" in sections["Initial hypothesis and what changed"]
    assert "11.2" not in sections["Initial hypothesis and what changed"]


def test_controls_memo_uses_actual_integration_inputs_not_hardcoded_150k():
    result = memo_result(Scenario(replacement_due=True, value_per_productive_hour=0,
                                 control_cost=1_000_000, control_saving=.5,
                                 control_engineers=1, control_integration_months=3,
                                 engineer_annual_cost=200_000))
    sections = dict(memo_sections(result))
    assert result["recommendation"]["id"] == "control"
    assert "lower-cost controls pilot" in sections["Decision"]
    assert "$450,000" in sections["Price and alternatives"]
    assert "$50,000" in sections["Price and alternatives"]
    assert "$1.85M" not in sections["Price and alternatives"]


def test_memo_states_selected_valuation_and_noise_interpretation():
    result = memo_result(Scenario(value_mode="fixed_output_savings", noise_mode="control_only"))
    sections = dict(memo_sections(result))
    assert "B*(1-1/R)" in sections["Price and alternatives"]
    assert "selected control-only interpretation" in sections["Commercial terms and limitations"]
    assert "already includes gate-time decoherence" not in sections["Commercial terms and limitations"]


def test_notebook_dependencies_are_installable_from_documented_research_extra():
    project = Path(__file__).resolve().parents[1]
    dependencies = tomllib.loads((project / "pyproject.toml").read_text())["project"]["optional-dependencies"]["research"]
    assert any(requirement.startswith("pandas") for requirement in dependencies)
    assert any(requirement.startswith("ipykernel") for requirement in dependencies)


def test_api_bounds_and_unknown_inputs_are_checked_before_simulation(monkeypatch):
    calls = []

    def fake_evaluate(scenario, **kwargs):
        calls.append(scenario)
        return {"scenario": scenario.model_dump(), "hardware_executed": False}

    monkeypatch.setattr(api, "evaluate", fake_evaluate)
    client = TestClient(api.create_app())
    good = client.post("/api/evaluate", json={"value_mode": "fixed_output_savings"})
    assert good.status_code == 200
    assert good.json()["scenario"]["value_mode"] == "fixed_output_savings"
    for body in ({"t2_us": 1000}, {"n_qubits": 3}, {"shots": 1_000_000}, {"value_realization": 1.5}, {"typo": 1}):
        assert client.post("/api/evaluate", json=body).status_code == 422
    for body in ({"t1_us": .0001, "t2_us": .0001}, {"baseline_gate_ns": 900_000}, {"n_qubits": 100, "layers": 100, "shots": 65_536}):
        assert client.post("/api/evaluate", json=body).status_code == 422
    assert len(calls) == 1
    assert client.get("/api/not-a-route").status_code == 404


def test_oversized_and_chunked_bodies_are_bounded_before_model_parsing():
    client = TestClient(api.create_app())
    giant = '{"extra":"' + "x" * 70_000 + '"}'
    assert client.post("/api/evaluate", content=giant, headers={"Content-Type": "application/json"}).status_code == 413
    chunks = (part for part in [b'{"extra":"', b"x" * 40_000, b"x" * 40_000, b'"}'])
    assert client.post("/api/evaluate", content=chunks, headers={"Content-Type": "application/json"}).status_code == 413


def test_invalid_nonfinite_json_cannot_crash_error_response():
    client = TestClient(api.create_app(), raise_server_exceptions=False)
    for literal in ("NaN", "Infinity", "-Infinity"):
        response = client.post("/api/evaluate", content='{"value_realization":' + literal + '}', headers={"Content-Type": "application/json"})
        assert response.status_code in (400, 422)


def test_busy_engine_rejects_excess_work_without_queuing_unbounded_jobs():
    client = TestClient(api.create_app())
    assert api._simulation_slots.acquire(blocking=False)
    assert api._simulation_slots.acquire(blocking=False)
    try:
        response = client.post("/api/evaluate", json={})
        assert response.status_code == 429
        assert response.headers["Retry-After"] == "2"
    finally:
        api._simulation_slots.release()
        api._simulation_slots.release()


def test_figure_exports_both_png_and_svg_without_suffix_errors(tmp_path):
    from qubityield.reporting import plot_decision

    result = analysis.evaluate(compact_scenario())
    path = tmp_path / "decision.png"
    plot_decision(result, path)
    assert path.read_bytes().startswith(b"\x89PNG")
    assert "<svg" in path.with_suffix(".svg").read_text()
