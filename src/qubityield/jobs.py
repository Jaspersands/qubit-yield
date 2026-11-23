"""Bounded background experiments sharing slots with synchronous computations."""

from __future__ import annotations

from collections import deque
import logging
import os
import threading
from typing import Callable

from .models import Scenario, coerce_scenario
from .storage import ExperimentStore, InvalidTransition, clean_label, identifier


logger = logging.getLogger(__name__)


class QueueFull(RuntimeError):
    """The bounded pending-work queue has no room."""


class QueueClosed(RuntimeError):
    """The application is shutting down or has not started."""


class _DirectoryLock:
    """Advisory lock prevents a second process recovering another's live jobs."""

    def __init__(self, store: ExperimentStore):
        self.path = store.data_dir / "worker.lock"
        self.stream = None

    def acquire(self):
        stream = self.path.open("a+b")
        try:
            if os.name == "nt":
                import msvcrt

                if self.path.stat().st_size == 0:
                    stream.write(b"0")
                    stream.flush()
                stream.seek(0)
                msvcrt.locking(stream.fileno(), msvcrt.LK_NBLCK, 1)
            else:
                import fcntl

                fcntl.flock(stream.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        except (OSError, BlockingIOError) as exc:
            stream.close()
            raise RuntimeError(
                "Another QubitYield server already owns this data directory"
            ) from exc
        self.stream = stream

    def release(self):
        if self.stream is None:
            return
        if os.name == "nt":
            import msvcrt

            self.stream.seek(0)
            msvcrt.locking(self.stream.fileno(), msvcrt.LK_UNLCK, 1)
        else:
            import fcntl

            fcntl.flock(self.stream.fileno(), fcntl.LOCK_UN)
        self.stream.close()
        self.stream = None


class JobManager:
    """Two finite workers and a bounded queue, with durable terminal results.

    Cancellation is intentionally only for queued work. In-flight Python
    computation is not killable safely. Graceful shutdown waits for it; abrupt
    process termination is recovered as explicit failure on next startup.
    """

    def __init__(
        self,
        store: ExperimentStore,
        compute_slots: threading.BoundedSemaphore,
        *,
        evaluator: Callable | None = None,
        workers: int = 2,
        queue_capacity: int = 8,
    ):
        if isinstance(workers, bool) or not isinstance(workers, int) or not 1 <= workers <= 2:
            raise ValueError("workers must be one or two")
        if (
            isinstance(queue_capacity, bool)
            or not isinstance(queue_capacity, int)
            or not 1 <= queue_capacity <= 32
        ):
            raise ValueError("queue_capacity must be from one to 32")
        if evaluator is None:
            from .analysis import evaluate

            evaluator = evaluate
        self.store = store
        self.compute_slots = compute_slots
        self.evaluator = evaluator
        self.worker_count = workers
        self.queue_capacity = queue_capacity
        self._condition = threading.Condition()
        self._queue: deque[str] = deque()
        self._pending: set[str] = set()
        self._threads: list[threading.Thread] = []
        self._started = False
        self._closing = False
        self._directory_lock = _DirectoryLock(store)

    def start(self) -> JobManager:
        acquired = False
        try:
            with self._condition:
                if self._started:
                    return self
                self._directory_lock.acquire()
                acquired = True
                self.store.recover_interrupted_jobs()
                self._started = True
                self._closing = False
                self._threads = [
                    threading.Thread(
                        target=self._worker, name=f"qubityield-worker-{index}", daemon=True
                    )
                    for index in range(self.worker_count)
                ]
                for thread in self._threads:
                    thread.start()
        except BaseException:
            if acquired:
                # A later thread may fail to start after an earlier worker is
                # already alive. Stop and join it before relinquishing ownership.
                # Joining while holding the condition would deadlock that worker.
                with self._condition:
                    self._closing = True
                    self._condition.notify_all()
                for thread in self._threads:
                    if thread.ident is not None:
                        thread.join()
                self._directory_lock.release()
                self._started = False
            raise
        return self

    def submit(
        self, scenario: Scenario | dict, label: str = "Experiment", include_depth: bool = False
    ) -> dict:
        scenario = coerce_scenario(scenario)
        label = clean_label(label)
        if not isinstance(include_depth, bool):
            raise ValueError("include_depth must be a boolean")
        with self._condition:
            if not self._started or self._closing:
                raise QueueClosed("Experiment workers are not accepting new jobs")
            # Includes jobs pulled by workers while they wait for a sync API
            # request to release a slot; those jobs are still truly queued.
            if len(self._pending) >= self.queue_capacity:
                raise QueueFull("Experiment queue is full. Try again after a job starts")
            job = self.store.create_job(scenario.model_dump(mode="json"), label, include_depth)
            self._pending.add(job["id"])
            self._queue.append(job["id"])
            self._condition.notify()
        return job

    def cancel(self, job_id: str) -> dict:
        job_id = identifier(job_id)
        with self._condition:
            job = self.store.cancel_job(job_id)
            self._pending.discard(job_id)
            try:
                self._queue.remove(job_id)
            except ValueError:
                pass  # A worker may be waiting for a slot; it checks _pending.
            self._condition.notify_all()
            return job

    def _worker(self):
        while True:
            with self._condition:
                self._condition.wait_for(lambda: self._queue or self._closing)
                if self._closing:
                    return
                job_id = self._queue.popleft()
            acquired = False
            while not acquired:
                with self._condition:
                    if self._closing or job_id not in self._pending:
                        break
                acquired = self.compute_slots.acquire(timeout=0.05)
            if not acquired:
                continue
            try:
                with self._condition:
                    if self._closing or job_id not in self._pending:
                        continue
                    if not self.store.start_job(job_id):
                        self._pending.discard(job_id)
                        continue
                    self._pending.remove(job_id)
                scenario, include_depth = self.store.job_inputs(job_id)
                result = self.evaluator(
                    Scenario.model_validate(scenario), refresh=True, include_depth=include_depth
                )
                self.store.complete_job(job_id, result)
            except Exception as exc:
                logger.exception("Background experiment %s failed", job_id)
                with self._condition:
                    self._pending.discard(job_id)
                detail = (
                    str(exc)
                    if isinstance(exc, ValueError)
                    else f"Unexpected {type(exc).__name__}; inspect the local server log"
                )
                try:
                    self.store.fail_job(job_id, detail)
                except Exception:
                    logger.exception("Could not persist experiment failure for %s", job_id)
            finally:
                self.compute_slots.release()

    def shutdown(self):
        with self._condition:
            if not self._started:
                return
            self._closing = True
            for job_id in tuple(self._pending):
                try:
                    self.store.cancel_job(
                        job_id, "Server stopped before this queued experiment started"
                    )
                except InvalidTransition:
                    pass
                except Exception:
                    logger.exception("Could not persist queued cancellation for %s", job_id)
            self._pending.clear()
            self._queue.clear()
            self._condition.notify_all()
        try:
            for thread in self._threads:
                thread.join()
        finally:
            self._directory_lock.release()
            self._started = False

    def __enter__(self):
        return self.start()

    def __exit__(self, *exc):
        self.shutdown()
