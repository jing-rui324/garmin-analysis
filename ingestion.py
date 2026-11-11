import os
from datetime import date, timezone, datetime, timedelta

from dotenv import load_dotenv
from garmin_personal_api import (
    GarminPersonalApiClient,
    PersonalApiAuthenticator,
)
import psycopg
from psycopg.types.json import Jsonb

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


def fetch_activities(client, start_date, end_date):
    """Fetch all activities between start_date and end_date, handling pagination."""
    start, limit = 0, 99
    activities = []

    print(f"Fetching activities from {start_date} to {end_date}")
    while True:
        page = client.search_activities(
            start=start, limit=limit, start_date=start_date, end_date=end_date
        )
        activities.extend(page)
        print(f"Fetched {len(page)} activities at offset {start}")

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
    load_dotenv()
    database_url = os.getenv("DATABASE_URL")
    if not database_url:
        raise SystemExit("DATABASE_URL not found. Check your .env file")

    with get_client() as client, psycopg.connect(database_url) as connection:
        start_date, end_date = incremental_window(connection)
        activities = fetch_activities(client, start_date, end_date)
        count = upsert_activities(connection, activities)
        print(f"Upserted {count} activities into the database.")


if __name__ == "__main__":
    main()
