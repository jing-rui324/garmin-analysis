import os
from datetime import date, timezone, datetime, timedelta
import logging

from dotenv import load_dotenv
from garmin_personal_api import (
    GarminPersonalApiClient,
    PersonalApiAuthenticator,
)

import psycopg
from psycopg.types.json import Jsonb

logger = logging.getLogger(__name__)

INSERT_SQL = """
    INSERT INTO raw.garmin_activities (
        activity_id,
        start_time,
        payload,
        source_endpoint
    ) VALUES (%s, %s, %s, %s)
    ON CONFLICT (activity_id) DO UPDATE SET
        start_time = EXCLUDED.start_time,
        payload = EXCLUDED.payload,
        ingested_at = EXCLUDED.ingested_at,
        source_endpoint = EXCLUDED.source_endpoint
"""

SOURCE_ENDPOINT = "/activitylist-service/activities/search/activities"

DEFAULT_START_DATE = date(2024, 1, 1)  # Default start date if no previous data exists

MAX_START_SQL = "SELECT MAX(start_time) FROM raw.garmin_activities"


def get_client():
    """Exchange the API key for a token and return an open client."""
    load_dotenv()
    api_key = os.getenv("GARMIN_PERSONAL_API_KEY")
    if not api_key:
        raise SystemExit("GARMIN_PERSONAL_API_KEY not found. Check your .env file")

    with PersonalApiAuthenticator() as authenticator:
        token = authenticator.obtain_token(api_key)

    return GarminPersonalApiClient(token.access_token)


def date_chunks(start_date, end_date, chunk_days=30):
    """Split the date range into chunks of chunk_days."""
    if chunk_days <= 0:
        raise ValueError(
            f"Chunk days: {chunk_days} is invalid. It must be a positive integer"
        )

    if end_date < start_date:
        raise ValueError(f"End date: {end_date} is before Start date: {start_date}")

    chunks_list = []
    current_start = start_date
    while current_start <= end_date:
        current_end = min(current_start + timedelta(days=chunk_days - 1), end_date)
        chunks_list.append((current_start, current_end))
        current_start = current_end + timedelta(days=1)
    return chunks_list


def fetch_activities(client, start_date, end_date):
    """Fetch all activities between start_date and end_date, handling pagination."""
    start, limit = 0, 99
    activities = []

    logger.debug("Fetching activities from %s to %s", start_date, end_date)
    while True:
        page = client.search_activities(
            start=start, limit=limit, start_date=start_date, end_date=end_date
        )
        activities.extend(page)
        logger.debug("Fetched %d activities at offset %d", len(page), start)

        if len(page) < limit:
            break
        start += len(page)

    return activities


def upsert_activities(connection, activities):
    """Upsert activities into the database."""
    with connection.cursor() as cursor:
        for activity in activities:
            activity_id = activity["activityId"]
            start_time = datetime.strptime(
                activity["startTimeGMT"],
                "%Y-%m-%d %H:%M:%S",
            ).replace(tzinfo=timezone.utc)

            cursor.execute(
                INSERT_SQL,
                (activity_id, start_time, Jsonb(activity), SOURCE_ENDPOINT),
            )
    connection.commit()

    return len(activities)


def ingest_window(client, connection, start_date, end_date, chunk_days=30):
    """Ingest activities in chunks between start_date and end_date."""
    total = 0
    chunks = date_chunks(start_date, end_date, chunk_days)

    for i, (chunk_start, chunk_end) in enumerate(chunks, start=1):
        activities = fetch_activities(client, chunk_start, chunk_end)
        count = upsert_activities(connection, activities)
        total += count
        logger.info(
            "Chunk %d/%d (%s to %s): Upserted %d activities into the database.",
            i,
            len(chunks),
            chunk_start,
            chunk_end,
            count,
        )

    return total


def incremental_window(connection, lookback_days=3):
    """Determine the start and end dates for incremental ingestion."""
    latest_start_time = connection.execute(MAX_START_SQL).fetchone()[0]
    if latest_start_time is None:
        start_date = DEFAULT_START_DATE
    else:
        start_date = latest_start_time.date() - timedelta(days=lookback_days)

    end_date = date.today()
    return start_date, end_date


def main():
    logging.basicConfig(
        level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s"
    )
    load_dotenv()
    database_url = os.getenv("DATABASE_URL")
    if not database_url:
        raise SystemExit("DATABASE_URL not found. Check your .env file")

    with get_client() as client, psycopg.connect(database_url) as connection:
        start_date, end_date = incremental_window(connection)
        total = ingest_window(client, connection, start_date, end_date)
        logger.info(
            "Ingested a total of %d activities from %s to %s.",
            total,
            start_date,
            end_date,
        )


if __name__ == "__main__":
    main()
