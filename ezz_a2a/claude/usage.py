"""Token, cost and time figures reported by the Claude CLI; absent fields stay null."""

USAGE_TOKEN_FIELDS = (
    "input_tokens", "output_tokens",
    "cache_creation_input_tokens", "cache_read_input_tokens",
)


class ClaudeReply(str):
    """The answer text, unchanged, carrying the metrics of the call that produced it."""

    def __new__(cls, answer: str, metrics: dict):
        reply = super().__new__(cls, answer)
        reply.metrics = metrics
        return reply


def _count(value) -> int | None:
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        return None
    return value


def _cost(value) -> float | None:
    if isinstance(value, bool) or not isinstance(value, (int, float)) or value < 0:
        return None
    return float(value)


def _model(result: dict) -> str | None:
    models = result.get("modelUsage")
    if not isinstance(models, dict) or not models:
        return None
    return ",".join(sorted(str(name) for name in models))


def build_metrics(result: dict, prompt_chars: int, duration_seconds: float) -> dict:
    """Copy what the CLI reported; the duration and prompt size are measured locally."""
    usage = result.get("usage")
    if not isinstance(usage, dict):
        usage = {}
    metrics = {field: _count(usage.get(field)) for field in USAGE_TOKEN_FIELDS}
    metrics.update(cost_usd=_cost(result.get("total_cost_usd")),
                   duration_seconds=duration_seconds,
                   model=_model(result), prompt_chars=prompt_chars)
    return metrics
