"""Handles generating, caching, and string the stats"""

from datetime import date, datetime, timedelta
from sys import exc_info

import structlog

from database_stats import DatabaseClient
from prometheus_stats import get_unresolved_tickets


type HangTimeData = dict[str, dict[str, float]]
type UnresolvedTicketsData = dict[str, int]


class SuperMegaStatsStore:
    def __init__(
        self,
        hang_time_data: HangTimeData | None = None,
        unresolved_tickets_data: UnresolvedTicketsData | None = None,
    ):
        self._hang_time_data: HangTimeData | None = hang_time_data
        self._unresolved_tickets_data: UnresolvedTicketsData | None = (
            unresolved_tickets_data
        )
        self.updated_at: datetime | None = (
            datetime.now() if (hang_time_data or unresolved_tickets_data) else None
        )

    @property
    def hang_time_data(self) -> HangTimeData | None:
        return self._hang_time_data

    @hang_time_data.setter
    def hang_time_data(self, value: HangTimeData):
        self._hang_time_data = value
        self.updated_at = datetime.now()

    @property
    def unresolved_tickets_data(self) -> UnresolvedTicketsData | None:
        return self._unresolved_tickets_data

    @unresolved_tickets_data.setter
    def unresolved_tickets_data(self, value: UnresolvedTicketsData):
        self._unresolved_tickets_data = value
        self.updated_at = datetime.now()


class SuperMegaStatsManager:
    def __init__(self):
        # A map of cache keys (which are (start, end) tuples) to stats stores
        self.stats_cache: dict[tuple[date, date], SuperMegaStatsStore] = dict()
        self._db_client = DatabaseClient()

    async def db_client(self) -> DatabaseClient:
        await self._db_client.open_pool()
        return self._db_client

    async def health_check(self) -> dict[str, bool]:
        db = await self.db_client()
        healths = {"database": await db.is_healthy()}
        overall_health = all(healths.values())
        return {"ok": overall_health, **healths}

    async def get_stats(self, start: date, end: date) -> SuperMegaStatsStore:
        logger = structlog.get_logger()
        cache_key = (start, end)
        if cache_key in self.stats_cache:
            store = self.stats_cache[cache_key]
            # Consider entries stale if they're from a previous day
            if store.updated_at and store.updated_at.date() == date.today():
                return store

        # No cache entry, so data must be fetched
        db = await self.db_client()
        store = SuperMegaStatsStore()
        store.unresolved_tickets_data = await get_unresolved_tickets(
            start, end, step=timedelta(days=1)
        )
        try:
            store.hang_time_data = {
                "p90": await db.get_question_hang_times(start, end, 0.90),
                "p95": await db.get_question_hang_times(start, end, 0.95),
            }
        except Exception:
            logger.error("Failed to fetch hang time", exc_info=exc_info())
        self.stats_cache[cache_key] = store
        return store
