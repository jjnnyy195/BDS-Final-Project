"""
skills_taxonomy.py
==================
Canonical skill taxonomy for the data/ML engineering job market, plus the
extraction logic that turns a free-text job description into a normalized
set of skill tags.

Design notes
------------
* The taxonomy is deliberately curated for ONE niche (data/ML engineering).
  A narrow taxonomy gives a far cleaner trend signal than a generic
  everything-bucket: when "dbt" or "RAG" moves month-over-month, that is a
  real, legible market signal rather than noise.
* Each canonical skill maps to a list of surface aliases. We match on word
  boundaries (case-insensitive) so "go" does not match "google" and "r" does
  not match every stray letter.
* Skills are grouped into categories so the dashboard can roll them up
  (e.g. "Orchestration", "Cloud", "ML/LLM").
"""

import re
from typing import Dict, List, Set

# ---------------------------------------------------------------------------
# Canonical taxonomy: category -> { canonical_skill -> [aliases] }
# Aliases are matched case-insensitively on word boundaries.
# ---------------------------------------------------------------------------
TAXONOMY: Dict[str, Dict[str, List[str]]] = {
    "Languages": {
        "Python": ["python"],
        "SQL": ["sql"],
        "Scala": ["scala"],
        "Java": ["java"],
        "Go": ["golang", r"go\b"],
        "R": [r"\br\b"],
        "Rust": ["rust"],
    },
    "Orchestration": {
        "Airflow": ["airflow", "apache airflow"],
        "dbt": ["dbt", "data build tool"],
        "Dagster": ["dagster"],
        "Prefect": ["prefect"],
        "Luigi": ["luigi"],
    },
    "Processing": {
        "Spark": ["spark", "pyspark", "apache spark"],
        "Flink": ["flink", "apache flink"],
        "Kafka": ["kafka", "apache kafka"],
        "Beam": ["apache beam", "dataflow"],
        "Hadoop": ["hadoop", "mapreduce"],
        "Hive": ["hive"],
    },
    "Warehouses": {
        "Snowflake": ["snowflake"],
        "BigQuery": ["bigquery", "big query"],
        "Redshift": ["redshift"],
        "Databricks": ["databricks"],
        "ClickHouse": ["clickhouse"],
        "DuckDB": ["duckdb"],
    },
    "Storage/DB": {
        "PostgreSQL": ["postgresql", "postgres"],
        "MySQL": ["mysql"],
        "MongoDB": ["mongodb", "mongo"],
        "Cassandra": ["cassandra"],
        "Redis": ["redis"],
        "Elasticsearch": ["elasticsearch", "elastic search"],
    },
    "Cloud": {
        "AWS": ["aws", "amazon web services"],
        "GCP": ["gcp", "google cloud"],
        "Azure": ["azure"],
    },
    "Infra/DevOps": {
        "Docker": ["docker"],
        "Kubernetes": ["kubernetes", "k8s"],
        "Terraform": ["terraform"],
        "CI/CD": ["ci/cd", "cicd", "continuous integration"],
    },
    "ML/LLM": {
        "TensorFlow": ["tensorflow"],
        "PyTorch": ["pytorch"],
        "scikit-learn": ["scikit-learn", "sklearn", "scikit learn"],
        "LLM": ["llm", "large language model", "gpt", "llama"],
        "RAG": ["rag", "retrieval augmented generation", "retrieval-augmented"],
        "Vector DB": ["vector database", "vector db", "pinecone", "weaviate", "faiss"],
        "MLflow": ["mlflow"],
        "Pandas": ["pandas"],
    },
    "BI/Viz": {
        "Tableau": ["tableau"],
        "Power BI": ["power bi", "powerbi"],
        "Looker": ["looker"],
    },
}

# Build a flat lookup of canonical -> category for quick reverse mapping.
SKILL_TO_CATEGORY: Dict[str, str] = {
    skill: category
    for category, skills in TAXONOMY.items()
    for skill in skills
}

# Pre-compile one regex per canonical skill from its aliases.
def _compile_patterns() -> Dict[str, re.Pattern]:
    compiled: Dict[str, re.Pattern] = {}
    for _category, skills in TAXONOMY.items():
        for canonical, aliases in skills.items():
            parts = []
            for a in aliases:
                # If the alias already contains a regex boundary token, trust it.
                if r"\b" in a:
                    parts.append(a)
                else:
                    parts.append(r"\b" + re.escape(a) + r"\b")
            compiled[canonical] = re.compile("|".join(parts), re.IGNORECASE)
    return compiled


_PATTERNS = _compile_patterns()


def extract_skills(text: str) -> List[str]:
    """Return the sorted list of canonical skills mentioned in `text`."""
    if not text:
        return []
    found: Set[str] = set()
    for canonical, pattern in _PATTERNS.items():
        if pattern.search(text):
            found.add(canonical)
    return sorted(found)


def all_skills() -> List[str]:
    """Flat list of every canonical skill in the taxonomy."""
    return sorted(SKILL_TO_CATEGORY.keys())


def category_of(skill: str) -> str:
    return SKILL_TO_CATEGORY.get(skill, "Other")


if __name__ == "__main__":
    sample = (
        "We are hiring a Senior Data Engineer. You will build pipelines with "
        "Apache Spark and Airflow, model data in dbt on Snowflake, and deploy "
        "on AWS with Docker and Kubernetes. Python and SQL required; experience "
        "with LLM/RAG systems and vector databases is a strong plus."
    )
    print("Extracted:", extract_skills(sample))
