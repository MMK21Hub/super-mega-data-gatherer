from contextlib import asynccontextmanager
from datetime import UTC, datetime, timedelta
from os import getenv
from sys import exc_info
from time import perf_counter, perf_counter_ns
from typing import Callable
from fastapi import FastAPI, Request
from structlog import get_logger
from structlog.contextvars import clear_contextvars, bind_contextvars
import uvicorn
import uuid

from database_stats import DatabaseClient
from logging_config import configure_logging
from prometheus_stats import get_unresolved_tickets

PROJECT_NAME = "Super Mega Data Gatherer"

configure_logging()
logger = get_logger()
logger.info(f"Initialising {PROJECT_NAME}", event_id="initialisation")

db_client = DatabaseClient()


@asynccontextmanager
async def app_lifespan(_: FastAPI):
    global db_client
    logger.info(f"Starting {PROJECT_NAME}", event_id="startup_start")
    await db_client.open_pool()
    logger.info(f"{PROJECT_NAME} is ready", event_id="startup_complete")
    yield
    logger.info(f"Shutting down {PROJECT_NAME}", event_id="shutdown_start")
    await db_client.close_pool()
    logger.info(f"{PROJECT_NAME} has shut down", event_id="shutdown_complete")


app = FastAPI(lifespan=app_lifespan)


async def get_hang_time_data(
    start: datetime, end: datetime
) -> dict[str, dict[str, float]] | None:
    try:
        return {
            "p90": await db_client.get_question_hang_times(start, end, 0.90),
            "p95": await db_client.get_question_hang_times(start, end, 0.95),
        }
    except Exception as e:
        logger.error(
            "Failed to fetch question hang time data",
            error=str(e),
            exc_info=exc_info(),
        )
        return None


@app.get("/api/v1/super-mega-stats")
async def super_mega_stats(start: datetime, end: datetime | None):
    end = end or datetime.now(UTC).replace(microsecond=0)
    return {
        "unresolved_tickets": await get_unresolved_tickets(
            start, end, step=timedelta(days=1)
        ),
        "hang_time": await get_hang_time_data(start, end),
    }


@app.get("/")
async def root(request: Request):
    return {
        "message": "hey bestie!!",
        "documentation_url": f"{request.base_url}docs",
        "source_code_url": "https://github.com/MMK21Hub/super-mega-data-gatherer",
    }


@app.get("/health")
async def health_check():
    healths = {"database": await db_client.is_healthy()}
    overall_health = all(healths.values())
    return {"ok": overall_health, **healths}


@app.middleware("http")
async def add_logging_context(request: Request, call_next: Callable):
    clear_contextvars()
    bind_contextvars(
        request_id=uuid.uuid1().hex,
        request=dict(
            method=request.method,
            path=request.url.path,
            client=request.client.host if request.client else None,
        ),
    )
    start_time = perf_counter_ns()
    response = await call_next(request)
    duration_ms = (perf_counter() - start_time) / 1_000_000
    logger.info(
        "HTTP request",
        event_id="request",
        duration_ms=duration_ms,
        status=response.status_code,
    )
    return response


if __name__ == "__main__":
    host = getenv("HOST") or "0.0.0.0"
    port_raw = getenv("PORT")
    try:
        port = int(port_raw or 8000)
    except ValueError:
        logger.fatal(
            "Invalid PORT environment variable, must be an integer",
            port=port_raw,
        )
        raise

    uvicorn.run(app, host=host, port=port, log_config=None)
