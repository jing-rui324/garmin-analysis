"""Explore the Garmin Personal API and save one scrubbed sample activity.

One-off tool, not part of the pipeline. Run from the project root:
    python explore_api.py
"""

import json
import os
from pathlib import Path

from dotenv import load_dotenv
from garmin_personal_api import GarminPersonalApiClient, PersonalApiAuthenticator

SAMPLE_PATH = Path(__file__).parent / "docs" / "sample_activity.json"

# Exact keys to mask. Lists of other people / free text are emptied entirely.
KEYS_TO_MASK = {
    "activityId",
    "activityName",
    "description",
    "locationName",
    "comments",
    "activityLikeAuthors",
}

# Any key containing one of these (case-insensitive) gets masked
PATTERNS_TO_MASK = ("latitude", "longitude", "owner", "url", "uuid", "fullname", "displayname")

# Pseudonymised ID: looks realistic, but doesn't point to a real activity
FAKE_ACTIVITY_ID = 1000000001


def get_client():
    """Exchange the API key for a token and return an open client."""
    load_dotenv()
    api_key = os.getenv("GARMIN_PERSONAL_API_KEY")
    if not api_key:
        raise SystemExit("GARMIN_PERSONAL_API_KEY not found. Check your .env file")

    with PersonalApiAuthenticator() as authenticator:
        token = authenticator.obtain_token(api_key)

    return GarminPersonalApiClient(token.access_token)


def fetch_runs(client, n):
    """Return the n most recent runs (newest first), including subtypes."""
    return client.search_activities(start=0, limit=n, activity_type="running")


def summarise(runs):
    for run in runs:
        print(
            f"{run['activityId']} | {run['startTimeLocal']} | "
            f"{run['activityType']['typeKey']:<18} | "
            f"{run.get('distance', 0) / 1000:6.2f} km | "
            f"{run.get('duration', 0) / 60:6.1f} min"
        )


def is_sensitive(key):
    lowered = key.lower()
    return key in KEYS_TO_MASK or any(pattern in lowered for pattern in PATTERNS_TO_MASK)


def mask_value(key, value):
    """Return a placeholder of the same type, so the schema stays visible."""
    if key == "activityId":
        return FAKE_ACTIVITY_ID
    if isinstance(value, bool):  # before int: True is also an int in Python
        return False
    if isinstance(value, float):
        return 0.0
    if isinstance(value, int):
        return 0
    if isinstance(value, str):
        return "REDACTED"
    if isinstance(value, list):
        return []
    if isinstance(value, dict):
        return {}
    return None


def scrub(value):
    """Return a scrubbed copy of an activity. Walks nested dicts and lists."""
    if isinstance(value, dict):
        return {
            key: mask_value(key, inner) if is_sensitive(key) else scrub(inner)
            for key, inner in value.items()
        }
    if isinstance(value, list):
        return [scrub(item) for item in value]
    return value  # numbers, strings, bools, None: safe to keep as-is


def sensitive_values(original):
    """Collect the real values that must never appear in the scrubbed output."""
    found = []

    def collect(value):
        if isinstance(value, dict):
            for key, inner in value.items():
                if is_sensitive(key) and isinstance(inner, (str, int, float)) and not isinstance(inner, bool):
                    found.append(str(inner))
                collect(inner)
        elif isinstance(value, list):
            for item in value:
                collect(item)

    collect(original)
    # Ignore tiny values like "0" that would match everywhere
    return [v for v in found if len(v) >= 4]


def check_clean(scrubbed, original):
    """Raise if any real sensitive value from the original survived scrubbing."""
    text = json.dumps(scrubbed)
    leaks = [value for value in sensitive_values(original) if value in text]
    if leaks:
        raise ValueError(f"Scrubbing missed {len(leaks)} sensitive value(s). Not saving.")


def main():
    with get_client() as client:
        runs = fetch_runs(client, 10)

    if not runs:
        raise SystemExit("No runs returned. Nothing to sample.")

    summarise(runs)

    # Sample = the longest recent run: it documents the most fields
    sample = max(runs, key=lambda run: run.get("distance", 0))
    cleaned = scrub(sample)
    check_clean(cleaned, sample)

    SAMPLE_PATH.parent.mkdir(exist_ok=True)
    with open(SAMPLE_PATH, "w", encoding="utf-8") as f:
        json.dump(cleaned, f, indent=2, sort_keys=True)
    print(f"Saved scrubbed sample ({sample['activityType']['typeKey']}) to {SAMPLE_PATH}")


if __name__ == "__main__":
    main()
