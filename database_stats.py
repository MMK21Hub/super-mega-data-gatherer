from datetime import datetime, timedelta
from sys import exc_info
from psycopg_pool import AsyncConnectionPool
import structlog

from env import get_env_or_raise

db_url = get_env_or_raise("NEPHTHYS_DATABASE_URL")
logger = structlog.get_logger()


class DatabaseClient:
    def __init__(self):
        self.db_url = db_url
        self.connection_pool = AsyncConnectionPool(
            self.db_url, min_size=1, max_size=2, timeout=30, open=False
        )
        self.max_cursor_retries = 5

    async def open_pool(self):
        await self.connection_pool.open()

    async def close_pool(self):
        await self.connection_pool.close()

    async def get_question_hang_times(
        self, start: datetime, end: datetime, percentile: float
    ):
        end = end + timedelta(days=1)

        async with self.connection_pool as pool:
            async with pool.connection() as conn:
                async with conn.cursor() as cur:
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

    async def is_healthy(self) -> bool:
        try:
            async with self.connection_pool.connection() as conn:
                await self.connection_pool.check_connection(conn)
                return True
        except Exception as e:
            logger.error(
                "Database health check failed",
                error=str(e),
                exc_info=exc_info(),
            )
            return False
