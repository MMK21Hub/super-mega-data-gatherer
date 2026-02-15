from contextlib import asynccontextmanager
from datetime import UTC, datetime, timedelta
from fastapi import FastAPI
from structlog import get_logger

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
        "message": "Hello World",
        "unresolved_tickets": await get_unresolved_tickets(start, end, step),
        "hang_time": {
            "p90": await db_client.get_question_hang_times(start, end, 0.90),
        },
    }


logger.info("Started Super Mega Data Gatherer")
