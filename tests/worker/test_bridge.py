"""A2A contract tests: real SDK and HTTP transport, no Claude or external network."""

import asyncio

import httpx
import pytest
from a2a.types import TaskState
from google.protobuf.json_format import MessageToDict

from ezz_a2a.claude.runner import ClaudeRunner, ClaudeUnavailable
from ezz_a2a.claude.usage import ClaudeReply
from ezz_a2a.client.send import send_task
from ezz_a2a.settings import MAX_PROMPT_CHARACTERS
from ezz_a2a.worker.app import create_app

TEST_TOKEN = "synthetic-test-token"
BASE_URL = "http://127.0.0.1:9130"


def invoke(runner, prompt="Review this synthetic context."):
    async def run():
        app = create_app(runner, TEST_TOKEN)
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=app), base_url=BASE_URL,
            headers={"Authorization": f"Bearer {TEST_TOKEN}"},
        ) as http_client:
            return await send_task(http_client, BASE_URL, prompt)
    return asyncio.run(run())


def test_sdk_discovery_and_completed_artifact():
    received = []

    async def runner(prompt):
        received.append(prompt)
        return "Synthetic finding with evidence."

    results = invoke(runner)
    task = results[-1]
    assert task.status.state == TaskState.TASK_STATE_COMPLETED
    assert task.artifacts[0].parts[0].text == "Synthetic finding with evidence."
    assert received == ["Review this synthetic context."]


def test_disabled_claude_fails_without_starting_process(monkeypatch):
    async def forbidden(*args, **kwargs):
        pytest.fail("Must not start a process with Claude disabled")

    monkeypatch.setattr(asyncio, "create_subprocess_exec", forbidden)
    results = invoke(ClaudeRunner("missing-claude", "explicit-model"))
    assert results[-1].status.state == TaskState.TASK_STATE_FAILED
    assert not results[-1].artifacts


@pytest.mark.parametrize("prompt", [" ", "x" * (MAX_PROMPT_CHARACTERS + 1)])
def test_invalid_context_never_invokes_worker(prompt):
    async def forbidden(_):
        pytest.fail("Invalid context must not consume quota")

    assert invoke(forbidden, prompt)[-1].status.state == TaskState.TASK_STATE_FAILED


def test_authentication_rejects_request_before_execution():
    async def forbidden(_):
        pytest.fail("A request without a token must not run Claude")

    async def run():
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=create_app(forbidden, TEST_TOKEN)),
            base_url=BASE_URL,
        ) as http_client:
            assert (await http_client.get("/.well-known/agent-card.json")).status_code == 401
            assert (await http_client.post("/", json={})).status_code == 401
    asyncio.run(run())


def test_worker_failure_has_no_success_artifact():
    async def runner(_):
        raise ClaudeUnavailable("synthetic quota failure")

    task = invoke(runner)[-1]
    assert task.status.state == TaskState.TASK_STATE_FAILED
    assert not task.artifacts


def test_metrics_travel_in_artifact_metadata_without_changing_the_text():
    metrics = {"input_tokens": 7, "output_tokens": None, "model": "synthetic-model"}

    async def runner(_):
        return ClaudeReply("Synthetic finding.", metrics)

    artifact = invoke(runner)[-1].artifacts[0]
    assert artifact.parts[0].text == "Synthetic finding."
    assert MessageToDict(artifact)["metadata"] == metrics
