import hmac
from http import HTTPStatus

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import JSONResponse


def require_bearer_token(app, token: str) -> None:
    """Reject every request that does not carry `Authorization: Bearer <token>`."""
    expected = f"Bearer {token}".encode()

    async def authenticate(request, call_next):
        supplied = request.headers.get("authorization", "").encode()
        if not hmac.compare_digest(supplied, expected):
            return JSONResponse({"error": "Unauthorized"}, status_code=HTTPStatus.UNAUTHORIZED)
        return await call_next(request)

    app.add_middleware(BaseHTTPMiddleware, dispatch=authenticate)
