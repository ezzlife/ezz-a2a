"""Protect subprocess boundaries without invoking Claude or consuming quota."""

import asyncio
import json
from pathlib import Path

import pytest

from ezz_a2a.claude.runner import ClaudeRunner, ClaudeUnavailable

FORCED_TIMEOUT_SECONDS = 0.01


class SyntheticProcess:
    pid = None  # conftest replaces the Job Object, so no real process is needed.

    def __init__(self, response, returncode=0):
        self.response = response
        self.returncode = returncode
        self.prompt = None
        self.killed = False

    async def communicate(self, prompt=None):
        self.prompt = prompt
        return self.response, b"synthetic stderr"

    def kill(self):
        self.killed = True
        self.returncode = -1


def test_prompt_goes_to_stdin_with_tools_disabled(monkeypatch):
    monkeypatch.setenv("ANTHROPIC_API_KEY", "synthetic-key-must-not-be-used")
    monkeypatch.setenv("ANTHROPIC_AUTH_TOKEN", "synthetic-token-must-not-be-used")
    process = SyntheticProcess(json.dumps({"result": "Review result"}).encode())
    captured = {}

    async def spawn(*command, **kwargs):
        captured.update(command=command, directory=kwargs["cwd"])
        assert Path(kwargs["cwd"]).is_dir()
        assert "ANTHROPIC_API_KEY" not in kwargs["env"]
        assert "ANTHROPIC_AUTH_TOKEN" not in kwargs["env"]
        return process

    monkeypatch.setattr(asyncio, "create_subprocess_exec", spawn)
    answer = asyncio.run(ClaudeRunner("claude.exe", "chosen-model", True)("Context"))
    assert answer == "Review result"
    assert process.prompt == b"Context"
    command = captured["command"]
    assert "Context" not in command
    assert command[command.index("--tools") + 1] == ""
    assert "--safe-mode" in command
    assert command[command.index("--setting-sources") + 1] == ""
    assert command[command.index("--model") + 1] == "chosen-model"
    assert not Path(captured["directory"]).exists()


@pytest.mark.parametrize("response,returncode", [
    (b"not json", 0), (b"[]", 0),
    (b'{"is_error": true, "result": "quota"}', 0),
    (b'{"result": "partial"}', 1), (b'{"result": ""}', 0),
])
def test_invalid_or_failed_result_is_not_reported_as_success(monkeypatch, response, returncode):
    async def spawn(*args, **kwargs):
        return SyntheticProcess(response, returncode)

    monkeypatch.setattr(asyncio, "create_subprocess_exec", spawn)
    with pytest.raises(ClaudeUnavailable):
        asyncio.run(ClaudeRunner("claude.exe", "model", True)("Context"))


def test_cli_exit_code_is_diagnosed_before_parsing_output(monkeypatch):
    async def spawn(*args, **kwargs):
        return SyntheticProcess(b"Error: synthetic login expired", returncode=1)

    monkeypatch.setattr(asyncio, "create_subprocess_exec", spawn)
    with pytest.raises(ClaudeUnavailable, match="code 1") as error:
        asyncio.run(ClaudeRunner("claude.exe", "model", True)("Context"))
    assert "synthetic login" not in str(error.value)


def test_timeout_kills_and_reaps_worker(monkeypatch):
    class StalledProcess(SyntheticProcess):
        async def communicate(self, prompt=None):
            if not self.killed:
                await asyncio.Event().wait()
            return b"", b""

    process = StalledProcess(b"", returncode=None)

    async def spawn(*args, **kwargs):
        return process

    monkeypatch.setattr(asyncio, "create_subprocess_exec", spawn)
    with pytest.raises(asyncio.TimeoutError):
        asyncio.run(ClaudeRunner("claude.exe", "model", True,
                                 timeout_seconds=FORCED_TIMEOUT_SECONDS)("Context"))
    assert process.killed
