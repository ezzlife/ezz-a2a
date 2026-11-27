"""Runner cleanup and cancellation regressions without launching Claude."""

import asyncio
import tempfile
from contextlib import contextmanager

import pytest

from ezz_a2a.claude.runner import ClaudeRunner, ClaudeUnavailable
from test_claude_runner import SyntheticProcess

TEST_DEADLINE_SECONDS = 1
FORCED_TIMEOUT_SECONDS = 0.01


def test_a2a_token_is_not_inherited_but_subscription_oauth_is_preserved(monkeypatch):
    monkeypatch.setenv("A2A_TOKEN", "synthetic-transport-secret")
    monkeypatch.setenv("CLAUDE_CODE_OAUTH_TOKEN", "synthetic-subscription-token")
    received = {}

    async def spawn(*args, **kwargs):
        received.update(kwargs["env"])
        return SyntheticProcess(b'{"result":"synthetic result"}')

    monkeypatch.setattr(asyncio, "create_subprocess_exec", spawn)
    assert asyncio.run(ClaudeRunner("claude.exe", "model", True)("Context")) == "synthetic result"
    assert "A2A_TOKEN" not in received
    assert received["CLAUDE_CODE_OAUTH_TOKEN"] == "synthetic-subscription-token"


@pytest.mark.parametrize("variable", ["ANTHROPIC_BASE_URL", "CLAUDE_CODE_USE_BEDROCK"])
def test_alternative_provider_fails_before_spawning_without_value(monkeypatch, variable):
    monkeypatch.setenv(variable, "synthetic-provider-value")
    spawned = []

    async def spawn(*args, **kwargs):
        spawned.append(True)
        return SyntheticProcess(b'{"result":"must not run"}')

    monkeypatch.setattr(asyncio, "create_subprocess_exec", spawn)
    with pytest.raises(ClaudeUnavailable) as error:
        asyncio.run(ClaudeRunner("claude.exe", "model", True)("Context"))
    assert not spawned
    assert variable in str(error.value)
    assert "synthetic-provider-value" not in str(error.value)


@pytest.mark.parametrize("timeout", [False, True])
def test_locked_temp_cleanup_does_not_replace_answer_or_timeout(monkeypatch, timeout):
    original_directory = tempfile.TemporaryDirectory

    @contextmanager
    def locked_directory(*args, **kwargs):
        ignore_cleanup_errors = kwargs.get("ignore_cleanup_errors", False)
        with original_directory(*args, **kwargs) as directory:
            try:
                yield directory
            finally:
                if not ignore_cleanup_errors:
                    raise PermissionError("synthetic locked descendant")

    class Process(SyntheticProcess):
        async def communicate(self, prompt=None):
            if timeout and not self.killed:
                await asyncio.Event().wait()
            return await super().communicate(prompt)

    process = Process(b'{"result":"paid synthetic answer"}', returncode=None)

    async def spawn(*args, **kwargs):
        return process

    monkeypatch.setattr(tempfile, "TemporaryDirectory", locked_directory)
    monkeypatch.setattr(asyncio, "create_subprocess_exec", spawn)
    runner = ClaudeRunner("claude.exe", "model", True, timeout_seconds=FORCED_TIMEOUT_SECONDS)
    if timeout:
        with pytest.raises(asyncio.TimeoutError):
            asyncio.run(runner("Context"))
        assert process.killed
    else:
        assert asyncio.run(runner("Context")) == "paid synthetic answer"


def test_cancelled_invocation_kills_process_and_propagates(monkeypatch):
    async def run():
        entered = asyncio.Event()

        class Process(SyntheticProcess):
            async def communicate(self, prompt=None):
                if not self.killed:
                    entered.set()
                    await asyncio.Event().wait()
                return b"", b""

        process = Process(b"", returncode=None)

        async def spawn(*args, **kwargs):
            return process

        monkeypatch.setattr(asyncio, "create_subprocess_exec", spawn)
        task = asyncio.create_task(ClaudeRunner("claude.exe", "model", True)("Context"))
        await asyncio.wait_for(entered.wait(), TEST_DEADLINE_SECONDS)
        task.cancel()
        with pytest.raises(asyncio.CancelledError):
            await asyncio.wait_for(task, TEST_DEADLINE_SECONDS)
        assert process.killed
    asyncio.run(run())
