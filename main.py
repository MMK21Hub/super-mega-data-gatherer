from datetime import UTC, datetime, timedelta
from fastapi import FastAPI
from structlog import get_logger

from logging_config import configure_logging
from stats import get_unresolved_tickets

configure_logging()
logger = get_logger()
app = FastAPI()


@app.get("/api/v1/super-mega-stats")
async def super_mega_stats(start: datetime, end: datetime | None, step: timedelta):
    end = end or datetime.now(UTC).replace(microsecond=0)
    return {
        "message": "Hello World",
        "unresolved_tickets": await get_unresolved_tickets(start, end, step),
    }


logger.info("Started Super Mega Data Gatherer")
