"""
HighView Ingestion Intelligence V2 — Governed Semantic Rule Registry
Centralized deterministic dictionaries, patterns, and threshold rules for semantic role and entity classification.
"""

from __future__ import annotations

import re
from typing import Sequence
from app.services.ingestion_v2.contracts.semantics import (
    MeasureClass,
    SemanticColumnRole,
    SemanticConcept,
    SemanticEntityType,
)

# Governed Lexical Patterns for Roles
IDENTIFIER_TOKENS: set[str] = {
    "id", "code", "num", "number", "key", "uuid", "hash", "ssn", "badge",
    "sku", "identifier", "worker_number", "associate_code", "staff_id",
}

LABEL_TOKENS: set[str] = {
    "name", "full_name", "first_name", "last_name", "label", "title",
    "description", "desc", "display_name", "caption",
}

TIME_TOKENS: set[str] = {
    "date", "time", "timestamp", "created_at", "updated_at", "year",
    "month", "day", "week", "quarter", "period", "datetime", "logged_at",
}

MEASURE_TOKENS: set[str] = {
    "salary", "revenue", "cost", "budget", "price", "amount", "count",
    "hours", "headcount", "score", "rating", "attendance", "rate", "pct",
    "percent", "total", "units", "quantity", "spend", "sales", "leaves",
    "variance", "duration", "tenure", "days", "turnover", "attrition",
}

STATUS_TOKENS: set[str] = {
    "status", "state", "stage", "flag", "phase", "condition", "disposition",
}

LOCATION_TOKENS: set[str] = {
    "city", "state", "country", "zip", "postal", "region", "address",
    "lat", "lon", "latitude", "longitude", "store_location", "geo", "zone",
}

TECHNICAL_METADATA_TOKENS: set[str] = {
    "row_hash", "source_file", "ingestion_timestamp", "_etag", "sys_id",
    "_row_id", "created_by", "modified_by", "sync_token",
}

# Entity Mapping Lexical Tokens
ENTITY_KEYWORD_MAP: dict[str, SemanticEntityType] = {
    # Person
    "emp": SemanticEntityType.PERSON,
    "employee": SemanticEntityType.PERSON,
    "worker": SemanticEntityType.PERSON,
    "staff": SemanticEntityType.PERSON,
    "person": SemanticEntityType.PERSON,
    "user": SemanticEntityType.PERSON,
    "customer": SemanticEntityType.PERSON,
    "client": SemanticEntityType.PERSON,
    "patient": SemanticEntityType.PERSON,
    "member": SemanticEntityType.PERSON,
    "candidate": SemanticEntityType.PERSON,

    # Department & Team
    "dept": SemanticEntityType.DEPARTMENT,
    "department": SemanticEntityType.DEPARTMENT,
    "division": SemanticEntityType.DEPARTMENT,
    "team": SemanticEntityType.TEAM,
    "squad": SemanticEntityType.TEAM,
    "unit": SemanticEntityType.ORGANIZATION,
    "organization": SemanticEntityType.ORGANIZATION,
    "company": SemanticEntityType.ORGANIZATION,

    # Store & Facility
    "store": SemanticEntityType.STORE,
    "shop": SemanticEntityType.STORE,
    "facility": SemanticEntityType.FACILITY,
    "warehouse": SemanticEntityType.FACILITY,
    "plant": SemanticEntityType.FACILITY,
    "branch": SemanticEntityType.LOCATION,
    "site": SemanticEntityType.LOCATION,

    # Product
    "product": SemanticEntityType.PRODUCT,
    "item": SemanticEntityType.PRODUCT,
    "sku": SemanticEntityType.PRODUCT,
    "merchandise": SemanticEntityType.PRODUCT,

    # Location & Region
    "location": SemanticEntityType.LOCATION,
    "loc": SemanticEntityType.LOCATION,
    "city": SemanticEntityType.LOCATION,
    "country": SemanticEntityType.LOCATION,
    "region": SemanticEntityType.REGION,
    "territory": SemanticEntityType.REGION,
    "zone": SemanticEntityType.REGION,

    # Transaction & Account
    "order": SemanticEntityType.TRANSACTION,
    "transaction": SemanticEntityType.TRANSACTION,
    "invoice": SemanticEntityType.TRANSACTION,
    "receipt": SemanticEntityType.TRANSACTION,
    "ticket": SemanticEntityType.TRANSACTION,
    "sale": SemanticEntityType.TRANSACTION,
    "account": SemanticEntityType.ACCOUNT,

    # Event & Audit
    "event": SemanticEntityType.EVENT,
    "incident": SemanticEntityType.EVENT,
    "log": SemanticEntityType.EVENT,

    # Device & Asset
    "device": SemanticEntityType.DEVICE,
    "sensor": SemanticEntityType.DEVICE,
    "machine": SemanticEntityType.DEVICE,
    "asset": SemanticEntityType.DEVICE,
}

MEASURE_KEYWORD_MAP: dict[str, MeasureClass] = {
    "revenue": MeasureClass.FINANCIAL,
    "budget": MeasureClass.FINANCIAL,
    "cost": MeasureClass.FINANCIAL,
    "expense": MeasureClass.FINANCIAL,
    "price": MeasureClass.FINANCIAL,
    "salary": MeasureClass.FINANCIAL,
    "sales": MeasureClass.FINANCIAL,
    "spend": MeasureClass.FINANCIAL,
    "profit": MeasureClass.FINANCIAL,
    "margin": MeasureClass.FINANCIAL,
    "count": MeasureClass.QUANTITY,
    "units": MeasureClass.QUANTITY,
    "quantity": MeasureClass.QUANTITY,
    "volume": MeasureClass.QUANTITY,
    "rate": MeasureClass.PERCENTAGE,
    "pct": MeasureClass.PERCENTAGE,
    "percent": MeasureClass.PERCENTAGE,
    "ratio": MeasureClass.PERCENTAGE,
    "duration": MeasureClass.DURATION,
    "tenure": MeasureClass.DURATION,
    "hours": MeasureClass.DURATION,
    "days": MeasureClass.DURATION,
    "seconds": MeasureClass.DURATION,
    "score": MeasureClass.SCORE,
    "rating": MeasureClass.SCORE,
    "index": MeasureClass.SCORE,
    "headcount": MeasureClass.HEADCOUNT,
    "fte": MeasureClass.HEADCOUNT,
}


def infer_measure_class(tokens: Sequence[str], unit: str | None = None) -> MeasureClass | None:
    """Infers measure class from lexical tokens and unit."""
    if unit:
        u = unit.lower()
        if u in ("$", "usd", "eur", "gbp", "jpy", "inr"):
            return MeasureClass.FINANCIAL
        if u in ("%", "pct", "percent"):
            return MeasureClass.PERCENTAGE
        if u in ("hrs", "hours", "days", "months", "years", "s", "sec", "seconds"):
            return MeasureClass.DURATION

    for t in tokens:
        if t in MEASURE_KEYWORD_MAP:
            return MEASURE_KEYWORD_MAP[t]

    return None


def infer_semantic_concept(role: SemanticColumnRole) -> SemanticConcept:
    """Maps semantic column role to its broad semantic concept."""
    if role == SemanticColumnRole.ENTITY_IDENTIFIER:
        return SemanticConcept.IDENTIFIER
    if role == SemanticColumnRole.ENTITY_LABEL:
        return SemanticConcept.DESCRIPTOR
    if role == SemanticColumnRole.MEASURE:
        return SemanticConcept.MEASURE
    if role == SemanticColumnRole.TIME:
        return SemanticConcept.TIME_SPAN
    if role in (SemanticColumnRole.STATUS, SemanticColumnRole.BOOLEAN):
        return SemanticConcept.STATUS
    if role in (SemanticColumnRole.DIMENSION, SemanticColumnRole.CATEGORY):
        return SemanticConcept.CATEGORICAL
    if role == SemanticColumnRole.LOCATION:
        return SemanticConcept.LOCATION_ATTRIBUTE
    if role == SemanticColumnRole.FREE_TEXT:
        return SemanticConcept.FREE_TEXT
    if role == SemanticColumnRole.TECHNICAL_METADATA:
        return SemanticConcept.TECHNICAL
    if role == SemanticColumnRole.AMBIGUOUS:
        return SemanticConcept.AMBIGUOUS
    return SemanticConcept.UNKNOWN


def normalize_tokens(name: str) -> list[str]:
    """Tokenize a column name into lowercase alphanumeric words."""
    cleaned = re.sub(r"[^a-zA-Z0-9]+", "_", name.lower()).strip("_")
    return [t for t in cleaned.split("_") if t]


def infer_lexical_role(tokens: Sequence[str]) -> tuple[SemanticColumnRole | None, float]:
    """Scores lexical alignment to semantic roles."""
    token_set = set(tokens)
    joined_name = "_".join(tokens)

    # Technical metadata check (compound and token level)
    for tm in TECHNICAL_METADATA_TOKENS:
        if tm in joined_name or tm in token_set:
            return SemanticColumnRole.TECHNICAL_METADATA, 0.90

    # Label check (prioritize entity label like employee_name over identifier)
    if any(t in LABEL_TOKENS for t in token_set):
        return SemanticColumnRole.ENTITY_LABEL, 0.85

    # Time check (prioritize temporal grains like week_number, month_id, created_at)
    if any(t in TIME_TOKENS for t in token_set):
        return SemanticColumnRole.TIME, 0.85

    # Identifier check
    if any(t in IDENTIFIER_TOKENS for t in token_set):
        return SemanticColumnRole.ENTITY_IDENTIFIER, 0.85

    # Status check
    if any(t in STATUS_TOKENS for t in token_set):
        return SemanticColumnRole.STATUS, 0.80

    # Location check
    if any(t in LOCATION_TOKENS for t in token_set):
        return SemanticColumnRole.LOCATION, 0.80

    # Measure check
    if any(t in MEASURE_TOKENS for t in token_set):
        return SemanticColumnRole.MEASURE, 0.80

    return None, 0.0


def infer_lexical_entity(tokens: Sequence[str]) -> tuple[SemanticEntityType, float]:
    """Infers entity type from lexical tokens."""
    for t in tokens:
        if t in ENTITY_KEYWORD_MAP:
            return ENTITY_KEYWORD_MAP[t], 0.85

    # Compound checks
    joined = "_".join(tokens)
    for kw, entity in ENTITY_KEYWORD_MAP.items():
        if kw in joined:
            return entity, 0.75

    return SemanticEntityType.UNKNOWN, 0.0


def detect_adversarial_contradiction(
    lexical_role: SemanticColumnRole | None,
    uniqueness_ratio: float,
    distinct_count: int,
    candidate_identifier_score: float,
    candidate_dimension_score: float,
    row_count: int,
) -> bool:
    """
    Detects severe contradictions between column naming and value structure.
    Example: Column named 'employee_id' where values are ['Sales', 'Finance', 'HR']
    with distinct_count = 3 and uniqueness_ratio = 0.03.
    """
    if lexical_role == SemanticColumnRole.ENTITY_IDENTIFIER:
        if row_count >= 10 and distinct_count <= 5 and uniqueness_ratio < 0.20:
            return True
        if candidate_identifier_score < 0.20 and candidate_dimension_score > 0.60:
            return True

    return False
