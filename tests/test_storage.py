"""Persistence, atomicity, metadata boundaries, and evidence corruption checks."""

import json
import sqlite3
from uuid import uuid4

import pytest
from pydantic import ValidationError

from qubityield.storage import (
    MAX_RESULT_BYTES,
    ExperimentMetadata,
    ExperimentStore,
    InvalidTransition,
    MetadataPatch,
    RecordNotFound,
    StorageCorrupt,
)


def evidence(seed=7):
    return {
        "scenario": {"seed": seed},
        "recommendation": {"id": "pulse", "contract_verdict": "Conditional"},
        "options": [{"id": "pulse", "customer_npv_usd": 123.5}],
        "evidence": {"source": "simulated"},
    }


def test_result_and_unicode_metadata_survive_a_new_connection(tmp_path):
    store = ExperimentStore(tmp_path)
    created = store.create_experiment(evidence(), " Research 📈 ", "first\nsecond", [" Science "])
    reopened = ExperimentStore(tmp_path)
    assert reopened.get_experiment(created["id"]) == created
    assert created["label"] == "Research 📈"
    assert created["tags"] == ["Science"]
    assert created["summary"]["customer_npv_usd"] == 123.5
    assert "result" not in reopened.list_experiments()[0]


def test_patch_preserves_omitted_fields_and_can_clear_notes_tags(tmp_path):
    store = ExperimentStore(tmp_path)
    record = store.create_experiment(evidence(), "Original", "notes", ["one"])
    patched = store.update_experiment(record["id"], {"label": " Revised "})
    assert patched["label"] == "Revised"
    assert patched["notes"] == "notes" and patched["tags"] == ["one"]
    assert patched["scenario_hash"] == record["scenario_hash"]
    cleared = store.update_experiment(record["id"], {"notes": "", "tags": []})
    assert cleared["notes"] == "" and cleared["tags"] == []
    assert store.get_experiment(record["id"])["result"] == evidence()


@pytest.mark.parametrize(
    "data",
    [
        {"label": ""},
        {"label": "   "},
        {"label": "x" * 121},
        {"label": "x\x00"},
        {"label": "line\nbreak"},
        {"label": "\ud800"},
        {"notes": "x" * 4001},
        {"notes": "\x00"},
        {"tags": ["a"] * 9},
        {"tags": ["one", "ONE"]},
        {"tags": [""]},
        {"tags": ["x" * 41]},
        {"tags": [1]},
        {"label": 123},
        {"notes": None},
        {"unrecognized": "no"},
    ],
)
def test_metadata_is_bounded_and_strict(data):
    with pytest.raises(ValidationError):
        ExperimentMetadata.model_validate(data)


@pytest.mark.parametrize(
    "data", [{}, {"label": None}, {"tags": None}, {"notes": None}, {"id": "new"}]
)
def test_patch_never_silently_accepts_null_or_unknown_fields(data):
    with pytest.raises(ValidationError):
        MetadataPatch.model_validate(data)


def test_ids_cannot_be_used_as_paths_or_sql(tmp_path):
    store = ExperimentStore(tmp_path)
    for malformed in ("../secrets", "/etc/passwd", "x' OR 1=1 --", "not-a-uuid"):
        with pytest.raises(ValueError):
            store.get_experiment(malformed)
    label = "'; DROP TABLE experiments; --"
    record = store.create_experiment(evidence(), label)
    assert store.get_experiment(record["id"])["label"] == label
    assert len(store.list_experiments()) == 1
    with pytest.raises(RecordNotFound):
        store.get_experiment(str(uuid4()))


def test_checksum_detects_accidental_result_corruption(tmp_path):
    store = ExperimentStore(tmp_path)
    record = store.create_experiment(evidence())
    with store.connection() as connection:
        connection.execute(
            "UPDATE experiments SET result_json=? WHERE id=?", ('{"changed":true}', record["id"])
        )
    with pytest.raises(StorageCorrupt, match="checksum"):
        store.get_experiment(record["id"])


def test_corrupted_metadata_cannot_leak_nonfinite_values_to_the_api(tmp_path):
    store = ExperimentStore(tmp_path)
    record = store.create_experiment(evidence())
    with store.connection() as connection:
        connection.execute(
            "UPDATE experiments SET summary_json=? WHERE id=?",
            ('{"recommended":"pulse","verdict":"test","customer_npv_usd":1e400}', record["id"]),
        )
    with pytest.raises(StorageCorrupt):
        store.list_experiments()


def test_corrupted_job_json_is_reported_instead_of_returned(tmp_path):
    store = ExperimentStore(tmp_path)
    job = store.create_job({}, "Test", False)
    with store.connection() as connection:
        connection.execute(
            "UPDATE jobs SET scenario_json=? WHERE id=?", ('{"seed":NaN}', job["id"])
        )
    with pytest.raises(StorageCorrupt):
        store.get_job(job["id"], include_result=True)


def test_nonfinite_or_mismatched_evidence_cannot_be_saved(tmp_path):
    store = ExperimentStore(tmp_path)
    invalid = evidence()
    invalid["options"][0]["customer_npv_usd"] = float("nan")
    with pytest.raises(ValueError):
        store.create_experiment(invalid)
    invalid = evidence()
    invalid["evidence"]["scenario_sha256"] = "wrong"
    with pytest.raises(ValueError, match="hash"):
        store.create_experiment(invalid)
    assert store.list_experiments() == []


def test_evidence_storage_limit_is_enforced(tmp_path):
    store = ExperimentStore(tmp_path)
    result = evidence()
    result["padding"] = "x" * MAX_RESULT_BYTES
    with pytest.raises(ValueError, match="8 MiB"):
        store.create_experiment(result)
    assert store.list_experiments() == []


def test_completion_and_experiment_creation_are_atomic(tmp_path, monkeypatch):
    store = ExperimentStore(tmp_path)
    job = store.create_job({"seed": 7}, "Atomic", False)
    assert store.start_job(job["id"])
    original = store._insert_experiment

    def fail_after_insert(*args):
        original(*args)
        raise sqlite3.OperationalError("simulated disk failure")

    monkeypatch.setattr(store, "_insert_experiment", fail_after_insert)
    with pytest.raises(sqlite3.OperationalError):
        store.complete_job(job["id"], evidence())
    assert store.get_job(job["id"])["status"] == "running"
    assert store.list_experiments() == []


def test_deleted_result_does_not_fabricate_old_job_evidence(tmp_path):
    store = ExperimentStore(tmp_path)
    job = store.create_job({"seed": 7}, "To delete", False)
    store.start_job(job["id"])
    completed = store.complete_job(job["id"], evidence())
    store.delete_experiment(completed["experiment_id"])
    job = store.get_job(job["id"], include_result=True)
    assert job["status"] == "completed" and job["result"] is None
    assert job["result_deleted"] is True
    assert job["scenario"] == {"seed": 7}
    with pytest.raises(RecordNotFound):
        store.delete_experiment(completed["experiment_id"])


def test_illegal_completion_does_not_create_an_experiment(tmp_path):
    store = ExperimentStore(tmp_path)
    job = store.create_job({"seed": 7}, "Not started", False)
    with pytest.raises(InvalidTransition):
        store.complete_job(job["id"], evidence())
    assert store.list_experiments() == []


def test_completion_cannot_attach_evidence_from_another_scenario(tmp_path):
    store = ExperimentStore(tmp_path)
    job = store.create_job({"seed": 7}, "Matching evidence only", False)
    store.start_job(job["id"])
    with pytest.raises(ValueError, match="requested scenario"):
        store.complete_job(job["id"], evidence(8))
    assert store.get_job(job["id"])["status"] == "running"
    assert store.list_experiments() == []


def test_completion_compares_normalized_scenarios_not_optional_field_spelling(tmp_path):
    from qubityield.models import Scenario

    store = ExperimentStore(tmp_path)
    job = store.create_job({"seed": 7}, "Normalized", False)
    store.start_job(job["id"])
    full = evidence()
    full["scenario"] = Scenario(seed=7).model_dump(mode="json")
    completed = store.complete_job(job["id"], full)
    assert completed["status"] == "completed"
    assert store.get_experiment(completed["experiment_id"])["result"] == full


def test_recovery_changes_only_interrupted_jobs(tmp_path):
    store = ExperimentStore(tmp_path)
    queued = store.create_job({}, "queued", False)
    running = store.create_job({}, "running", False)
    cancelled = store.create_job({}, "cancelled", False)
    store.start_job(running["id"])
    store.cancel_job(cancelled["id"])
    assert store.recover_interrupted_jobs() == 2
    assert store.get_job(queued["id"])["status"] == "failed"
    assert store.get_job(running["id"])["status"] == "failed"
    assert "restarted" in store.get_job(running["id"])["error"]
    assert store.get_job(cancelled["id"])["status"] == "cancelled"


def test_newer_schema_is_rejected_without_overwriting_it(tmp_path):
    path = tmp_path / "experiments.sqlite3"
    with sqlite3.connect(path) as connection:
        connection.execute("PRAGMA user_version=99")
    with pytest.raises(StorageCorrupt):
        ExperimentStore(tmp_path)
    with sqlite3.connect(path) as connection:
        assert connection.execute("PRAGMA user_version").fetchone()[0] == 99


def test_pagination_is_bounded_and_results_are_json_serializable(tmp_path):
    store = ExperimentStore(tmp_path)
    ids = [store.create_experiment(evidence(seed))["id"] for seed in (1, 2, 3)]
    assert [row["id"] for row in store.list_experiments(1, 1)] == [ids[1]]
    for limit in (0, 201, True):
        with pytest.raises(ValueError):
            store.list_experiments(limit)
    json.dumps(store.list_experiments(), allow_nan=False)
