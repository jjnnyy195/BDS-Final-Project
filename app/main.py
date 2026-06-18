"""
main.py  (uvicorn app.main:app)
===============================
The single deployable web service. Serves:
  * GET /                      -> the dashboard (server-rendered)
  * GET /api/trending          -> rising/falling skills
  * GET /api/snapshot          -> latest-month skill ranking
  * GET /api/skill/{skill}     -> one skill's monthly time series
  * GET /api/salary            -> salary premium ranking
  * GET /api/digest            -> weekly digest (json) | ?format=text
  * GET /api/health            -> liveness + row counts

A background APScheduler job re-runs ingestion daily. On an empty database at
startup we auto-seed from the sample fixtures so a fresh deploy is never blank.
"""

import os
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request, Query
from fastapi.responses import HTMLResponse, PlainTextResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from apscheduler.schedulers.background import BackgroundScheduler

from app.db import init_db, get_session, JobPosting
from app import queries
from app.chart import line_chart, PALETTE
from app.digest import build_digest, render_text
from ingestion.run import run as run_ingestion

BASE = os.path.dirname(__file__)
templates = Jinja2Templates(directory=os.path.join(BASE, "templates"))

INGEST_MODE = os.environ.get("INGEST_MODE", "sample")   # 'sample' or 'live'
scheduler = BackgroundScheduler()


def _row_count() -> int:
    s = get_session()
    try:
        return s.query(JobPosting).count()
    finally:
        s.close()


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    if _row_count() == 0:
        # Fresh DB: seed so the dashboard is never empty on first load.
        run_ingestion(mode="sample")
    # Daily refresh. In sample mode this is a no-op-ish reaggregation; in live
    # mode it pulls fresh postings from JSearch.
    scheduler.add_job(lambda: run_ingestion(mode=INGEST_MODE),
                      "interval", hours=24, id="daily_ingest", replace_existing=True)
    scheduler.start()
    yield
    scheduler.shutdown(wait=False)


app = FastAPI(title="SkillSignal", lifespan=lifespan)

_static_dir = os.path.join(BASE, "static")
if os.path.isdir(_static_dir):
    app.mount("/static", StaticFiles(directory=_static_dir), name="static")


# ----------------------------- JSON API ------------------------------------
@app.get("/api/health")
def health():
    return {"status": "ok", "postings": _row_count(),
            "markets": queries.market_totals()}


@app.get("/api/trending")
def api_trending(market: str = "GLOBAL", window: int = 3, top_n: int = 8):
    return queries.trending(market, window=window, top_n=top_n)


@app.get("/api/snapshot")
def api_snapshot(market: str = "GLOBAL", month: str = None):
    return queries.snapshot(market, month=month)


@app.get("/api/skill/{skill}")
def api_skill(skill: str, market: str = "GLOBAL"):
    return {"skill": skill, "market": market,
            "series": queries.skill_series(skill, market)}


@app.get("/api/salary")
def api_salary(market: str = "GLOBAL", min_postings: int = 5):
    return queries.salary_premium(market, min_postings=min_postings)


@app.get("/api/digest")
def api_digest(market: str = "GLOBAL", format: str = Query("json")):
    d = build_digest(market)
    if format == "text":
        return PlainTextResponse(render_text(d))
    return JSONResponse(d)


# ----------------------------- Dashboard ------------------------------------
@app.get("/", response_class=HTMLResponse)
def dashboard(request: Request, market: str = "GLOBAL"):
    if market not in ("GLOBAL", "TW"):
        market = "GLOBAL"
    months = queries.list_months(market)
    t = queries.trending(market, window=3, top_n=8)
    snap = queries.snapshot(market)
    salary = queries.salary_premium(market)[:12]
    totals = queries.market_totals()

    # Build series for the top-6 most-demanded skills for the line chart.
    top6 = [row["skill"] for row in snap[:6]]
    series = {sk: queries.skill_series(sk, market) for sk in top6}
    chart_svg = line_chart(series, months)

    return templates.TemplateResponse(request, "dashboard.html", {
        "market": market, "months": months,
        "rising": t["rising"], "falling": t["falling"],
        "snapshot": snap, "salary": salary, "totals": totals,
        "series": series, "top6": top6, "chart_svg": chart_svg,
        "palette": PALETTE,
        "latest_month": months[-1] if months else "—",
    })
