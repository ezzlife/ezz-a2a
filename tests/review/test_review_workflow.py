"""Review scope, native discovery and separate-process HTTP regressions."""

import asyncio
import hashlib
import json
import os
import sys
from io import BytesIO, TextIOWrapper

import httpx
import pytest
from a2a.types import Message, Task, TaskState, TaskStatus

from ezz_a2a.claude.executable import resolve_claude_executable
from ezz_a2a.client.send import completed_task, send_task
from ezz_a2a.review.local_service import local_service
from ezz_a2a.review.task import prepare_review

CONNECT_TIMEOUT_SECONDS = 1


def test_npm_launcher_resolves_to_native_binary(tmp_path, monkeypatch):
    monkeypatch.setattr("ezz_a2a.claude.executable.IS_WINDOWS", True)
    launcher = tmp_path / "claude.cmd"
    launcher.write_text("launcher", encoding="utf-8")
    native = tmp_path / "node_modules/@anthropic-ai/claude-code/bin/claude.exe"
    native.parent.mkdir(parents=True)
    native.write_bytes(b"synthetic executable")
    monkeypatch.setattr("ezz_a2a.claude.executable.shutil.which", lambda _: str(launcher))
    assert resolve_claude_executable() == str(native.resolve())


def test_explicit_launcher_is_rejected(tmp_path):
    launcher = tmp_path / "claude.cmd"
    launcher.write_text("launcher", encoding="utf-8")
    with pytest.raises(FileNotFoundError):
        resolve_claude_executable(str(launcher))


def write_task(tmp_path, files):
    task = tmp_path / "task.json"
    task.write_text(json.dumps({
        "id": "synthetic", "objective": "Review", "base_commit": "synthetic",
        "dependencies": [], "files": files, "acceptance": ["No edits"], "checks": [],
    }), encoding="utf-8")
    return task


@pytest.mark.parametrize("name", ["../outside.py", ".env", "private.db"])
def test_invalid_scope_rejected_before_sending(tmp_path, name):
    with pytest.raises(ValueError):
        prepare_review(write_task(tmp_path, [name]), tmp_path)


def test_source_snapshot_contains_exact_context_and_digest(tmp_path):
    source = tmp_path / "src/example.py"
    source.parent.mkdir(parents=True)
    source.write_bytes(b"value = 42\n")
    task, sources, _, prompt = prepare_review(write_task(tmp_path, ["src/example.py"]), tmp_path)
    assert sources[0]["content"] == "value = 42\n"
    assert sources[0]["sha256"] == hashlib.sha256(b"value = 42\n").hexdigest()
    assert "value = 42" in prompt
    assert task["id"] == "synthetic"


@pytest.mark.parametrize("state", [TaskState.TASK_STATE_FAILED, TaskState.TASK_STATE_CANCELED,
                                   TaskState.TASK_STATE_WORKING, TaskState.TASK_STATE_INPUT_REQUIRED])
def test_only_completed_tasks_are_successful(state):
    assert completed_task([Task(status=TaskStatus(state=state))]) is None


def test_empty_results_and_direct_messages_are_not_completed_reviews():
    assert completed_task([]) is None
    assert completed_task([Message()]) is None


def test_real_http_server_in_separate_process_without_claude():
    async def run(url, token):
        async with httpx.AsyncClient(
            headers={"Authorization": f"Bearer {token}"}, trust_env=False,
        ) as client:
            return await send_task(client, url, "Synthetic disabled quota check")

    with local_service("unused-model") as (url, token, pid):
        assert pid != os.getpid()
        task = asyncio.run(run(url, token))[-1]
        assert task.status.state == TaskState.TASK_STATE_FAILED
        assert not task.artifacts
    with httpx.Client(trust_env=False) as client:
        with pytest.raises(httpx.TransportError):
            client.get(url, timeout=CONNECT_TIMEOUT_SECONDS)


def test_review_saves_transport_failure_as_evidence(tmp_path, monkeypatch):
    from ezz_a2a.review.cli import main

    source = tmp_path / "src/source.py"
    source.parent.mkdir(parents=True)
    source.write_bytes(b"value = 1\n")
    task_file = write_task(tmp_path, ["src/source.py"])
    output = tmp_path / "evidence.json"

    def failed_service(*args, **kwargs):
        raise RuntimeError("synthetic failure with sensitive details")

    monkeypatch.setattr("ezz_a2a.review.cli.local_service", failed_service)
    monkeypatch.setattr(sys, "argv", ["review.py", str(task_file), "--model", "unused",
                                     "--repository", str(tmp_path), "--output", str(output)])
    monkeypatch.setattr(sys, "stdout", TextIOWrapper(BytesIO(), encoding="cp1252"))
    assert main() == 1
    evidence = json.loads(output.read_text(encoding="utf-8"))
    assert evidence["execution_error"] == "RuntimeError"
    assert "sensitive details" not in output.read_text(encoding="utf-8")
    assert evidence["accepted_by_coordinator"] is False
