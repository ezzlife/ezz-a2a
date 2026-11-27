"""Local A2A 1.0 review worker: serves the Agent Card and runs Claude on supplied context."""

import argparse
import os
import socket

import uvicorn

from ezz_a2a.claude.executable import resolve_claude_executable
from ezz_a2a.claude.runner import ClaudeRunner, ClaudeUnavailable, validate_provider_environment
from ezz_a2a.settings import DEFAULT_PORT, LOCAL_HOST, PORT_ANNOUNCEMENT_PREFIX
from ezz_a2a.worker.app import create_app


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--port", type=int, default=DEFAULT_PORT)
    parser.add_argument("--claude")
    parser.add_argument("--model", required=True)
    parser.add_argument("--enable-claude", action="store_true")
    args = parser.parse_args()
    if args.enable_claude:
        try:
            validate_provider_environment()
        except ClaudeUnavailable as error:
            parser.error(str(error))
    executable = resolve_claude_executable(args.claude) if args.enable_claude else "claude"
    runner = ClaudeRunner(executable, args.model, enabled=args.enable_claude)
    # Bind before announcing: with --port 0 no other process can take the port
    # between choosing it and serving, so the bearer only reaches this server.
    listener = socket.socket()
    listener.bind((LOCAL_HOST, args.port))
    port = listener.getsockname()[1]
    app = create_app(runner, os.environ.get("A2A_TOKEN", ""), port)
    print(f"{PORT_ANNOUNCEMENT_PREFIX}{port}", flush=True)
    uvicorn.Server(uvicorn.Config(app, access_log=False)).run(sockets=[listener])
