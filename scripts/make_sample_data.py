"""
make_sample_data.py
===================
Generates realistic JSearch-shaped fixture data for both markets across the
last 6 months, with deliberately *moving* skill trends so the dashboard shows
something real (e.g. RAG / vector DBs rising, Hadoop declining).

This is sample/demo data, clearly labeled as such. In live mode the exact same
pipeline consumes real JSearch responses; the fixture only exists so the system
is runnable with no API key. Run:

    python scripts/make_sample_data.py
"""

import os
import json
import random
from datetime import date, timedelta

random.seed(42)

OUT_DIR = os.path.join(os.path.dirname(__file__), "..", "data")
os.makedirs(OUT_DIR, exist_ok=True)

EMPLOYERS_TW = [
    "TSMC", "MediaTek", "Appier", "Gogoro", "KKBOX", "17LIVE", "Dcard",
    "PChome", "Cathay FHC", "E.SUN Bank", "Foxconn", "Garmin Taiwan",
    "iKala", "Perfect Corp", "Migo", "CTBC Bank",
]
EMPLOYERS_GLOBAL = [
    "Stripe", "Notion", "Datadog", "Snowflake Inc", "Airbnb", "Coinbase",
    "Instacart", "DoorDash", "Robinhood", "Plaid", "Ramp", "Brex",
    "Figma", "Vercel", "OpenAI", "Anthropic",
]

TITLES = [
    "Data Engineer", "Senior Data Engineer", "Machine Learning Engineer",
    "ML Platform Engineer", "Data Platform Engineer", "Staff Data Engineer",
    "Analytics Engineer", "ML Infrastructure Engineer",
]

# Each skill has a base prevalence and a monthly drift. Positive drift = rising
# demand over the window; negative = declining. months_ago=5 is oldest.
# (base, drift) -> probability at month m = clamp(base + drift*(5 - months_ago))
SKILL_TREND = {
    "Python":        (0.85, 0.005),
    "SQL":           (0.80, 0.003),
    "Spark":         (0.55, -0.01),
    "Airflow":       (0.45, 0.005),
    "dbt":           (0.30, 0.025),   # rising fast
    "Snowflake":     (0.35, 0.02),    # rising
    "Databricks":    (0.30, 0.02),    # rising
    "Kafka":         (0.35, 0.0),
    "AWS":           (0.55, 0.005),
    "GCP":           (0.35, 0.008),
    "Azure":         (0.25, 0.005),
    "Docker":        (0.50, 0.004),
    "Kubernetes":    (0.40, 0.008),
    "Terraform":     (0.25, 0.01),
    "Hadoop":        (0.30, -0.03),   # declining fast
    "Hive":          (0.20, -0.02),   # declining
    "PyTorch":       (0.30, 0.015),
    "TensorFlow":    (0.30, -0.005),
    "LLM":           (0.15, 0.045),   # rising very fast
    "RAG":           (0.08, 0.04),    # rising very fast
    "Vector DB":     (0.07, 0.035),   # rising very fast
    "MLflow":        (0.18, 0.012),
    "Pandas":        (0.45, 0.0),
    "Tableau":       (0.20, -0.005),
    "Power BI":      (0.18, 0.002),
    "BigQuery":      (0.22, 0.01),
    "PostgreSQL":    (0.30, 0.003),
    "MongoDB":       (0.18, -0.002),
    "Scala":         (0.20, -0.015),  # declining with Spark/Java stacks
    "Go":            (0.12, 0.008),
}

SKILL_PHRASE = {
    "Python": "Python", "SQL": "SQL", "Spark": "Apache Spark", "Airflow": "Airflow",
    "dbt": "dbt", "Snowflake": "Snowflake", "Databricks": "Databricks",
    "Kafka": "Kafka", "AWS": "AWS", "GCP": "GCP", "Azure": "Azure",
    "Docker": "Docker", "Kubernetes": "Kubernetes", "Terraform": "Terraform",
    "Hadoop": "Hadoop", "Hive": "Hive", "PyTorch": "PyTorch",
    "TensorFlow": "TensorFlow", "LLM": "LLM", "RAG": "RAG",
    "Vector DB": "vector database", "MLflow": "MLflow", "Pandas": "pandas",
    "Tableau": "Tableau", "Power BI": "Power BI", "BigQuery": "BigQuery",
    "PostgreSQL": "PostgreSQL", "MongoDB": "MongoDB", "Scala": "Scala", "Go": "Go",
}

# Salary bands (annual, local currency) by seniority keyword.
def salary_for(title, market):
    senior = any(k in title for k in ("Senior", "Staff", "Lead", "Principal"))
    if market == "TW":
        lo = random.randint(1_300_000, 1_700_000) if senior else random.randint(800_000, 1_200_000)
        hi = lo + random.randint(200_000, 500_000)
        return lo, hi, "TWD", "year"
    else:
        lo = random.randint(170_000, 220_000) if senior else random.randint(120_000, 160_000)
        hi = lo + random.randint(20_000, 60_000)
        return lo, hi, "USD", "year"


def clamp(x, lo=0.02, hi=0.97):
    return max(lo, min(hi, x))


def gen_market(market, employers, postings_per_month=70):
    items = []
    today = date.today()
    for months_ago in range(6):           # 0..5 (0 = current month)
        # First day of that month-ago bucket (approx, 30-day steps is fine here).
        bucket_start = today - timedelta(days=30 * months_ago)
        for _ in range(postings_per_month):
            title = random.choice(TITLES)
            employer = random.choice(employers)
            smin, smax, cur, per = salary_for(title, market)
            # ~35% of postings disclose salary (realistic for the niche).
            disclose = random.random() < 0.35

            # Decide skills from the drifting probabilities.
            chosen = []
            for skill, (base, drift) in SKILL_TREND.items():
                p = clamp(base + drift * (5 - months_ago))
                if random.random() < p:
                    chosen.append(skill)
            if not chosen:
                chosen = ["Python", "SQL"]

            desc = ("We are looking for a " + title + ". Responsibilities include "
                    "building and maintaining data pipelines. Required skills: "
                    + ", ".join(SKILL_PHRASE[s] for s in chosen) + ".")

            posted = bucket_start - timedelta(days=random.randint(0, 27))
            items.append({
                "job_title": title,
                "employer_name": employer,
                "job_city": "Taipei" if market == "TW" else random.choice(
                    ["San Francisco", "New York", "Seattle", "Remote"]),
                "job_state": "" if market == "TW" else "",
                "job_country": "Taiwan" if market == "TW" else "United States",
                "job_is_remote": random.random() < (0.15 if market == "TW" else 0.4),
                "job_min_salary": smin if disclose else None,
                "job_max_salary": smax if disclose else None,
                "job_salary_currency": cur if disclose else None,
                "job_salary_period": per if disclose else None,
                "job_posted_at_datetime_utc": posted.isoformat() + "T00:00:00Z",
                "job_description": desc,
            })
    return items


def main():
    tw = gen_market("TW", EMPLOYERS_TW)
    gl = gen_market("GLOBAL", EMPLOYERS_GLOBAL)
    with open(os.path.join(OUT_DIR, "sample_tw.json"), "w", encoding="utf-8") as f:
        json.dump(tw, f, ensure_ascii=False, indent=1)
    with open(os.path.join(OUT_DIR, "sample_global.json"), "w", encoding="utf-8") as f:
        json.dump(gl, f, ensure_ascii=False, indent=1)
    print(f"Wrote {len(tw)} TW + {len(gl)} GLOBAL sample postings to data/")


if __name__ == "__main__":
    main()
