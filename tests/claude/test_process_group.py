"""POSIX containment contracts, including real descendants on POSIX hosts."""

import os
import signal
import subprocess
import time
from types import SimpleNamespace

import pytest

from ezz_a2a.claude import process_group
from ezz_a2a.claude.errors import ProcessTreeError
from ezz_a2a.demo.liveness import is_alive
from ezz_a2a.demo.process_tree import LEVEL_COMMAND, ROOT_LEVEL, read_level_pids

EXIT_WAIT_SECONDS = 5
POLL_INTERVAL_SECONDS = 0.05


def test_existing_group_is_killed_on_terminate_and_close(monkeypatch):
    killed = []
    monkeypatch.setattr(os, "getpgid", lambda pid: pid, raising=False)
    monkeypatch.setattr(os, "killpg", lambda *args: killed.append(args), raising=False)
    monkeypatch.setattr(signal, "SIGKILL", 9, raising=False)
    tree = process_group.contain_process_group(4242)
    tree.terminate()
    tree.close()
    assert killed == [(4242, 9), (4242, 9)]


def test_refuses_a_process_in_another_group(monkeypatch):
    monkeypatch.setattr(os, "getpgid", lambda pid: 100, raising=False)
    with pytest.raises(ProcessTreeError, match="leader"):
        process_group.contain_process_group(4242)


def test_missing_process_fails_closed(monkeypatch):
    def missing(pid):
        raise ProcessLookupError(3, "gone")

    monkeypatch.setattr(os, "getpgid", missing, raising=False)
    with pytest.raises(ProcessTreeError, match="getpgid"):
        process_group.contain_process_group(4242)


@pytest.mark.parametrize("states", ["4242 S\n", "4242 Z\n4242 S\n", ""])
def test_permission_error_is_reported_unless_group_is_zombie_only(monkeypatch, states):
    monkeypatch.setattr(os, "getpgid", lambda pid: pid, raising=False)
    monkeypatch.setattr(signal, "SIGKILL", 9, raising=False)

    def denied(*args):
        raise PermissionError(1, "synthetic denial")

    monkeypatch.setattr(os, "killpg", denied, raising=False)
    monkeypatch.setattr(subprocess, "run",
                        lambda *a, **k: SimpleNamespace(stdout=states), raising=False)
    tree = process_group.contain_process_group(4242)
    with pytest.raises(ProcessTreeError):
        tree.close()


def test_zombie_only_group_permission_error_is_harmless(monkeypatch):
    monkeypatch.setattr(os, "getpgid", lambda pid: pid, raising=False)
    monkeypatch.setattr(signal, "SIGKILL", 9, raising=False)

    def denied(*args):
        raise PermissionError(1, "synthetic zombie group")

    monkeypatch.setattr(os, "killpg", denied, raising=False)
    monkeypatch.setattr(subprocess, "run", lambda *a, **k:
                        SimpleNamespace(stdout="4242 Z\n4242 Z+\n5000 S\n"), raising=False)
    process_group.contain_process_group(4242).close()


@pytest.mark.parametrize("inspection_error", [FileNotFoundError(),
                                            subprocess.TimeoutExpired("ps", 5)])
def test_unavailable_process_inspection_does_not_hide_denial(monkeypatch, inspection_error):
    monkeypatch.setattr(os, "getpgid", lambda pid: pid, raising=False)
    monkeypatch.setattr(signal, "SIGKILL", 9, raising=False)

    def denied(*args):
        raise PermissionError(1, "synthetic denial")

    def unavailable(*args, **kwargs):
        raise inspection_error

    monkeypatch.setattr(os, "killpg", denied, raising=False)
    monkeypatch.setattr(subprocess, "run", unavailable)
    with pytest.raises(ProcessTreeError):
        process_group.contain_process_group(4242).close()


@pytest.mark.skipif(os.name == "nt", reason="Requires POSIX process groups")
@pytest.mark.parametrize("ending", ["terminate", "close"])
def test_ending_group_kills_real_descendants(ending):
    parent = subprocess.Popen([*LEVEL_COMMAND, str(ROOT_LEVEL)], stdout=subprocess.PIPE,
                              text=True, start_new_session=True)
    tree = process_group.contain_process_group(parent.pid)
    try:
        descendants = read_level_pids(parent)
        assert all(is_alive(pid) for pid in descendants)
        getattr(tree, ending)()
        parent.wait(timeout=EXIT_WAIT_SECONDS)
        deadline = time.monotonic() + EXIT_WAIT_SECONDS
        while any(is_alive(pid) for pid in descendants) and time.monotonic() < deadline:
            time.sleep(POLL_INTERVAL_SECONDS)
        assert not any(is_alive(pid) for pid in descendants)
    finally:
        tree.close()
        parent.wait(timeout=EXIT_WAIT_SECONDS)
        parent.stdout.close()
