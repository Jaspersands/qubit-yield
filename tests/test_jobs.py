"""Real worker concurrency, cancellation races, restart, and lifecycle checks."""

import queue
import threading
import time

import pytest

from qubityield.jobs import JobManager, QueueClosed, QueueFull
from qubityield.storage import ExperimentStore, InvalidTransition


def result(scenario):
    return {
        "scenario": scenario.model_dump(mode="json"),
        "recommendation": {"id": "pulse", "contract_verdict": "Conditional"},
        "options": [{"id": "pulse", "customer_npv_usd": 123.0}],
    }


def wait_state(store, job_id, statuses, timeout=5):
    end = time.monotonic() + timeout
    while time.monotonic() < end:
        job = store.get_job(job_id)
        if job["status"] in statuses:
            return job
        time.sleep(0.005)
    raise AssertionError(f"Job never reached {statuses}: {store.get_job(job_id)}")


class BlockingEvaluator:
    def __init__(self):
        self.release = threading.Event()
        self.started = queue.Queue()
        self.lock = threading.Lock()
        self.active = 0
        self.maximum = 0

    def __call__(self, scenario, **kwargs):
        with self.lock:
            self.active += 1
            self.maximum = max(self.maximum, self.active)
        self.started.put(scenario.seed)
        try:
            if not self.release.wait(timeout=5):
                raise RuntimeError("test release was not signaled")
            return result(scenario)
        finally:
            with self.lock:
                self.active -= 1


def test_completed_job_persists_full_result_and_original_inputs(tmp_path):
    store = ExperimentStore(tmp_path)
    with JobManager(
        store, threading.BoundedSemaphore(2), evaluator=lambda scenario, **kw: result(scenario)
    ) as manager:
        job = manager.submit({"seed": 29}, "Saved run", True)
        completed = wait_state(store, job["id"], {"completed"})
    reopened = ExperimentStore(tmp_path)
    detail = reopened.get_job(job["id"], include_result=True)
    assert detail["scenario"]["seed"] == 29 and detail["include_depth"] is True
    assert detail["result"]["scenario"]["seed"] == 29
    assert detail["started_at"] and detail["finished_at"]
    assert reopened.get_experiment(completed["experiment_id"])["label"] == "Saved run"


def test_shared_slots_bound_background_and_synchronous_computation(tmp_path):
    store = ExperimentStore(tmp_path)
    slots = threading.BoundedSemaphore(2)
    slots.acquire()  # A synchronous computation already occupies one slot.
    evaluator = BlockingEvaluator()
    manager = JobManager(store, slots, evaluator=evaluator).start()
    try:
        jobs = [manager.submit({"seed": seed}) for seed in (1, 2, 3)]
        evaluator.started.get(timeout=2)
        assert evaluator.maximum == 1
        assert sum(j["status"] == "running" for j in store.list_jobs()) == 1
        slots.release()
        evaluator.started.get(timeout=2)
        assert evaluator.maximum == 2
        evaluator.release.set()
        for job in jobs:
            wait_state(store, job["id"], {"completed"})
        assert evaluator.maximum == 2
    finally:
        evaluator.release.set()
        manager.shutdown()


def test_queue_capacity_includes_workers_waiting_for_a_shared_slot(tmp_path):
    store = ExperimentStore(tmp_path)
    slots = threading.BoundedSemaphore(1)
    slots.acquire()
    manager = JobManager(
        store, slots, queue_capacity=1, evaluator=lambda s, **kw: result(s)
    ).start()
    try:
        first = manager.submit({"seed": 1})
        with pytest.raises(QueueFull):
            manager.submit({"seed": 2})
        assert manager.cancel(first["id"])["status"] == "cancelled"
        second = manager.submit({"seed": 3})
        slots.release()
        wait_state(store, second["id"], {"completed"})
        assert store.get_job(first["id"])["status"] == "cancelled"
    finally:
        manager.shutdown()


def test_running_work_cannot_be_falsely_cancelled(tmp_path):
    store = ExperimentStore(tmp_path)
    evaluator = BlockingEvaluator()
    manager = JobManager(store, threading.BoundedSemaphore(2), evaluator=evaluator).start()
    try:
        job = manager.submit({})
        evaluator.started.get(timeout=2)
        with pytest.raises(InvalidTransition):
            manager.cancel(job["id"])
        assert store.get_job(job["id"])["status"] == "running"
        evaluator.release.set()
        wait_state(store, job["id"], {"completed"})
        with pytest.raises(InvalidTransition):
            manager.cancel(job["id"])
    finally:
        evaluator.release.set()
        manager.shutdown()


def test_worker_failure_is_recorded_and_does_not_kill_the_queue(tmp_path):
    store = ExperimentStore(tmp_path)

    def evaluator(scenario, **kwargs):
        if scenario.seed == 1:
            raise ValueError("Invalid test configuration")
        return result(scenario)

    with JobManager(store, threading.BoundedSemaphore(2), evaluator=evaluator) as manager:
        bad = manager.submit({"seed": 1})
        good = manager.submit({"seed": 2})
        failure = wait_state(store, bad["id"], {"failed"})
        wait_state(store, good["id"], {"completed"})
    assert failure["error"] == "Invalid test configuration"
    assert len(store.list_experiments()) == 1


def test_startup_recovers_interrupted_jobs_without_rerunning(tmp_path):
    store = ExperimentStore(tmp_path)
    old = store.create_job({"seed": 7}, "Interrupted", False)
    store.start_job(old["id"])
    calls = []
    with JobManager(
        store, threading.BoundedSemaphore(2), evaluator=lambda *args, **kw: calls.append(1)
    ):
        assert store.get_job(old["id"])["status"] == "failed"
    assert calls == []


def test_shutdown_cancels_pending_work_but_waits_for_running_work(tmp_path):
    store = ExperimentStore(tmp_path)
    evaluator = BlockingEvaluator()
    manager = JobManager(
        store, threading.BoundedSemaphore(1), workers=1, evaluator=evaluator
    ).start()
    first = manager.submit({"seed": 1})
    evaluator.started.get(timeout=2)
    pending = manager.submit({"seed": 2})
    finished = threading.Event()
    thread = threading.Thread(target=lambda: (manager.shutdown(), finished.set()))
    thread.start()
    try:
        wait_state(store, pending["id"], {"cancelled"})
        assert not finished.is_set()
        assert store.get_job(first["id"])["status"] == "running"
        evaluator.release.set()
        thread.join(timeout=3)
        assert finished.is_set()
        assert store.get_job(first["id"])["status"] == "completed"
        with pytest.raises(QueueClosed):
            manager.submit({})
        manager.shutdown()  # Idempotent.
    finally:
        evaluator.release.set()
        thread.join(timeout=3)


def test_two_servers_cannot_recover_each_others_live_jobs(tmp_path):
    store = ExperimentStore(tmp_path)
    first = JobManager(store, threading.BoundedSemaphore(2)).start()
    second = JobManager(ExperimentStore(tmp_path), threading.BoundedSemaphore(2))
    try:
        with pytest.raises(RuntimeError, match="already owns"):
            second.start()
    finally:
        first.shutdown()
    second.start()
    second.shutdown()


def test_partial_worker_start_failure_stops_started_threads_before_releasing_lock(
    tmp_path, monkeypatch
):
    store = ExperimentStore(tmp_path)
    manager = JobManager(store, threading.BoundedSemaphore(2))
    real_start = threading.Thread.start
    calls = 0

    def fail_second_start(thread):
        nonlocal calls
        calls += 1
        if calls == 2:
            raise RuntimeError("simulated operating system thread limit")
        real_start(thread)

    with monkeypatch.context() as patch:
        patch.setattr(threading.Thread, "start", fail_second_start)
        with pytest.raises(RuntimeError, match="thread limit"):
            manager.start()
    assert len(manager._threads) == 2
    assert manager._threads[0].ident is not None
    assert not any(thread.is_alive() for thread in manager._threads)
    assert manager._directory_lock.stream is None
    with pytest.raises(QueueClosed):
        manager.submit({})
    with JobManager(store, threading.BoundedSemaphore(2)):
        pass  # The failed startup relinquished its directory only after cleanup.


def test_wrong_scenario_returned_by_evaluator_fails_without_saving_evidence(tmp_path):
    store = ExperimentStore(tmp_path)

    def mismatched(scenario, **kwargs):
        return result(scenario.model_copy(update={"seed": scenario.seed + 1}))

    with JobManager(store, threading.BoundedSemaphore(2), evaluator=mismatched) as manager:
        job = manager.submit({"seed": 7})
        failed = wait_state(store, job["id"], {"failed"})
        assert "requested scenario" in failed["error"]
        assert failed["experiment_id"] is None
        assert store.list_experiments() == []
