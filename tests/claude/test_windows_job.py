"""Job Object containment with a real process tree; no Claude involved."""

import os
import subprocess
import sys
import time

import pytest

from ezz_a2a.claude.errors import ProcessTreeError
from ezz_a2a.claude.process_tree import SPAWN_OPTIONS
from ezz_a2a.claude.windows_job import contain_with_job_object as contain_process_tree

pytestmark = pytest.mark.skipif(os.name != "nt", reason="Job Objects exist only on Windows")

GRANDCHILD_STARTUP_SECONDS = 10
EXIT_WAIT_SECONDS = 5
POLL_INTERVAL_SECONDS = 0.1
PROCESS_LIFETIME_SECONDS = 60
LOOP_STALL_SECONDS = 0.5  # longer than the child needs to start its grandchild
NONEXISTENT_PID = 2 ** 32 - 4  # Highest DWORD multiple of 4; never assigned.
# The child starts a long-lived grandchild, records its PID and keeps running.
PARENT_SCRIPT = (
    "import subprocess, sys, time\n"
    f"grandchild = subprocess.Popen([sys.executable, '-c', 'import time; time.sleep({PROCESS_LIFETIME_SECONDS})'])\n"
    "open(sys.argv[1], 'w').write(str(grandchild.pid))\n"
    f"time.sleep({PROCESS_LIFETIME_SECONDS})\n"
)


def is_running(pid: int) -> bool:
    listing = subprocess.run(["tasklist", "/FI", f"PID eq {pid}", "/NH"],
                             capture_output=True, text=True, check=True).stdout
    return str(pid) in listing


def wait_until(condition, seconds):
    deadline = time.monotonic() + seconds
    while not condition():
        if time.monotonic() >= deadline:
            return False
        time.sleep(POLL_INTERVAL_SECONDS)
    return True


def start_tree(tmp_path):
    record = tmp_path / "grandchild.pid"
    parent = subprocess.Popen([sys.executable, "-c", PARENT_SCRIPT, str(record)])
    tree = contain_process_tree(parent.pid)
    assert wait_until(lambda: record.exists() and record.read_text(), GRANDCHILD_STARTUP_SECONDS)
    return parent, tree, int(record.read_text())


@pytest.mark.parametrize("ending", ["terminate", "close"])
def test_ending_the_job_kills_grandchildren_not_only_the_child(tmp_path, ending):
    parent, tree, grandchild = start_tree(tmp_path)
    try:
        assert is_running(grandchild)
        getattr(tree, ending)()
        parent.wait(timeout=EXIT_WAIT_SECONDS)
        assert wait_until(lambda: not is_running(grandchild), EXIT_WAIT_SECONDS)
    finally:
        tree.close()
        if parent.poll() is None:
            parent.kill()


def test_a_child_started_like_the_runner_cannot_escape_while_the_loop_stalls(tmp_path):
    record = tmp_path / "grandchild.pid"
    parent = subprocess.Popen([sys.executable, "-c", PARENT_SCRIPT, str(record)], **SPAWN_OPTIONS)
    time.sleep(LOOP_STALL_SECONDS)  # another task holding the event loop before containment
    tree = contain_process_tree(parent.pid)
    try:
        assert wait_until(lambda: record.exists() and record.read_text(), GRANDCHILD_STARTUP_SECONDS)
        grandchild = int(record.read_text())
        tree.terminate()
        parent.wait(timeout=EXIT_WAIT_SECONDS)
        assert wait_until(lambda: not is_running(grandchild), EXIT_WAIT_SECONDS)
    finally:
        tree.close()
        if parent.poll() is None:
            parent.kill()
        if record.exists() and record.read_text():
            subprocess.run(["taskkill", "/F", "/PID", record.read_text()], capture_output=True)


def test_unknown_process_fails_closed():
    with pytest.raises(ProcessTreeError):
        contain_process_tree(NONEXISTENT_PID)
