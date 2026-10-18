"""
HighView Ingestion V2 — Phase I4: Relationship Discovery & Candidate Rules
Component: Candidate Generation & Validation Rules & Thresholds

Governed thresholds, scoring matrices, synonym registries, and blocking filters.
Zero scattered magic numbers.
"""

from __future__ import annotations

import re
from typing import Sequence
from app.services.ingestion_v2.contracts.normalization import CanonicalPhysicalType
from app.services.ingestion_v2.contracts.semantics import SemanticColumnRole, SemanticEntityType

# Governed Thresholds
AUTO_ACCEPT_THRESHOLD: float = 0.78
AMBIGUITY_THRESHOLD: float = 0.45
MIN_OVERLAP_FOR_CANDIDATE: float = 0.05
MIN_CARDINALITY_FOR_KEY: int = 2
MAX_NULL_KEY_RATIO: float = 0.30
HIGH_NULL_PENALTY_RATIO: float = 0.15
MAX_PAIRWISE_CANDIDATE_LIMIT: int = 500  # Pairwise explosion protection
MAX_COMPOSITE_COLS: int = 3

# Validation Signal Weights (sum to 1.0)
WEIGHT_REFERENTIAL_COVERAGE: float = 0.25
WEIGHT_SEMANTIC_COMPATIBILITY: float = 0.25
WEIGHT_KEY_UNIQUENESS: float = 0.20
WEIGHT_DATATYPE_COMPATIBILITY: float = 0.15
WEIGHT_LEXICAL_SIMILARITY: float = 0.15

# Known cross-domain identifier synonyms/aliases
KEY_SYNONYM_CLUSTERS: dict[str, set[str]] = {
    "PERSON_ID": {
        "employee_id", "emp_id", "worker_number", "worker_id", "associate_code",
        "staff_identifier", "staff_id", "person_id", "member_id", "personnel_id",
    },
    "STORE_ID": {
        "store_id", "store_num", "store_number", "store_code", "retail_store_id",
        "shop_id", "outlet_id", "branch_id", "branch_code",
    },
    "PRODUCT_ID": {
        "product_id", "item_id", "sku", "sku_code", "sku_cde", "product_code",
        "material_id", "part_number", "part_no",
    },
    "LOCATION_ID": {
        "location_id", "loc_id", "site_id", "facility_id", "depot_id", "warehouse_id",
    },
    "TRANSACTION_ID": {
        "order_id", "transaction_id", "txn_id", "invoice_id", "receipt_id", "sale_id",
    },
    "DEPARTMENT_ID": {
        "department_id", "dept_id", "department_code", "dept_code", "cost_center",
    },
}


def normalize_identifier_token(col_name: str) -> str:
    """Normalize column name token for stem matching."""
    s = col_name.strip().lower()
    s = re.sub(r"[^a-z0-9_]", "_", s)
    return s


def compute_name_similarity(col_a: str, col_b: str) -> float:
    """
    Compute lexical and semantic name similarity between two column names.
    Supports differently named valid keys:
    - employee_id <-> worker_number
    - associate_code <-> staff_identifier
    """
    norm_a = normalize_identifier_token(col_a)
    norm_b = normalize_identifier_token(col_b)

    if norm_a == norm_b:
        return 1.0

    # Check synonym clusters
    for cluster_name, members in KEY_SYNONYM_CLUSTERS.items():
        if norm_a in members and norm_b in members:
            return 0.95

    # Check stem equivalence (e.g., stripping suffix _id, _number, _code, _num)
    stem_a = re.sub(r"_(id|number|no|num|code|identifier|key)$", "", norm_a)
    stem_b = re.sub(r"_(id|number|no|num|code|identifier|key)$", "", norm_b)
    if stem_a and stem_b and stem_a == stem_b:
        return 0.90

    # Token overlap (Jaccard similarity on underscores)
    tokens_a = set(norm_a.split("_")) - {""}
    tokens_b = set(norm_b.split("_")) - {""}
    if not tokens_a or not tokens_b:
        return 0.0

    inter = len(tokens_a & tokens_b)
    union = len(tokens_a | tokens_b)
    jaccard = inter / union if union > 0 else 0.0

    # If they share an important entity token (e.g. 'store', 'employee', 'product')
    entity_stems = {"employee", "worker", "store", "product", "item", "location", "facility", "order", "dept", "department"}
    shared_entities = (tokens_a & tokens_b) & entity_stems
    if shared_entities:
        return max(0.75, jaccard)

    return round(jaccard, 3)


def compute_semantic_role_compatibility(
    role_a: SemanticColumnRole,
    role_b: SemanticColumnRole,
) -> float:
    """
    Evaluate structural semantic role compatibility for foreign key relationships.
    Strict Rule: Numeric MEASURE can NEVER be joined to an ENTITY_IDENTIFIER.
    """
    # Strict rejection for numeric measures
    if role_a == SemanticColumnRole.MEASURE or role_b == SemanticColumnRole.MEASURE:
        return 0.0

    # Free text cannot form structured foreign keys
    if role_a == SemanticColumnRole.FREE_TEXT or role_b == SemanticColumnRole.FREE_TEXT:
        return 0.0

    # Technical metadata cannot form structured foreign keys
    if role_a == SemanticColumnRole.TECHNICAL_METADATA or role_b == SemanticColumnRole.TECHNICAL_METADATA:
        return 0.0

    if role_a == SemanticColumnRole.ENTITY_IDENTIFIER and role_b == SemanticColumnRole.ENTITY_IDENTIFIER:
        return 1.0

    if (role_a == SemanticColumnRole.ENTITY_IDENTIFIER and role_b in (SemanticColumnRole.DIMENSION, SemanticColumnRole.CATEGORY)) or \
       (role_b == SemanticColumnRole.ENTITY_IDENTIFIER and role_a in (SemanticColumnRole.DIMENSION, SemanticColumnRole.CATEGORY)):
        return 0.85

    if (role_a == SemanticColumnRole.ENTITY_IDENTIFIER and role_b == SemanticColumnRole.ENTITY_LABEL) or \
       (role_b == SemanticColumnRole.ENTITY_IDENTIFIER and role_a == SemanticColumnRole.ENTITY_LABEL):
        return 0.35

    if role_a == SemanticColumnRole.TIME and role_b == SemanticColumnRole.TIME:
        return 0.90

    if role_a in (SemanticColumnRole.DIMENSION, SemanticColumnRole.CATEGORY) and \
       role_b in (SemanticColumnRole.DIMENSION, SemanticColumnRole.CATEGORY):
        return 0.50

    if role_a == SemanticColumnRole.STATUS and role_b == SemanticColumnRole.STATUS:
        # Status to status is usually a false match unless explicitly part of composite workflow
        return 0.20

    if role_a == SemanticColumnRole.UNKNOWN or role_b == SemanticColumnRole.UNKNOWN:
        return 0.30

    if role_a == SemanticColumnRole.AMBIGUOUS or role_b == SemanticColumnRole.AMBIGUOUS:
        return 0.20

    return 0.10


def compute_entity_type_compatibility(
    entity_a: SemanticEntityType,
    entity_b: SemanticEntityType,
) -> float:
    """
    Evaluate entity type compatibility.
    Cross-entity joins (e.g. PERSON <-> STORE) are strictly incompatible.
    """
    if entity_a == entity_b and entity_a not in (SemanticEntityType.UNKNOWN, SemanticEntityType.AMBIGUOUS):
        return 1.0

    # One is unknown, other is known: partial compatibility
    if (entity_a in (SemanticEntityType.UNKNOWN, SemanticEntityType.AMBIGUOUS) and
        entity_b not in (SemanticEntityType.UNKNOWN, SemanticEntityType.AMBIGUOUS)) or \
       (entity_b in (SemanticEntityType.UNKNOWN, SemanticEntityType.AMBIGUOUS) and
        entity_a not in (SemanticEntityType.UNKNOWN, SemanticEntityType.AMBIGUOUS)):
        return 0.60

    if entity_a in (SemanticEntityType.UNKNOWN, SemanticEntityType.AMBIGUOUS) and \
       entity_b in (SemanticEntityType.UNKNOWN, SemanticEntityType.AMBIGUOUS):
        return 0.40

    # Two distinct, known real-world entities (e.g. PERSON vs STORE) are incompatible
    return 0.0


def compute_physical_type_compatibility(
    type_a: CanonicalPhysicalType | str,
    type_b: CanonicalPhysicalType | str,
) -> float:
    """
    Evaluate canonical physical type compatibility.
    Text-to-text, int-to-int: 1.0.
    Incompatible types (e.g. BOOLEAN <-> DATETIME): 0.0.
    """
    val_a = type_a.value if hasattr(type_a, "value") else str(type_a)
    val_b = type_b.value if hasattr(type_b, "value") else str(type_b)

    if val_a == val_b:
        return 1.0

    # Integers can match string IDs (e.g. employee_id stored as int in one table and string in another)
    if {val_a, val_b} <= {"INTEGER", "STRING"}:
        return 0.85

    # Categorical and String are fully compatible
    if {val_a, val_b} <= {"STRING", "CATEGORICAL"}:
        return 0.95

    # Date and Datetime can be aligned
    if {val_a, val_b} <= {"DATE", "DATETIME"}:
        return 0.90

    # Float and Integer
    if {val_a, val_b} <= {"INTEGER", "FLOAT"}:
        return 0.70

    return 0.0
