"""
db.py
=====
Storage layer. Uses SQLAlchemy so the same code runs against Postgres (the
production / deployed target) or SQLite (zero-setup local + grader runs).

Schema (3 tables)
-----------------
job_postings   raw, deduplicated postings as ingested
posting_skills join table: which canonical skills appear in each posting
skill_trends   pre-aggregated monthly rollups powering the dashboard

The DATABASE_URL env var selects the backend. If unset we fall back to a
local SQLite file so `python -m ingestion.run --sample` works with no
infrastructure at all.
"""

import os
from datetime import datetime
from sqlalchemy import (
    create_engine, Column, Integer, String, Float, Date, DateTime,
    ForeignKey, UniqueConstraint, Index, func,
)
from sqlalchemy.orm import declarative_base, relationship, sessionmaker

DATABASE_URL = os.environ.get("DATABASE_URL", "sqlite:///./data/skillsignal.db")

# Render hands out postgres:// URLs; SQLAlchemy wants postgresql://
if DATABASE_URL.startswith("postgres://"):
    DATABASE_URL = DATABASE_URL.replace("postgres://", "postgresql://", 1)

_connect_args = {"check_same_thread": False} if DATABASE_URL.startswith("sqlite") else {}
engine = create_engine(DATABASE_URL, connect_args=_connect_args, pool_pre_ping=True)
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)
Base = declarative_base()


class JobPosting(Base):
    __tablename__ = "job_postings"

    id = Column(Integer, primary_key=True)
    # external_id is the dedup key: a stable hash of (employer, title, market).
    external_id = Column(String(64), unique=True, nullable=False, index=True)
    title = Column(String(300), nullable=False)
    employer = Column(String(300))
    market = Column(String(8), nullable=False, index=True)   # "TW" or "GLOBAL"
    location = Column(String(300))
    is_remote = Column(Integer, default=0)
    salary_min = Column(Float)
    salary_max = Column(Float)
    salary_currency = Column(String(8))
    salary_period = Column(String(16))      # year / month / hour
    salary_annual_usd = Column(Float)       # normalized for cross-market compare
    posted_date = Column(Date, index=True)
    description = Column(String)
    source = Column(String(64))
    ingested_at = Column(DateTime, default=datetime.utcnow)

    skills = relationship("PostingSkill", back_populates="posting",
                          cascade="all, delete-orphan")


class PostingSkill(Base):
    __tablename__ = "posting_skills"

    id = Column(Integer, primary_key=True)
    posting_id = Column(Integer, ForeignKey("job_postings.id"), nullable=False)
    skill = Column(String(64), nullable=False, index=True)
    category = Column(String(64), nullable=False, index=True)

    posting = relationship("JobPosting", back_populates="skills")

    __table_args__ = (
        UniqueConstraint("posting_id", "skill", name="uq_posting_skill"),
        Index("ix_skill_market", "skill"),
    )


class SkillTrend(Base):
    """Pre-aggregated monthly rollup: how many postings mentioned each skill,
    in each market, in each month. This is what the dashboard reads."""
    __tablename__ = "skill_trends"

    id = Column(Integer, primary_key=True)
    month = Column(String(7), nullable=False, index=True)   # 'YYYY-MM'
    market = Column(String(8), nullable=False, index=True)
    skill = Column(String(64), nullable=False, index=True)
    category = Column(String(64), nullable=False)
    posting_count = Column(Integer, default=0)
    share = Column(Float, default=0.0)          # fraction of that month's postings
    avg_salary_usd = Column(Float)              # avg annual USD where disclosed

    __table_args__ = (
        UniqueConstraint("month", "market", "skill", name="uq_trend_row"),
    )


def init_db():
    """Create all tables. Safe to call repeatedly."""
    os.makedirs("./data", exist_ok=True)
    Base.metadata.create_all(engine)


def get_session():
    return SessionLocal()


if __name__ == "__main__":
    init_db()
    print(f"Initialized DB at: {DATABASE_URL}")
