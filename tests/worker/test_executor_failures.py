"""Executor terminal events, confidentiality, cancellation and busy behavior."""

import asyncio

import pytest
from a2a.helpers import new_text_message
from a2a.server.agent_execution import RequestContext
from a2a.server.context import ServerCallContext
from a2a.server.tasks import TaskUpdater
from a2a.types import Role, SendMessageRequest, TaskState

from ezz_a2a.worker.executor import ReviewExecutor

SYNTHETIC_SECRET = "synthetic-secret-must-not-leak"
TEST_DEADLINE_SECONDS = 1


class RecordingEvents:
    def __init__(self):
        self.events = []

    async def enqueue_event(self, event):
        self.events.append(event)


def context():
    return RequestContext(ServerCallContext(), request=SendMessageRequest(
        message=new_text_message("Synthetic review", role=Role.ROLE_USER),
    ))


def test_unexpected_runner_error_becomes_sanitized_failed_event():
    async def runner(_):
        raise RuntimeError(SYNTHETIC_SECRET)

    events = RecordingEvents()
    asyncio.run(ReviewExecutor(runner).execute(context(), events))
    assert events.events[-1].status.state == TaskState.TASK_STATE_FAILED
    assert "RuntimeError" in str(events.events[-1])
    assert SYNTHETIC_SECRET not in str(events.events)


def test_artifact_failure_is_reported_without_secret(monkeypatch):
    async def runner(_):
        return "synthetic answer"

    async def broken_artifact(*args, **kwargs):
        raise RuntimeError(SYNTHETIC_SECRET)

    monkeypatch.setattr(TaskUpdater, "add_artifact", broken_artifact)
    events = RecordingEvents()
    asyncio.run(ReviewExecutor(runner).execute(context(), events))
    assert events.events[-1].status.state == TaskState.TASK_STATE_FAILED
    assert SYNTHETIC_SECRET not in str(events.events)


def test_failure_of_failure_handler_raises_only_sanitized_exception(monkeypatch):
    async def runner(_):
        raise RuntimeError(SYNTHETIC_SECRET)

    original = TaskUpdater.update_status

    async def broken_status(self, state, *args, **kwargs):
        if state == TaskState.TASK_STATE_FAILED:
            raise ValueError(SYNTHETIC_SECRET)
        return await original(self, state, *args, **kwargs)

    monkeypatch.setattr(TaskUpdater, "update_status", broken_status)
    with pytest.raises(RuntimeError) as error:
        asyncio.run(ReviewExecutor(runner).execute(context(), RecordingEvents()))
    assert SYNTHETIC_SECRET not in str(error.value)
    assert error.value.__suppress_context__


def test_cancellation_propagates_without_completed_event():
    async def runner(_):
        raise asyncio.CancelledError()

    events = RecordingEvents()
    with pytest.raises(asyncio.CancelledError):
        asyncio.run(ReviewExecutor(runner).execute(context(), events))
    assert all(getattr(event, "status", None) is None or
               event.status.state != TaskState.TASK_STATE_COMPLETED for event in events.events)


def test_busy_worker_rejects_second_task_without_invoking_it():
    async def run():
        entered, release = asyncio.Event(), asyncio.Event()
        received = []

        async def runner(prompt):
            received.append(prompt)
            entered.set()
            await release.wait()
            return "synthetic answer"

        executor = ReviewExecutor(runner)
        first, second = RecordingEvents(), RecordingEvents()
        task = asyncio.create_task(executor.execute(context(), first))
        try:
            await asyncio.wait_for(entered.wait(), TEST_DEADLINE_SECONDS)
            await asyncio.wait_for(executor.execute(context(), second), TEST_DEADLINE_SECONDS)
            assert second.events[-1].status.state == TaskState.TASK_STATE_FAILED
            assert len(received) == 1
        finally:
            release.set()
            await task
        assert first.events[-1].status.state == TaskState.TASK_STATE_COMPLETED
    asyncio.run(run())


class YieldingEvents(RecordingEvents):
    async def enqueue_event(self, event):
        await asyncio.sleep(0)
        await super().enqueue_event(event)


def test_simultaneous_tasks_reject_the_second_instead_of_queueing_it():
    async def run():
        received = []

        async def runner(prompt):
            received.append(prompt)
            await asyncio.sleep(0)
            return "synthetic answer"

        executor = ReviewExecutor(runner)
        first, second = YieldingEvents(), YieldingEvents()
        await asyncio.wait_for(asyncio.gather(executor.execute(context(), first),
                                              executor.execute(context(), second)),
                               TEST_DEADLINE_SECONDS)
        states = sorted(events.events[-1].status.state for events in (first, second))
        assert states == sorted([TaskState.TASK_STATE_COMPLETED, TaskState.TASK_STATE_FAILED])
        assert len(received) == 1
    asyncio.run(run())
