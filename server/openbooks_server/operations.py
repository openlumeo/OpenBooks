"""Health, readiness, metrics and public catalog routes."""

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import JSONResponse, Response

from . import admission as adm
from .catalog import Samples, formats, health
from .metrics import metrics_response

router = APIRouter()
samples = Samples()
READY_RETRY_AFTER_S = "5"


@router.get("/healthz")
def get_healthz() -> dict:
    return {"status": "alive"}


@router.get("/readyz")
def get_readyz(request: Request) -> JSONResponse:
    draining, ready = adm.current.draining, bool(request.app.state.model_ready)
    ok = ready and not draining
    return JSONResponse(
        {"ready": ok, "model_ready": ready, "draining": draining},
        status_code=200 if ok else 503,
        headers={} if ok else {"Retry-After": READY_RETRY_AFTER_S},
    )


@router.get("/metrics")
def get_metrics():
    return metrics_response()


@router.get("/v1/health")
def get_health() -> dict:
    return health()


@router.get("/v1/formats")
def get_formats() -> dict:
    return formats()


@router.get("/v1/samples")
def get_samples() -> dict:
    return {"samples": samples.list()}


@router.get("/v1/samples/{case_id}")
def get_sample(case_id: str):
    hit = samples.get(case_id)
    if hit is None:
        raise HTTPException(404, "no such sample")
    filename, content = hit
    return Response(
        content,
        media_type="application/octet-stream",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )
