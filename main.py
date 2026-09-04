import uuid
from collections.abc import Callable
from contextlib import asynccontextmanager
from datetime import UTC, date, datetime
from time import perf_counter_ns

import uvicorn
from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import JSONResponse
from structlog import get_logger
from structlog.contextvars import bind_contextvars, clear_contextvars

from config import ConfigError, load_config
from logging_config import configure_logging
from prometheus_stats import PrometheusClient
from stats_store import SuperMegaStatsManager

PROJECT_NAME = "Super Mega Data Gatherer"

# The event served by the legacy v1 endpoint
LEGACY_EVENT_SLUG = "flavortown"

# Cannot query before the help channel begun
# TODO: make this configurable or smarter somehow
EARLIEST_DATE = date(2025, 11, 17)

configure_logging()
logger = get_logger()
logger.info(f"Initialising {PROJECT_NAME}", event_id="initialisation")

try:
    config = load_config()
except ConfigError as e:
    logger.fatal("Invalid configuration", event_id="config_error", error=str(e))
    raise

managers: dict[str, SuperMegaStatsManager] = {
    slug: SuperMegaStatsManager(
        event, PrometheusClient(config.prometheus_url, event.prometheus_selector)
    )
    for slug, event in config.events.items()
}
if LEGACY_EVENT_SLUG not in managers:
    logger.warning(
        f"Legacy event '{LEGACY_EVENT_SLUG}' is not configured,"
        f" so /api/v1/super-mega-stats will return 404",
        event_id="legacy_event_missing",
    )


@asynccontextmanager
async def app_lifespan(_: FastAPI):
    logger.info(f"Starting {PROJECT_NAME}", event_id="startup_start")
    # Any future initialisation can go here
    logger.info(f"{PROJECT_NAME} is ready", event_id="startup_complete")
    yield
    logger.info(f"Shutting down {PROJECT_NAME}", event_id="shutdown_start")
    # Any future cleanup can go here
    logger.info(f"{PROJECT_NAME} has shut down", event_id="shutdown_complete")


app = FastAPI(lifespan=app_lifespan)


def validate_date_range(start: date, end: date):
    today_utc = datetime.now(UTC).date()

    # Validation - this isn't really needed, but it helps limit the maximum
    # possible size of the cache and maybe prevents callers getting confused if
    # they give an invalid date range.
    for d in [start, end]:
        if d < EARLIEST_DATE:
            raise HTTPException(status_code=400, detail=f"Date {d} is too far back!")
        if d > today_utc:
            raise HTTPException(status_code=400, detail="Date cannot be in the future")
    if end < start:
        raise HTTPException(
            status_code=400,
            detail="End date cannot be earlier than start date",
        )


async def stats_response(manager: SuperMegaStatsManager, start: date, end: date | None):
    end = end or datetime.now(UTC).date()
    validate_date_range(start, end)

    fetched = await manager.get_stats(start, end)
    logger.debug(
        "Fetched stats",
        cache_hit=fetched.from_cache,
        start=start.isoformat(),
        end=end.isoformat(),
        **(
            {"age_seconds": round(fetched.age.total_seconds(), 1)}
            if fetched.age
            else {}
        ),
    )
    stats = fetched.stats
    return {
        "unresolved_tickets": stats.unresolved_tickets_data,
        "hang_time": stats.hang_time_data,
    }


@app.get("/api/v1/super-mega-stats")
async def super_mega_stats(start: date, end: date | None = None):
    manager = managers.get(LEGACY_EVENT_SLUG)
    if manager is None:
        raise HTTPException(
            status_code=404,
            detail=f"Legacy event '{LEGACY_EVENT_SLUG}' is not configured",
        )
    bind_contextvars(event=LEGACY_EVENT_SLUG)
    return await stats_response(manager, start, end)


@app.get("/api/v2/{event}/super-mega-stats")
async def super_mega_stats_v2(event: str, start: date, end: date | None = None):
    manager = managers.get(event)
    if manager is None:
        raise HTTPException(
            status_code=404,
            detail=f"Unknown event '{event}'. Available events: {', '.join(managers)}",
        )
    bind_contextvars(event=event)
    return await stats_response(manager, start, end)


@app.get("/")
async def root(request: Request):
    return {
        "message": "hey bestie!!",
        "documentation_url": f"{request.base_url}docs",
        "source_code_url": "https://github.com/MMK21Hub/super-mega-data-gatherer",
    }


@app.get("/health")
async def health_check():
    healths = {slug: await manager.health_check() for slug, manager in managers.items()}
    overall_health = all(health["ok"] for health in healths.values())
    return JSONResponse(
        {"ok": overall_health, "events": healths},
        status_code=200 if overall_health else 503,
    )


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
    uvicorn.run(app, host=config.host, port=config.port, log_config=None)
