from __future__ import annotations

import csv
import hashlib
import json
from pathlib import Path

import pytest

from qubityield.cli import main
from qubityield.portable import (
    compare_scenarios,
    read_json,
    safe_csv_cell,
    verify_manifest,
    write_comparison_csv,
)


@pytest.mark.parametrize("raw", [
    '{"x": NaN}', '{"x": Infinity}', '{"x": -Infinity}', '{"x": 1e400}',
    '{"x": 1, "x": 2}', '{"a":{"x":1,"x":2}}', '[' * 2000 + ']' * 2000,
])
def test_rejects_ambiguous_or_nonfinite_json(tmp_path, raw):
    path = tmp_path / "input.json"
    path.write_text(raw)
    with pytest.raises(ValueError):
        read_json(path)


def test_json_byte_limit_and_encoding(tmp_path):
    path = tmp_path / "input.json"
    path.write_bytes(b'\xef\xbb\xbf{"name":"value"}')
    assert read_json(path) == {"name": "value"}
    with pytest.raises(ValueError, match="input limit"):
        read_json(path, max_bytes=4)
    path.write_bytes(b'\xff')
    with pytest.raises(ValueError, match="UTF-8"):
        read_json(path)


@pytest.mark.parametrize("values", [[], {}, [None], [{"name": " ", "scenario": {}}],
    [{"name": "same", "scenario": {}}, {"name": " same ", "scenario": {}}],
    [{"name": "a", "scenario": {}, "unexpected": True}],
    [{"name": str(index), "scenario": {}} for index in range(17)],
])
def test_bad_batch_fails_before_evaluation(monkeypatch, values):
    def forbidden(*args, **kwargs):
        pytest.fail("Invalid batch started a computation")
    monkeypatch.setattr("qubityield.portable.evaluate", forbidden)
    with pytest.raises(ValueError):
        compare_scenarios(values)


def test_comparison_preserves_inputs_and_valuation_reversal(tmp_path):
    result = compare_scenarios([
        {"name": "Additional output", "scenario": {"shots": 512}},
        {"name": "Same output", "scenario": {"shots": 512, "value_mode": "fixed_output_savings"}},
    ])
    first, second = result["comparison"]
    assert result["count"] == 2
    assert first["physical_fingerprint"] == second["physical_fingerprint"]
    assert first["scenario_sha256"] != second["scenario_sha256"]
    assert first["pulse_npv_usd"] > second["pulse_npv_usd"]
    assert second["best_option_after_fees"] == "baseline"
    assert result["analyses"][1]["result"]["scenario"]["value_mode"] == "fixed_output_savings"
    # CSV must preserve all input names and financial signs without formula evaluation.
    result["comparison"][0]["name"] = '=HYPERLINK("https://example.com")'
    path = tmp_path / "comparison.csv"
    write_comparison_csv(result, path)
    with path.open() as source:
        rows = list(csv.DictReader(source))
    assert rows[0]["name"].startswith("'=HYPERLINK")
    assert float(rows[1]["pulse_npv_usd"]) < 0


@pytest.mark.parametrize("value", ["=1+1", " +SUM(A1)", "-2+3", "@cmd", "\t=cmd"])
def test_csv_text_formulas_inert(value):
    assert safe_csv_cell(value) == "'" + value
    assert safe_csv_cell(-123.0) == -123.0
    assert safe_csv_cell("normal text") == "normal text"


def _manifest(name="evidence.txt", data=b"evidence"):
    return {"schema_version": 1, "algorithm": "SHA-256", "files": {
        name: {"sha256": hashlib.sha256(data).hexdigest(), "bytes": len(data)}}}


def test_manifest_detects_tampering_and_missing_files(tmp_path):
    path = tmp_path / "evidence.txt"
    path.write_bytes(b"evidence")
    assert verify_manifest(_manifest(), tmp_path)["valid"]
    path.write_bytes(b"Evidence")
    report = verify_manifest(_manifest(), tmp_path)
    assert not report["valid"]
    assert report["verified"] == 0
    path.unlink()
    assert "missing" in verify_manifest(_manifest(), tmp_path)["failures"][0]["reason"]


@pytest.mark.parametrize("name", ["../outside", "/tmp/outside", "a/../../outside", "a\\b", "./a", "a//b", ""])
def test_manifest_rejects_unsafe_paths(tmp_path, name):
    with pytest.raises(ValueError):
        verify_manifest(_manifest(name=name), tmp_path)


def test_manifest_rejects_symlink_outside_root(tmp_path):
    root = tmp_path / "project"
    root.mkdir()
    outside = tmp_path / "outside"
    outside.write_bytes(b"evidence")
    (root / "evidence.txt").symlink_to(outside)
    with pytest.raises(ValueError, match="leaves the project"):
        verify_manifest(_manifest(), root)


def test_manifest_symlink_loop_is_a_validation_error(tmp_path, capsys):
    (tmp_path / "loop").symlink_to("loop")
    path = tmp_path / "manifest.json"
    path.write_text(json.dumps(_manifest(name="loop")))
    with pytest.raises(ValueError, match="resolve path safely"):
        verify_manifest(_manifest(name="loop"), tmp_path)
    assert main(["verify-manifest", "--manifest", str(path), "--root", str(tmp_path)]) == 2
    assert "Traceback" not in capsys.readouterr().err


@pytest.mark.parametrize("alias", ["same", "symlink", "hardlink"])
def test_comparison_rejects_output_aliases_before_computing(tmp_path, monkeypatch, alias):
    def forbidden(*args, **kwargs):
        pytest.fail("Output alias was not rejected before computing")
    monkeypatch.setattr("qubityield.portable.evaluate", forbidden)
    source, output, table = tmp_path / "input.json", tmp_path / "output.json", tmp_path / "output.csv"
    source.write_text('[{"name":"Case","scenario":{}}]')
    output.write_text("preserve this")
    if alias == "same":
        table = output
    elif alias == "symlink":
        table.symlink_to(output)
    else:
        table.hardlink_to(output)
    assert main(["compare", "--scenarios", str(source), "--output", str(output), "--csv", str(table)]) == 2
    assert output.read_text() == "preserve this"


def test_cli_reports_invalid_input_without_traceback(tmp_path, capsys):
    path = tmp_path / "invalid.json"
    path.write_text("[]")
    assert main(["evaluate", "--scenario", str(path)]) == 2
    captured = capsys.readouterr()
    assert "JSON object" in captured.err
    assert "Traceback" not in captured.err


def test_cli_comparison_and_manifest_exit_codes(tmp_path, capsys):
    inputs = tmp_path / "batch.json"
    output = tmp_path / "result.json"
    csv_path = tmp_path / "result.csv"
    inputs.write_text(json.dumps([{"name": "Base", "scenario": {"shots": 256}}]))
    assert main(["compare", "--scenarios", str(inputs), "--output", str(output), "--csv", str(csv_path)]) == 0
    assert json.loads(output.read_text())["count"] == 1
    manifest = tmp_path / "manifest.json"
    manifest.write_text(json.dumps(_manifest("result.csv", csv_path.read_bytes())))
    assert main(["verify-manifest", "--manifest", str(manifest), "--root", str(tmp_path)]) == 0
    csv_path.write_text("changed")
    assert main(["verify-manifest", "--manifest", str(manifest), "--root", str(tmp_path)]) == 1


@pytest.mark.parametrize("command,kind", [("stress", "stress_envelope"), ("pricing", "pricing_feasibility")])
def test_decision_cli_exports_matching_evidence(tmp_path: Path, command: str, kind: str):
    request = {"scenario": {"shots": 256}}
    if command == "stress":
        request.update({"grid_points": 3, "value_low": 1000, "value_high": 1000,
                        "realization_low": .35, "realization_high": .35,
                        "contract_low": 5_000_000, "contract_high": 5_000_000})
    source, output = tmp_path / "request.json", tmp_path / "output.json"
    source.write_text(json.dumps(request))
    assert main([command, "--request", str(source), "--output", str(output)]) == 0
    result = json.loads(output.read_text())
    assert result["kind"] == kind
    assert result["evidence"]["shots"] == 256
    assert result["scenario"]["shots"] == result["benchmark"]["baseline"]["shots"]
    assert result["physical_fingerprint"] == result["evidence"]["physical_fingerprint"]
