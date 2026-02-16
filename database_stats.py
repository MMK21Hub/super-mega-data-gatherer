import asyncio
from datetime import datetime, timedelta
from sys import exc_info
import psycopg
import structlog

from env import get_env_or_raise

db_url = get_env_or_raise("NEPHTHYS_DATABASE_URL")
logger = structlog.get_logger()


class DatabaseClient:
    def __init__(self):
        self.db_url = db_url
        self.connection = None
        self.max_cursor_retries = 5

    async def connect(self):
        self.connection = await psycopg.AsyncConnection.connect(self.db_url)
        logger.debug("Connected to the database")

    async def db_cursor(self, attempt=0) -> psycopg.AsyncCursor:
        if not self.connection:
            raise RuntimeError("Database client is not connected")
        try:
            return self.connection.cursor()
        except psycopg.OperationalError as e:
            logger.error(
                "Failed to initialise database cursor",
                attempt=attempt,
                error=str(e),
            )
            if attempt > self.max_cursor_retries:
                logger.error("Exceeded maximum db_cursor() retry attempts")
                raise
            await asyncio.sleep(0.2)
            return await self.db_cursor(attempt + 1)

    async def get_question_hang_times(
        self, start: datetime, end: datetime, percentile: float
    ):
        end = end + timedelta(days=1)

        conn = self.connection
        if not conn:
            raise RuntimeError("Database client is not connected")

        try:
            async with await self.db_cursor() as cur:
                await cur.execute(
                    """
                    WITH assigned_tickets AS (
                        SELECT
                            date_trunc('day', "assignedAt") AS assignedAt,
                            EXTRACT(EPOCH FROM ("assignedAt" - "createdAt")) AS resolution_seconds
                        FROM "Ticket"
                        WHERE "assignedAt" BETWEEN %s AND %s
                    )
                    SELECT assignedAt,
                            percentile_cont(%s) WITHIN GROUP (ORDER BY resolution_seconds) AS "resolution_time",
                            COUNT(resolution_seconds) as count
                    FROM assigned_tickets
                    GROUP BY assignedAt
                    ORDER BY assignedAt;
                    """,
                    (start, end, percentile),
                )
                rows = await cur.fetchall()

                # Convert to dict
                output = {}
                debug_output = []
                for date, value, count in rows:
                    day_str = date.date().isoformat()
                    output[day_str] = value
                    debug_output.append(
                        {"date": day_str, "value": value, "count": count}
                    )
                logger.debug(
                    "Fetched question hang times",
                    start=start.isoformat(),
                    end=end.isoformat(),
                    percentile=percentile,
                    result=debug_output,
                )
                return output
        except psycopg.OperationalError as e:
            logger.error("Failed to initialise database cursor", error=str(e))

    async def is_healthy(self) -> bool:
        if not self.connection:
            return False
        try:
            async with self.connection.cursor() as cur:
                await cur.execute("SELECT 1")
                result = await cur.fetchone()
                return result is not None and result[0] == 1
        except Exception:
            logger.error("Database health check failed", exc_info=exc_info())
            return False

    async def disconnect(self):
        if self.connection:
            await self.connection.close()
