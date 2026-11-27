"""The runner ends Claude's whole process tree, not only claude.exe."""

import asyncio

import pytest

from ezz_a2a.claude import runner as claude_runner
from ezz_a2a.claude.runner import ClaudeRunner, ClaudeUnavailable
from test_claude_runner import SyntheticProcess
from ezz_a2a.claude.errors import ProcessTreeError

SYNTHETIC_PID = 4242
FORCED_TIMEOUT_SECONDS = 0.01


class HangingProcess(SyntheticProcess):
    pid = SYNTHETIC_PID

    async def communicate(self, prompt=None):
        if not self.killed:
            await asyncio.Event().wait()
        return b"", b""


def spawning(monkeypatch, process):
    async def spawn(*args, **kwargs):
        return process
    monkeypatch.setattr(asyncio, "create_subprocess_exec", spawn)


def test_success_closes_the_job_so_leftover_descendants_end(monkeypatch, process_trees):
    process = SyntheticProcess(b'{"result":"synthetic result"}')
    process.pid = SYNTHETIC_PID
    spawning(monkeypatch, process)
    assert asyncio.run(ClaudeRunner("claude.exe", "model", True)("Context")) == "synthetic result"
    [tree] = process_trees
    assert tree.pid == SYNTHETIC_PID
    assert tree.events == ["close"]


def test_timeout_terminates_the_whole_tree(monkeypatch, process_trees):
    process = HangingProcess(b"", returncode=None)
    spawning(monkeypatch, process)
    with pytest.raises(asyncio.TimeoutError):
        asyncio.run(ClaudeRunner("claude.exe", "model", True,
                                 timeout_seconds=FORCED_TIMEOUT_SECONDS)("Context"))
    [tree] = process_trees
    assert tree.events == ["terminate", "close"]
    assert process.killed


def test_uncontainable_worker_is_killed_and_never_answers(monkeypatch):
    process = HangingProcess(b"", returncode=None)
    spawning(monkeypatch, process)

    def refuse(pid):
        raise ProcessTreeError(5, "synthetic access denied")

    monkeypatch.setattr(claude_runner, "contain_process_tree", refuse)
    with pytest.raises(ClaudeUnavailable, match="contain"):
        asyncio.run(ClaudeRunner("claude.exe", "model", True)("Context"))
    assert process.killed


def test_cleanup_failure_still_reaps_direct_process(monkeypatch):
    process = HangingProcess(b"", returncode=None)
    spawning(monkeypatch, process)

    class BrokenTree:
        def terminate(self):
            raise ProcessTreeError(1, "synthetic permission failure")

        def close(self):
            pass

    monkeypatch.setattr(claude_runner, "contain_process_tree", lambda pid: BrokenTree())
    with pytest.raises(ProcessTreeError):
        asyncio.run(ClaudeRunner("claude", "model", True,
                                 timeout_seconds=FORCED_TIMEOUT_SECONDS)("Context"))
    assert process.killed
