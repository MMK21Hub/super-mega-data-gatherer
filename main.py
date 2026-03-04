from contextlib import asynccontextmanager
from datetime import UTC, date, datetime
from os import getenv
from time import perf_counter_ns
from typing import Callable
from fastapi import FastAPI, HTTPException, Request
from structlog import get_logger
from structlog.contextvars import clear_contextvars, bind_contextvars
import uvicorn
import uuid

from logging_config import configure_logging
from stats_store import SuperMegaStatsManager

PROJECT_NAME = "Super Mega Data Gatherer"

configure_logging()
logger = get_logger()
logger.info(f"Initialising {PROJECT_NAME}", event_id="initialisation")

stats_manager = SuperMegaStatsManager()


@asynccontextmanager
async def app_lifespan(_: FastAPI):
    global db_client
    logger.info(f"Starting {PROJECT_NAME}", event_id="startup_start")
    # Any future initialisation can go here
    logger.info(f"{PROJECT_NAME} is ready", event_id="startup_complete")
    yield
    logger.info(f"Shutting down {PROJECT_NAME}", event_id="shutdown_start")
    # Any future cleanup can go here
    logger.info(f"{PROJECT_NAME} has shut down", event_id="shutdown_complete")


app = FastAPI(lifespan=app_lifespan)


@app.get("/api/v1/super-mega-stats")
async def super_mega_stats(start: date, end: date | None = None):
    today_utc = datetime.now(UTC).date()
    end = end or today_utc

    # Validation - this isn't really needed, but it helps limit the maximum
    # possible size of the cache and maybe prevents callers getting confused if
    # they give an invalid date range.
    for d in [start, end]:
        # Cannot query before the help channel begun
        # TODO: make this configurable or smarter somehow
        if d < date(2025, 11, 17):
            raise HTTPException(status_code=400, detail=f"Date {d} is too far back!")
        if d > today_utc:
            raise HTTPException(status_code=400, detail="Date cannot be in the future")
    if end < start:
        raise HTTPException(
            status_code=400,
            detail="End date cannot be earlier than start date",
        )

    stats_response = await stats_manager.get_stats(start, end)
    logger.debug(
        "Fetched stats",
        cache_hit=stats_response.from_cache,
        start=start.isoformat(),
        end=end.isoformat(),
        **(
            {"age_seconds": round(stats_response.age.total_seconds(), 1)}
            if stats_response.age
            else {}
        ),
    )
    stats = stats_response.stats
    return {
        "unresolved_tickets": stats.unresolved_tickets_data,
        "hang_time": stats.hang_time_data,
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
    return await stats_manager.health_check()


@app.middleware("http")
async def add_logging_context(request: Request, call_next: Callable):
    clear_contextvars()
    bind_contextvars(request_id=uuid.uuid1().hex)
    start_time = perf_counter_ns()
    response = await call_next(request)
    duration_ms = (perf_counter_ns() - start_time) / 1_000_000
    logger.info(
        "HTTP request",
        event_id="request",
        request=dict(
            method=request.method,
            path=request.url.path,
            client=request.client.host if request.client else None,
        ),
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
