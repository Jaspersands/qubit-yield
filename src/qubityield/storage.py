"""Durable, local SQLite evidence ledger with bounded metadata and checksums."""

from __future__ import annotations

from contextlib import contextmanager
from datetime import datetime, timezone
import hashlib
import json
import math
import os
from pathlib import Path
import sqlite3
from typing import Any
import unicodedata
from uuid import UUID, uuid4

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from .models import Scenario


MAX_RESULT_BYTES = 8 * 1024 * 1024
JOB_STATES = {"queued", "running", "completed", "failed", "cancelled"}


class RecordNotFound(LookupError):
    """The requested ledger object does not exist."""


class StorageCorrupt(RuntimeError):
    """Stored evidence failed structural or checksum validation."""


class InvalidTransition(ValueError):
    """The requested job state change is not valid."""


def timestamp() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="microseconds")


def identifier(value: str | UUID) -> str:
    try:
        return str(UUID(str(value)))
    except (TypeError, ValueError, AttributeError) as exc:
        raise ValueError("Record ID must be a UUID") from exc


def validate_text(value: str, *, label: str, limit: int, multiline: bool = False) -> str:
    if not isinstance(value, str):
        raise ValueError(f"{label} must be text")
    try:
        encoded = value.encode("utf-8")
    except UnicodeError as exc:
        raise ValueError(f"{label} must be valid UTF-8 text") from exc
    if len(value) > limit or len(encoded) > 4 * limit:
        raise ValueError(f"{label} must contain at most {limit} characters")
    allowed = "\n\r\t" if multiline else ""
    if any(unicodedata.category(char) in {"Cc", "Cs"} and char not in allowed for char in value):
        raise ValueError(f"{label} contains unsupported control characters")
    return value


def clean_label(value: str) -> str:
    value = validate_text(value, label="label", limit=120).strip()
    if not value:
        raise ValueError("label must contain at least one visible character")
    return value


def clean_tags(values: list[str]) -> list[str]:
    if not isinstance(values, list) or len(values) > 8:
        raise ValueError("tags must be a list containing at most eight tags")
    result = []
    for value in values:
        value = validate_text(value, label="tag", limit=40).strip()
        if not value:
            raise ValueError("tags must not be empty")
        if value.casefold() in {tag.casefold() for tag in result}:
            raise ValueError("tags must be unique (case-insensitive)")
        result.append(value)
    return result


class ExperimentMetadata(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    label: str = "Experiment"
    notes: str = ""
    tags: list[str] = Field(default_factory=list)

    _label = field_validator("label")(clean_label)
    _tags = field_validator("tags")(clean_tags)

    @field_validator("notes")
    @classmethod
    def valid_notes(cls, value: str) -> str:
        return validate_text(value, label="notes", limit=4000, multiline=True)


class MetadataPatch(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    label: str | None = None
    notes: str | None = None
    tags: list[str] | None = None

    @model_validator(mode="after")
    def check_patch(self) -> MetadataPatch:
        if not self.model_fields_set:
            raise ValueError("Provide at least one of label, notes, or tags")
        changes = {key: getattr(self, key) for key in self.model_fields_set}
        if any(value is None for value in changes.values()):
            raise ValueError(
                "Metadata fields cannot be null; use empty notes or tags to clear them"
            )
        validated = ExperimentMetadata.model_validate(changes)
        for key in changes:
            object.__setattr__(self, key, getattr(validated, key))
        return self


def default_data_dir() -> Path:
    override = os.environ.get("QUBITYIELD_DATA_DIR")
    if override:
        return Path(override).expanduser().resolve()
    if os.name == "nt" and os.environ.get("LOCALAPPDATA"):
        return Path(os.environ["LOCALAPPDATA"]) / "QubitYield"
    base = Path(os.environ.get("XDG_DATA_HOME", Path.home() / ".local" / "share"))
    return base.expanduser().resolve() / "qubityield"


def _dump(value: Any) -> str:
    try:
        return json.dumps(value, ensure_ascii=False, allow_nan=False, separators=(",", ":"))
    except (TypeError, ValueError, UnicodeError, RecursionError) as exc:
        raise ValueError("Evidence must be finite, JSON-serializable data") from exc


def _load(raw: str) -> Any:
    """Reject corrupt JSON that could crash response serialization downstream."""

    def reject_constant(value):
        raise ValueError("Nonfinite stored JSON")

    try:
        if not isinstance(raw, str):
            raise ValueError("Stored JSON must be text")
        value = json.loads(raw, parse_constant=reject_constant)
        pending = [(value, 0)]
        while pending:
            item, depth = pending.pop()
            if isinstance(item, float) and not math.isfinite(item):
                raise ValueError("Nonfinite stored JSON")
            if isinstance(item, str):
                item.encode("utf-8")
            if isinstance(item, (dict, list)):
                if depth >= 64:
                    raise ValueError("Stored JSON nesting exceeds supported depth")
                children = (
                    list(item.keys()) + list(item.values()) if isinstance(item, dict) else item
                )
                pending.extend((child, depth + 1) for child in children)
        return value
    except (TypeError, ValueError, RecursionError) as exc:
        raise StorageCorrupt("Stored JSON is malformed, nonfinite, or invalid UTF-8") from exc


def _result_parts(result: dict) -> tuple[str, str, str, str]:
    if not isinstance(result, dict) or not isinstance(result.get("scenario"), dict):
        raise ValueError("Evidence must include its scenario")
    try:
        recommendation = result["recommendation"]
        selected = next(
            option for option in result["options"] if option["id"] == recommendation["id"]
        )
        npv = float(selected["customer_npv_usd"])
        if not math.isfinite(npv):
            raise ValueError("NPV must be finite")
        summary = {
            "recommended": str(recommendation["id"]),
            "verdict": str(recommendation["contract_verdict"]),
            "customer_npv_usd": npv,
        }
    except (KeyError, TypeError, StopIteration) as exc:
        raise ValueError("Evidence must contain a recommendation and matching option") from exc
    scenario_text = json.dumps(
        result["scenario"], sort_keys=True, separators=(",", ":"), allow_nan=False
    )
    scenario_hash = hashlib.sha256(scenario_text.encode()).hexdigest()
    claimed = result.get("evidence", {}).get("scenario_sha256")
    if claimed is not None and claimed != scenario_hash:
        raise ValueError("Evidence scenario hash does not match its scenario")
    raw = _dump(result)
    encoded = raw.encode("utf-8")
    if len(encoded) > MAX_RESULT_BYTES:
        raise ValueError("Evidence exceeds the 8 MiB storage limit")
    return raw, hashlib.sha256(encoded).hexdigest(), scenario_hash, _dump(summary)


class ExperimentStore:
    """Each operation uses its own connection; writes are atomic transactions."""

    def __init__(self, data_dir: Path | str | None = None):
        self.data_dir = (
            Path(data_dir).expanduser().resolve() if data_dir is not None else default_data_dir()
        )
        self.data_dir.mkdir(parents=True, exist_ok=True, mode=0o700)
        self.path = self.data_dir / "experiments.sqlite3"
        with self.connection() as connection:
            version = connection.execute("PRAGMA user_version").fetchone()[0]
            if version > 1:
                raise StorageCorrupt("Ledger schema is newer than this version of QubitYield")
            connection.execute("PRAGMA journal_mode=WAL")
            connection.executescript("""
                CREATE TABLE IF NOT EXISTS experiments (
                    id TEXT PRIMARY KEY, label TEXT NOT NULL, notes TEXT NOT NULL,
                    tags_json TEXT NOT NULL, created_at TEXT NOT NULL, updated_at TEXT NOT NULL,
                    scenario_hash TEXT NOT NULL, summary_json TEXT NOT NULL,
                    result_json TEXT NOT NULL, result_sha256 TEXT NOT NULL
                );
                CREATE INDEX IF NOT EXISTS experiments_created ON experiments(created_at DESC);
                CREATE TABLE IF NOT EXISTS jobs (
                    id TEXT PRIMARY KEY, status TEXT NOT NULL, label TEXT NOT NULL,
                    created_at TEXT NOT NULL, started_at TEXT, finished_at TEXT, error TEXT,
                    experiment_id TEXT REFERENCES experiments(id) ON DELETE SET NULL,
                    scenario_json TEXT NOT NULL, include_depth INTEGER NOT NULL
                );
                CREATE INDEX IF NOT EXISTS jobs_created ON jobs(created_at DESC);
                PRAGMA user_version=1;
            """)
        if os.name != "nt":
            self.path.chmod(0o600)

    @contextmanager
    def connection(self):
        connection = sqlite3.connect(self.path, timeout=5.0)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA foreign_keys=ON")
        connection.execute("PRAGMA busy_timeout=5000")
        try:
            with connection:
                yield connection
        finally:
            connection.close()

    @staticmethod
    def _metadata(row: sqlite3.Row) -> dict:
        try:
            metadata = ExperimentMetadata(
                label=row["label"], notes=row["notes"], tags=_load(row["tags_json"])
            )
            summary = _load(row["summary_json"])
            if not isinstance(summary, dict) or set(summary) != {
                "recommended",
                "verdict",
                "customer_npv_usd",
            }:
                raise ValueError("Invalid stored summary")
            if not isinstance(summary["recommended"], str) or not isinstance(
                summary["verdict"], str
            ):
                raise ValueError("Invalid stored summary text")
            if isinstance(summary["customer_npv_usd"], bool) or not isinstance(
                summary["customer_npv_usd"], (int, float)
            ):
                raise ValueError("Invalid stored summary number")
            return {
                key: row[key]
                for key in ("id", "label", "notes", "created_at", "updated_at", "scenario_hash")
            } | {"tags": metadata.tags, "summary": summary}
        except (TypeError, ValueError, KeyError) as exc:
            raise StorageCorrupt("Stored experiment metadata is unreadable") from exc

    @staticmethod
    def _job(row: sqlite3.Row) -> dict:
        if row["status"] not in JOB_STATES:
            raise StorageCorrupt("Stored job state is invalid")
        return {
            key: row[key]
            for key in (
                "id",
                "status",
                "created_at",
                "started_at",
                "finished_at",
                "label",
                "error",
                "experiment_id",
            )
        }

    @staticmethod
    def _pagination(limit: int, offset: int = 0) -> None:
        if isinstance(limit, bool) or not isinstance(limit, int) or not 1 <= limit <= 200:
            raise ValueError("limit must be an integer from 1 to 200")
        if isinstance(offset, bool) or not isinstance(offset, int) or not 0 <= offset <= 1_000_000:
            raise ValueError("offset must be an integer from 0 to 1000000")

    def list_experiments(self, limit: int = 100, offset: int = 0) -> list[dict]:
        self._pagination(limit, offset)
        with self.connection() as connection:
            rows = connection.execute(
                "SELECT id,label,notes,tags_json,created_at,updated_at,scenario_hash,summary_json "
                "FROM experiments ORDER BY created_at DESC,id DESC LIMIT ? OFFSET ?",
                (limit, offset),
            ).fetchall()
        return [self._metadata(row) for row in rows]

    def get_experiment(self, experiment_id: str | UUID) -> dict:
        with self.connection() as connection:
            row = connection.execute(
                "SELECT * FROM experiments WHERE id=?", (identifier(experiment_id),)
            ).fetchone()
        if row is None:
            raise RecordNotFound("Experiment not found")
        raw = row["result_json"]
        if not isinstance(raw, str):
            raise StorageCorrupt("Saved evidence must be JSON text")
        if hashlib.sha256(raw.encode("utf-8")).hexdigest() != row["result_sha256"]:
            raise StorageCorrupt("Saved evidence checksum mismatch; restore a known-good backup")
        try:
            result = _load(raw)
        except (TypeError, ValueError, RecursionError) as exc:
            raise StorageCorrupt("Saved evidence is unreadable") from exc
        return self._metadata(row) | {"result": result}

    def create_experiment(
        self,
        result: dict,
        label: str = "Experiment",
        notes: str = "",
        tags: list[str] | None = None,
    ) -> dict:
        metadata = ExperimentMetadata(label=label, notes=notes, tags=tags or [])
        parts = _result_parts(result)
        experiment_id = str(uuid4())
        now = timestamp()
        with self.connection() as connection:
            self._insert_experiment(connection, experiment_id, now, metadata, parts)
        return self.get_experiment(experiment_id)

    @staticmethod
    def _insert_experiment(connection, experiment_id, now, metadata, parts):
        raw, checksum, scenario_hash, summary = parts
        connection.execute(
            "INSERT INTO experiments VALUES (?,?,?,?,?,?,?,?,?,?)",
            (
                experiment_id,
                metadata.label,
                metadata.notes,
                _dump(metadata.tags),
                now,
                now,
                scenario_hash,
                summary,
                raw,
                checksum,
            ),
        )

    def update_experiment(self, experiment_id: str | UUID, changes: MetadataPatch | dict) -> dict:
        experiment_id = identifier(experiment_id)
        patch = MetadataPatch.model_validate(
            changes.model_dump(exclude_unset=True)
            if isinstance(changes, MetadataPatch)
            else changes
        )
        with self.connection() as connection:
            connection.execute("BEGIN IMMEDIATE")
            row = connection.execute(
                "SELECT * FROM experiments WHERE id=?", (experiment_id,)
            ).fetchone()
            if row is None:
                raise RecordNotFound("Experiment not found")
            original = {
                "label": row["label"],
                "notes": row["notes"],
                "tags": _load(row["tags_json"]),
            }
            metadata = ExperimentMetadata.model_validate(
                original | patch.model_dump(exclude_unset=True)
            )
            connection.execute(
                "UPDATE experiments SET label=?,notes=?,tags_json=?,updated_at=? WHERE id=?",
                (metadata.label, metadata.notes, _dump(metadata.tags), timestamp(), experiment_id),
            )
        detail = self.get_experiment(experiment_id)
        detail.pop("result")
        return detail

    def delete_experiment(self, experiment_id: str | UUID) -> None:
        with self.connection() as connection:
            changed = connection.execute(
                "DELETE FROM experiments WHERE id=?", (identifier(experiment_id),)
            ).rowcount
        if not changed:
            raise RecordNotFound("Experiment not found")

    def create_job(self, scenario: dict, label: str, include_depth: bool) -> dict:
        label = clean_label(label)
        job_id = str(uuid4())
        with self.connection() as connection:
            connection.execute(
                "INSERT INTO jobs VALUES (?,?,?,?,?,?,?,?,?,?)",
                (
                    job_id,
                    "queued",
                    label,
                    timestamp(),
                    None,
                    None,
                    None,
                    None,
                    _dump(scenario),
                    int(include_depth),
                ),
            )
        return self.get_job(job_id)

    def list_jobs(self, limit: int = 100) -> list[dict]:
        self._pagination(limit)
        with self.connection() as connection:
            rows = connection.execute(
                "SELECT * FROM jobs ORDER BY created_at DESC,id DESC LIMIT ?", (limit,)
            ).fetchall()
        return [self._job(row) for row in rows]

    def get_job(self, job_id: str | UUID, *, include_result: bool = False) -> dict:
        with self.connection() as connection:
            row = connection.execute(
                "SELECT * FROM jobs WHERE id=?", (identifier(job_id),)
            ).fetchone()
        if row is None:
            raise RecordNotFound("Job not found")
        job = self._job(row)
        if include_result:
            job["scenario"] = _load(row["scenario_json"])
            job["include_depth"] = bool(row["include_depth"])
        if include_result and job["status"] == "completed":
            try:
                experiment = (
                    self.get_experiment(job["experiment_id"]) if job["experiment_id"] else None
                )
            except RecordNotFound:
                experiment = None
            job["result"] = experiment["result"] if experiment else None
            job["result_deleted"] = experiment is None
        return job

    def job_inputs(self, job_id: str) -> tuple[dict, bool]:
        with self.connection() as connection:
            row = connection.execute(
                "SELECT scenario_json,include_depth FROM jobs WHERE id=?", (identifier(job_id),)
            ).fetchone()
        if row is None:
            raise RecordNotFound("Job not found")
        return _load(row["scenario_json"]), bool(row["include_depth"])

    def start_job(self, job_id: str) -> bool:
        with self.connection() as connection:
            return bool(
                connection.execute(
                    "UPDATE jobs SET status='running',started_at=? WHERE id=? AND status='queued'",
                    (timestamp(), identifier(job_id)),
                ).rowcount
            )

    def cancel_job(self, job_id: str, reason: str | None = None) -> dict:
        job_id = identifier(job_id)
        with self.connection() as connection:
            changed = connection.execute(
                "UPDATE jobs SET status='cancelled',finished_at=?,error=? WHERE id=? AND status='queued'",
                (timestamp(), reason, job_id),
            ).rowcount
            if not changed:
                if (
                    connection.execute("SELECT 1 FROM jobs WHERE id=?", (job_id,)).fetchone()
                    is None
                ):
                    raise RecordNotFound("Job not found")
                raise InvalidTransition(
                    "Only queued jobs can be cancelled; running work cannot be interrupted safely"
                )
        return self.get_job(job_id)

    def fail_job(self, job_id: str, error: str) -> None:
        with self.connection() as connection:
            connection.execute(
                "UPDATE jobs SET status='failed',finished_at=?,error=? WHERE id=? AND status IN ('queued','running')",
                (timestamp(), error[:1000], identifier(job_id)),
            )

    def complete_job(self, job_id: str, result: dict) -> dict:
        parts = _result_parts(result)
        job_id = identifier(job_id)
        experiment_id, now = str(uuid4()), timestamp()
        with self.connection() as connection:
            connection.execute("BEGIN IMMEDIATE")
            row = connection.execute(
                "SELECT label,status,scenario_json FROM jobs WHERE id=?", (job_id,)
            ).fetchone()
            if row is None:
                raise RecordNotFound("Job not found")
            if row["status"] != "running":
                raise InvalidTransition("Only a running job can complete")
            requested = Scenario.model_validate(_load(row["scenario_json"]))
            returned = Scenario.model_validate(result["scenario"])
            if requested.model_dump(mode="json") != returned.model_dump(mode="json"):
                raise ValueError("Completed evidence does not match the job's requested scenario")
            self._insert_experiment(
                connection, experiment_id, now, ExperimentMetadata(label=row["label"]), parts
            )
            connection.execute(
                "UPDATE jobs SET status='completed',finished_at=?,experiment_id=?,error=NULL WHERE id=?",
                (now, experiment_id, job_id),
            )
        return self.get_job(job_id)

    def recover_interrupted_jobs(self) -> int:
        with self.connection() as connection:
            return connection.execute(
                "UPDATE jobs SET status='failed',finished_at=?,error=? WHERE status IN ('queued','running')",
                (
                    timestamp(),
                    "Server restarted before this experiment finished. Submit a new job to rerun it.",
                ),
            ).rowcount
