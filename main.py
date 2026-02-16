from contextlib import asynccontextmanager
from datetime import UTC, datetime, timedelta
from os import getenv
from sys import exc_info
from fastapi import FastAPI, Request
from structlog import get_logger
import uvicorn
import uvicorn.config

from database_stats import DatabaseClient
from logging_config import configure_logging
from prometheus_stats import get_unresolved_tickets

configure_logging()
logger = get_logger()


@asynccontextmanager
async def app_lifespan(_: FastAPI):
    global db_client
    db_client = DatabaseClient()
    await db_client.connect()
    yield
    await db_client.disconnect()


app = FastAPI(lifespan=app_lifespan)


@app.get("/api/v1/super-mega-stats")
async def super_mega_stats(start: datetime, end: datetime | None, step: timedelta):
    end = end or datetime.now(UTC).replace(microsecond=0)
    return {
        "unresolved_tickets": await get_unresolved_tickets(start, end, step),
        "hang_time": {
            "p90": await db_client.get_question_hang_times(start, end, 0.90),
        },
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


logger.info("Starting Super Mega Data Gatherer")

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
