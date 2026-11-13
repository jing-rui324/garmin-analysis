# Garmin activities analysis project

An ELT pipeline that pulls my running activities from the Garmin Personal API into Postgres and models them with dbt into tested, analysis-ready tables, such as weekly training volume with a rolling 4-week average.

```
Garmin Personal API
        |
        v
ingestion.py           incremental or backfill date windows, idempotent upserts
        |
        v
Postgres (Docker)      raw.garmin_activities: one JSONB payload per activity
        |
        v
dbt                    staging -> intermediate -> marts, tested at every layer
```

## Status

| Part                                                            | State          |
| --------------------------------------------------------------- | -------------- |
| Ingestion: incremental and backfill modes, idempotent upserts   | ✅ Done        |
| Postgres in Docker, schema created by an init script            | ✅ Done        |
| dbt models: staging → intermediate → marts                      | ✅ Done        |
| dbt tests: 17 data tests, including a cross-mart reconciliation | ✅ Done        |
| Orchestration with Airflow (ingest → dbt build, daily)          | 🚧 In progress |
| Dashboard, CI                                                   | ⬜ Planned     |

## What's in the repo

| Path                                                   | What it does                                                                                                      |
| ------------------------------------------------------ | ----------------------------------------------------------------------------------------------------------------- |
| [ingestion.py](ingestion.py)                           | Fetches activities for a date window (paginated, in chunks) and upserts the raw JSON into `raw.garmin_activities` |
| [compose.yaml](compose.yaml), [db/init/](db/init/)     | Postgres 16 with a named volume; the init script creates the `raw` schema and table on first start                |
| [garmin_dbt/](garmin_dbt/)                             | dbt project: models, YAML tests and singular SQL tests                                                            |
| [explore_api.py](explore_api.py)                       | One-off exploration script that saves a scrubbed sample activity                                                  |
| [docs/sample_activity.json](docs/sample_activity.json) | One activity with all personal fields masked, to document the payload shape                                       |

### dbt models

| Model                    | Layer        | Description                                                                                                                 |
| ------------------------ | ------------ | --------------------------------------------------------------------------------------------------------------------------- |
| `stg_garmin__activities` | Staging      | One row per activity. Extracts and casts fields from the JSON payload; no filtering                                         |
| `int_runs`               | Intermediate | Runs only, including treadmill and track runs via Garmin's activity type hierarchy. Unit conversions and pace               |
| `fct_runs`               | Mart         | One row per run, explicit columns, full precision                                                                           |
| `agg_weekly_training`    | Mart         | One row per week, including weeks with no runs (date spine). Distance, time, pace, longest run and a rolling 4-week average |

## Running it

Requires **Python 3.12** (dbt doesn't support newer versions yet), Docker Desktop, and a Garmin Personal API key.

1. Create a `.env` file in the project root:
   ```
   GARMIN_PERSONAL_API_KEY=your-key
   DATABASE_URL=postgresql://garmin:garmin@localhost:55432/garmin
   ```
2. Start Postgres and install dependencies:
   ```
   docker compose up -d
   py -3.12 -m venv venv
   venv\Scripts\activate
   pip install -r requirements.txt
   ```
3. Ingest:
   ```
   python ingestion.py                                       # incremental: last stored activity minus 3 days, up to today
   python ingestion.py --start 2024-01-01 --end 2024-12-31   # backfill an explicit range, in 30-day chunks
   python ingestion.py --help
   ```
4. Build and test the models. This needs a dbt profile named `garmin_dbt` in `~/.dbt/profiles.yml` pointing at `localhost:55432`, schema `analytics`:
   ```
   cd garmin_dbt
   dbt deps
   dbt build
   ```

## Design decisions

- **ELT, with raw stored as JSONB.** The full API payload is kept as-is, and all parsing happens in dbt. If a model needs a new field, it already exists in raw, so there's no need to re-fetch.
- **Idempotent upserts.** `INSERT ... ON CONFLICT (activity_id) DO UPDATE` means any window can be re-run safely. Re-ingesting overlapping dates updates rows instead of duplicating them.
- **The date window is an input, not something the loader works out for itself.** `ingest_window(client, connection, start, end)` fetches exactly the dates it's given. The command-line script derives an incremental window, with a 3-day lookback for late watch syncs; Airflow will pass each run's data interval instead.
- **Chunked backfills.** Long ranges are split into chunks that each commit separately, so a failure part-way through keeps earlier progress, and a re-run is harmless.
- **Validate input where it enters.** Command-line arguments are checked before any API or database connection is opened; missing configuration fails with a clear message.
- **Runs are identified by Garmin's type hierarchy (`parentTypeId = 1`), not by name.** Filtering on `typeKey = 'running'` silently dropped 150 treadmill and track runs. An independent singular test now guards against this.
- **UTC for loading, local time for analysis.** The incremental watermark uses `startTimeGMT`; dates and weeks in the marts use the watch's local start time.
- **Never average averages.** Weekly pace is total time ÷ total distance, not the mean of each run's pace.
- **Weeks with no runs are rows, not gaps.** A date spine fills empty weeks with 0 runs and NULL pace (pace is undefined, not zero), so rolling averages count rest weeks correctly. The rolling average is NULL until 4 full weeks exist, and for the current, incomplete week.
- **Two-tier range tests.** Physically impossible values (e.g. max HR outside 30–230) fail the build; unusual but possible values (max HR above 200) only warn.
- **Reconciliation test.** Total distance and run count in the weekly mart must match `fct_runs`, which catches rows lost or duplicated by joins.

## Privacy

Activity data is personal health and location data, so none of it is committed. `.env`, raw exports and database volumes are git-ignored, and the only sample payload is scrubbed: names, IDs, GPS coordinates and owner details are masked, and a check refuses to save the file if any original sensitive value survives.
