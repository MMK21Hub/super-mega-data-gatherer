from datetime import date, datetime, timedelta
from aiohttp import ClientSession
import structlog

from env import get_env_or_raise

PROMETHEUS_URL = get_env_or_raise("PROMETHEUS_URL")
NEPHTHYS_DATABASE_URL = get_env_or_raise("NEPHTHYS_DATABASE_URL")

logger = structlog.get_logger()


async def query_prometheus_range(
    query: str, start: datetime, end: datetime, step: timedelta
):
    http = ClientSession()  # TODO: persist session
    async with http.get(
        PROMETHEUS_URL + "/api/v1/query_range",
        params={
            "query": query,
            "start": start.timestamp(),
            "end": end.timestamp(),
            "step": step.total_seconds(),
        },
    ) as response:
        json = await response.json()
        if json["status"] != "success":
            logger.error("Failed to query Prometheus", query=query, response=json)
            raise RuntimeError("Failed to query Prometheus")
        await http.close()
        return json["data"]


async def get_unresolved_tickets(start: datetime, end: datetime, step: timedelta):
    response = await query_prometheus_range(
        query="""
        nephthys_in_progress_tickets{instance="support-watcher-flavortown:9000"}
        + nephthys_open_tickets{instance="support-watcher-flavortown:9000"}
        """,
        start=start,
        end=end,
        step=step,
    )

    series = response["result"]
    this_series = series[0]
    values_over_time = this_series["values"]
    result_series: dict[str, int] = {}
    for timestamp, value in values_over_time:
        day = date.fromtimestamp(float(timestamp))
        result_series[day.isoformat()] = int(value)

    return result_series
