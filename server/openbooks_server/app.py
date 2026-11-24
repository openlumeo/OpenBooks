"""FastAPI app. Bind to 127.0.0.1 only; the Next.js server is the sole client.

uvicorn openbooks_server.app:app --host 127.0.0.1 --port 8765
"""

from __future__ import annotations

import asyncio
import signal
from contextlib import asynccontextmanager

from fastapi import FastAPI

from .catalog import model_status
from .drain import begin_drain
from .execution import router as execution_router
from .middleware import OpsMiddleware
from .operations import router as operations_router


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
app.include_router(operations_router)
app.include_router(execution_router)
