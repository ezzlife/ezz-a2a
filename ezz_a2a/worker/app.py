from a2a.server.request_handlers import DefaultRequestHandler
from a2a.server.routes import create_agent_card_routes, create_jsonrpc_routes
from a2a.server.tasks import InMemoryTaskStore
from starlette.applications import Starlette

from ezz_a2a.settings import DEFAULT_PORT
from ezz_a2a.worker.agent_card import build_agent_card
from ezz_a2a.worker.auth import require_bearer_token
from ezz_a2a.worker.executor import ReviewExecutor


def create_app(runner, token: str, port: int = DEFAULT_PORT):
    """Build the Starlette app: Agent Card and JSON-RPC routes behind a bearer token."""
    if not token.strip():
        raise ValueError("A2A_TOKEN is required.")
    card = build_agent_card(port)
    handler = DefaultRequestHandler(
        agent_executor=ReviewExecutor(runner), task_store=InMemoryTaskStore(),
        agent_card=card,
    )
    app = Starlette(routes=[*create_agent_card_routes(card),
                            *create_jsonrpc_routes(handler, "/")])
    require_bearer_token(app, token)
    return app
