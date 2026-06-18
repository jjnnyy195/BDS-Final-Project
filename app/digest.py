"""
digest.py
=========
Builds the "weekly digest" payload — the product's push channel. Returns both
a structured dict (for the /api/digest endpoint) and a plain-text rendering
(what would go in an email body). Pure function of the current DB state.
"""

from datetime import date
from typing import Dict

from app.queries import trending, salary_premium, snapshot, latest_month


def build_digest(market: str = "GLOBAL") -> Dict:
    month = latest_month(market) or "—"
    t = trending(market, window=3, top_n=5)
    top_skills = snapshot(market)[:5]
    salary = salary_premium(market)[:5]
    return {
        "market": market,
        "generated": date.today().isoformat(),
        "month": month,
        "rising": t["rising"],
        "falling": t["falling"],
        "top_skills": top_skills,
        "salary_leaders": salary,
    }


def render_text(d: Dict) -> str:
    lines = []
    lines.append(f"SkillSignal weekly digest — {d['market']} — {d['month']}")
    lines.append("=" * 52)
    lines.append("")
    lines.append("RISING (last 3 months):")
    for r in d["rising"]:
        lines.append(f"  +{r['delta']*100:4.0f}pp  {r['skill']:12} "
                     f"{r['share_then']*100:.0f}% -> {r['share_now']*100:.0f}%")
    lines.append("")
    lines.append("COOLING:")
    for r in d["falling"]:
        lines.append(f"  {r['delta']*100:5.0f}pp  {r['skill']:12} "
                     f"{r['share_then']*100:.0f}% -> {r['share_now']*100:.0f}%")
    lines.append("")
    lines.append("MOST-DEMANDED THIS MONTH:")
    for s in d["top_skills"]:
        lines.append(f"  {s['share']*100:4.0f}%  {s['skill']}")
    lines.append("")
    lines.append("HIGHEST AVG SALARY (disclosed, annual USD):")
    for s in d["salary_leaders"]:
        lines.append(f"  ${s['avg_salary_usd']:>9,.0f}  {s['skill']}")
    lines.append("")
    lines.append("— Reply STOP to unsubscribe. Data: Google for Jobs via JSearch.")
    return "\n".join(lines)


if __name__ == "__main__":
    print(render_text(build_digest("GLOBAL")))
