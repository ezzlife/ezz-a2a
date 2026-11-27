"""Run an explicit review over real localhost HTTP and save evidence."""

import argparse
import asyncio
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

import httpx
from google.protobuf.json_format import MessageToDict

from ezz_a2a.claude.executable import resolve_claude_executable
from ezz_a2a.claude.runner import ClaudeUnavailable, validate_provider_environment
from ezz_a2a.client.send import CLIENT_TIMEOUT_SECONDS, completed_task, send_task
from ezz_a2a.review.evidence import EvidenceStore
from ezz_a2a.review.local_service import local_service
from ezz_a2a.review.task import prepare_review
from ezz_a2a.settings import EXIT_FAILURE, EXIT_SUCCESS

EXIT_COMPLETED = EXIT_SUCCESS
EXIT_EXECUTION_FAILED = EXIT_FAILURE
EXIT_PUBLICATION_FAILED = 3
EXIT_INTERRUPTED = 130  # Conventional shell code for Ctrl-C.


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("task_file", type=Path)
    parser.add_argument("--repository", type=Path, default=Path.cwd())
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--model", required=True)
    parser.add_argument("--claude")
    parser.add_argument("--enable-claude", action="store_true")
    return parser


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _preflight(parser, args):
    """Validate everything that can fail before paying for a review."""
    try:
        task, sources, context, prompt = prepare_review(args.task_file, args.repository)
        executable = None
        if args.enable_claude:
            validate_provider_environment()
            executable = resolve_claude_executable(args.claude)
        store = EvidenceStore(args.output)
    except ClaudeUnavailable as error:
        parser.error(str(error))
    except (ValueError, OSError) as error:
        parser.error(f"Preflight {type(error).__name__}: check task, executable and output")
    evidence = {"task": task, "sources": sources, "context": context, "model": args.model,
                "started_at_utc": _now(), "claude_enabled": args.enable_claude,
                "accepted_by_coordinator": False}
    try:
        store.write(evidence)
    except OSError as error:
        parser.error(f"Preflight {type(error).__name__}: output is not writable")
    return evidence, prompt, executable, store


async def _send(base_url: str, token: str, prompt: str):
    async with httpx.AsyncClient(
        headers={"Authorization": f"Bearer {token}"},
        timeout=CLIENT_TIMEOUT_SECONDS, trust_env=False,
    ) as client:
        return await send_task(client, base_url, prompt)


def _execute(args, evidence, prompt, executable):
    """Run the review through a local worker; record the outcome in `evidence`."""
    results = []
    try:
        with local_service(args.model, executable, args.enable_claude) as (url, token, pid):
            evidence.update(transport="localhost HTTP JSON-RPC", server_pid=pid,
                            client_pid=os.getpid())
            results = asyncio.run(_send(url, token, prompt))
            evidence["responses"] = [MessageToDict(result) for result in results]
    except (Exception, KeyboardInterrupt) as error:
        # Do not persist exception text that could contain authentication headers.
        evidence["execution_error"] = type(error).__name__
    evidence["finished_at_utc"] = _now()
    return results


def _publish(store, evidence) -> bool:
    """Persist before printing: a closed console must not lose a paid answer."""
    try:
        store.write(evidence)
    except OSError as error:
        print(f"Save failed ({type(error).__name__}); the staged file may be "
              f"incomplete: {store.pending}", file=sys.stderr)
        return False
    publication = store.publish()
    if not publication.published:
        print(f"Publication failed ({publication.warning}); complete evidence "
              f"kept at: {publication.pending}", file=sys.stderr)
        return False
    if publication.warning:
        print(f"Evidence published; cleanup pending: {publication.pending}", file=sys.stderr)
    return True


def _report(final, output: Path) -> None:
    print(f"Status: {'COMPLETED' if final else 'FAILED'}")
    if final:
        for artifact in final.artifacts:
            for part in artifact.parts:
                print(part.text)
    print(f"Evidence: {output}")


def main() -> int:
    sys.stdout.reconfigure(errors="replace")
    parser = _build_parser()
    args = parser.parse_args()
    evidence, prompt, executable, store = _preflight(parser, args)
    results = _execute(args, evidence, prompt, executable)
    if not _publish(store, evidence):
        return EXIT_PUBLICATION_FAILED
    # Any execution error, even after a completed task, is not a clean success.
    final = None if "execution_error" in evidence else completed_task(results)
    _report(final, args.output)
    if evidence.get("execution_error") == KeyboardInterrupt.__name__:
        return EXIT_INTERRUPTED
    return EXIT_COMPLETED if final else EXIT_EXECUTION_FAILED
