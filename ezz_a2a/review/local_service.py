"""Own the lifetime of a separate localhost A2A server process."""

import os
import queue
import secrets
import subprocess
import sys
import threading
import time
from contextlib import contextmanager

import httpx

from ezz_a2a.settings import EPHEMERAL_PORT, LOCAL_HOST, PORT_ANNOUNCEMENT_PREFIX

STARTUP_TIMEOUT_SECONDS = 15
READINESS_INTERVAL_SECONDS = 0.1
SHUTDOWN_TIMEOUT_SECONDS = 5
CONNECT_TIMEOUT_SECONDS = 1
AGENT_CARD_PATH = "/.well-known/agent-card.json"
SERVER_EXITED = "A2A server exited before becoming available"


def _announced_ports(server_stdout) -> queue.Queue:
    """Drain the server stdout in the background; queue every announced port."""
    ports = queue.Queue()

    def drain():
        for line in server_stdout:
            if line.startswith(PORT_ANNOUNCEMENT_PREFIX):
                ports.put(int(line.removeprefix(PORT_ANNOUNCEMENT_PREFIX)))

    threading.Thread(target=drain, daemon=True).start()
    return ports


def _wait_for_port(process, ports: queue.Queue, deadline: float) -> int:
    while True:
        if process.poll() is not None:
            raise RuntimeError(SERVER_EXITED)
        try:
            return ports.get(timeout=READINESS_INTERVAL_SECONDS)
        except queue.Empty:
            if time.monotonic() >= deadline:
                raise TimeoutError("A2A server did not announce its port in time")


def _wait_until_serving(process, base_url: str, token: str, deadline: float) -> None:
    headers = {"Authorization": f"Bearer {token}"}
    with httpx.Client(headers=headers, trust_env=False,
                      timeout=CONNECT_TIMEOUT_SECONDS) as client:
        while True:
            if process.poll() is not None:
                raise RuntimeError(SERVER_EXITED)
            try:
                client.get(base_url + AGENT_CARD_PATH).raise_for_status()
                return
            except httpx.TransportError:
                if time.monotonic() >= deadline:
                    raise TimeoutError("A2A server did not start in time")
                time.sleep(READINESS_INTERVAL_SECONDS)


def _server_command(model: str, executable: str | None, enabled: bool) -> list[str]:
    command = [sys.executable, "-m", "ezz_a2a.worker",
               "--model", model, "--port", str(EPHEMERAL_PORT)]
    if enabled:
        command.append("--enable-claude")
    if executable:
        command += ["--claude", executable]
    return command


def _stop(process) -> None:
    if process.poll() is None:
        process.terminate()
    try:
        process.wait(timeout=SHUTDOWN_TIMEOUT_SECONDS)
    except subprocess.TimeoutExpired:
        process.kill()
        process.wait()


@contextmanager
def local_service(model: str, executable: str | None = None, enabled: bool = False):
    """Start a worker on a free port; yield (base_url, token, pid) and stop it afterwards."""
    token = secrets.token_urlsafe()
    process = subprocess.Popen(
        _server_command(model, executable, enabled), env=dict(os.environ, A2A_TOKEN=token),
        stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, text=True,
    )
    try:
        deadline = time.monotonic() + STARTUP_TIMEOUT_SECONDS
        port = _wait_for_port(process, _announced_ports(process.stdout), deadline)
        base_url = f"http://{LOCAL_HOST}:{port}"
        _wait_until_serving(process, base_url, token, deadline)
        yield base_url, token, process.pid
    finally:
        _stop(process)
