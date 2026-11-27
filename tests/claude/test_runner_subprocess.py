"""Real subprocess lifecycle through the runner; no Claude call or quota."""

import asyncio
import json
import sys
import time

import pytest

from ezz_a2a.claude import runner as runner_module
from ezz_a2a.claude.process_tree import contain_process_tree
from ezz_a2a.claude.runner import ClaudeRunner
from ezz_a2a.demo.liveness import is_alive, terminate

TIMEOUT_CASE_SECONDS = 5
RUNNER_DEADLINE_SECONDS = 15
STARTUP_DEADLINE_SECONDS = 10
EXIT_WAIT_SECONDS = 5
POLL_INTERVAL_SECONDS = 0.05

CLI_SCRIPT = """
import json, os, subprocess, sys, time
from pathlib import Path
prompt = sys.stdin.buffer.read().decode('utf-8')
# Let Windows assign the root to its Job Object before it creates descendants.
CHILD_SPAWN_DELAY_SECONDS = 0.5
PROCESS_LIFETIME_SECONDS = 60
time.sleep(CHILD_SPAWN_DELAY_SECONDS)
child = subprocess.Popen([sys.executable, '-c',
                          f'import time; time.sleep({PROCESS_LIFETIME_SECONDS})'],
                         stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL,
                         stderr=subprocess.DEVNULL)
Path(sys.argv[1]).write_text(json.dumps([os.getpid(), child.pid]), encoding='utf-8')
if sys.argv[2] == 'success':
    print(json.dumps({'result': prompt}), flush=True)
else:
    time.sleep(PROCESS_LIFETIME_SECONDS)
"""


@pytest.mark.parametrize("ending", ["success", "timeout", "cancel"])
def test_runner_ends_real_descendants(monkeypatch, tmp_path, ending):
    monkeypatch.setattr(runner_module, "contain_process_tree", contain_process_tree)
    script = tmp_path / "synthetic_cli.py"
    script.write_text(CLI_SCRIPT, encoding="utf-8")
    record = tmp_path / "pids.json"

    class SyntheticCLI(ClaudeRunner):
        def _command(self):
            return [sys.executable, str(script), str(record), ending]

    async def run():
        timeout = TIMEOUT_CASE_SECONDS if ending == "timeout" else RUNNER_DEADLINE_SECONDS
        runner = SyntheticCLI(sys.executable, "synthetic", True, timeout_seconds=timeout)
        invocation = asyncio.create_task(runner("Context with Unicode: á日本語"))
        if ending == "cancel":
            deadline = time.monotonic() + STARTUP_DEADLINE_SECONDS
            while not record.exists() or not record.read_text(encoding="utf-8"):
                if invocation.done():
                    await invocation
                    pytest.fail("Runner ended before starting descendants")
                if time.monotonic() >= deadline:
                    invocation.cancel()
                    try:
                        await invocation
                    except asyncio.CancelledError:
                        pass
                    pytest.fail("Synthetic CLI did not become ready")
                await asyncio.sleep(POLL_INTERVAL_SECONDS)
            invocation.cancel()
            with pytest.raises(asyncio.CancelledError):
                await invocation
        elif ending == "timeout":
            with pytest.raises(asyncio.TimeoutError):
                await invocation
        else:
            assert await invocation == "Context with Unicode: á日本語"

    pids = []
    try:
        asyncio.run(run())
        pids = json.loads(record.read_text(encoding="utf-8"))
        deadline = time.monotonic() + EXIT_WAIT_SECONDS
        while any(is_alive(pid) for pid in pids) and time.monotonic() < deadline:
            time.sleep(POLL_INTERVAL_SECONDS)
        assert not any(is_alive(pid) for pid in pids)
    finally:
        if not pids and record.exists():
            pids = json.loads(record.read_text(encoding="utf-8"))
        for pid in pids:
            if is_alive(pid):
                terminate(pid)
