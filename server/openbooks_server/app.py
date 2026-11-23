"""FastAPI app. Bind to 127.0.0.1 only; the Next.js server is the sole client.

    uvicorn openbooks_server.app:app --host 127.0.0.1 --port 8765
"""
from __future__ import annotations

import asyncio
import json
import logging
import signal
import threading
import time
from contextlib import asynccontextmanager
from typing import Any

from fastapi import FastAPI, File, Form, HTTPException, Request, UploadFile
from fastapi.responses import JSONResponse, Response, StreamingResponse
from openbooks.core.errors import EngineFault, Refusal
from openbooks.core.schema import SCHEMA_VERSION, validate_output
from openbooks.pipeline import Params
from openbooks.statements.assets import ModelUnavailable

from . import admission as adm
from .admission import Rejected, Ticket, estimate_ocr_pages
from .catalog import Samples, formats, health, installed_linker, load_model, model_status
from .drain import begin_drain
from .jobs import Job, Jobs, job_key
from .metrics import input_kind, metrics_response, observe_stages, registry
from .middleware import OpsMiddleware
from .responses import reject_response
from .runs import MAX_FILES, Run, parse_params

samples = Samples()
jobs = Jobs()
log = logging.getLogger("openbooks_server")
READY_RETRY_AFTER_S = "5"
CLIENT_CLOSED_REQUEST = 499
SSE_MEDIA_TYPE = "text/event-stream"


@asynccontextmanager
async def lifespan(_app: FastAPI):
    status = await asyncio.to_thread(model_status)
    _app.state.model_ready = bool(status["model_ready"])
    loop = asyncio.get_running_loop()
    prev = signal.getsignal(signal.SIGTERM)
    try:
        signal.signal(signal.SIGTERM, lambda n, _f: begin_drain(loop, prev, n))
    except ValueError:
        pass
    yield


app = FastAPI(title="Open Books engine service", version="0.1.0", lifespan=lifespan)
app.add_middleware(OpsMiddleware)
app.state.model_ready = False


@app.get("/healthz")
def get_healthz() -> dict:
    return {"status": "alive"}


@app.get("/readyz")
def get_readyz() -> JSONResponse:
    draining, ready = adm.current.draining, bool(app.state.model_ready)
    ok = ready and not draining
    return JSONResponse({"ready": ok, "model_ready": ready, "draining": draining},
                        status_code=200 if ok else 503, headers={} if ok else {"Retry-After": READY_RETRY_AFTER_S})


@app.get("/metrics")
def get_metrics():
    return metrics_response()


@app.get("/v1/health")
def get_health() -> dict:
    return health()


@app.get("/v1/formats")
def get_formats() -> dict:
    return formats()


@app.get("/v1/samples")
def get_samples() -> dict:
    return {"samples": samples.list()}


@app.get("/v1/samples/{case_id}")
def get_sample(case_id: str):
    hit = samples.get(case_id)
    if hit is None:
        raise HTTPException(404, "no such sample")
    filename, content = hit
    return Response(content, media_type="application/octet-stream",
                    headers={"Content-Disposition": f'attachment; filename="{filename}"'})


def _json_field(raw: str | None, name: str) -> Any:
    if not raw:
        return None
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        raise HTTPException(422, f"{name} is not valid JSON") from None


def _sse(event: str, data: dict) -> bytes:
    return f"event: {event}\ndata: {json.dumps(data, ensure_ascii=False, separators=(',', ':'))}\n\n".encode()


def _run_params(file_count: int, params: str | None, file_params: str | None) -> tuple[Params, dict[int, Params]]:
    """Validate the form's params and per-file overrides (keys are file indices). Raises 422 on any problem."""
    if not file_count:
        raise HTTPException(422, "attach at least one file")
    if file_count > MAX_FILES:
        raise HTTPException(422, f"at most {MAX_FILES} files per run")
    try:
        base = parse_params(_json_field(params, "params"))
        raw_per = _json_field(file_params, "file_params")
        if raw_per is None:
            raw_per = {}
        if not isinstance(raw_per, dict):
            raise ValueError("file_params must be an object keyed by file index")
        indices = {str(i) for i in range(file_count)}
        per_file: dict[int, Params] = {}
        for key, value in raw_per.items():
            if key not in indices:
                raise ValueError(f"file_params key {key!r} is not a file index")
            per_file[int(key)] = parse_params(value, base)
    except ValueError as e:
        raise HTTPException(422, str(e)) from None
    return base, per_file


async def _stage_uploads(run: Run, files: list[UploadFile]) -> None:
    """Copy uploads into the run's temp dir; on any failure the dir is removed before re-raising."""
    try:
        for f in files:
            await asyncio.to_thread(run.stage, f.filename or "", f.file)
    except Exception:
        run.cleanup()
        raise


@app.post("/v1/runs")
async def post_runs(
    request: Request,
    files: list[UploadFile] = File(...),
    params: str | None = Form(None),
    file_params: str | None = Form(None),
):
    base, per_file = _run_params(len(files), params, file_params)
    key = job_key(request)
    run = Run()
    await _stage_uploads(run, files)
    if key:
        async def work(job: Job) -> None:
            ticket = None
            try:
                ticket, early = await _admit(request, run, base.ocr, detached=True)
                if early is not None:
                    job.push("error", json.loads(early.body))
                    return
                loop = asyncio.get_running_loop()

                async def push(event: str, data: dict) -> None:
                    job.push(event, data)

                def emit(event: str, data: dict) -> None:
                    asyncio.run_coroutine_threadsafe(push(event, data), loop).result()

                def observe(method: str | None, suffix: str, stages: dict[str, float]) -> None:
                    observe_stages(input_kind(method, suffix), stages)

                await asyncio.to_thread(run.execute, base, per_file, emit, observe)
            finally:
                if ticket is not None:
                    ticket.release()
                run.cleanup()

        return _start_job(request, "runs", key, run, work)
    ticket, early = await _admit(request, run, base.ocr)
    if early is not None:
        return early
    return _stream_run(run, ticket, base, per_file, request.state.request_id)


def _start_job(request: Request, kind: str, key: str, run: Run, work) -> Response:
    response = jobs.start(kind, key, work, request.state.request_id)
    if response.status_code != 202:
        run.cleanup()
    return response


@app.get("/v1/runs")
async def poll_runs(request: Request, cursor: int = 0) -> Response:
    return jobs.poll("runs", job_key(request, required=True), cursor)


def _stream_run(run: Run, ticket: Ticket, base: Params, per_file: dict[int, Params], rid: str) -> StreamingResponse:
    """Run the engine on a worker thread and stream its events as server-sent events."""
    loop = asyncio.get_running_loop()
    queue: asyncio.Queue[bytes | None] = asyncio.Queue()
    serialisation_s = [0.0]
    kinds: list[str] = []

    def emit(event: str, data: dict) -> None:
        t = time.perf_counter()
        frame = _sse(event, data)
        serialisation_s[0] += time.perf_counter() - t
        loop.call_soon_threadsafe(queue.put_nowait, frame)

    def observe(method: str | None, suffix: str, stages: dict[str, float]) -> None:
        kind = input_kind(method, suffix)
        kinds.append(kind)
        observe_stages(kind, stages)

    def work() -> None:
        try:
            run.execute(base, per_file, emit, observe)
        except Exception as e:
            log.exception("run failed request_id=%s", rid)
            emit("run.error", {"message": f"The engine failed on this run ({type(e).__name__}). Details are in the server log."})
        finally:
            observe_stages(kinds[0] if kinds else "other", {"queue_wait": ticket.waited, "serialization": serialisation_s[0]})
            ticket.release()
            loop.call_soon_threadsafe(queue.put_nowait, None)

    threading.Thread(target=work, name="openbooks-run", daemon=True).start()

    async def stream():
        try:
            while (chunk := await queue.get()) is not None:
                yield chunk
        finally:
            run.cancelled.set()

    return StreamingResponse(stream(), media_type=SSE_MEDIA_TYPE,
                             headers={"Cache-Control": "no-store", "X-Accel-Buffering": "no"})


async def _admit(request: Request, run: Run, ocr: bool, *, detached: bool = False) -> tuple[Ticket | None, Response | None]:
    """Admit the staged upload and wait for a slot. Returns (ticket, None) or (None, response); cleans up on refusal."""
    nbytes = sum(f.size for f in run.files)
    try:
        pages = await _count_ocr_pages(run) if ocr else 0
        ticket = adm.current.admit(nbytes, pages)
    except Rejected as r:
        run.cleanup()
        return None, reject_response(r.reason)
    async def disconnected() -> bool:
        return not detached and await request.is_disconnected()

    try:
        outcome = await ticket.wait_turn(disconnected)
    except asyncio.CancelledError:
        ticket.release()
        run.cleanup()
        raise
    if outcome == "ok":
        return ticket, None
    ticket.release()
    run.cleanup()
    if outcome == "disconnected":
        registry.inc("openbooks_rejections_total", reason="client_disconnected")
        return None, Response(status_code=CLIENT_CLOSED_REQUEST)
    return None, reject_response("queue_timeout")


async def _count_ocr_pages(run: Run) -> int:
    counts = await asyncio.gather(*(asyncio.to_thread(estimate_ocr_pages, f.path) for f in run.files))
    return sum(counts)


@app.post("/v1/roles")
async def post_roles(request: Request, file: UploadFile = File(...), params: str | None = Form(None)) -> JSONResponse:
    """The typed heads' own reading of one PDF or scan: per word role, value type, conformal sets, abstained.
    Inputs use `file` and the same parsing `params` as /v1/runs. Layout roles require a passing balance check."""
    from openbooks.pipeline import MAX_BYTES

    try:
        p = parse_params(_json_field(params, "params"))
    except ValueError as e:
        raise HTTPException(422, str(e)) from None
    key = job_key(request)
    run = Run()
    detached = False
    try:
        await asyncio.to_thread(run.stage, file.filename or "", file.file)
        staged = run.files[0]
        if staged.size > MAX_BYTES:
            raise HTTPException(413, f"file is {staged.size} bytes; the limit is {MAX_BYTES}")
        if staged.path.suffix.lower() not in {".pdf", ".png", ".jpg", ".jpeg"}:
            raise Refusal("UNSUPPORTED_INPUT", "The typed heads read PDFs and scans only.")
        if key:
            async def work(job: Job) -> None:
                try:
                    response = await _read_roles(request, run, p, detached=True)
                    job.push("roles" if response.status_code == 200 else "error",
                             json.loads(response.body))
                finally:
                    run.cleanup()

            response = _start_job(request, "roles", key, run, work)
            detached = response.status_code == 202
            return response
        return await _read_roles(request, run, p)
    except Refusal as e:
        return JSONResponse({"error": e.code, "message": e.message}, status_code=422)
    finally:
        if not detached:
            run.cleanup()


async def _read_roles(request: Request, run: Run, p: Params, *, detached: bool = False) -> Response:
    ticket = None
    staged = run.files[0]
    try:
        ticket, early = await _admit(request, run, p.ocr, detached=detached)
        if early is not None:
            return early
        model = await asyncio.to_thread(load_model)
        from .inference import infer_file

        timings: dict[str, float] = {}
        doc = await asyncio.to_thread(infer_file, staged.path, p, model, timings)
        observe_stages(input_kind(doc.get("method"), staged.path.suffix), {**timings, "queue_wait": ticket.waited})
        return JSONResponse(doc)
    except ModelUnavailable as e:
        return JSONResponse({"error": "model_unavailable", "message": e.message}, status_code=503)
    except EngineFault as e:
        return JSONResponse({"error": "engine_fault", "message": str(e)}, status_code=503)
    except Refusal as e:
        return JSONResponse({"error": e.code, "message": e.message}, status_code=422)
    finally:
        if ticket is not None:
            ticket.release()


@app.get("/v1/roles")
async def poll_roles(request: Request, cursor: int = 0) -> Response:
    return jobs.poll("roles", job_key(request, required=True), cursor)


@app.post("/v1/link")
def post_link(body: dict) -> JSONResponse:
    docs = body.get("docs")
    if not isinstance(docs, list) or not all(isinstance(d, dict) for d in docs):
        raise HTTPException(422, "docs must be a list of openbooks.v1 documents")
    try:
        for doc in docs:
            if doc.get("schema_version") != SCHEMA_VERSION or doc.get("status") not in ("ok", "refused"):
                raise ValueError("expected a released or refused openbooks.v1 document")
            if doc["status"] == "ok":
                validate_output(doc)
        linker = installed_linker()
        if linker is None:
            return JSONResponse({"error": "link_unavailable", "message": "No reconciliation provider is available."},
                                status_code=503)
        return JSONResponse(linker.link(docs))
    except (Refusal, KeyError, TypeError, ValueError) as e:
        raise HTTPException(422, f"docs are not valid openbooks.v1 output: {e}") from None
