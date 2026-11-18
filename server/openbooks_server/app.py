"""FastAPI app. Bind to 127.0.0.1 only; the Next.js server is the sole client.

    uvicorn openbooks_server.app:app --host 127.0.0.1 --port 8765
"""
from __future__ import annotations

import asyncio
import json
import logging
import threading
from contextlib import asynccontextmanager

from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from fastapi.responses import FileResponse, JSONResponse, StreamingResponse
from openbooks_lab.link import link

from .catalog import Samples, formats, health
from .runs import MAX_FILES, Run, parse_params

samples = Samples()
log = logging.getLogger("openbooks_server")


def _inference():
    """The torch-backed module, imported on first use so the service still starts without the [scan] extra."""
    try:
        from . import inference
    except ImportError as e:
        raise HTTPException(503, f"typed heads unavailable: {e}") from None
    return inference


@asynccontextmanager
async def lifespan(_app: FastAPI):
    if health()["model_weights_present"]:  # load weights now so the first request is not the slow one
        try:
            await asyncio.to_thread(lambda: _inference().warm())
        except Exception:  # health reports the issue; the service still serves everything but the heads
            log.exception("model warm-up failed")
    yield
    samples.close()


app = FastAPI(title="Open Books engine service", version="0.1.0", lifespan=lifespan)


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
    filename, path = hit
    return FileResponse(path, filename=filename, media_type="application/octet-stream")


def _json_field(raw: str | None, name: str):
    if not raw:
        return None
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        raise HTTPException(422, f"{name} is not valid JSON") from None


def _sse(event: str, data: dict) -> bytes:
    return f"event: {event}\ndata: {json.dumps(data, ensure_ascii=False, separators=(',', ':'))}\n\n".encode()


@app.post("/v1/runs")
async def post_runs(
    files: list[UploadFile] = File(...),
    params: str | None = Form(None),
    file_params: str | None = Form(None),
):
    if not files:
        raise HTTPException(422, "attach at least one file")
    if len(files) > MAX_FILES:
        raise HTTPException(422, f"at most {MAX_FILES} files per run")
    try:
        base = parse_params(_json_field(params, "params"))
        raw_per = _json_field(file_params, "file_params") or {}
        if not isinstance(raw_per, dict):
            raise ValueError("file_params must be an object keyed by file index")
        per_file = {}
        for k, v in raw_per.items():
            if not str(k).isdigit() or int(k) >= len(files):
                raise ValueError(f"file_params key {k!r} is not a file index")
            per_file[int(k)] = parse_params(v, base)
    except ValueError as e:
        raise HTTPException(422, str(e)) from None

    run = Run()
    try:
        for f in files:
            await asyncio.to_thread(run.stage, f.filename or "", f.file)
    except Exception:
        run.cleanup()
        raise

    loop = asyncio.get_running_loop()
    queue: asyncio.Queue[bytes | None] = asyncio.Queue()

    def emit(event: str, data: dict) -> None:
        loop.call_soon_threadsafe(queue.put_nowait, _sse(event, data))

    def work() -> None:
        try:
            run.execute(base, per_file, emit)
        except Exception as e:
            log.exception("run failed")
            emit("run.error", {"message": f"The engine failed on this run ({type(e).__name__}). Details are in the server log."})
        finally:
            loop.call_soon_threadsafe(queue.put_nowait, None)

    threading.Thread(target=work, name="openbooks-run", daemon=True).start()

    async def stream():
        try:
            while (chunk := await queue.get()) is not None:
                yield chunk
        finally:
            run.cancelled.set()

    return StreamingResponse(stream(), media_type="text/event-stream",
                             headers={"Cache-Control": "no-store", "X-Accel-Buffering": "no"})


@app.post("/v1/roles")
async def post_roles(file: UploadFile = File(...), params: str | None = Form(None)) -> JSONResponse:
    """The typed heads' own reading of one PDF or scan: per word role, value type, conformal sets, abstained.
    Inputs match /v1/runs: `file` and `params` (ocr, date_order are used; the rest are ignored here)."""
    inference = _inference()
    from openbooks.pipeline import MAX_BYTES
    from openbooks_core.errors import Refusal

    try:
        p = parse_params(_json_field(params, "params"))
    except ValueError as e:
        raise HTTPException(422, str(e)) from None
    run = Run()
    try:
        await asyncio.to_thread(run.stage, file.filename or "", file.file)
        staged = run.files[0]
        if staged.size > MAX_BYTES:
            raise HTTPException(413, f"file is {staged.size} bytes; the limit is {MAX_BYTES}")
        return JSONResponse(await asyncio.to_thread(inference.infer_file, staged.path, p))
    except Refusal as e:
        return JSONResponse({"error": e.code, "message": e.message}, status_code=422)
    except inference.ModelUnavailable as e:
        return JSONResponse({"error": "model_unavailable", "message": str(e)}, status_code=503)
    finally:
        run.cleanup()


@app.post("/v1/link")
def post_link(body: dict) -> JSONResponse:
    docs = body.get("docs")
    if not isinstance(docs, list) or not all(isinstance(d, dict) for d in docs):
        raise HTTPException(422, "docs must be a list of openbooks.v1 documents")
    try:
        return JSONResponse(link(docs))
    except (KeyError, TypeError, ValueError) as e:
        raise HTTPException(422, f"docs are not valid openbooks.v1 output: {e}") from None
