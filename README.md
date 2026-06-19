# SkillSignal — Data & ML Hiring Intelligence

A small end-to-end system that turns public job-posting data into a product: a feed of which engineering skills are rising and falling in demand for the data/ML engineering job market, in Taiwan and globally.

It ingests live postings from Google for Jobs (via the JSearch API), extracts a curated set of engineering skills from each description, aggregates them into monthly trends, and serves the result as a dashboard, a JSON API, and a weekly digest.

> Big Data Systems final project — National Taiwan University, Spring 2026.

**Live demo:** https://skillsignal-zjbb.onrender.com
**Repository:** https://github.com/jjnnyy195/BDS-Final-Project

---

## What it does

- **Ingests** data/ML engineering postings for two markets (Taiwan + global)
  from the JSearch API over Google for Jobs.
- **Extracts** ~30 canonical skills (Spark, Airflow, dbt, Snowflake, LLM, RAG,
  vector DBs, …) from free-text job descriptions using a curated taxonomy.
- **Normalizes** disclosed salaries into a single annual-USD figure so the two
  markets are comparable.
- **Aggregates** everything into monthly demand-share and average-salary figures
  per skill per market.
- **Delivers** via (a) a server-rendered dashboard, (b) a JSON API, and (c) a
  weekly text digest.

The deployed instance runs on **live data**. Trend depth accumulates over time
as the daily scheduler adds months of history; a single pull populates the
current month.

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

---

## Running locally

The system runs with **no API key** using bundled sample data — the simplest
way to try it.

```bash
# 1. (Recommended) create and activate a virtual environment
python3 -m venv .venv
source .venv/bin/activate          # Windows: .venv\Scripts\activate

# 2. Install dependencies
pip install -r requirements.txt

# 3. Run one ingestion cycle in SAMPLE mode (builds a local SQLite DB)
python -m ingestion.run --sample

# 4. Start the web service
uvicorn app.main:app --reload
```

Then open <http://127.0.0.1:8000> for the dashboard.

> Requires Python 3.10 or newer (the code uses modern type-hint syntax).

### Running locally with live data (optional)

1. Get a free JSearch API key (free tier: 200 requests/month, no credit card)
   from RapidAPI: <https://rapidapi.com/letscrape-6bRBa3QguO5/api/jsearch>
2. Set the key and run a live cycle:

   ```bash
   export RAPIDAPI_KEY=your_key_here
   python -m ingestion.run --live
   ```

Each cycle issues one request per (niche query × market) — 8 requests total — so the free tier supports ~25 refresh cycles per month.

---

## API endpoints

| Endpoint | What it returns |
|---|---|
| `GET /` | The dashboard (HTML). Use `?market=TW` or `?market=GLOBAL`. |
| `GET /api/health` | Liveness + row counts. |
| `GET /api/trending?market=GLOBAL&window=3` | Biggest rising / falling skills. |
| `GET /api/snapshot?market=GLOBAL` | Latest-month skill ranking. |
| `GET /api/skill/{skill}?market=GLOBAL` | One skill's monthly time series. |
| `GET /api/salary?market=GLOBAL` | Average disclosed salary per skill. |
| `GET /api/digest?market=GLOBAL&format=text` | Weekly digest (json or text). |
| `GET /api/refresh?secret=...` | Manually trigger an ingestion cycle. |

---

## Reproducing the data-collection step

```bash
# Regenerate the deterministic sample dataset (seed = 42)
python scripts/make_sample_data.py

# Rebuild the database + aggregates from it
rm -f data/skillsignal.db
python -m ingestion.run --sample

# Inspect the resulting trends
python -c "from app.queries import trending; import json; \
print(json.dumps(trending('GLOBAL'), indent=2))"
```

---

## Project layout

```
.
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
├── render.yaml            Render deploy blueprint
└── README.md
```

---

## Deployment

Deployed on Render via the included `render.yaml` blueprint, which provisions a web service plus a Postgres database. To switch an instance to live data, set the environment variables `INGEST_MODE=live` and `RAPIDAPI_KEY=<your key>`, then trigger a refresh.

---

## Notes & limitations

- Most real postings omit salary, so the salary signal is best-effort and can be sparse; the product treats it as secondary to demand share.
- Trend depth builds up over time — a single ingestion fills only the current month, and the rising/falling view becomes meaningful once several months of history accumulate (the cold-start problem discussed in the report).
- Skill extraction is dictionary-based for transparency and reproducibility; a production version would add an LLM tagging pass to improve recall.