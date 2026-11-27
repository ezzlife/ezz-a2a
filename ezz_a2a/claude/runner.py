"""Invoke Claude only when explicitly enabled, with supplied context and no tools."""

import asyncio
import json
import os
import tempfile
import time
from pathlib import Path

from ezz_a2a.claude.errors import ProcessTreeError
from ezz_a2a.claude.process_tree import SPAWN_OPTIONS, contain_process_tree
from ezz_a2a.claude.usage import ClaudeReply, build_metrics

DURATION_DECIMALS = 3
DEFAULT_TIMEOUT_SECONDS = 180
DEFAULT_MAX_TURNS = 1
PROCESS_CLEANUP_TIMEOUT_SECONDS = 5
WITHHELD_VARIABLES = ("ANTHROPIC_API_KEY", "ANTHROPIC_AUTH_TOKEN", "A2A_TOKEN")
UNSUPPORTED_PROVIDER_VARIABLES = (
    "ANTHROPIC_BASE_URL", "CLAUDE_CODE_USE_BEDROCK",
    "CLAUDE_CODE_USE_VERTEX", "CLAUDE_CODE_USE_FOUNDRY",
)
NO_MCP_SERVERS = '{"mcpServers":{}}'
NO_HOOKS_NO_MEMORY = '{"disableAllHooks":true,"autoMemoryEnabled":false}'
REVIEWER_SYSTEM_PROMPT = (
    "You are a delegated reviewer. Use only the context you receive. "
    "Do not delegate, run commands or claim to have tested files. "
    "Report findings, evidence and limitations to the coordinator. "
    "Write the review in English."
)


class ClaudeUnavailable(RuntimeError):
    """The worker cannot produce a successful response."""


def validate_provider_environment(environment=None) -> None:
    """Reject alternative providers, naming variables but never their values."""
    source = os.environ if environment is None else environment
    configured = [name for name in UNSUPPORTED_PROVIDER_VARIABLES
                  if source.get(name, "").strip()]
    if configured:
        raise ClaudeUnavailable("Unsupported alternative provider: " + ", ".join(configured))


def _child_environment() -> dict:
    """Environment for Claude: the subscription login is kept, API secrets are not."""
    environment = os.environ.copy()
    validate_provider_environment(environment)
    for name in WITHHELD_VARIABLES:
        environment.pop(name, None)
    return environment


def _extract_reply(stdout: bytes, prompt_chars: int, duration_seconds: float) -> ClaudeReply:
    try:
        result = json.loads(stdout)
    except (ValueError, UnicodeError) as error:
        raise ClaudeUnavailable("Claude returned a non-JSON response.") from error
    if not isinstance(result, dict) or result.get("is_error"):
        raise ClaudeUnavailable("Claude did not complete the request; check access/quota.")
    answer = result.get("result")
    if not isinstance(answer, str) or not answer.strip():
        raise ClaudeUnavailable("Claude returned no content.")
    return ClaudeReply(answer, build_metrics(result, prompt_chars, duration_seconds))


class ClaudeRunner:
    def __init__(self, executable: str, model: str, enabled: bool = False,
                 timeout_seconds: float = DEFAULT_TIMEOUT_SECONDS):
        self.executable = executable
        self.model = model
        self.enabled = enabled
        self.timeout_seconds = timeout_seconds

    async def __call__(self, prompt: str) -> ClaudeReply:
        if not self.enabled:
            raise ClaudeUnavailable("Claude disabled; enable it after checking quota.")
        environment = _child_environment()
        started = time.monotonic()
        # A killed process can leave its working directory locked on Windows;
        # cleanup errors must never replace a paid answer, a timeout or a cancellation.
        with tempfile.TemporaryDirectory(prefix="a2a-claude-",
                                         ignore_cleanup_errors=True) as empty_directory:
            process, stdout = await self._run_contained(prompt, environment,
                                                        Path(empty_directory))
        if process.returncode:
            # stderr is discarded on purpose: CLI logs may contain private data.
            raise ClaudeUnavailable(
                f"Claude exited with code {process.returncode}; check access/quota.")
        return _extract_reply(stdout, len(prompt), round(time.monotonic() - started,
                                                         DURATION_DECIMALS))

    def _command(self) -> list[str]:
        return [
            self.executable, "-p", "--output-format", "json",
            "--safe-mode",
            "--model", self.model, "--tools", "",
            "--strict-mcp-config", "--mcp-config", NO_MCP_SERVERS,
            "--setting-sources", "",
            "--settings", NO_HOOKS_NO_MEMORY,
            "--disable-slash-commands", "--no-session-persistence",
            "--max-turns", str(DEFAULT_MAX_TURNS),
            "--append-system-prompt", REVIEWER_SYSTEM_PROMPT,
        ]

    async def _run_contained(self, prompt: str, environment: dict, working_directory: Path):
        try:
            process = await asyncio.create_subprocess_exec(
                *self._command(), cwd=working_directory, env=environment,
                stdin=asyncio.subprocess.PIPE, stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE, **SPAWN_OPTIONS,
            )
        except OSError as error:
            raise ClaudeUnavailable("Could not start Claude Code.") from error
        try:
            process_tree = contain_process_tree(process.pid)
        except ProcessTreeError as error:
            # Fail closed: an uncontained process could outlive a timeout.
            await self._stop(process)
            raise ClaudeUnavailable("Could not contain the Claude process.") from error
        try:
            stdout, _ = await asyncio.wait_for(
                process.communicate(prompt.encode("utf-8")), self.timeout_seconds,
            )
        except (asyncio.TimeoutError, asyncio.CancelledError):
            try:
                process_tree.terminate()
            finally:
                await self._stop(process)
            raise
        finally:
            # Also ends descendants left behind by a process that already exited.
            process_tree.close()
        return process, stdout

    @staticmethod
    async def _stop(process) -> None:
        if process.returncode is None:
            process.kill()
        try:
            await asyncio.wait_for(process.communicate(), PROCESS_CLEANUP_TIMEOUT_SECONDS)
        except asyncio.TimeoutError:
            pass
