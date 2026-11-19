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
from fastapi.responses import JSONResponse, Response, StreamingResponse
from openbooks_core.errors import Refusal
from openbooks_core.schema import SCHEMA_VERSION, validate_output
from openbooks_statements.assets import ModelUnavailable

from .catalog import Samples, formats, health, installed_linker, load_model, model_status
from .runs import MAX_FILES, Run, parse_params

samples = Samples()
log = logging.getLogger("openbooks_server")


@asynccontextmanager
async def lifespan(_app: FastAPI):
    await asyncio.to_thread(model_status)
    yield


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
    filename, content = hit
    return Response(content, media_type="application/octet-stream",
                    headers={"Content-Disposition": f'attachment; filename="{filename}"'})


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
        raw_per = _json_field(file_params, "file_params")
        if raw_per is None:
            raw_per = {}
        if not isinstance(raw_per, dict):
            raise ValueError("file_params must be an object keyed by file index")
        per_file = {}
        indices = {str(i) for i in range(len(files))}
        for k, v in raw_per.items():
            if k not in indices:
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
    from openbooks.pipeline import MAX_BYTES

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
        if staged.path.suffix.lower() not in {".pdf", ".png", ".jpg", ".jpeg"}:
            raise Refusal("UNSUPPORTED_INPUT", "The typed heads read PDFs and scans only.")
        model = await asyncio.to_thread(load_model)
        from .inference import infer_file

        return JSONResponse(await asyncio.to_thread(infer_file, staged.path, p, model))
    except ModelUnavailable as e:
        return JSONResponse({"error": "model_unavailable", "message": e.message}, status_code=503)
    except Refusal as e:
        return JSONResponse({"error": e.code, "message": e.message}, status_code=422)
    finally:
        run.cleanup()


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
