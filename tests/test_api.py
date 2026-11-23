"""Public API contracts and concrete boundary failures."""

import json
import hashlib
import sqlite3
import threading
import time
from uuid import uuid4

import pytest

from fastapi.testclient import TestClient

from qubityield.api import create_app


@pytest.fixture(autouse=True)
def isolated_ledger(monkeypatch, tmp_path):
    monkeypatch.setenv("QUBITYIELD_DATA_DIR", str(tmp_path / "ledger"))


def completed_job(client, job_id, timeout=8):
    end = time.monotonic() + timeout
    while time.monotonic() < end:
        response = client.get(f"/api/jobs/{job_id}")
        assert response.status_code == 200
        detail = response.json()
        if detail["status"] in {"completed", "failed", "cancelled"}:
            return detail
        time.sleep(0.01)
    raise AssertionError("Background experiment did not finish")


def test_default_request_returns_real_evidence():
    with TestClient(create_app()) as client:
        result = client.post("/api/evaluate", json={})
        assert result.status_code == 200
        body = result.json()
        assert body["benchmark"]["baseline"]["gate_count"] == 200
        assert body["evidence"]["hardware_executed"] is False
        assert body["recommendation"]["id"] == "pulse"
        assert len(body["depth_curve"]) >= 5


def test_unknown_fields_and_nonphysical_inputs_rejected():
    with TestClient(create_app()) as client:
        for payload in (
            {"hidden_multiplier": 10},
            {"n_qubits": 21},
            {"t1_us": 10, "t2_us": 30},
            {"shots": 1000000},
        ):
            assert client.post("/api/evaluate", json=payload).status_code == 422


def test_nonstandard_json_is_safe_client_error():
    with TestClient(create_app()) as client:
        for value in ("NaN", "Infinity", "-Infinity"):
            response = client.post(
                "/api/evaluate",
                content='{"value_per_productive_hour":' + value + "}",
                headers={"Content-Type": "application/json"},
            )
            assert response.status_code == 400
            assert "finite-number JSON" in response.json()["detail"]


def test_oversized_body_is_rejected_before_parsing():
    with TestClient(create_app()) as client:
        response = client.post(
            "/api/evaluate",
            content=json.dumps({"large": "x" * 70000}),
            headers={"Content-Type": "application/json"},
        )
        assert response.status_code == 413


def test_financial_change_reuses_matching_physics_but_changes_value():
    with TestClient(create_app()) as client:
        default = client.post("/api/evaluate", json={}).json()
        changed = client.post("/api/evaluate", json={"value_per_productive_hour": 0}).json()
        assert (
            default["evidence"]["physical_fingerprint"]
            == changed["evidence"]["physical_fingerprint"]
        )
        assert default["evidence"]["scenario_sha256"] != changed["evidence"]["scenario_sha256"]
        assert changed["recommendation"]["best_at_current_quote"] == "baseline"


def test_health_never_implies_a_real_hardware_connection():
    with TestClient(create_app()) as client:
        assert client.get("/api/health").json()["hardware_connected"] is False


@pytest.mark.parametrize("content_type", [None, "application/json", "application/vnd.api+json"])
@pytest.mark.parametrize("number", ["NaN", "Infinity", "1e400", "-1e400"])
def test_nonfinite_json_is_rejected_for_every_json_media_type(content_type, number):
    headers = {} if content_type is None else {"Content-Type": content_type}
    with TestClient(create_app()) as client:
        response = client.post(
            "/api/evaluate", content='{"discount_rate":' + number + "}", headers=headers
        )
        assert response.status_code == 400
        assert "finite-number JSON" in response.json()["detail"]


def test_deeply_nested_json_is_a_client_error_not_recursion_crash():
    with TestClient(create_app()) as client:
        response = client.post(
            "/api/evaluate",
            content="[" * 2000 + "0" + "]" * 2000,
            headers={"Content-Type": "application/json"},
        )
        assert response.status_code == 400


def test_source_fingerprint_uses_executing_package_when_resource_root_changes(
    monkeypatch, tmp_path
):
    from pathlib import Path

    import qubityield.analysis as analysis
    from qubityield.models import Scenario

    monkeypatch.setattr(analysis, "project_root", lambda: tmp_path)
    result = analysis.evaluate(Scenario(), include_depth=False)
    expected = hashlib.sha256()
    for source in sorted(Path(analysis.__file__).resolve().parent.glob("*.py")):
        expected.update(source.name.encode())
        expected.update(source.read_bytes())
    assert result["evidence"]["source_code_sha256"] == expected.hexdigest()
    assert result["evidence"]["source_code_sha256"] != hashlib.sha256().hexdigest()


def test_async_experiment_metadata_and_deletion_round_trip(tmp_path):
    with TestClient(create_app(data_dir=tmp_path)) as client:
        response = client.post(
            "/api/jobs",
            json={
                "label": "First 📊",
                "scenario": {"n_qubits": 2, "layers": 2, "shots": 256},
                "include_depth": False,
            },
        )
        assert response.status_code == 202
        detail = completed_job(client, response.json()["id"])
        assert detail["status"] == "completed", detail
        assert detail["result"]["depth_curve"] == []
        experiment_id = detail["experiment_id"]
        listed = client.get("/api/experiments").json()["experiments"]
        assert len(listed) == 1 and listed[0]["id"] == experiment_id
        assert "result" not in listed[0]
        patched = client.patch(
            f"/api/experiments/{experiment_id}",
            json={"label": " Renamed ", "notes": "review\nagain", "tags": ["reviewed"]},
        )
        assert patched.status_code == 200
        assert patched.json()["label"] == "Renamed"
    with TestClient(create_app(data_dir=tmp_path)) as client:
        saved = client.get(f"/api/experiments/{experiment_id}")
        assert saved.status_code == 200
        assert saved.json()["notes"] == "review\nagain"
        assert saved.json()["result"] == detail["result"]
        deleted = client.delete(f"/api/experiments/{experiment_id}")
        assert deleted.status_code == 204 and not deleted.content
        assert client.get(f"/api/experiments/{experiment_id}").status_code == 404
        old_job = client.get(f"/api/jobs/{detail['id']}").json()
        assert old_job["status"] == "completed" and old_job["result_deleted"]
        assert old_job["result"] is None


@pytest.mark.parametrize(
    "payload",
    [
        {"label": ""},
        {"label": "x" * 121},
        {"label": "newline\n"},
        {"label": 4},
        {"include_depth": "true"},
        {"extra": True},
        {"scenario": {"unexpected": 1}},
    ],
)
def test_job_schema_rejects_invalid_requests_without_queueing(payload):
    with TestClient(create_app()) as client:
        assert client.post("/api/jobs", json=payload).status_code == 422
        assert client.get("/api/jobs").json()["jobs"] == []


@pytest.mark.parametrize(
    "payload",
    [
        {},
        {"label": None},
        {"notes": "x" * 4001},
        {"tags": ["a"] * 9},
        {"tags": ["same", "SAME"]},
        {"path": "../../secrets"},
    ],
)
def test_metadata_patch_validation_precedes_record_lookup(payload):
    with TestClient(create_app()) as client:
        assert client.patch(f"/api/experiments/{uuid4()}", json=payload).status_code == 422


@pytest.mark.parametrize("body", ['{"label":"\\ud800"}', '{"\\ud800":1}', b'{"label":"\xff"}'])
def test_invalid_utf8_json_never_reaches_storage_or_error_serialization(body):
    with TestClient(create_app()) as client:
        response = client.post(
            "/api/jobs", content=body, headers={"Content-Type": "application/json"}
        )
        assert response.status_code == 400


@pytest.mark.parametrize(
    "content_type", ["text/plain", "application/octet-stream", "application/x-www-form-urlencoded"]
)
def test_non_json_bytes_are_unsupported_media_not_a_serialization_crash(content_type):
    with TestClient(create_app()) as client:
        response = client.post("/api/jobs", content=b"\xff", headers={"Content-Type": content_type})
        assert response.status_code == 415
        assert client.get("/api/jobs").json()["jobs"] == []


@pytest.mark.parametrize(
    "body",
    [
        b'{"label":"first","label":"second"}',
        b'{"scenario":{"seed":7,"seed":8}}',
        '{"label":"UTF16"}'.encode("utf-16"),
        '{"label":"UTF32"}'.encode("utf-32"),
    ],
)
def test_ambiguous_duplicate_keys_and_non_utf8_encodings_are_rejected(body):
    with TestClient(create_app()) as client:
        response = client.post(
            "/api/jobs", content=body, headers={"Content-Type": "application/json"}
        )
        assert response.status_code == 400
        assert client.get("/api/jobs").json()["jobs"] == []


def test_utf8_bom_remains_supported_without_changing_the_scenario():
    with TestClient(create_app()) as client:
        response = client.post(
            "/api/jobs",
            content=b'\xef\xbb\xbf{"scenario":{"n_qubits":2,"layers":2,"shots":256}}',
            headers={"Content-Type": "application/json"},
        )
        assert response.status_code == 202
        detail = completed_job(client, response.json()["id"])
        assert detail["status"] == "completed" and detail["scenario"]["n_qubits"] == 2


def test_missing_invalid_and_pathlike_record_ids_are_safe():
    with TestClient(create_app()) as client:
        for collection in ("jobs", "experiments"):
            assert client.get(f"/api/{collection}/{uuid4()}").status_code == 404
            assert client.get(f"/api/{collection}/not-a-uuid").status_code == 422
            assert client.get(f"/api/{collection}/..%2F..%2Fetc%2Fpasswd").status_code == 404
        assert client.post(f"/api/jobs/{uuid4()}/cancel").status_code == 404
        assert client.delete(f"/api/experiments/{uuid4()}").status_code == 404
        assert client.get("/api/experiments?limit=201").status_code == 422
        assert client.get("/api/experiments?offset=-1").status_code == 422


def test_full_queue_cancellation_and_busy_sync_routes_share_capacity():
    slots = threading.BoundedSemaphore(2)
    slots.acquire()
    slots.acquire()
    with TestClient(create_app(compute_slots=slots, queue_capacity=1)) as client:
        first = client.post("/api/jobs", json={"label": "Queued"})
        assert first.status_code == 202
        assert client.post("/api/jobs", json={}).status_code == 429
        assert client.post("/api/evaluate", json={}).status_code == 429
        assert client.post("/api/stress", json={}).status_code == 429
        assert client.post("/api/pricing", json={}).status_code == 429
        job_id = first.json()["id"]
        cancelled = client.post(f"/api/jobs/{job_id}/cancel")
        assert cancelled.status_code == 200 and cancelled.json()["status"] == "cancelled"
        assert client.post(f"/api/jobs/{job_id}/cancel").status_code == 409
        detail = client.get(f"/api/jobs/{job_id}").json()
        assert detail["scenario"]["seed"] == 7
        slots.release()
        slots.release()


def test_failed_job_returns_truthful_failure_and_does_not_persist_result():
    def failing_evaluator(*args, **kwargs):
        raise ValueError("Deliberate test failure")

    with TestClient(create_app(evaluator=failing_evaluator)) as client:
        submitted = client.post("/api/jobs", json={}).json()
        detail = completed_job(client, submitted["id"])
        assert detail["status"] == "failed"
        assert detail["error"] == "Deliberate test failure"
        assert client.get("/api/experiments").json()["experiments"] == []


def test_storage_error_is_503_not_internal_server_error(monkeypatch):
    with TestClient(create_app()) as client:

        def unavailable(*args, **kwargs):
            raise sqlite3.OperationalError("simulated locked database")

        monkeypatch.setattr(client.app.state.store, "list_experiments", unavailable)
        response = client.get("/api/experiments")
        assert response.status_code == 503
        assert "unavailable" in response.json()["detail"]


def test_corrupted_saved_result_is_a_clear_503():
    with TestClient(create_app()) as client:
        response = client.post(
            "/api/jobs", json={"scenario": {"n_qubits": 2, "layers": 2, "shots": 256}}
        )
        detail = completed_job(client, response.json()["id"])
        experiment_id = detail["experiment_id"]
        with client.app.state.store.connection() as connection:
            connection.execute(
                "UPDATE experiments SET result_json='{}' WHERE id=?", (experiment_id,)
            )
        assert client.get(f"/api/experiments/{experiment_id}").status_code == 503


def test_decision_routes_compute_one_matched_benchmark_and_attach_provenance():
    from qubityield.analysis import evaluate

    calls = []

    def instrumented(scenario, **kwargs):
        calls.append(kwargs)
        return evaluate(scenario, **kwargs)

    with TestClient(create_app(evaluator=instrumented)) as client:
        for route in ("stress", "pricing"):
            calls.clear()
            response = client.post(f"/api/{route}", json={})
            assert response.status_code == 200, response.text
            body = response.json()
            assert len(calls) == 1 and calls[0]["include_depth"] is False
            assert body["evidence"]["hardware_executed"] is False
            assert body["benchmark"]["baseline"]["gate_count"] == 200


def test_metadata_cors_preflight_is_supported_for_the_local_dev_ui():
    with TestClient(create_app()) as client:
        response = client.options(
            f"/api/experiments/{uuid4()}",
            headers={
                "Origin": "http://localhost:5173",
                "Access-Control-Request-Method": "PATCH",
                "Access-Control-Request-Headers": "Content-Type",
            },
        )
        assert response.status_code == 200
        assert "PATCH" in response.headers["Access-Control-Allow-Methods"]
