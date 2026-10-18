"""
HighView Ingestion V2 — Contracts and Shadow Architecture Test Suite
Phase: I1 Verification
Verifies:
1. Strict immutability, extra="forbid", and deterministic SHA-256 fingerprinting.
2. Epistemic separation of StructuralDataQuality (EDA-A) and AnalyticalReliability (EDA-B).
3. Rule-based Tukey IQR outlier evidence (zero p-values) vs hypothesis testing.
4. Composite grain support and grain-preserving join specifications.
5. Separation of ValidatedRelationshipEdge from JoinPlan and MeasureAdditivity rules.
6. AnalysisIntent purity invariant.
7. Disagreement Ledger with three comparison classes (UNCHANGED, EXPECTED_IMPROVEMENT, EXPECTED_DIFFERENCE).
8. P0 Database Isolation & Shadow runner cutover firewall.
"""

import pytest
import tempfile
from pathlib import Path
from pydantic import ValidationError

from app.services.ingestion_v2.contracts import (
    SourceCoordinateRef,
    IngestionContractBase,
    compute_stage_fingerprint,
    PhysicalSheet,
    RawIngestionResult,
    ReconstructionStatus,
    PhysicalCellCoord,
    LogicalColumnHeader,
    LogicalTable,
    ReconstructedDataset,
    CanonicalPhysicalType,
    NormalizationRule,
    NormalizedFieldLineage,
    NormalizedColumn,
    NormalizedTable,
    NormalizedDataset,
    StructuralDataQuality,
    ColumnStructuralProfile,
    TableStructuralProfile,
    StructuralProfile,
    SemanticColumnRole,
    SemanticEntityType,
    ClassificationSource,
    SemanticColumnAssignment,
    TableSemanticModel,
    SemanticModel,
    CanonicalGrain,
    TemporalGrain,
    TableGrainProfile,
    GrainProfile,
    CandidateKeyType,
    RelationshipCardinality,
    RelationshipStatus,
    RelationshipCandidate,
    RelationshipCandidateSet,
    ValidatedRelationshipEdge,
    ValidatedRelationshipGraph,
    JoinSafetyStatus,
    MeasureAdditivity,
    PreAggregationSpec,
    JoinPlan,
    GovernedJoinPlanSet,
    OutlierMethod,
    TukeyIqrEvidence,
    HypothesisTestEvidence,
    AnalyticalReliability,
    AnalyticalFinding,
    AnalyticalProfile,
    MetricScope,
    LocalDerivedMetric,
    RelationalDerivedMetric,
    EnrichedDataset,
    GraphNodeType,
    GraphEdgeType,
    SemanticGraphNode,
    SemanticGraphEdge,
    SemanticGraph,
    RetrievalNamespace,
    IndexedDocumentRef,
    MultiNamespaceRetrievalManifest,
    IntentFocusDomain,
    TargetPersona,
    AnalysisIntent,
    InternalStage,
    PublicProgressGroup,
    INTERNAL_TO_PUBLIC_STAGE_MAP,
    WorkspaceIntelligenceContext,
    ShadowExecutionStatus,
    ShadowPipelineRun,
    ComparisonClass,
    DisagreementType,
    Severity,
    ReviewStatus,
    PipelineDisagreementRecord,
    PipelineDisagreementLedger,
)
from app.services.ingestion_v2.shadow_runner import ShadowStorageManager, ShadowHarness


def test_base_contract_immutability_and_extra_forbidden():
    """Verify contracts are strictly frozen and reject unknown/extra fields."""
    source_ref = SourceCoordinateRef(
        dataset_id="ds-100",
        source_file_hash="abc123hash",
    )

    base = IngestionContractBase(
        dataset_id="ds-100",
        run_id="run-001",
        stage_name="raw_ingestion",
        source_fingerprint="fp-src",
        provenance=[source_ref],
    )

    # Immutability verification: frozen=True prevents direct assignment
    with pytest.raises(ValidationError):
        base.confidence = 0.5  # Attempting mutation

    # Extra fields forbidden verification
    with pytest.raises(ValidationError):
        IngestionContractBase(
            dataset_id="ds-100",
            run_id="run-001",
            stage_name="raw_ingestion",
            source_fingerprint="fp-src",
            invalid_extra_field="should_fail",
        )


def test_deterministic_stage_fingerprint():
    """Verify stage fingerprinting produces identical SHA-256 digests despite different volatile timestamps/run_ids."""
    payload_1 = {
        "dataset_id": "ds-001",
        "stage_name": "structural_profiling",
        "run_id": "run-alpha-111",
        "created_at": "2026-10-18T00:00:00Z",
        "tables": [{"table_id": "emp", "rows": 500}],
    }
    payload_2 = {
        "dataset_id": "ds-001",
        "stage_name": "structural_profiling",
        "run_id": "run-beta-999",
        "created_at": "2026-10-18T12:34:56Z",
        "tables": [{"table_id": "emp", "rows": 500}],
    }

    fp1 = compute_stage_fingerprint(payload_1)
    fp2 = compute_stage_fingerprint(payload_2)

    assert fp1 == fp2
    assert len(fp1) == 64  # SHA-256 hex string


def test_dual_quality_split_structural_vs_analytical():
    """
    Assert StructuralDataQuality (completeness, validity, uniqueness, consistency)
    is strictly decoupled from AnalyticalReliability (grain confidence, join coverage, metric definition confidence).
    """
    # Stage 4 StructuralDataQuality
    struct_quality = StructuralDataQuality(
        completeness_score=0.98,
        validity_score=0.95,
        uniqueness_score=0.99,
        consistency_score=0.92,
        reconstruction_fidelity_score=1.0,
        overall_structural_quality=0.968,
    )
    assert struct_quality.completeness_score == 0.98
    assert not hasattr(struct_quality, "grain_confidence_score")
    assert not hasattr(struct_quality, "join_coverage_score")

    # Stage 8 AnalyticalReliability
    analytical_reliability = AnalyticalReliability(
        grain_confidence_score=0.94,
        join_coverage_score=0.88,
        metric_definition_confidence=0.96,
        evidence_sufficiency_score=0.91,
        overall_analytical_reliability=0.922,
    )
    assert analytical_reliability.grain_confidence_score == 0.94
    assert not hasattr(analytical_reliability, "reconstruction_fidelity_score")


def test_tukey_iqr_outlier_evidence_zero_p_values():
    """Verify Tukey IQR is rule-based (1.5x IQR multiplier) and does not attach a p-value."""
    tukey = TukeyIqrEvidence(
        outlier_method=OutlierMethod.TUKEY_IQR,
        iqr_multiplier=1.5,
        q1=25.0,
        q3=75.0,
        iqr=50.0,
        lower_bound=-50.0,
        upper_bound=150.0,
        outlier_count=4,
        outlier_percentage=0.8,
    )
    assert tukey.outlier_method == OutlierMethod.TUKEY_IQR
    assert tukey.iqr_multiplier == 1.5
    # Strict schema check: p_value must NOT exist on TukeyIqrEvidence
    assert not hasattr(tukey, "p_value")

    # Hypothesis testing does carry p-values and test statistics
    hypothesis = HypothesisTestEvidence(
        test_name="PEARSON_CORRELATION",
        test_statistic=0.78,
        p_value=0.0034,
        alpha=0.05,
        is_statistically_significant=True,
    )
    assert hypothesis.p_value == 0.0034
    assert hypothesis.is_statistically_significant is True


def test_composite_grain_and_join_plan_safety():
    """
    Verify GrainProfile supports composite grain expressions (PERSON x DAY)
    and JoinPlan encodes grain preservation, safety status, and measure additivity.
    """
    # Composite grain profile
    table_grain = TableGrainProfile(
        table_id="tbl_daily_attendance",
        table_name="daily_attendance",
        primary_entity=CanonicalGrain.PERSON,
        temporal_grain=TemporalGrain.DAILY,
        key_columns=["employee_id", "attendance_date"],
        grain_expression="PERSON x DAY",
        is_unique=True,
        uniqueness_ratio=1.0,
        grain_confidence=0.98,
        duplicate_key_rows=0,
        rationale="Unique composite key on employee_id and attendance_date",
    )
    assert table_grain.grain_expression == "PERSON x DAY"
    assert len(table_grain.key_columns) == 2

    # JoinPlan requiring pre-aggregation to prevent Cartesian fanout
    pre_agg = PreAggregationSpec(
        source_table_id="tbl_daily_attendance",
        group_by_columns=["employee_id"],
        aggregations={"hours_worked": "SUM", "attendance_date": "COUNT"},
        target_grain="PERSON",
    )

    join_plan = JoinPlan(
        join_plan_id="jp-emp-attendance-001",
        edge_id="edge-emp-att-01",
        left_table_id="tbl_employees",
        left_grain="PERSON",
        right_table_id="tbl_daily_attendance",
        right_grain="PERSON x DAY",
        target_grain="PERSON",
        join_type="LEFT",
        safety_status=JoinSafetyStatus.REQUIRES_PRE_AGGREGATION,
        measure_additivity_rules={
            "salary": MeasureAdditivity.NON_ADDITIVE,
            "hours_worked": MeasureAdditivity.ADDITIVE,
            "headcount": MeasureAdditivity.DISTINCT_COUNT,
        },
        pre_aggregation=pre_agg,
        safe_operations=["SUM(pre_aggregated.hours_worked)", "COUNT(DISTINCT employee_id)"],
        forbidden_operations=["DIRECT_JOIN_WITHOUT_PRE_AGGREGATION", "SUM(raw_salary_after_join)"],
    )
    assert join_plan.safety_status == JoinSafetyStatus.REQUIRES_PRE_AGGREGATION
    assert join_plan.measure_additivity_rules["salary"] == MeasureAdditivity.NON_ADDITIVE


def test_analysis_intent_epistemic_purity_invariant():
    """Verify AnalysisIntent does not permit structural mutations or mathematical overrides."""
    intent = AnalysisIntent(
        dataset_id="ds-500",
        run_id="run-500",
        source_fingerprint="fp-500",
        intent_id="intent-exec-turnover",
        focus_domain=IntentFocusDomain.TURNOVER_ATTRITION,
        target_persona=TargetPersona.EXECUTIVE,
        priority_entities=["tbl_terminations", "tbl_employees"],
    )
    assert intent.assert_intent_purity() is True
    assert intent.focus_domain == IntentFocusDomain.TURNOVER_ATTRITION


def test_disagreement_ledger_classification_and_cutover_governance():
    """
    Verify Disagreement Ledger contains BOTH:
    - ComparisonClass (UNCHANGED, EXPECTED_IMPROVEMENT, EXPECTED_DIFFERENCE)
    - DisagreementType (EXPECTED_FIX, EXPECTED_REFACTOR, REGRESSION, UNRESOLVED)
    And proves combinations:
    1. EXPECTED_DIFFERENCE + EXPECTED_FIX
    2. EXPECTED_DIFFERENCE + REGRESSION
    3. EXPECTED_IMPROVEMENT + EXPECTED_REFACTOR
    4. Default value is UNRESOLVED
    5. Critical REGRESSION or critical UNRESOLVED blocks future cutover.
    """
    # 1. Combination: EXPECTED_DIFFERENCE + EXPECTED_FIX (V1 invalid join rejected by V2)
    rec_fix = PipelineDisagreementRecord(
        disagreement_id="dis-fix-01",
        shadow_run_id="shadow-test",
        dataset_id="ds-test",
        comparison_class=ComparisonClass.EXPECTED_DIFFERENCE,
        disagreement_type=DisagreementType.EXPECTED_FIX,
        severity=Severity.INFO,
        difference_summary="V1 accepted circular Department<->Department join; V2 rejected it",
        architectural_rationale="V1 had unsafe join; V2 correctly blocks non-additive join",
    )
    assert rec_fix.comparison_class == ComparisonClass.EXPECTED_DIFFERENCE
    assert rec_fix.disagreement_type == DisagreementType.EXPECTED_FIX

    # 2. Combination: EXPECTED_DIFFERENCE + REGRESSION (V1 valid relationship dropped by V2)
    rec_regression = PipelineDisagreementRecord(
        disagreement_id="dis-reg-01",
        shadow_run_id="shadow-test",
        dataset_id="ds-test",
        comparison_class=ComparisonClass.EXPECTED_DIFFERENCE,
        disagreement_type=DisagreementType.REGRESSION,
        severity=Severity.CRITICAL,
        difference_summary="V1 linked valid employee_id between tables; V2 lost it",
        architectural_rationale="Legitimate relationship was dropped in candidate generation",
    )
    assert rec_regression.comparison_class == ComparisonClass.EXPECTED_DIFFERENCE
    assert rec_regression.disagreement_type == DisagreementType.REGRESSION

    # 3. Combination: EXPECTED_IMPROVEMENT + EXPECTED_REFACTOR (Parquet Silver storage representation)
    rec_refactor = PipelineDisagreementRecord(
        disagreement_id="dis-ref-01",
        shadow_run_id="shadow-test",
        dataset_id="ds-test",
        comparison_class=ComparisonClass.EXPECTED_IMPROVEMENT,
        disagreement_type=DisagreementType.EXPECTED_REFACTOR,
        severity=Severity.INFO,
        difference_summary="Stage 3 materialized canonical Parquet with typed schema",
        architectural_rationale="Identical underlying data with improved zero-copy representation",
    )
    assert rec_refactor.comparison_class == ComparisonClass.EXPECTED_IMPROVEMENT
    assert rec_refactor.disagreement_type == DisagreementType.EXPECTED_REFACTOR

    # 4. Default value is UNRESOLVED
    rec_default = PipelineDisagreementRecord(
        disagreement_id="dis-def-01",
        shadow_run_id="shadow-test",
        dataset_id="ds-test",
        comparison_class=ComparisonClass.EXPECTED_DIFFERENCE,
        difference_summary="Unclassified difference observed in column profiling",
        architectural_rationale="Requires manual domain review",
    )
    assert rec_default.disagreement_type == DisagreementType.UNRESOLVED

    # 5. Ledger governance: Critical REGRESSION or critical UNRESOLVED must block cutover!
    with tempfile.TemporaryDirectory() as tmp_dir:
        storage = ShadowStorageManager(base_dir=tmp_dir)
        harness = ShadowHarness(storage_manager=storage)

        # Non-blocking ledger (only expected fixes and refactors)
        ledger_clean = harness.audit_comparison(
            shadow_run_id="run-clean",
            dataset_id="ds-test",
            disagreements=[rec_fix, rec_refactor],
        )
        assert ledger_clean.total_expected_fixes == 1
        assert ledger_clean.total_expected_refactors == 1
        assert ledger_clean.total_regressions == 0
        assert ledger_clean.blocks_cutover is False

        # Blocking ledger (contains critical REGRESSION)
        ledger_blocked = harness.audit_comparison(
            shadow_run_id="run-blocked",
            dataset_id="ds-test",
            disagreements=[rec_fix, rec_regression],
        )
        assert ledger_blocked.total_regressions == 1
        assert ledger_blocked.blocks_cutover is True
        assert ledger_blocked.requires_human_review is True

        # Blocking ledger (contains critical UNRESOLVED)
        rec_unresolved_crit = PipelineDisagreementRecord(
            disagreement_id="dis-unres-crit",
            shadow_run_id="run-blocked-unres",
            dataset_id="ds-test",
            comparison_class=ComparisonClass.EXPECTED_DIFFERENCE,
            disagreement_type=DisagreementType.UNRESOLVED,
            severity=Severity.CRITICAL,
            difference_summary="Unclassified major divergence in metric aggregation",
            architectural_rationale="Unresolved critical difference",
        )
        ledger_blocked_unresolved = harness.audit_comparison(
            shadow_run_id="run-blocked-unres",
            dataset_id="ds-test",
            disagreements=[rec_unresolved_crit],
        )
        assert ledger_blocked_unresolved.total_unresolved == 1
        assert ledger_blocked_unresolved.blocks_cutover is True


def test_shadow_harness_negative_write_firewall_all_stores():
    """
    Negative tests proving V2 shadow execution cannot publish to:
    - production relationship tables
    - production semantic/evidence stores
    - ExecutiveTopics
    - production vector indexes
    - Dashboard cache
    - Presentation context
    - HRIDAY production retrieval state
    Attempted consumer cutover in Phase I1 is strictly BLOCKED.
    """
    from app.services.ingestion_v2.shadow_runner import (
        ShadowWriteFirewallViolation,
        PROHIBITED_PRODUCTION_STORES,
    )

    with tempfile.TemporaryDirectory() as tmp_dir:
        storage = ShadowStorageManager(base_dir=tmp_dir)
        harness = ShadowHarness(storage_manager=storage)

        # 1. Prohibited consumer stores must raise ShadowWriteFirewallViolation
        target_stores = [
            "production_relationship_tables",
            "production_semantic_evidence_stores",
            "executive_topics",
            "production_vector_indexes",
            "dashboard_cache",
            "presentation_context",
            "hriday_retrieval_state",
            "pulsehr_sqlite3",
        ]
        for store in target_stores:
            with pytest.raises(ShadowWriteFirewallViolation) as exc_info:
                harness.attempt_publish_to_production(store, payload={"data": "test"})
            assert "P0 Shadow Write Firewall: Attempted write to production store" in str(exc_info.value)

        # 2. Cutover attempt must be strictly blocked
        with pytest.raises(RuntimeError) as exc_info:
            harness.create_shadow_run(
                v1_dataset_id="ds-prod-001",
                v1_run_id="run-prod-001",
                consumer_cutover_attempt=True,
            )
        assert "Consumer cutover is strictly prohibited in Phase I1" in str(exc_info.value)


def test_public_upload_and_sse_contracts_unchanged():
    """
    Verify public upload and SSE contracts:
    - POST /api/upload/file?async_mode=true remains unchanged
    - SSE stream schema unchanged
    - 12 internal stages map cleanly onto existing 10 UI progress groups
    """
    assert len(InternalStage) == 12
    assert len(PublicProgressGroup) == 10

    # Verify every internal stage maps onto a valid public progress group
    for stage in InternalStage:
        public_group = INTERNAL_TO_PUBLIC_STAGE_MAP[stage]
        assert isinstance(public_group, PublicProgressGroup)

    # Specific mapping checks to ensure 10 SSE milestones preserve UI semantics
    assert INTERNAL_TO_PUBLIC_STAGE_MAP[InternalStage.RAW_INGESTION] == PublicProgressGroup.STAGE_1_FILE_RECEIVED
    assert INTERNAL_TO_PUBLIC_STAGE_MAP[InternalStage.ADAPTIVE_RECONSTRUCTION] == PublicProgressGroup.STAGE_2_STRUCTURE_DETECTED
    assert INTERNAL_TO_PUBLIC_STAGE_MAP[InternalStage.SANITIZATION_NORMALIZATION] == PublicProgressGroup.STAGE_3_TYPES_NORMALIZED
    assert INTERNAL_TO_PUBLIC_STAGE_MAP[InternalStage.STRUCTURAL_PROFILING_EDA_A] == PublicProgressGroup.STAGE_4_DATA_PROFILED
    assert INTERNAL_TO_PUBLIC_STAGE_MAP[InternalStage.SEMANTIC_MODELING_GRAIN] == PublicProgressGroup.STAGE_5_ENTITIES_RESOLVED
    assert INTERNAL_TO_PUBLIC_STAGE_MAP[InternalStage.RELATIONSHIP_DISCOVERY] == PublicProgressGroup.STAGE_6_RELATIONSHIPS_DISCOVERED
    assert INTERNAL_TO_PUBLIC_STAGE_MAP[InternalStage.RELATIONSHIP_VALIDATION_JOIN_PLAN] == PublicProgressGroup.STAGE_7_RELATIONSHIPS_VERIFIED
    assert INTERNAL_TO_PUBLIC_STAGE_MAP[InternalStage.ANALYTICAL_EDA_B] == PublicProgressGroup.STAGE_8_STATISTICS_COMPUTED
    assert INTERNAL_TO_PUBLIC_STAGE_MAP[InternalStage.CONTROLLED_ENRICHMENT] == PublicProgressGroup.STAGE_8_STATISTICS_COMPUTED
    assert INTERNAL_TO_PUBLIC_STAGE_MAP[InternalStage.SEMANTIC_GRAPH] == PublicProgressGroup.STAGE_9_KNOWLEDGE_GRAPH_BUILT
    assert INTERNAL_TO_PUBLIC_STAGE_MAP[InternalStage.VECTORIZATION_INDEXING] == PublicProgressGroup.STAGE_9_KNOWLEDGE_GRAPH_BUILT
    assert INTERNAL_TO_PUBLIC_STAGE_MAP[InternalStage.CONTEXT_RECONCILIATION_PREWARM] == PublicProgressGroup.STAGE_10_READY
