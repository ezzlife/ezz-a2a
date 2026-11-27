"""Usage metrics come from the CLI's JSON; a field it omits is null, never invented."""

import asyncio
import json

import pytest

from ezz_a2a.claude.runner import ClaudeRunner
from ezz_a2a.claude.usage import build_metrics

PROMPT = "Context for review"
DURATION_SECONDS = 1.5
CLI_RESULT = {
    "result": "Review result",
    "total_cost_usd": 0.0065129,
    "usage": {"input_tokens": 2, "output_tokens": 4,
              "cache_creation_input_tokens": 1601, "cache_read_input_tokens": 649},
    "modelUsage": {"claude-sonnet-5-5": {"inputTokens": 2}},
}
METRIC_FIELDS = {
    "input_tokens", "output_tokens", "cache_creation_input_tokens",
    "cache_read_input_tokens", "cost_usd", "duration_seconds", "model", "prompt_chars",
}


def test_reported_usage_is_recorded_as_measured():
    metrics = build_metrics(CLI_RESULT, len(PROMPT), DURATION_SECONDS)
    assert metrics == {
        "input_tokens": 2, "output_tokens": 4,
        "cache_creation_input_tokens": 1601, "cache_read_input_tokens": 649,
        "cost_usd": 0.0065129, "duration_seconds": DURATION_SECONDS,
        "model": "claude-sonnet-5-5", "prompt_chars": len(PROMPT),
    }


@pytest.mark.parametrize("result", [
    {"result": "x"},
    {"result": "x", "usage": "broken", "modelUsage": [], "total_cost_usd": "free"},
    {"result": "x", "usage": {"input_tokens": True, "output_tokens": -1}},
])
def test_missing_or_malformed_fields_are_null(result):
    metrics = build_metrics(result, len(PROMPT), DURATION_SECONDS)
    assert set(metrics) == METRIC_FIELDS
    for field in METRIC_FIELDS - {"duration_seconds", "prompt_chars"}:
        assert metrics[field] is None
    assert metrics["duration_seconds"] == DURATION_SECONDS
    assert metrics["prompt_chars"] == len(PROMPT)


class SyntheticProcess:
    pid = None
    returncode = 0

    def __init__(self, response):
        self.response = response

    async def communicate(self, prompt=None):
        return self.response, b""


def test_runner_reply_keeps_the_answer_text_and_adds_metrics(monkeypatch):
    async def spawn(*args, **kwargs):
        return SyntheticProcess(json.dumps(CLI_RESULT).encode())

    monkeypatch.setattr(asyncio, "create_subprocess_exec", spawn)
    reply = asyncio.run(ClaudeRunner("claude.exe", "model", True)(PROMPT))
    assert reply == "Review result"
    assert type(reply.metrics) is dict and set(reply.metrics) == METRIC_FIELDS
    assert reply.metrics["input_tokens"] == 2
    assert reply.metrics["prompt_chars"] == len(PROMPT)
    assert reply.metrics["duration_seconds"] >= 0
