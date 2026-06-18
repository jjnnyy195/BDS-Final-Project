"""
queries.py
==========
Read-side helpers. Everything the API and dashboard need to answer:
  * What skills are trending (rising / falling) right now?
  * What's the salary premium for a given skill?
  * Snapshot of the latest month, per market.

Kept separate from the web layer so it is unit-testable and reusable by the
weekly-digest generator.
"""

from collections import defaultdict
from typing import List, Dict, Optional

from app.db import get_session, SkillTrend, JobPosting, func


def list_months(market: str = "GLOBAL") -> List[str]:
    s = get_session()
    try:
        rows = (s.query(SkillTrend.month)
                .filter(SkillTrend.market == market)
                .distinct().order_by(SkillTrend.month).all())
        return [r[0] for r in rows]
    finally:
        s.close()


def latest_month(market: str = "GLOBAL") -> Optional[str]:
    months = list_months(market)
    return months[-1] if months else None


def skill_series(skill: str, market: str = "GLOBAL") -> List[Dict]:
    """Monthly share + posting_count time series for one skill."""
    s = get_session()
    try:
        rows = (s.query(SkillTrend)
                .filter(SkillTrend.skill == skill, SkillTrend.market == market)
                .order_by(SkillTrend.month).all())
        return [{"month": r.month, "share": r.share,
                 "posting_count": r.posting_count,
                 "avg_salary_usd": r.avg_salary_usd} for r in rows]
    finally:
        s.close()


def snapshot(market: str = "GLOBAL", month: Optional[str] = None) -> List[Dict]:
    """All skills for one month, ranked by share, with avg salary + category."""
    month = month or latest_month(market)
    if not month:
        return []
    s = get_session()
    try:
        rows = (s.query(SkillTrend)
                .filter(SkillTrend.market == market, SkillTrend.month == month)
                .order_by(SkillTrend.share.desc()).all())
        return [{"skill": r.skill, "category": r.category, "share": r.share,
                 "posting_count": r.posting_count,
                 "avg_salary_usd": r.avg_salary_usd} for r in rows]
    finally:
        s.close()


def trending(market: str = "GLOBAL", window: int = 3, top_n: int = 8) -> Dict[str, List[Dict]]:
    """Compare the latest month's share to `window` months earlier and return
    the biggest risers and fallers (by absolute share-point change)."""
    months = list_months(market)
    if len(months) < 2:
        return {"rising": [], "falling": []}
    latest = months[-1]
    base_idx = max(0, len(months) - 1 - window)
    base = months[base_idx]

    s = get_session()
    try:
        def share_map(m):
            rows = (s.query(SkillTrend.skill, SkillTrend.share, SkillTrend.category)
                    .filter(SkillTrend.market == market, SkillTrend.month == m).all())
            return {sk: (sh, cat) for sk, sh, cat in rows}

        now, then = share_map(latest), share_map(base)
    finally:
        s.close()

    deltas = []
    for skill, (sh_now, cat) in now.items():
        sh_then = then.get(skill, (0.0, cat))[0]
        deltas.append({
            "skill": skill, "category": cat,
            "share_now": sh_now, "share_then": sh_then,
            "delta": round(sh_now - sh_then, 4),
            "from_month": base, "to_month": latest,
        })
    deltas.sort(key=lambda d: d["delta"])
    falling = [d for d in deltas if d["delta"] < 0][:top_n]
    rising = [d for d in reversed(deltas) if d["delta"] > 0][:top_n]
    return {"rising": rising, "falling": falling}


def salary_premium(market: str = "GLOBAL", min_postings: int = 5) -> List[Dict]:
    """Average disclosed annual-USD salary per skill (latest month), ranked.
    This is the spine of the willingness-to-pay argument."""
    month = latest_month(market)
    if not month:
        return []
    s = get_session()
    try:
        rows = (s.query(SkillTrend)
                .filter(SkillTrend.market == market, SkillTrend.month == month,
                        SkillTrend.avg_salary_usd.isnot(None),
                        SkillTrend.posting_count >= min_postings)
                .order_by(SkillTrend.avg_salary_usd.desc()).all())
        return [{"skill": r.skill, "category": r.category,
                 "avg_salary_usd": r.avg_salary_usd,
                 "posting_count": r.posting_count} for r in rows]
    finally:
        s.close()


def market_totals() -> Dict[str, int]:
    s = get_session()
    try:
        rows = (s.query(JobPosting.market, func.count(JobPosting.id))
                .group_by(JobPosting.market).all())
        return {m: c for m, c in rows}
    finally:
        s.close()
