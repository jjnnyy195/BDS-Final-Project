"""
run.py  (python -m ingestion.run)
=================================
Orchestrates one ingestion cycle:

  1. Fetch postings for each niche query x market (live or sample mode).
  2. Deduplicate on external_id and upsert into job_postings.
  3. Extract canonical skills from each description -> posting_skills.
  4. Rebuild the skill_trends monthly aggregate table.

Usage
-----
  python -m ingestion.run --sample        # no key, uses fixtures
  python -m ingestion.run --live --pages 2 # real JSearch calls
"""

import argparse
from collections import defaultdict
from datetime import date

from app.db import init_db, get_session, JobPosting, PostingSkill, SkillTrend
from app.skills_taxonomy import extract_skills, category_of
from ingestion.jsearch_client import (
    fetch_live, fetch_sample, NICHE_QUERIES, MARKETS,
)


def _collect(mode: str, pages: int):
    """Return a flat list of normalized posting dicts for all markets."""
    rows = []
    for market in MARKETS:
        if mode == "sample":
            rows.extend(fetch_sample(market))
        else:
            for q in NICHE_QUERIES:
                rows.extend(fetch_live(q, market, pages=pages))
    return rows


def _upsert_postings(session, rows):
    """Insert new postings (dedup on external_id) and attach skills.
    Returns (new_count, skipped_count)."""
    existing = {r[0] for r in session.query(JobPosting.external_id).all()}
    new_count = 0
    skipped = 0
    for r in rows:
        if r["external_id"] in existing:
            skipped += 1
            continue
        existing.add(r["external_id"])
        posting = JobPosting(
            external_id=r["external_id"], title=r["title"], employer=r["employer"],
            market=r["market"], location=r["location"], is_remote=r["is_remote"],
            salary_min=r["salary_min"], salary_max=r["salary_max"],
            salary_currency=r["salary_currency"], salary_period=r["salary_period"],
            salary_annual_usd=r["salary_annual_usd"], posted_date=r["posted_date"],
            description=r["description"], source=r["source"],
        )
        for skill in extract_skills(r["description"]):
            posting.skills.append(PostingSkill(skill=skill, category=category_of(skill)))
        session.add(posting)
        new_count += 1
    session.commit()
    return new_count, skipped


def rebuild_trends(session):
    """Recompute skill_trends from scratch off job_postings + posting_skills."""
    session.query(SkillTrend).delete()
    session.commit()

    postings = session.query(JobPosting).all()

    # month -> market -> total postings   (denominator for share)
    totals = defaultdict(lambda: defaultdict(int))
    # (month, market, skill) -> [count, salary_sum, salary_n, category]
    agg = defaultdict(lambda: [0, 0.0, 0, ""])

    # Map posting id -> (month, market, salary) once.
    for p in postings:
        month = p.posted_date.strftime("%Y-%m")
        totals[month][p.market] += 1
        for ps in p.skills:
            key = (month, p.market, ps.skill)
            cell = agg[key]
            cell[0] += 1
            if p.salary_annual_usd:
                cell[1] += p.salary_annual_usd
                cell[2] += 1
            cell[3] = ps.category

    for (month, market, skill), (count, sal_sum, sal_n, cat) in agg.items():
        denom = totals[month][market] or 1
        session.add(SkillTrend(
            month=month, market=market, skill=skill, category=cat,
            posting_count=count, share=round(count / denom, 4),
            avg_salary_usd=round(sal_sum / sal_n, 2) if sal_n else None,
        ))
    session.commit()
    return len(agg)


def run(mode="sample", pages=1):
    init_db()
    session = get_session()
    try:
        rows = _collect(mode, pages)
        new_count, skipped = _upsert_postings(session, rows)
        trend_rows = rebuild_trends(session)
        print(f"[{date.today()}] mode={mode} fetched={len(rows)} "
              f"new={new_count} skipped_dupes={skipped} trend_rows={trend_rows}")
    finally:
        session.close()


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    g = ap.add_mutually_exclusive_group()
    g.add_argument("--sample", action="store_true", help="use bundled fixtures (no key)")
    g.add_argument("--live", action="store_true", help="call the real JSearch API")
    ap.add_argument("--pages", type=int, default=1, help="pages per query in live mode")
    args = ap.parse_args()
    mode = "live" if args.live else "sample"
    run(mode=mode, pages=args.pages)
