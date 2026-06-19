# SkillSignal

A small end-to-end system that turns public job-posting data into a paid product:
a monthly **skill-demand trend feed** for the data/ML engineering job market,
Taiwan-first plus a global comparison market.

It ingests postings from Google for Jobs (via the JSearch API), extracts a
canonical set of engineering skills from each description, aggregates them into
monthly trends, and serves the result as a dashboard, a JSON API, and a weekly
digest.

> Big Data Systems final project — National Taiwan University, Spring 2026.

---

## What it does

- Ingests data/ML engineering postings for two markets (TW + global).
- Extracts ~30 canonical skills (Spark, Airflow, dbt, Snowflake, LLM, RAG, vector DBs, …) from free-text descriptions using a curated taxonomy.
- Normalizes disclosed salaries into a single annual-USD figure so the two markets are comparable.
- Aggregates everything into monthly `skill_trends` rows (demand share + average salary per skill per market).
- Delivers via (a) a server-rendered dashboard, (b) a JSON API, and (c) a weekly text digest.

---

## Architecture

```
                 ┌──────────────────────┐
  Google for Jobs│   JSearch API        │  (live mode)
  via JSearch ──▶│   ingestion/         │
                 │   jsearch_client.py  │  ◀── sample fixtures (sample mode)
                 └──────────┬───────────┘
                            │  normalized posting dicts
                            ▼
                 ┌──────────────────────┐
                 │  ingestion/run.py    │  dedup → extract skills → upsert
                 │  skills_taxonomy.py  │
                 └──────────┬───────────┘
                            │
                            ▼
                 ┌──────────────────────┐
                 │  Postgres / SQLite   │  job_postings
                 │  app/db.py           │  posting_skills
                 │                      │  skill_trends (aggregate)
                 └──────────┬───────────┘
                            │  read side (app/queries.py)
                            ▼
                 ┌──────────────────────┐
                 │  FastAPI (app/main)  │
                 │  • / dashboard       │
                 │  • /api/* JSON       │
                 │  • /api/digest       │
                 └──────────────────────┘
   APScheduler re-runs ingestion daily.
```

A more detailed diagram is in the report.

---

## Quick start (no API key needed)

The system ships with seeded sample data, so it runs with zero external
dependencies. This is the recommended path for graders.

```bash
# 1. (Optional but recommended) create a virtual environment
python3 -m venv .venv
source .venv/bin/activate          # Windows: .venv\Scripts\activate

# 2. Install dependencies
pip install -r requirements.txt

# 3. (Optional) regenerate the sample dataset — already included in data/
python scripts/make_sample_data.py

# 4. Run one ingestion cycle in SAMPLE mode (builds the local SQLite DB)
python -m ingestion.run --sample

# 5. Start the web service
uvicorn app.main:app --reload
```

Then open <http://127.0.0.1:8000> for the dashboard.

> Note: on first launch the app auto-seeds itself from the sample fixtures if
> the database is empty, so step 4 is optional — but running it explicitly is
> the clearest way to see the pipeline work.

---

## Running with live data (optional)

1. Get a free JSearch API key (free tier = 200 requests/month, no credit card)
   from RapidAPI: <https://rapidapi.com/letscrape-6bRBa3QguO5/api/jsearch>
2. Copy `.env.example` to `.env` and set `RAPIDAPI_KEY`.
3. Run a live ingestion cycle:

   ```bash
   export RAPIDAPI_KEY=your_key_here      # or put it in .env
   python -m ingestion.run --live --pages 1
   ```

Each cycle issues one request per (niche query × market). With four queries and
two markets that is 8 requests, so the 200/month free tier supports ~25 refresh
cycles per month — plenty for a daily feed.

---

## API endpoints

| Endpoint | What it returns |
|---|---|
| `GET /` | The dashboard (HTML). `?market=TW` or `?market=GLOBAL`. |
| `GET /api/health` | Liveness + row counts. |
| `GET /api/trending?market=GLOBAL&window=3` | Biggest rising / falling skills. |
| `GET /api/snapshot?market=GLOBAL` | Latest-month skill ranking. |
| `GET /api/skill/{skill}?market=GLOBAL` | One skill's monthly time series. |
| `GET /api/salary?market=GLOBAL` | Average disclosed salary per skill. |
| `GET /api/digest?market=GLOBAL&format=text` | Weekly digest (json or text). |

---

## Reproducing the data-collection step

The demand evidence in the report is built from public job-posting data. To
reproduce the data layer end to end:

```bash
# Regenerate the seeded sample (deterministic, seed=42)
python scripts/make_sample_data.py

# Rebuild the DB + aggregates from it
rm -f data/skillsignal.db
python -m ingestion.run --sample

# Inspect the resulting trends
python -c "from app.queries import trending; import json; \
print(json.dumps(trending('GLOBAL'), indent=2))"
```

For live data, follow the "Running with live data" section above; the same
`ingestion/run.py` consumes real JSearch responses through the identical
parsing and aggregation path.

---

## Project layout

```
skillsignal/
├── app/
│   ├── main.py            FastAPI app: API + dashboard + scheduler
│   ├── db.py              SQLAlchemy models (Postgres / SQLite)
│   ├── skills_taxonomy.py canonical skill taxonomy + extraction
│   ├── queries.py         read-side aggregation helpers
│   ├── chart.py           dependency-free inline-SVG line chart
│   ├── digest.py          weekly digest builder
│   └── templates/
│       └── dashboard.html the dashboard UI
├── ingestion/
│   ├── jsearch_client.py  JSearch client + salary normalizer (live/sample)
│   └── run.py             ingestion orchestrator (python -m ingestion.run)
├── scripts/
│   └── make_sample_data.py  deterministic sample-data generator
├── data/
│   ├── sample_tw.json     seeded Taiwan fixtures
│   └── sample_global.json seeded global fixtures
├── requirements.txt
├── render.yaml            one-click Render deploy blueprint
├── .env.example
└── README.md
```

---

## Notes & limitations

- Sample data is clearly labeled in the UI ("LIVE DEMO / sample data") and is deterministic so results are reproducible.
- Salary coverage is sparse in real data (most postings omit pay); the product treats salary as a secondary, best-effort signal.
- Skill extraction is dictionary-based for transparency and reproducibility; a production version would layer in an LLM tagging pass for recall.
