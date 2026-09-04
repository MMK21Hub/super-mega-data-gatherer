from datetime import date, timedelta

import structlog
from psycopg_pool import AsyncConnectionPool

from env import get_env_or_raise

db_url = get_env_or_raise("NEPHTHYS_DATABASE_URL")
logger = structlog.get_logger()


class DatabaseClient:
    def __init__(self):
        self.db_url = db_url
        self.connection_pool = AsyncConnectionPool(
            self.db_url,
            min_size=1,
            max_size=2,
            timeout=5,
            open=False,
            check=AsyncConnectionPool.check_connection,
            max_idle=5 * 60,
        )

    async def open_pool(self):
        await self.connection_pool.open()

    async def close_pool(self):
        await self.connection_pool.close()

    async def get_question_hang_times(self, start: date, end: date, percentile: float):
        end = end + timedelta(days=1)

        async with self.connection_pool.connection() as conn, conn.cursor() as cur:
            await cur.execute(
                """
                WITH params AS (
                    SELECT
                        %s::timestamp AS start_time,
                        %s::timestamp AS end_time,
                        %s::float8    AS percentile
                ),
                days AS (
                    SELECT generate_series(
                        p.start_time,
                        p.end_time,
                        interval '1 day'
                    ) AS day
                    FROM params p
                ),
                hangs AS (
                    SELECT
                        d.day,
                        EXTRACT(EPOCH FROM (
                            LEAST(COALESCE(t."assignedAt", p.end_time), d.day + interval '1 day')
                            - t."createdAt"
                        )) AS hang_seconds
                    FROM days d
                    CROSS JOIN params p
                    JOIN "Ticket" t
                        ON t."createdAt" <= d.day
                        AND (t."closedAt" >= d.day OR t."closedAt" IS NULL)
                    WHERE t."createdAt" <= p.end_time
                    AND (t."closedAt" >= p.start_time OR t."closedAt" IS NULL)
                )
                SELECT
                    day AS "time",
                    percentile_cont(p.percentile) WITHIN GROUP (ORDER BY hang_seconds) AS hang_time,
                    COUNT(*) AS count
                FROM hangs
                CROSS JOIN params p
                GROUP BY day, p.percentile
                ORDER BY day;
                """,
                (start, end, percentile),
            )
            rows = await cur.fetchall()

            # Convert to dict
            output = {}
            debug_output = []
            for date, hang_time, count in rows:
                day_str = date.date().isoformat()
                rounded_value = round(hang_time, 2)
                output[day_str] = rounded_value
                debug_output.append(
                    {"date": day_str, "value": rounded_value, "count": count}
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
            logger.exception("Database health check failed", error=str(e))
            return False
