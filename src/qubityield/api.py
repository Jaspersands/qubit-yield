"""Local-first API and dashboard host. No account, paid API, or QPU access required."""

from __future__ import annotations

import asyncio
from contextlib import asynccontextmanager
import json
import math
import sqlite3
import threading
from pathlib import Path
from uuid import UUID

from fastapi import FastAPI, HTTPException, Query, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, ConfigDict, Field, StrictBool, field_validator

from qubityield import __version__
from qubityield.analysis import evaluate
from qubityield.decision_tools import (
    PricingRequest,
    StressRequest,
    evaluate_pricing,
    evaluate_stress,
)
from qubityield.jobs import JobManager, QueueClosed, QueueFull
from qubityield.models import Scenario
from qubityield.paths import project_root
from qubityield.storage import (
    ExperimentStore,
    InvalidTransition,
    MetadataPatch,
    RecordNotFound,
    StorageCorrupt,
    clean_label,
)

_simulation_slots = threading.BoundedSemaphore(2)


class JobRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    scenario: Scenario = Field(default_factory=Scenario)
    label: str = Field(default="Experiment", strict=True)
    include_depth: StrictBool = False

    _label = field_validator("label")(clean_label)


class BodySizeLimit:
    """Bound JSON request bodies before FastAPI parses them."""

    def __init__(self, app, max_bytes: int = 65536, max_depth: int = 32):
        self.app = app
        self.max_bytes = max_bytes
        self.max_depth = max_depth

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http" or scope["method"] not in {"POST", "PUT", "PATCH"}:
            await self.app(scope, receive, send)
            return
        chunks, size = [], 0
        while True:
            message = await receive()
            if message["type"] == "http.disconnect":
                return
            size += len(message.get("body", b""))
            if size > self.max_bytes:
                response = JSONResponse(
                    {"detail": "Request exceeds the 64 KiB limit."}, status_code=413
                )
                await response(scope, receive, send)
                return
            chunks.append(message)
            if not message.get("more_body", False):
                break
        raw = b"".join(message.get("body", b"") for message in chunks)
        content_type = (
            next(
                (
                    value
                    for key, value in scope.get("headers", [])
                    if key.lower() == b"content-type"
                ),
                b"",
            )
            .lower()
            .partition(b";")[0]
            .strip()
        )
        # Match FastAPI's JSON body rules, including an omitted Content-Type
        # and structured JSON suffixes. Otherwise nonfinite inputs can reach
        # validation-error serialization and turn a bad request into a 500.
        is_json = (
            not content_type
            or content_type == b"application/json"
            or (content_type.startswith(b"application/") and content_type.endswith(b"+json"))
        )
        if raw and not is_json:
            response = JSONResponse(
                {"detail": "Request body must use an application/json media type."},
                status_code=415,
            )
            await response(scope, receive, send)
            return
        if raw and is_json:

            def reject_nonfinite(value):
                raise ValueError("Nonstandard JSON number")

            def finite_float(value):
                number = float(value)
                if not math.isfinite(number):
                    raise ValueError("JSON number exceeds finite floating-point range")
                return number

            def unique_object(pairs):
                result = {}
                for key, value in pairs:
                    if key in result:
                        raise ValueError("Duplicate JSON object key")
                    result[key] = value
                return result

            try:
                parsed = json.loads(
                    raw.decode("utf-8-sig"),
                    parse_constant=reject_nonfinite,
                    parse_float=finite_float,
                    object_pairs_hook=unique_object,
                )
                pending = [(parsed, 0)]
                while pending:
                    value, depth = pending.pop()
                    if isinstance(value, str):
                        value.encode(
                            "utf-8"
                        )  # Reject unpaired Unicode surrogates before error serialization.
                    if isinstance(value, (dict, list)):
                        if depth >= self.max_depth:
                            raise ValueError("JSON nesting exceeds the supported limit")
                        children = (
                            list(value.keys()) + list(value.values())
                            if isinstance(value, dict)
                            else value
                        )
                        pending.extend((child, depth + 1) for child in children)
            except (ValueError, UnicodeError, RecursionError):
                response = JSONResponse(
                    {
                        "detail": f"Request body must be valid finite-number JSON with nesting below {self.max_depth} levels."
                    },
                    status_code=400,
                )
                await response(scope, receive, send)
                return
        index = 0

        async def replay():
            nonlocal index
            if index < len(chunks):
                message = chunks[index]
                index += 1
                return message
            return await receive()

        await self.app(scope, replay, send)


def create_app(
    web_dir: Path | None = None,
    *,
    data_dir: Path | None = None,
    evaluator=None,
    compute_slots=None,
    queue_capacity: int = 8,
    workers: int = 2,
) -> FastAPI:
    compute = evaluator or evaluate
    slots = compute_slots if compute_slots is not None else _simulation_slots

    @asynccontextmanager
    async def lifespan(app):
        store = ExperimentStore(data_dir)
        manager = JobManager(
            store, slots, evaluator=compute, workers=workers, queue_capacity=queue_capacity
        )
        manager.start()
        app.state.store = store
        app.state.jobs = manager
        try:
            yield
        finally:
            await asyncio.to_thread(manager.shutdown)

    app = FastAPI(
        title="QubitYield",
        version=__version__,
        description="Fictional case data and simulated quantum evidence. See /docs for typed API schemas.",
        lifespan=lifespan,
    )
    app.add_middleware(BodySizeLimit)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
        allow_methods=["GET", "POST", "PATCH", "DELETE"],
        allow_headers=["Content-Type"],
    )

    @app.exception_handler(RecordNotFound)
    async def missing_record(request, exc):
        return JSONResponse({"detail": str(exc)}, status_code=404)

    @app.exception_handler(InvalidTransition)
    async def invalid_transition(request, exc):
        return JSONResponse({"detail": str(exc)}, status_code=409)

    @app.exception_handler(QueueFull)
    async def queue_full(request, exc):
        return JSONResponse({"detail": str(exc)}, status_code=429, headers={"Retry-After": "2"})

    @app.exception_handler(QueueClosed)
    async def queue_closed(request, exc):
        return JSONResponse({"detail": str(exc)}, status_code=503)

    @app.exception_handler(StorageCorrupt)
    async def corrupt_storage(request, exc):
        return JSONResponse({"detail": str(exc)}, status_code=503)

    @app.exception_handler(sqlite3.Error)
    async def unavailable_storage(request, exc):
        return JSONResponse(
            {"detail": "Experiment storage is unavailable. Check the local data directory."},
            status_code=503,
        )

    def store() -> ExperimentStore:
        if not hasattr(app.state, "store"):
            raise HTTPException(
                503, "Experiment storage is not initialized; start the application lifecycle"
            )
        return app.state.store

    def jobs() -> JobManager:
        if not hasattr(app.state, "jobs"):
            raise HTTPException(
                503, "Experiment workers are not initialized; start the application lifecycle"
            )
        return app.state.jobs

    @app.get("/api/health")
    def health():
        return {"status": "ok", "version": __version__, "hardware_connected": False}

    @app.get("/api/defaults")
    def defaults():
        return Scenario().model_dump(mode="json")

    @app.get("/api/case")
    def case():
        path = project_root() / "data" / "case_facts.json"
        if not path.is_file():
            raise HTTPException(404, "Case facts are available in the source checkout.")
        return json.loads(path.read_text())

    def run(scenario: Scenario, refresh: bool, decision=None):
        if not slots.acquire(blocking=False):
            raise HTTPException(
                429,
                "Both experiment workers are busy. Try again shortly.",
                headers={"Retry-After": "2"},
            )
        try:
            result = compute(scenario, refresh=refresh, include_depth=decision is None)
            if decision is not None:
                response = decision(result["benchmark"])
                response["evidence"] = result["evidence"]
                response["benchmark"] = result["benchmark"]
                return response
            return result
        except ValueError as exc:
            raise HTTPException(422, str(exc)) from exc
        finally:
            slots.release()

    @app.post("/api/evaluate")
    def evaluate_route(scenario: Scenario):
        return run(scenario, refresh=False)

    @app.post("/api/benchmark")
    def benchmark_route(scenario: Scenario):
        return run(scenario, refresh=True)

    @app.post("/api/stress")
    def stress_route(request: StressRequest):
        return run(request.scenario, False, lambda benchmark: evaluate_stress(request, benchmark))

    @app.post("/api/pricing")
    def pricing_route(request: PricingRequest):
        return run(request.scenario, False, lambda benchmark: evaluate_pricing(request, benchmark))

    @app.post("/api/jobs", status_code=202)
    def create_job(request: JobRequest):
        return jobs().submit(request.scenario, request.label, request.include_depth)

    @app.get("/api/jobs")
    def list_jobs(limit: int = Query(default=100, ge=1, le=200)):
        return {"jobs": store().list_jobs(limit)}

    @app.get("/api/jobs/{job_id}")
    def job_detail(job_id: UUID):
        return store().get_job(job_id, include_result=True)

    @app.post("/api/jobs/{job_id}/cancel")
    def cancel_job(job_id: UUID):
        return jobs().cancel(str(job_id))

    @app.get("/api/experiments")
    def list_experiments(
        limit: int = Query(default=100, ge=1, le=200),
        offset: int = Query(default=0, ge=0, le=1_000_000),
    ):
        return {"experiments": store().list_experiments(limit, offset)}

    @app.get("/api/experiments/{experiment_id}")
    def experiment_detail(experiment_id: UUID):
        return store().get_experiment(experiment_id)

    @app.patch("/api/experiments/{experiment_id}")
    def update_experiment(experiment_id: UUID, changes: MetadataPatch):
        return store().update_experiment(experiment_id, changes)

    @app.delete("/api/experiments/{experiment_id}", status_code=204)
    def delete_experiment(experiment_id: UUID):
        store().delete_experiment(experiment_id)
        return Response(status_code=204)

    @app.get("/api/demo")
    def demo():
        path = project_root() / "artifacts" / "analysis.json"
        if path.is_file():
            return json.loads(path.read_text())
        return run(Scenario(), refresh=False)

    @app.get("/api/evidence")
    def evidence():
        return {
            "analysis": "/artifacts/analysis.json",
            "multi_seed": "/artifacts/multi_seed.json",
            "independent_validation": "/artifacts/qiskit_validation.json",
            "decision_memo": "/artifacts/decision_memo.pdf",
            "results_table": "/artifacts/options.csv",
            "figures": "/artifacts/decision_landscape.png",
        }

    artifacts = project_root() / "artifacts"
    if artifacts.is_dir():
        app.mount("/artifacts", StaticFiles(directory=artifacts), name="artifacts")

    assets = web_dir or project_root() / "web" / "dist"
    if assets.is_dir() and (assets / "index.html").exists():
        # The UI uses in-memory navigation; no broad catch-all masks API 404s.
        app.mount("/", StaticFiles(directory=assets, html=True), name="dashboard")
    else:

        @app.get("/")
        def no_frontend():
            return JSONResponse(
                {
                    "application": "QubitYield",
                    "api_docs": "/docs",
                    "dashboard": "Run npm ci && npm run build in web/, then restart the server.",
                }
            )

    return app


app = create_app()
