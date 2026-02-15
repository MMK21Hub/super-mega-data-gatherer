from datetime import datetime
import psycopg
import structlog

from env import get_env_or_raise

db_url = get_env_or_raise("NEPHTHYS_DATABASE_URL")
logger = structlog.get_logger()


class DatabaseClient:
    def __init__(self):
        self.db_url = db_url
        self.connection = None

    async def connect(self):
        self.connection = await psycopg.AsyncConnection.connect(self.db_url)
        logger.debug("Connected to the database")
        print(self.connection)

    async def get_question_hang_times(
        self, start: datetime, end: datetime, percentile: float
    ):
        conn = self.connection
        if not conn:
            raise RuntimeError("Database client is not connected")

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
                        percentile_cont(%s) WITHIN GROUP (ORDER BY resolution_seconds) AS "resolution_time"
                FROM assigned_tickets
                GROUP BY assignedAt
                ORDER BY assignedAt;
                """,
                (start, end, percentile),
            )
            rows = await cur.fetchall()

            # Convert to dict
            output = {}
            for date, value in rows:
                day_str = date.date().isoformat()
                output[day_str] = value
            return output

    async def disconnect(self):
        if self.connection:
            await self.connection.close()
