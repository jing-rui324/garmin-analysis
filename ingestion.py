import os
from dotenv import load_dotenv
from garmin_personal_api import (
    GarminPersonalApiClient,
    PersonalApiAuthenticator,
)
from datetime import date, timezone, datetime, timedelta
import psycopg

load_dotenv()
api_key = os.getenv("GARMIN_PERSONAL_API_KEY")
database_url = os.getenv("DATABASE_URL")

with PersonalApiAuthenticator() as authenticator:
    token = authenticator.obtain_token(api_key)

with GarminPersonalApiClient(token.access_token) as client:
    start = 0
    limit = 99
    insert_sql = """
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
        
    with psycopg.connect(database_url) as connection:
        latest_start_time = connection.execute("SELECT MAX(start_time) FROM raw.garmin_activities").fetchone()[0]
        if latest_start_time is None:
            start_date = date(2024, 1, 1)
        else:
            start_date = latest_start_time.date() - timedelta(days=3)

        end_date = date.today()
        
        with connection.cursor() as cursor:
            while True:
                page = client.search_activities(
                    start=start,
                    limit=limit,
                    start_date=start_date,
                    end_date=end_date
                    )
                print(f"Fetched {len(page)} activities at offset {start}")
                print(f"Fetching activities from {start_date} to {end_date}")

                for activity in page:
                    activity_id = activity["activityId"]
                    start_time = datetime.strptime(
                        activity["startTimeGMT"],
                        "%Y-%m-%d %H:%M:%S",
                    ).replace(tzinfo=timezone.utc)
                    payload = activity
                    source_endpoint = "/activitylist-service/activities/search/activities"
        
                    cursor.execute(
                        insert_sql,
                        (activity_id, start_time, psycopg.types.json.Jsonb(payload), source_endpoint),
                    )

                connection.commit()

                if len(page) < limit:
                    break

                start += len(page)