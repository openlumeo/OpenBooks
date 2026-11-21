"""JSON error bodies shared by the middleware and the handlers. Each one also counts itself in metrics."""
from __future__ import annotations

from fastapi.responses import JSONResponse

from . import admission as adm
from .metrics import registry

DRAINING = "draining"
_DRAINING_MESSAGE = "The engine is restarting. Retry shortly."
_CAPACITY_MESSAGE = "The engine is at capacity. Retry after the delay."


def reject_response(reason: str) -> JSONResponse:
    """Refusal for admission reason: 503 while draining, otherwise 429. Always carries Retry-After."""
    registry.inc("openbooks_rejections_total", reason=reason)
    draining = reason == DRAINING
    retry = adm.current.retry_after
    body = {"error": "draining" if draining else "overloaded", "reason": reason,
            "message": _DRAINING_MESSAGE if draining else _CAPACITY_MESSAGE, "retry_after": retry}
    return JSONResponse(body, status_code=503 if draining else 429, headers={"Retry-After": str(retry)})


def unauthorised_response() -> JSONResponse:
    """401 for a missing or wrong engine key."""
    return JSONResponse({"error": "unauthorized", "message": "A valid engine key is required."}, status_code=401)
