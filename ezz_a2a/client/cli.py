"""Send a text file to a running worker and print the A2A responses as JSON."""

import argparse
import asyncio
import os
import sys
from pathlib import Path

import httpx
from google.protobuf.json_format import MessageToJson

from ezz_a2a.client.send import CLIENT_TIMEOUT_SECONDS, completed_task, send_task
from ezz_a2a.settings import DEFAULT_PORT, EXIT_FAILURE, LOCAL_HOST


async def _run(token: str, port: int, prompt: str) -> None:
    async with httpx.AsyncClient(
        headers={"Authorization": f"Bearer {token}"}, timeout=CLIENT_TIMEOUT_SECONDS,
        trust_env=False,
    ) as http_client:
        results = await send_task(http_client, f"http://{LOCAL_HOST}:{port}", prompt)
    for result in results:
        print(MessageToJson(result))
    if completed_task(results) is None:
        raise SystemExit(EXIT_FAILURE)


def main():
    sys.stdout.reconfigure(errors="replace")
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("task_file", type=Path)
    parser.add_argument("--port", type=int, default=DEFAULT_PORT)
    args = parser.parse_args()
    token = os.environ.get("A2A_TOKEN", "")
    if not token.strip():
        parser.error("A2A_TOKEN is required")
    asyncio.run(_run(token, args.port, args.task_file.read_text(encoding="utf-8")))
