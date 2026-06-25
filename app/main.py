from __future__ import annotations

import logging

from contextlib import asynccontextmanager

from dotenv import load_dotenv

load_dotenv()  # populate os.environ from .env before settings are read

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from slowapi.middleware import SlowAPIMiddleware
from slowapi.util import get_remote_address

from app import __version__
from app.api import admin, health, jobs, ui
from app.config import get_settings
from app.logging_conf import configure_logging
from app.state import get_print_queue, get_store

settings = get_settings()
configure_logging(settings)
logger = logging.getLogger("hoc.main")

limiter = Limiter(key_func=get_remote_address, default_limits=[f"{settings.rate_limit_per_minute}/minute"])

@asynccontextmanager
async def lifespan(app: FastAPI):
    get_store()
    get_print_queue().start()
    logger.info("hoc-label-print-service v%s started", __version__)
    yield
    get_print_queue().stop()
    get_store().close()
    logger.info("hoc-label-print-service stopped cleanly")


app = FastAPI(title="House of Coffee Label Print Service", version=__version__, lifespan=lifespan)
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)
app.add_middleware(SlowAPIMiddleware)

# LAN-local appliance: no CORS needed since the only client is the WooCommerce
# server-side plugin making same-network requests, not browser JS from other origins.

app.include_router(health.router, tags=["health"])
app.include_router(jobs.router, tags=["jobs"])
app.include_router(admin.router, tags=["admin"])
app.include_router(ui.router, tags=["ui"])


@app.exception_handler(Exception)
def unhandled_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    logger.exception("Unhandled exception on %s %s", request.method, request.url.path)
    return JSONResponse(status_code=500, content={"detail": "Internal server error", "code": "internal_error"})


