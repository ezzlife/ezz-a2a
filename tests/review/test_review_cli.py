"""CLI preflight, exit contracts and durable output after real task responses."""

import io
import json
import sys
from contextlib import contextmanager
from pathlib import Path

import pytest
from a2a.helpers import new_text_part
from a2a.types import Artifact, Task, TaskState, TaskStatus

from ezz_a2a.review import cli as review


@pytest.fixture
def case(tmp_path, monkeypatch):
    source = tmp_path / "src/source.py"
    source.parent.mkdir(parents=True)
    source.write_bytes(b"value = 1\n")
    task = tmp_path / "task.json"
    task.write_text(json.dumps({
        "id": "synthetic", "objective": "Review", "base_commit": "synthetic",
        "dependencies": [], "files": ["src/source.py"],
        "acceptance": ["No edits"], "checks": [],
    }), encoding="utf-8")
    output = tmp_path / "output.json"
    monkeypatch.setattr(sys, "argv", ["review.py", str(task), "--model", "unused",
                                     "--repository", str(tmp_path), "--output", str(output)])
    stream = io.TextIOWrapper(io.BytesIO(), encoding="cp1252", write_through=True)
    monkeypatch.setattr(sys, "stdout", stream)

    @contextmanager
    def synthetic_service(*args, **kwargs):
        yield "http://127.0.0.1:9130", "synthetic-token", 123

    async def result(*args, **kwargs):
        return [Task(id="synthetic-task", status=TaskStatus(state=TaskState.TASK_STATE_COMPLETED),
                     artifacts=[Artifact(parts=[new_text_part("Unicode: ≠ 漢字")])])]

    monkeypatch.setattr(review, "local_service", synthetic_service)
    monkeypatch.setattr(review, "send_task", result)
    return output, stream


def test_missing_executable_is_preflight_error_without_traceback(case, monkeypatch):
    output, _ = case
    monkeypatch.setattr(sys, "argv", sys.argv + ["--enable-claude", "--claude", "missing-binary"])
    with pytest.raises(SystemExit) as error:
        review.main()
    assert error.value.code == 2
    assert not output.exists()


def test_unwritable_evidence_directory_fails_before_starting_service(case, monkeypatch):
    output, _ = case
    original_open = Path.open
    started = []

    def blocked(path, *args, **kwargs):
        if path.suffix == ".pending":
            raise PermissionError("synthetic unwritable directory")
        return original_open(path, *args, **kwargs)

    @contextmanager
    def forbidden_service(*args, **kwargs):
        started.append(True)
        yield "http://127.0.0.1:9130", "token", 123

    monkeypatch.setattr(Path, "open", blocked)
    monkeypatch.setattr(review, "local_service", forbidden_service)
    with pytest.raises(SystemExit) as error:
        review.main()
    assert error.value.code == 2
    assert not started
    assert not output.exists()


def test_publication_failure_keeps_result_and_returns_distinct_exit(case, monkeypatch, capsys):
    output, _ = case

    def unsupported(*args):
        raise OSError("synthetic unsupported hardlinks")

    monkeypatch.setattr("ezz_a2a.review.evidence.os.link", unsupported)
    assert review.main() == 3
    pending = list(output.parent.glob("*.pending"))
    assert len(pending) == 1
    evidence = json.loads(pending[0].read_text(encoding="utf-8"))
    assert evidence["responses"][0]["artifacts"][0]["parts"][0]["text"] == "Unicode: ≠ 漢字"
    assert str(pending[0]) in capsys.readouterr().err
    assert not output.exists()


def test_alternative_provider_is_preflight_error_without_value(case, monkeypatch, capsys):
    output, _ = case
    monkeypatch.setenv("ANTHROPIC_BASE_URL", "https://synthetic-proxy.invalid")
    monkeypatch.setattr(review, "resolve_claude_executable", lambda explicit: "claude.exe")
    monkeypatch.setattr(sys, "argv", sys.argv + ["--enable-claude"])
    with pytest.raises(SystemExit) as error:
        review.main()
    assert error.value.code == 2
    assert "synthetic-proxy" not in capsys.readouterr().err
    assert not output.exists()


def test_service_teardown_error_after_completion_is_not_success(case, monkeypatch):
    output, _ = case

    @contextmanager
    def failing_teardown(*args, **kwargs):
        yield "http://127.0.0.1:9130", "synthetic-token", 123
        raise RuntimeError("synthetic teardown failure")

    monkeypatch.setattr(review, "local_service", failing_teardown)
    assert review.main() == 1
    evidence = json.loads(output.read_text(encoding="utf-8"))
    assert evidence["execution_error"] == "RuntimeError"
    assert evidence["responses"][0]["artifacts"][0]["parts"][0]["text"] == "Unicode: ≠ 漢字"


def test_console_failure_does_not_lose_paid_answer(case, monkeypatch):
    output, _ = case

    class ClosedPipe(io.TextIOWrapper):
        def write(self, text):
            raise BrokenPipeError("synthetic closed consumer")

    monkeypatch.setattr(sys, "stdout", ClosedPipe(io.BytesIO(), encoding="utf-8"))
    with pytest.raises(BrokenPipeError):
        review.main()
    evidence = json.loads(output.read_text(encoding="utf-8"))
    assert evidence["responses"][0]["artifacts"][0]["parts"][0]["text"] == "Unicode: ≠ 漢字"


def test_interrupt_is_saved_and_reported_as_interrupted(case, monkeypatch):
    output, _ = case

    async def interrupted(*args, **kwargs):
        raise KeyboardInterrupt

    monkeypatch.setattr(review, "send_task", interrupted)
    assert review.main() == review.EXIT_INTERRUPTED
    assert json.loads(output.read_text(encoding="utf-8"))["execution_error"] == "KeyboardInterrupt"


def test_completed_unicode_response_prints_safely_and_preserves_utf8(case, monkeypatch):
    output, stream = case
    monkeypatch.setattr(sys, "stdout", stream)
    assert review.main() == 0
    stream.flush()
    assert "COMPLETED" in stream.buffer.getvalue().decode("cp1252")
    evidence = json.loads(output.read_text(encoding="utf-8"))
    assert evidence["responses"][0]["artifacts"][0]["parts"][0]["text"] == "Unicode: ≠ 漢字"
