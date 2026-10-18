"""
HighView Ingestion V2 — Epistemic Dependency Integrity Test Suite
Verifies:
1. Static AST analysis of all contract files ensures zero backward/inverted dependencies.
2. Runtime transition validation blocks illegal dependencies (e.g. Stage 4 consuming Stage 8).
3. Stage order is strictly monotonic and follows the 12-stage epistemic hierarchy.
"""

import pytest
from pathlib import Path

from app.services.ingestion_v2.contracts.shadow import InternalStage
from app.services.ingestion_v2.dependency_guard import (
    STAGE_EPISTEMIC_RANK,
    EpistemicIntegrityViolation,
    validate_stage_transition,
    audit_contract_ast_dependencies,
)


def test_monotonic_stage_epistemic_ranks():
    """Verify that all 12 internal stages have uniquely ordered ranks 1 through 12."""
    assert len(STAGE_EPISTEMIC_RANK) == 12
    ranks = list(STAGE_EPISTEMIC_RANK.values())
    assert sorted(ranks) == list(range(1, 13))

    # Verify key architectural invariants
    # Structural profiling (EDA-A) must precede Semantic Modeling
    assert STAGE_EPISTEMIC_RANK[InternalStage.STRUCTURAL_PROFILING_EDA_A] < STAGE_EPISTEMIC_RANK[InternalStage.SEMANTIC_MODELING_GRAIN]
    # Semantic Modeling must precede Relationship Discovery
    assert STAGE_EPISTEMIC_RANK[InternalStage.SEMANTIC_MODELING_GRAIN] < STAGE_EPISTEMIC_RANK[InternalStage.RELATIONSHIP_DISCOVERY]
    # Relationship Validation must precede Analytical EDA-B
    assert STAGE_EPISTEMIC_RANK[InternalStage.RELATIONSHIP_VALIDATION_JOIN_PLAN] < STAGE_EPISTEMIC_RANK[InternalStage.ANALYTICAL_EDA_B]
    # Analytical EDA-B must precede Controlled Enrichment
    assert STAGE_EPISTEMIC_RANK[InternalStage.ANALYTICAL_EDA_B] < STAGE_EPISTEMIC_RANK[InternalStage.CONTROLLED_ENRICHMENT]
    # Controlled Enrichment must precede Semantic Graph
    assert STAGE_EPISTEMIC_RANK[InternalStage.CONTROLLED_ENRICHMENT] < STAGE_EPISTEMIC_RANK[InternalStage.SEMANTIC_GRAPH]
    # Semantic Graph must precede Retrieval Indexing
    assert STAGE_EPISTEMIC_RANK[InternalStage.SEMANTIC_GRAPH] < STAGE_EPISTEMIC_RANK[InternalStage.VECTORIZATION_INDEXING]


def test_runtime_stage_transition_guard():
    """Verify validate_stage_transition allows forward dependencies and blocks backward dependencies."""
    # Valid forward consumption: Stage 4 (EDA-A) consuming Stage 1 (Raw) and Stage 3 (Normalization)
    assert validate_stage_transition(
        target_stage=InternalStage.STRUCTURAL_PROFILING_EDA_A,
        consumed_stages=[InternalStage.RAW_INGESTION, InternalStage.SANITIZATION_NORMALIZATION],
    ) is True

    # Valid forward consumption: Stage 8 (EDA-B) consuming Stage 7 (Validated Relationships / Joins)
    assert validate_stage_transition(
        target_stage=InternalStage.ANALYTICAL_EDA_B,
        consumed_stages=[InternalStage.RELATIONSHIP_VALIDATION_JOIN_PLAN],
    ) is True

    # ILLEGAL: Stage 4 (EDA-A) attempting to consume Stage 8 (EDA-B)
    with pytest.raises(EpistemicIntegrityViolation) as exc_info:
        validate_stage_transition(
            target_stage=InternalStage.STRUCTURAL_PROFILING_EDA_A,
            consumed_stages=[InternalStage.ANALYTICAL_EDA_B],
        )
    assert "cannot consume output from subsequent or concurrent stage" in str(exc_info.value)

    # ILLEGAL: Stage 5 (Semantics) attempting to consume Stage 10 (Semantic Graph)
    with pytest.raises(EpistemicIntegrityViolation):
        validate_stage_transition(
            target_stage=InternalStage.SEMANTIC_MODELING_GRAIN,
            consumed_stages=[InternalStage.SEMANTIC_GRAPH],
        )


def test_ast_scan_zero_inverted_contract_dependencies():
    """
    Scans the actual backend/app/services/ingestion_v2/contracts directory using AST parsing.
    Asserts zero backward imports exist across contract modules.
    """
    contracts_dir = Path(__file__).resolve().parent.parent / "app" / "services" / "ingestion_v2" / "contracts"
    assert contracts_dir.exists(), f"Contracts directory not found: {contracts_dir}"

    violations = audit_contract_ast_dependencies(contracts_dir)
    assert violations == [], f"Found epistemic dependency violations in contracts: {violations}"


def test_dependency_guard_negative_cases_fail_automatically():
    """
    Negative tests proving the architecture guard blocks invalid backward dependencies:
    1. StructuralProfiler (Stage 4) imports SemanticGraph (Stage 10) -> FAIL
    2. SemanticModel (Stage 5) imports AnalyticalProfile (Stage 8) -> FAIL
    3. GrainProfile (Stage 5) imports Enrichment (Stage 9) -> FAIL
    4. RelationshipValidator (Stage 7) imports Retrieval (Stage 11) -> FAIL
    """
    import tempfile
    from app.services.ingestion_v2.dependency_guard import audit_code_dependencies

    # Case 1: StructuralProfiler (Stage 4) importing SemanticGraph (Stage 10)
    code_1 = """
from app.services.ingestion_v2.contracts.semantic_graph import SemanticGraph
def profile_table(tbl):
    return SemanticGraph()
"""
    v1 = audit_code_dependencies(code_1, InternalStage.STRUCTURAL_PROFILING_EDA_A)
    assert len(v1) == 1
    assert "imports from later stage SEMANTIC_GRAPH" in v1[0]

    # Case 2: SemanticModel (Stage 5) importing AnalyticalProfile (Stage 8)
    code_2 = """
import app.services.ingestion_v2.contracts.analytics as eda_b
def classify():
    pass
"""
    v2 = audit_code_dependencies(code_2, InternalStage.SEMANTIC_MODELING_GRAIN)
    assert len(v2) == 1
    assert "imports from later stage ANALYTICAL_EDA_B" in v2[0]

    # Case 3: Grain layer (Stage 5) importing Enrichment (Stage 9)
    code_3 = """
from app.services.ingestion_v2.contracts.enrichment import LocalDerivedMetric
def infer_grain():
    pass
"""
    v3 = audit_code_dependencies(code_3, InternalStage.SEMANTIC_MODELING_GRAIN)
    assert len(v3) == 1
    assert "imports from later stage CONTROLLED_ENRICHMENT" in v3[0]

    # Case 4: Relationship validation (Stage 7) importing Retrieval (Stage 11)
    code_4 = """
from app.services.ingestion_v2.contracts import retrieval
def validate_edges():
    pass
"""
    v4 = audit_code_dependencies(code_4, InternalStage.RELATIONSHIP_VALIDATION_JOIN_PLAN)
    assert len(v4) == 1
    assert "imports from later stage VECTORIZATION_INDEXING" in v4[0]

    # Case 5: Verify temp directory AST scanner detects inverted imports
    with tempfile.TemporaryDirectory() as tmp_dir:
        tmp_path = Path(tmp_dir)
        bad_contract = tmp_path / "profiling.py"
        bad_contract.write_text(
            "from app.services.ingestion_v2.contracts.semantic_graph import SemanticGraph\n",
            encoding="utf-8",
        )
        violations = audit_contract_ast_dependencies(tmp_path)
        assert len(violations) == 1
        assert "Inverted AST import in profiling.py" in violations[0]
        assert "imports from later stage SEMANTIC_GRAPH" in violations[0]
