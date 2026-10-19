"""
HighView Ingestion V2 — Phase I7 Retrieval Namespaces & Authority Classes
Stage 11: Multi-Namespace Hybrid Retrieval

Core Epistemic Law:
RETRIEVAL FINDS CANDIDATES. RETRIEVAL DOES NOT ESTABLISH TRUTH.
Vector similarity does NOT prove a relationship.
BM25 match does NOT prove a metric definition.
Graph proximity does NOT prove causation.
"""

from enum import Enum


class RetrievalNamespace(str, Enum):
    """
    Four distinct, non-collapsible retrieval namespaces.
    Strict isolation prevents cross-domain semantic contamination.
    """
    RAW_SCHEMA = "RAW_SCHEMA"          # Physical tables, columns, physical types, profiles, candidate keys
    SEMANTIC = "SEMANTIC"              # Entities, dimensions, measures, metric definitions, grains, families
    RELATIONSHIP = "RELATIONSHIP"      # Validated structural relationships and governed JoinPlans
    ANALYTICAL = "ANALYTICAL"          # Observed EDA-B analytical findings, effect sizes, statistical reliability

    # Exact target index aliases
    RAW_SCHEMA_INDEX = "RAW_SCHEMA"
    SEMANTIC_INDEX = "SEMANTIC"
    RELATIONSHIP_INDEX = "RELATIONSHIP"
    ANALYTICAL_INDEX = "ANALYTICAL"


class AuthorityClass(str, Enum):
    """
    Authority tier of the indexed artifact.
    Authority is strictly separated from retrieval relevance scoring.
    """
    STRUCTURAL = "STRUCTURAL"                  # Physical schema & structural profiles
    SEMANTIC = "SEMANTIC"                      # Governed semantic concepts, metric formulas, grains
    RELATIONSHIP = "RELATIONSHIP"              # Authorized join edges and JoinPlans
    ANALYTICAL_EVIDENCE = "ANALYTICAL_EVIDENCE" # Empirically observed findings with EVID-* provenance


class QueryIntent(str, Enum):
    """
    Lightweight deterministic query intent classes.
    Routes queries to target namespaces and assigns authority boost weights.
    """
    SCHEMA_LOOKUP = "SCHEMA_LOOKUP"
    SEMANTIC_LOOKUP = "SEMANTIC_LOOKUP"
    RELATIONSHIP_LOOKUP = "RELATIONSHIP_LOOKUP"
    METRIC_LOOKUP = "METRIC_LOOKUP"
    ANALYTICAL_FINDING_LOOKUP = "ANALYTICAL_FINDING_LOOKUP"
    CROSS_TABLE_ANALYTICAL_QUERY = "CROSS_TABLE_ANALYTICAL_QUERY"
    TECHNICAL_PROVENANCE_LOOKUP = "TECHNICAL_PROVENANCE_LOOKUP"
    GENERAL_DATASET_QUERY = "GENERAL_DATASET_QUERY"
