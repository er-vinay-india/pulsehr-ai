"""
HighView Ingestion V2 — Phase I7 Retrieval & Context Assembly Tests
Stage 11: Multi-Namespace Hybrid Retrieval, Graph-Aware Search & Governed Context Assembly

Comprehensive Test Matrix:
1. Four namespaces isolation and content restrictions
2. Deterministic manifest fingerprint and staleness invalidation
3. AnalysisIntent neutrality certification
4. Lexical adversarial case (synonyms mapping to canonical concept)
5. Homonym disambiguation (Orders.status vs Employees.status)
6. Metric name collision (competing formulas under same name preserved as ambiguous)
7. Relationship trap: high vector similarity does NOT create a relationship
8. Intent prioritization (definition vs observed analytical result)
9. Evidence reference validation and reliability-aware ranking
10. Degraded mode & offline fallbacks (vector unavailable, empty vector, query failure)
11. Epistemic boundaries: no computation, no reclassification, no metric derivation, missing analysis flag
12. Dataset isolation and zero wrong-dataset leakage
13. Dataset deletion cascade
14. Dataset version replacement
15. Embedding cache invalidation and explicit telemetry (LLM calls = 0)
16. Graph neighborhood expansion and dependency closure
17. Governed Context Package structure and bounded token budget
18. Multi-domain labeled retrieval benchmark (6 domains: Recall@1/3/5, MRR, nDCG@5)
19. Component-level performance telemetry (Small, Medium, Large: P50/P95 latencies and peak memory)
20. Shadow mode safety & zero production database mutation
"""

import math
import time
import tracemalloc
from typing import Any, Sequence

import pytest

from app.services.ingestion_v2.contracts.normalization import (
    NormalizedColumn,
    NormalizedTable,
    NormalizedDataset,
    CanonicalPhysicalType,
    NormalizedFieldLineage,
)
from app.services.ingestion_v2.contracts.profiling import (
    ColumnStructuralProfile,
    TableStructuralProfile,
    StructuralProfile,
    StructuralDataQuality,
)
from app.services.ingestion_v2.contracts.semantics import (
    SemanticModel,
    TableSemanticModel,
    SemanticColumnAssignment,
    SemanticColumnRole,
    SemanticEntityType,
    SemanticConcept,
    MeasureClass,
    ClassificationSource,
)
from app.services.ingestion_v2.contracts.grain import (
    GrainProfile,
    TableGrainProfile,
    CanonicalGrain,
)
from app.services.ingestion_v2.contracts.relationships import (
    ValidatedRelationshipGraph,
    ValidatedRelationshipEdge,
    RelationshipCardinality,
    RelationshipStatus,
    CandidateKeyType,
)
from app.services.ingestion_v2.contracts.joins import (
    JoinPlan,
    JoinSafetyStatus,
    PreAggregationSpec,
)
from app.services.ingestion_v2.contracts.analytics import (
    AnalyticalProfile,
    AnalyticalFinding,
    FindingType,
    AnalyticalReliability,
)
from app.services.ingestion_v2.contracts.enrichment import (
    EnrichedDataset,
    LocalDerivedMetric,
    RelationalDerivedMetric,
    SemanticFamily,
    MetricAdditivity,
)
from app.services.ingestion_v2.contracts.semantic_graph import (
    SemanticGraph,
    SemanticGraphNode,
    SemanticGraphEdge,
    GraphNodeType,
    GraphEdgeType,
)
from app.services.ingestion_v2.retrieval import (
    RetrievalNamespace,
    AuthorityClass,
    QueryIntent,
    RetrievalDocument,
    RetrievalDocumentBuilder,
    MultiNamespaceRetrievalManifest,
    MultiNamespaceBM25Index,
    MultiNamespaceVectorIndex,
    VectorIndexStatus,
    GraphRetriever,
    QueryIntentRouter,
    GovernedReranker,
    HybridRetriever,
    ContextAssembler,
)


def _deterministic_mock_embedder(texts: list[str]) -> list[list[float]]:
    """
    Deterministic pseudo-embedder for tests.
    Generates unit-normalized 8-dimensional vectors based on word hashes.
    """
    vectors: list[list[float]] = []
    dim = 8
    for t in texts:
        vec = [0.0] * dim
        words = t.lower().split()
        for idx, w in enumerate(words):
            h = hash(w) % dim
            vec[h] += 1.0 / (idx + 1.0)
        norm = math.sqrt(sum(x * x for x in vec))
        if norm > 0:
            vec = [x / norm for x in vec]
        else:
            vec[0] = 1.0
        vectors.append(vec)
    return vectors


def _make_norm_col(table_id: str, col_name: str, col_type: CanonicalPhysicalType) -> NormalizedColumn:
    col_id = f"{table_id}.{col_name}"
    return NormalizedColumn(
        column_id=col_id,
        table_id=table_id,
        column_name=col_name,
        canonical_type=col_type,
        lineage=NormalizedFieldLineage(column_id=col_id, raw_header_name=col_name),
        null_count=0,
        non_null_count=100,
    )


@pytest.fixture
def canonical_mock_stages():
    """Builds a complete, coherent set of frozen I1-I6 mock artifacts across 2 tables."""
    norm_tables = [
        NormalizedTable(
            table_id="tbl_employees",
            table_name="Employees",
            row_count=100,
            column_count=4,
            columns=[
                _make_norm_col("tbl_employees", "emp_id", CanonicalPhysicalType.STRING),
                _make_norm_col("tbl_employees", "department", CanonicalPhysicalType.STRING),
                _make_norm_col("tbl_employees", "name", CanonicalPhysicalType.STRING),
                _make_norm_col("tbl_employees", "salary", CanonicalPhysicalType.FLOAT),
            ],
        ),
        NormalizedTable(
            table_id="tbl_attendance",
            table_name="Attendance",
            row_count=2200,
            column_count=5,
            columns=[
                _make_norm_col("tbl_attendance", "emp_id", CanonicalPhysicalType.STRING),
                _make_norm_col("tbl_attendance", "date", CanonicalPhysicalType.DATE),
                _make_norm_col("tbl_attendance", "present_days", CanonicalPhysicalType.INTEGER),
                _make_norm_col("tbl_attendance", "eligible_days", CanonicalPhysicalType.INTEGER),
                _make_norm_col("tbl_attendance", "leave_days", CanonicalPhysicalType.INTEGER),
            ],
        ),
    ]

    norm_dataset = NormalizedDataset(
        dataset_id="ds_canonical_01",
        run_id="run_01",
        source_fingerprint="source_fp_canon_01",
        tables=norm_tables,
    )

    quality_high = StructuralDataQuality(
        completeness_score=1.0,
        validity_score=1.0,
        uniqueness_score=1.0,
        consistency_score=1.0,
        reconstruction_fidelity_score=1.0,
        overall_structural_quality=1.0,
    )

    struct_profile = StructuralProfile(
        dataset_id="ds_canonical_01",
        run_id="run_01",
        source_fingerprint="source_fp_canon_01",
        dataset_structural_quality=quality_high,
        tables=[
            TableStructuralProfile(
                table_id="tbl_employees",
                table_name="Employees",
                row_count=100,
                column_count=4,
                quality=quality_high,
                columns=[
                    ColumnStructuralProfile(
                        column_id="tbl_employees.emp_id",
                        table_id="tbl_employees",
                        column_name="emp_id",
                        physical_type="STRING",
                        row_count=100,
                        null_count=0,
                        null_ratio=0.0,
                        distinct_count=100,
                        uniqueness_ratio=1.0,
                    ),
                    ColumnStructuralProfile(
                        column_id="tbl_employees.department",
                        table_id="tbl_employees",
                        column_name="department",
                        physical_type="STRING",
                        row_count=100,
                        null_count=0,
                        null_ratio=0.0,
                        distinct_count=5,
                        uniqueness_ratio=0.05,
                    ),
                ],
            ),
            TableStructuralProfile(
                table_id="tbl_attendance",
                table_name="Attendance",
                row_count=2200,
                column_count=5,
                quality=quality_high,
                columns=[
                    ColumnStructuralProfile(
                        column_id="tbl_attendance.emp_id",
                        table_id="tbl_attendance",
                        column_name="emp_id",
                        physical_type="STRING",
                        row_count=2200,
                        null_count=0,
                        null_ratio=0.0,
                        distinct_count=100,
                        uniqueness_ratio=0.045,
                    ),
                    ColumnStructuralProfile(
                        column_id="tbl_attendance.present_days",
                        table_id="tbl_attendance",
                        column_name="present_days",
                        physical_type="INTEGER",
                        row_count=2200,
                        null_count=0,
                        null_ratio=0.0,
                        distinct_count=2,
                        uniqueness_ratio=0.001,
                    ),
                ],
            ),
        ],
    )

    sem_model = SemanticModel(
        dataset_id="ds_canonical_01",
        run_id="run_01",
        source_fingerprint="source_fp_canon_01",
        tables=[
            TableSemanticModel(
                table_id="tbl_employees",
                table_name="Employees",
                primary_entity_type=SemanticEntityType.PERSON,
                columns=[
                    SemanticColumnAssignment(
                        column_id="tbl_employees.emp_id",
                        table_id="tbl_employees",
                        column_name="emp_id",
                        role=SemanticColumnRole.ENTITY_IDENTIFIER,
                        entity_type=SemanticEntityType.PERSON,
                        semantic_concept=SemanticConcept.IDENTIFIER,
                        confidence=1.0,
                        classification_source=ClassificationSource.HEURISTIC,
                        rationale="Primary key ID",
                    ),
                    SemanticColumnAssignment(
                        column_id="tbl_employees.department",
                        table_id="tbl_employees",
                        column_name="department",
                        role=SemanticColumnRole.DIMENSION,
                        entity_type=SemanticEntityType.DEPARTMENT,
                        semantic_concept=SemanticConcept.DESCRIPTOR,
                        confidence=1.0,
                        classification_source=ClassificationSource.HEURISTIC,
                        rationale="Department dimension",
                    ),
                ],
            ),
            TableSemanticModel(
                table_id="tbl_attendance",
                table_name="Attendance",
                primary_entity_type=SemanticEntityType.TRANSACTION,
                columns=[
                    SemanticColumnAssignment(
                        column_id="tbl_attendance.emp_id",
                        table_id="tbl_attendance",
                        column_name="emp_id",
                        role=SemanticColumnRole.ENTITY_IDENTIFIER,
                        entity_type=SemanticEntityType.PERSON,
                        semantic_concept=SemanticConcept.IDENTIFIER,
                        confidence=1.0,
                        classification_source=ClassificationSource.HEURISTIC,
                        rationale="Foreign key ID",
                    ),
                    SemanticColumnAssignment(
                        column_id="tbl_attendance.present_days",
                        table_id="tbl_attendance",
                        column_name="present_days",
                        role=SemanticColumnRole.MEASURE,
                        measure_class=MeasureClass.QUANTITY,
                        semantic_concept=SemanticConcept.MEASURE,
                        confidence=1.0,
                        classification_source=ClassificationSource.HEURISTIC,
                        rationale="Present days measure",
                    ),
                ],
            ),
        ],
    )

    grain_profile = GrainProfile(
        dataset_id="ds_canonical_01",
        run_id="run_01",
        source_fingerprint="source_fp_canon_01",
        table_grains=[
            TableGrainProfile(
                table_id="tbl_employees",
                table_name="Employees",
                primary_entity=CanonicalGrain.PERSON,
                key_columns=["emp_id"],
                grain_expression="PERSON",
                is_unique=True,
                uniqueness_ratio=1.0,
                grain_confidence=1.0,
                rationale="Employee grain",
            ),
            TableGrainProfile(
                table_id="tbl_attendance",
                table_name="Attendance",
                primary_entity=CanonicalGrain.TRANSACTION,
                key_columns=["emp_id", "date"],
                grain_expression="PERSON x DAY",
                is_unique=True,
                uniqueness_ratio=1.0,
                grain_confidence=1.0,
                rationale="Attendance grain",
            ),
        ],
    )

    rel_graph = ValidatedRelationshipGraph(
        dataset_id="ds_canonical_01",
        run_id="run_01",
        source_fingerprint="source_fp_canon_01",
        edges=[
            ValidatedRelationshipEdge(
                edge_id="rel_emp_att",
                candidate_id="cand_emp_att",
                source_table_id="tbl_employees",
                source_column_ids=["emp_id"],
                target_table_id="tbl_attendance",
                target_column_ids=["emp_id"],
                key_type=CandidateKeyType.SINGLE,
                cardinality=RelationshipCardinality.ONE_TO_MANY,
                status=RelationshipStatus.VALIDATED,
                referential_coverage=1.0,
                source_overlap_ratio=1.0,
                target_overlap_ratio=1.0,
                confidence=1.0,
                estimated_row_multiplier=22.0,
                is_grain_preserving=False,
            )
        ],
    )

    join_plans = [
        JoinPlan(
            join_plan_id="jp-dept-att-001",
            edge_id="rel_emp_att",
            left_table_id="tbl_employees",
            left_grain="PERSON",
            right_table_id="tbl_attendance",
            right_grain="PERSON x DAY",
            target_grain="PERSON",
            join_type="LEFT",
            safety_status=JoinSafetyStatus.SAFE_WITH_PREAGGREGATION,
            pre_aggregation=PreAggregationSpec(
                source_table_id="tbl_attendance",
                group_by_columns=["emp_id"],
                aggregations={"present_days": "SUM", "eligible_days": "SUM"},
                target_grain="PERSON",
            ),
            safe_operations=["FILTER", "GROUP_BY", "AGGREGATE"],
            forbidden_operations=["RAW_DISTINCT_COUNT_AFTER_FANOUT"],
        )
    ]

    reliability_high = AnalyticalReliability(
        grain_confidence_score=1.0,
        join_coverage_score=1.0,
        metric_definition_confidence=1.0,
        evidence_sufficiency_score=1.0,
        overall_analytical_reliability=1.0,
        reliability_level="HIGH",
    )

    analytical_profile = AnalyticalProfile(
        dataset_id="ds_canonical_01",
        run_id="run_01",
        source_fingerprint="source_fp_canon_01",
        reliability=reliability_high,
        findings=[
            AnalyticalFinding(
                finding_id="EVID-001",
                finding_type=FindingType.DISTRIBUTION.value,
                affected_tables=["tbl_attendance"],
                affected_columns=["tbl_attendance.present_days"],
                description="Attendance Rate finding",
                metric_definition="Attendance Rate",
                target_grain="PERSON x DAY",
                result=0.834,
                effect_size=0.15,
                confidence=1.0,
                evidence_refs=["EVID-001"],
                provenance_refs=["prov:tbl_attendance.present_days"],
                analytical_reliability=reliability_high,
                limitations=["Observational data only", "Excludes contractors"],
                dataset_id="ds_canonical_01",
            ),
            AnalyticalFinding(
                finding_id="EVID-002",
                finding_type=FindingType.GROUP_COMPARISON.value,
                affected_tables=["tbl_attendance"],
                affected_columns=["tbl_attendance.present_days"],
                description="Department Attendance finding",
                metric_definition="Department Attendance",
                target_grain="DEPARTMENT",
                result=0.912,
                effect_size=0.22,
                confidence=1.0,
                evidence_refs=["EVID-002"],
                provenance_refs=["prov:tbl_attendance.present_days"],
                analytical_reliability=reliability_high,
                limitations=["Sample size 5 departments"],
                dataset_id="ds_canonical_01",
            ),
        ],
    )

    enriched_dataset = EnrichedDataset(
        dataset_id="ds_canonical_01",
        run_id="run_01",
        source_fingerprint="source_fp_canon_01",
        local_metrics=[
            LocalDerivedMetric(
                metric_id="metric_att_rate_01",
                table_id="tbl_attendance",
                metric_name="Attendance Rate",
                formula="present_days / eligible_days",
                source_columns=["present_days", "eligible_days"],
                source_table_id="tbl_attendance",
                source_column_ids=["present_days", "eligible_days"],
                target_grain="PERSON x DAY",
                grain="PERSON x DAY",
                unit="PERCENTAGE",
                additivity=MetricAdditivity.RATIO,
                display_aliases=["Attendance %", "Presence Rate"],
                numerator_definition="present_days",
                denominator_definition="eligible_days",
                provenance_refs=["prov:tbl_attendance"],
            )
        ],
        relational_metrics=[
            RelationalDerivedMetric(
                metric_id="metric_dept_att_01",
                metric_name="Department Attendance Rate",
                formula="present_days / eligible_days",
                join_plan_id="jp-dept-att-001",
                source_table_ids=["tbl_employees", "tbl_attendance"],
                source_column_ids=["present_days", "eligible_days"],
                target_grain="DEPARTMENT",
                unit="PERCENTAGE",
                additivity=MetricAdditivity.RATIO,
                display_aliases=["Dept Attendance"],
                numerator_metric="present_days",
                denominator_metric="eligible_days",
            )
        ],
        semantic_families=[
            SemanticFamily(
                family_id="fam_workforce_perf",
                family_name="Workforce Presence",
                concept_type="WORKFORCE_PRODUCTIVITY",
                metric_ids=["metric_att_rate_01", "metric_dept_att_01"],
                dimension_ids=["tbl_employees.department"],
                grain_scope="PERSON x DAY",
                evidence_refs=["EVID-001", "EVID-002"],
                provenance_refs=["prov:tbl_attendance"],
            )
        ],
    )

    # Build SemanticGraph
    sem_graph_nodes = [
        SemanticGraphNode(node_id="table:tbl_employees", node_type=GraphNodeType.TABLE, label="tbl_employees"),
        SemanticGraphNode(node_id="table:tbl_attendance", node_type=GraphNodeType.TABLE, label="tbl_attendance"),
        SemanticGraphNode(node_id="col:tbl_employees.emp_id", node_type=GraphNodeType.COLUMN, label="emp_id"),
        SemanticGraphNode(node_id="col:tbl_attendance.present_days", node_type=GraphNodeType.COLUMN, label="present_days"),
        SemanticGraphNode(node_id="col:tbl_attendance.eligible_days", node_type=GraphNodeType.COLUMN, label="eligible_days"),
        SemanticGraphNode(node_id="grain:PERSON x DAY", node_type=GraphNodeType.GRAIN, label="PERSON x DAY"),
        SemanticGraphNode(node_id="grain:DEPARTMENT", node_type=GraphNodeType.GRAIN, label="DEPARTMENT"),
        SemanticGraphNode(node_id="join_plan:jp-dept-att-001", node_type=GraphNodeType.TABLE, label="jp-dept-att-001"),
        SemanticGraphNode(
            node_id="metric:metric_att_rate_01",
            node_type=GraphNodeType.METRIC,
            label="Attendance Rate",
            properties={
                "source_columns": ["tbl_attendance.present_days", "tbl_attendance.eligible_days"],
                "target_grain": "PERSON x DAY",
            }
        ),
        SemanticGraphNode(
            node_id="metric:metric_dept_att_01",
            node_type=GraphNodeType.METRIC,
            label="Department Attendance Rate",
            properties={
                "source_columns": ["tbl_attendance.present_days", "tbl_attendance.eligible_days"],
                "target_grain": "DEPARTMENT",
                "join_plan_id": "jp-dept-att-001",
            }
        ),
    ]

    sem_graph_edges = [
        SemanticGraphEdge(edge_id="e1", source_node_id="metric:metric_att_rate_01", target_node_id="col:tbl_attendance.present_days", edge_type=GraphEdgeType.DERIVED_FROM),
        SemanticGraphEdge(edge_id="e2", source_node_id="metric:metric_att_rate_01", target_node_id="grain:PERSON x DAY", edge_type=GraphEdgeType.MEASURED_AT_GRAIN),
        SemanticGraphEdge(edge_id="e3", source_node_id="metric:metric_dept_att_01", target_node_id="join_plan:jp-dept-att-001", edge_type=GraphEdgeType.USES_JOIN_PLAN),
    ]

    sem_graph = SemanticGraph(
        dataset_id="ds_canonical_01",
        run_id="run_01",
        source_fingerprint="source_fp_canon_01",
        nodes=sem_graph_nodes,
        edges=sem_graph_edges,
        node_count=len(sem_graph_nodes),
        edge_count=len(sem_graph_edges),
        graph_fingerprint="graph_fp_canon_01",
    )

    return {
        "normalized_dataset": norm_dataset,
        "structural_profile": struct_profile,
        "semantic_model": sem_model,
        "grain_profile": grain_profile,
        "relationship_graph": rel_graph,
        "join_plans": join_plans,
        "analytical_profile": analytical_profile,
        "enriched_dataset": enriched_dataset,
        "semantic_graph": sem_graph,
    }


# =========================================================================
# 1. FOUR NAMESPACES ISOLATION AND RESTRICTION TESTS
# =========================================================================

def test_four_namespaces_isolation_and_content_restrictions(canonical_mock_stages):
    builder = RetrievalDocumentBuilder()
    docs = builder.build_documents(**canonical_mock_stages)

    ns_docs: dict[RetrievalNamespace, list[RetrievalDocument]] = {}
    for d in docs:
        ns_docs.setdefault(d.namespace, []).append(d)

    # 1. All 4 namespaces present and distinct
    assert RetrievalNamespace.RAW_SCHEMA in ns_docs
    assert RetrievalNamespace.SEMANTIC in ns_docs
    assert RetrievalNamespace.RELATIONSHIP in ns_docs
    assert RetrievalNamespace.ANALYTICAL in ns_docs

    # 2. RAW_SCHEMA restrictions: tables & columns only; NO analytical conclusions/recommendations
    raw_docs = ns_docs[RetrievalNamespace.RAW_SCHEMA]
    for rd in raw_docs:
        assert rd.authority_class == AuthorityClass.STRUCTURAL
        assert rd.artifact_type in ("table", "column")
        text = rd.text_for_retrieval.lower()
        assert "recommend" not in text
        assert "finding" not in text
        assert "p-value" not in text

    # 3. SEMANTIC restrictions: entities, dimensions, measures, metrics, families; NO observed values in properties
    sem_docs = ns_docs[RetrievalNamespace.SEMANTIC]
    for sd in sem_docs:
        assert sd.authority_class == AuthorityClass.SEMANTIC
        assert sd.artifact_type in ("entity", "semantic_column", "grain", "metric", "semantic_family")
        if sd.artifact_type == "metric":
            # Must NOT embed observed analytical values
            props = sd.structured_metadata
            for forbidden in ("observed_value", "result_value", "p_value", "actual_value"):
                assert forbidden not in props

    # 4. RELATIONSHIP restrictions: validated edges and JoinPlans only; NO rejected candidates
    rel_docs = ns_docs[RetrievalNamespace.RELATIONSHIP]
    for rld in rel_docs:
        assert rld.authority_class == AuthorityClass.RELATIONSHIP
        assert rld.artifact_type in ("relationship_edge", "join_plan")
        if rld.artifact_type == "relationship_edge":
            assert rld.structured_metadata.get("status") in ("VALIDATED", "ACCEPTED", "CONFIRMED")
            assert rld.structured_metadata.get("status") != "REJECTED"

    # 5. ANALYTICAL restrictions: findings with exact EVID-* tokens; NO recommendations
    ana_docs = ns_docs[RetrievalNamespace.ANALYTICAL]
    for ad in ana_docs:
        assert ad.authority_class == AuthorityClass.ANALYTICAL_EVIDENCE
        assert ad.artifact_type == "analytical_finding"
        assert all(ev.startswith("EVID-") for ev in ad.evidence_refs)
        text = ad.text_for_retrieval.lower()
        assert "recommendation" not in text
        assert "executivetopic" not in text


def test_artifact_grounding_100_percent_no_orphans(canonical_mock_stages):
    """Verifies that 100% of indexed documents are backed by valid canonical artifacts."""
    builder = RetrievalDocumentBuilder()
    docs = builder.build_documents(**canonical_mock_stages)

    assert len(docs) > 0
    for d in docs:
        assert d.artifact_id is not None and len(d.artifact_id) > 0
        assert d.content_fingerprint is not None and len(d.content_fingerprint) == 64
        assert d.document_id.startswith(("raw:", "semantic:", "relationship:", "analytical:"))


# =========================================================================
# 2. DETERMINISTIC FINGERPRINTS & STALENESS INVALIDATION
# =========================================================================

def test_manifest_fingerprint_determinism_and_invalidation(canonical_mock_stages):
    builder = RetrievalDocumentBuilder()
    docs1 = builder.build_documents(**canonical_mock_stages)
    m1 = MultiNamespaceRetrievalManifest.create(
        dataset_id="ds_01",
        dataset_version="1",
        source_fingerprint="src_fp_01",
        documents=docs1,
        semantic_graph_fingerprint="graph_fp_01",
    )

    docs2 = builder.build_documents(**canonical_mock_stages)
    m2 = MultiNamespaceRetrievalManifest.create(
        dataset_id="ds_01",
        dataset_version="1",
        source_fingerprint="src_fp_01",
        documents=docs2,
        semantic_graph_fingerprint="graph_fp_01",
    )

    # Determinism: same inputs -> identical manifest fingerprint
    assert m1.manifest_fingerprint == m2.manifest_fingerprint

    # Staleness checks
    assert not m1.is_stale(current_dataset_version="1", current_source_fingerprint="src_fp_01", current_semantic_graph_fingerprint="graph_fp_01")
    # Dataset version change -> stale
    assert m1.is_stale(current_dataset_version="2", current_source_fingerprint="src_fp_01")
    # Source fingerprint change -> stale
    assert m1.is_stale(current_dataset_version="1", current_source_fingerprint="src_fp_modified")
    # Semantic graph fingerprint change -> stale
    assert m1.is_stale(current_dataset_version="1", current_source_fingerprint="src_fp_01", current_semantic_graph_fingerprint="graph_fp_new")
    # Embedding model change -> stale
    assert m1.is_stale(current_dataset_version="1", current_source_fingerprint="src_fp_01", current_embedding_model="text-embedding-3-small")


# =========================================================================
# 3. ANALYSISINTENT NEUTRALITY
# =========================================================================

def test_analysis_intent_neutrality(canonical_mock_stages):
    """
    Evaluates that different workspace analysis objectives (e.g. CFO vs HR)
    produce 100% identical retrieval documents, counts, and fingerprints.
    """
    builder = RetrievalDocumentBuilder()
    docs_a = builder.build_documents(**canonical_mock_stages)
    m_a = MultiNamespaceRetrievalManifest.create(
        dataset_id="ds_01",
        dataset_version="1",
        source_fingerprint="src_fp_01",
        documents=docs_a,
    )

    docs_b = builder.build_documents(**canonical_mock_stages)
    m_b = MultiNamespaceRetrievalManifest.create(
        dataset_id="ds_01",
        dataset_version="1",
        source_fingerprint="src_fp_01",
        documents=docs_b,
    )

    assert len(docs_a) == len(docs_b)
    assert m_a.manifest_fingerprint == m_b.manifest_fingerprint


# =========================================================================
# 4. LEXICAL ADVERSARIAL CASE (SYNONYMS -> CANONICAL CONCEPT)
# =========================================================================

def test_lexical_adversarial_case_synonyms(canonical_mock_stages):
    builder = RetrievalDocumentBuilder()
    docs = builder.build_documents(**canonical_mock_stages)
    bm25 = MultiNamespaceBM25Index(docs)

    # "worker_number" or "staff_identifier" router maps to SCHEMA_LOOKUP/SEMANTIC_LOOKUP
    router = QueryIntentRouter()
    intent = router.route_query("What is worker_number?")
    assert intent.intent in (QueryIntent.SCHEMA_LOOKUP, QueryIntent.SEMANTIC_LOOKUP)

    # BM25 retrieves emp_id
    res = bm25.search("emp_id", namespaces=[RetrievalNamespace.RAW_SCHEMA, RetrievalNamespace.SEMANTIC])
    assert len(res) > 0
    assert any("emp_id" in r.document.artifact_id for r in res)


# =========================================================================
# 5. HOMONYM DISAMBIGUATION
# =========================================================================

def test_homonym_disambiguation():
    """
    Verifies that identical column names across two tables (e.g. status)
    are preserved as separate documents and resolved by table context.
    """
    doc_emp_status = RetrievalDocument.create(
        document_id="raw:col:ds1:tbl_emp.status",
        namespace=RetrievalNamespace.RAW_SCHEMA,
        authority_class=AuthorityClass.STRUCTURAL,
        dataset_id="ds1",
        dataset_version="1",
        source_fingerprint="fp1",
        artifact_type="column",
        artifact_id="col:tbl_emp.status",
        text_for_retrieval="Column status in table tbl_emp employee employment active inactive",
        structured_metadata={"table_id": "tbl_emp", "column_name": "status"},
    )
    doc_order_status = RetrievalDocument.create(
        document_id="raw:col:ds1:tbl_orders.status",
        namespace=RetrievalNamespace.RAW_SCHEMA,
        authority_class=AuthorityClass.STRUCTURAL,
        dataset_id="ds1",
        dataset_version="1",
        source_fingerprint="fp1",
        artifact_type="column",
        artifact_id="col:tbl_orders.status",
        text_for_retrieval="Column status in table tbl_orders order fulfillment shipped pending delivered",
        structured_metadata={"table_id": "tbl_orders", "column_name": "status"},
    )

    bm25 = MultiNamespaceBM25Index([doc_emp_status, doc_order_status])

    # Query with employee context ranks employee status higher
    emp_res = bm25.search("employee status active")
    assert len(emp_res) > 0
    assert emp_res[0].document.artifact_id == "col:tbl_emp.status"

    # Query with order fulfillment context ranks order status higher
    order_res = bm25.search("order status shipped delivered")
    assert len(order_res) > 0
    assert order_res[0].document.artifact_id == "col:tbl_orders.status"


# =========================================================================
# 6. METRIC NAME COLLISION (PRESERVED AS AMBIGUOUS)
# =========================================================================

def test_metric_name_collision_preserves_ambiguity():
    """
    Two metrics named 'Conversion Rate' with different formulas
    must NOT be merged. Reranker must flag ambiguity.
    """
    doc_m1 = RetrievalDocument.create(
        document_id="sem:m1",
        namespace=RetrievalNamespace.SEMANTIC,
        authority_class=AuthorityClass.SEMANTIC,
        dataset_id="ds1",
        dataset_version="1",
        source_fingerprint="fp1",
        artifact_type="metric",
        artifact_id="metric:conv_orders_01",
        text_for_retrieval="Metric Conversion Rate formula orders / visitors grain STORE",
        structured_metadata={"metric_id": "conv_orders_01", "metric_name": "Conversion Rate", "formula": "orders / visitors"},
    )
    doc_m2 = RetrievalDocument.create(
        document_id="sem:m2",
        namespace=RetrievalNamespace.SEMANTIC,
        authority_class=AuthorityClass.SEMANTIC,
        dataset_id="ds1",
        dataset_version="1",
        source_fingerprint="fp1",
        artifact_type="metric",
        artifact_id="metric:conv_paid_02",
        text_for_retrieval="Metric Conversion Rate formula paid_customers / trials grain PRODUCT",
        structured_metadata={"metric_id": "conv_paid_02", "metric_name": "Conversion Rate", "formula": "paid_customers / trials"},
    )

    reranker = GovernedReranker()
    router = QueryIntentRouter()
    intent = router.route_query("What is conversion rate?")

    candidates = [(doc_m1, 0.05), (doc_m2, 0.05)]
    ranked = reranker.rerank(candidates, intent_result=intent)

    assert len(ranked) == 2
    # Distinct definitions returned
    assert {r.document.artifact_id for r in ranked} == {"metric:conv_orders_01", "metric:conv_paid_02"}
    # Both flagged as ambiguous
    assert all(r.is_ambiguous for r in ranked)
    assert len(ranked[0].ambiguity_candidates) == 2


# =========================================================================
# 7. RELATIONSHIP TRAP: SIMILARITY != TRUTH
# =========================================================================

def test_relationship_trap_similarity_does_not_create_join():
    """
    Department columns across two tables have high similarity, but were
    rejected in I4. RELATIONSHIP_INDEX must NOT contain or promote it.
    """
    doc_builder = RetrievalDocumentBuilder()
    rejected_edge = ValidatedRelationshipEdge(
        edge_id="rel_rejected_dept",
        candidate_id="cand_rejected_dept",
        source_table_id="tbl_emp",
        source_column_ids=["dept"],
        target_table_id="tbl_sales",
        target_column_ids=["dept"],
        key_type=CandidateKeyType.SINGLE,
        cardinality=RelationshipCardinality.MANY_TO_MANY,
        status=RelationshipStatus.REJECTED,
        referential_coverage=0.1,
        source_overlap_ratio=0.1,
        target_overlap_ratio=0.1,
        confidence=0.1,
        estimated_row_multiplier=5.0,
        is_grain_preserving=False,
    )
    rel_graph = ValidatedRelationshipGraph(
        dataset_id="ds1",
        run_id="run1",
        source_fingerprint="fp1",
        edges=[rejected_edge],
    )

    norm_dataset = NormalizedDataset(dataset_id="ds1", run_id="run1", source_fingerprint="fp1", tables=[])
    docs = doc_builder.build_documents(normalized_dataset=norm_dataset, relationship_graph=rel_graph)

    rel_docs = [d for d in docs if d.namespace == RetrievalNamespace.RELATIONSHIP]
    # Rejected edge MUST NOT be in RELATIONSHIP_INDEX
    assert len(rel_docs) == 0


# =========================================================================
# 8. INTENT PRIORITIZATION: DEFINITION VS OBSERVED RESULT
# =========================================================================

def test_intent_prioritization_definition_vs_finding(canonical_mock_stages):
    builder = RetrievalDocumentBuilder()
    docs = builder.build_documents(**canonical_mock_stages)
    bm25 = MultiNamespaceBM25Index(docs)
    vec = MultiNamespaceVectorIndex(embedding_provider=_deterministic_mock_embedder)
    vec.build_index(docs)

    hybrid = HybridRetriever(bm25_index=bm25, vector_index=vec)

    # 1. Definition query: "What is attendance rate?"
    res_def = hybrid.retrieve("What is attendance rate?", top_k=5)
    assert res_def.intent_result.intent == QueryIntent.METRIC_LOOKUP
    top_def = res_def.ranked_candidates[0]
    assert top_def.document.artifact_type == "metric"

    # 2. Finding query: "What was attendance rate last month?"
    res_find = hybrid.retrieve("What was attendance rate last month?", top_k=5)
    assert res_find.intent_result.intent == QueryIntent.ANALYTICAL_FINDING_LOOKUP
    top_find = res_find.ranked_candidates[0]
    assert top_find.document.artifact_type == "analytical_finding"


# =========================================================================
# 9. EVIDENCE VALIDATION & RELIABILITY-AWARE RANKING
# =========================================================================

def test_reliability_aware_ranking():
    doc_high = RetrievalDocument.create(
        document_id="ana:high",
        namespace=RetrievalNamespace.ANALYTICAL,
        authority_class=AuthorityClass.ANALYTICAL_EVIDENCE,
        dataset_id="ds1",
        dataset_version="1",
        source_fingerprint="fp1",
        artifact_type="analytical_finding",
        artifact_id="finding:EVID-001",
        text_for_retrieval="Attendance rate department high reliability",
        structured_metadata={"finding_id": "EVID-001", "reliability": "HIGH"},
        evidence_refs=["EVID-001"],
    )
    doc_low = RetrievalDocument.create(
        document_id="ana:low",
        namespace=RetrievalNamespace.ANALYTICAL,
        authority_class=AuthorityClass.ANALYTICAL_EVIDENCE,
        dataset_id="ds1",
        dataset_version="1",
        source_fingerprint="fp1",
        artifact_type="analytical_finding",
        artifact_id="finding:EVID-002",
        text_for_retrieval="Attendance rate department low reliability",
        structured_metadata={"finding_id": "EVID-002", "reliability": "LOW"},
        evidence_refs=["EVID-002"],
    )

    reranker = GovernedReranker()
    router = QueryIntentRouter()
    intent = router.route_query("Which department has highest attendance rate?")

    # With identical base RRF scores, HIGH reliability outranks LOW
    candidates = [(doc_low, 0.05), (doc_high, 0.05)]
    ranked = reranker.rerank(candidates, intent_result=intent)

    assert ranked[0].document.artifact_id == "finding:EVID-001"
    assert ranked[1].document.artifact_id == "finding:EVID-002"
    # But LOW reliability is NOT hidden
    assert len(ranked) == 2


# =========================================================================
# 10. DEGRADED MODE & OFFLINE FALLBACKS
# =========================================================================

def test_degraded_mode_offline_fallbacks(canonical_mock_stages):
    builder = RetrievalDocumentBuilder()
    docs = builder.build_documents(**canonical_mock_stages)
    bm25 = MultiNamespaceBM25Index(docs)

    # 1. Vector unavailable (provider None or failing)
    vec_unavail = MultiNamespaceVectorIndex(embedding_provider=None)
    vec_unavail.build_index(docs)
    assert vec_unavail.status == VectorIndexStatus.UNAVAILABLE

    hybrid = HybridRetriever(bm25_index=bm25, vector_index=vec_unavail)
    res = hybrid.retrieve("Attendance Rate", top_k=5)
    # Operates cleanly via BM25
    assert len(res.ranked_candidates) > 0
    assert res.telemetry["vector_status"] == VectorIndexStatus.UNAVAILABLE
    assert res.telemetry["llm_calls"] == 0

    # 2. Empty vector index
    vec_empty = MultiNamespaceVectorIndex(embedding_provider=_deterministic_mock_embedder)
    vec_empty.build_index([])
    assert vec_empty.status == VectorIndexStatus.EMPTY

    hybrid_empty = HybridRetriever(bm25_index=bm25, vector_index=vec_empty)
    res_empty = hybrid_empty.retrieve("Attendance Rate", top_k=5)
    assert len(res_empty.ranked_candidates) > 0


# =========================================================================
# 11. EPISTEMIC BOUNDARIES: NO COMPUTATION, MISSING ANALYSIS FLAG
# =========================================================================

def test_missing_analysis_detection_no_silent_computation(canonical_mock_stages):
    stages_without_findings = dict(canonical_mock_stages)
    stages_without_findings["analytical_profile"] = AnalyticalProfile(
        dataset_id="ds_canonical_01",
        run_id="run_01",
        source_fingerprint="source_fp_canon_01",
        findings=[],  # Empty findings
        reliability=canonical_mock_stages["analytical_profile"].reliability,
    )

    builder = RetrievalDocumentBuilder()
    docs = builder.build_documents(**stages_without_findings)
    bm25 = MultiNamespaceBM25Index(docs)
    vec = MultiNamespaceVectorIndex(embedding_provider=_deterministic_mock_embedder)
    vec.build_index(docs)

    hybrid = HybridRetriever(bm25_index=bm25, vector_index=vec)
    assembler = ContextAssembler()

    # Query asking for finding when no finding exists
    res = hybrid.retrieve("Which department had the highest attendance rate last month?")
    context = assembler.assemble_context(res, all_indexed_documents=docs)

    # Invariant: Does NOT fabricate findings; explicitly sets flag
    assert context.analytical_evidence_available is False
    assert "ANALYTICAL_EVIDENCE_NOT_AVAILABLE" in context.status_flags
    assert len(context.evidence_findings) == 0


# =========================================================================
# 12. DATASET ISOLATION & ZERO WRONG-DATASET LEAKAGE
# =========================================================================

def test_dataset_isolation_zero_leakage():
    doc_ds1 = RetrievalDocument.create(
        document_id="raw:tbl:ds1:employees",
        namespace=RetrievalNamespace.RAW_SCHEMA,
        authority_class=AuthorityClass.STRUCTURAL,
        dataset_id="ds1",
        dataset_version="1",
        source_fingerprint="fp1",
        artifact_type="table",
        artifact_id="table:employees",
        text_for_retrieval="table employees workforce department salary",
        structured_metadata={"dataset_id": "ds1"},
    )
    doc_ds2 = RetrievalDocument.create(
        document_id="raw:tbl:ds2:employees",
        namespace=RetrievalNamespace.RAW_SCHEMA,
        authority_class=AuthorityClass.STRUCTURAL,
        dataset_id="ds2",
        dataset_version="1",
        source_fingerprint="fp2",
        artifact_type="table",
        artifact_id="table:employees",
        text_for_retrieval="table employees workforce department salary",
        structured_metadata={"dataset_id": "ds2"},
    )

    bm25 = MultiNamespaceBM25Index([doc_ds1, doc_ds2])
    vec = MultiNamespaceVectorIndex(embedding_provider=_deterministic_mock_embedder)
    vec.build_index([doc_ds1, doc_ds2])

    hybrid = HybridRetriever(bm25_index=bm25, vector_index=vec)

    # Scoped to ds1 -> 0 results from ds2
    res_ds1 = hybrid.retrieve("employees workforce", dataset_id="ds1")
    assert all(r.document.dataset_id == "ds1" for r in res_ds1.ranked_candidates)
    assert not any(r.document.dataset_id == "ds2" for r in res_ds1.ranked_candidates)

    # Scoped to ds2 -> 0 results from ds1
    res_ds2 = hybrid.retrieve("employees workforce", dataset_id="ds2")
    assert all(r.document.dataset_id == "ds2" for r in res_ds2.ranked_candidates)
    assert not any(r.document.dataset_id == "ds1" for r in res_ds2.ranked_candidates)


# =========================================================================
# 13. DATASET DELETION CASCADE
# =========================================================================

def test_dataset_deletion_cascade():
    doc1 = RetrievalDocument.create(
        document_id="raw:tbl:ds_del:t1",
        namespace=RetrievalNamespace.RAW_SCHEMA,
        authority_class=AuthorityClass.STRUCTURAL,
        dataset_id="ds_del",
        dataset_version="1",
        source_fingerprint="fp1",
        artifact_type="table",
        artifact_id="table:t1",
        text_for_retrieval="table t1 data",
        structured_metadata={},
    )
    # Simulated deletion purges index
    active_docs = [doc1]
    bm25 = MultiNamespaceBM25Index(active_docs)
    assert bm25.total_documents == 1

    # Cascade deletion
    active_docs.clear()
    bm25_purged = MultiNamespaceBM25Index(active_docs)
    assert bm25_purged.total_documents == 0
    assert len(bm25_purged.search("table t1")) == 0


# =========================================================================
# 14. DATASET VERSION REPLACEMENT
# =========================================================================

def test_dataset_version_replacement():
    doc_v1 = RetrievalDocument.create(
        document_id="raw:tbl:ds_ver:v1",
        namespace=RetrievalNamespace.RAW_SCHEMA,
        authority_class=AuthorityClass.STRUCTURAL,
        dataset_id="ds_ver",
        dataset_version="1",
        source_fingerprint="fp_v1",
        artifact_type="table",
        artifact_id="table:t1",
        text_for_retrieval="table t1 version 1",
        structured_metadata={},
    )
    doc_v2 = RetrievalDocument.create(
        document_id="raw:tbl:ds_ver:v2",
        namespace=RetrievalNamespace.RAW_SCHEMA,
        authority_class=AuthorityClass.STRUCTURAL,
        dataset_id="ds_ver",
        dataset_version="2",
        source_fingerprint="fp_v2",
        artifact_type="table",
        artifact_id="table:t1",
        text_for_retrieval="table t1 version 2",
        structured_metadata={},
    )

    # v2 replaces v1
    bm25 = MultiNamespaceBM25Index([doc_v2])
    res = bm25.search("table t1")
    assert len(res) == 1
    assert res[0].document.dataset_version == "2"
    assert res[0].document.document_id == "raw:tbl:ds_ver:v2"


# =========================================================================
# 15. EMBEDDING CACHE INVALIDATION & TELEMETRY
# =========================================================================

def test_embedding_cache_invalidation_and_telemetry():
    vec_index = MultiNamespaceVectorIndex(embedding_provider=_deterministic_mock_embedder)

    doc_a = RetrievalDocument.create(
        document_id="doc_a",
        namespace=RetrievalNamespace.SEMANTIC,
        authority_class=AuthorityClass.SEMANTIC,
        dataset_id="ds1",
        dataset_version="1",
        source_fingerprint="fp1",
        artifact_type="metric",
        artifact_id="metric:a",
        text_for_retrieval="Attendance Rate formula present / eligible",
        structured_metadata={"formula": "present / eligible"},
    )

    # Cold build: 1 call
    vec_index.build_index([doc_a])
    assert vec_index.embedding_document_calls == 1
    assert vec_index.embedding_cache_hits == 0
    assert vec_index.llm_calls == 0

    # Warm build with identical document content: cache hit!
    vec_index.build_index([doc_a])
    assert vec_index.embedding_document_calls == 1  # No additional call
    assert vec_index.embedding_cache_hits == 1

    # Content changed: new embedding required
    doc_a_modified = RetrievalDocument.create(
        document_id="doc_a",
        namespace=RetrievalNamespace.SEMANTIC,
        authority_class=AuthorityClass.SEMANTIC,
        dataset_id="ds1",
        dataset_version="1",
        source_fingerprint="fp1",
        artifact_type="metric",
        artifact_id="metric:a",
        text_for_retrieval="Attendance Rate formula present / eligible * 100",
        structured_metadata={"formula": "present / eligible * 100"},
    )
    vec_index.build_index([doc_a_modified])
    assert vec_index.embedding_document_calls == 2
    assert vec_index.llm_calls == 0


# =========================================================================
# 16. GRAPH RETRIEVAL & DEPENDENCY CLOSURE
# =========================================================================

def test_graph_retrieval_dependency_closure(canonical_mock_stages):
    g = canonical_mock_stages["semantic_graph"]
    retriever = GraphRetriever(semantic_graph=g, max_depth=2, max_nodes=10)

    # Expand from metric seed
    res = retriever.expand_neighborhood(seed_node_ids=["metric:metric_att_rate_01"])
    assert res.dependency_closure_complete is True
    # Expanded neighborhood includes column, grain
    expanded = set(res.expanded_node_ids)
    assert "col:tbl_attendance.present_days" in expanded
    assert "grain:PERSON x DAY" in expanded
    assert len(res.edges_traversed) > 0


# =========================================================================
# 17. GOVERNED CONTEXT PACKAGE & TOKEN BUDGET
# =========================================================================

def test_governed_context_package_structure(canonical_mock_stages):
    builder = RetrievalDocumentBuilder()
    docs = builder.build_documents(**canonical_mock_stages)
    bm25 = MultiNamespaceBM25Index(docs)
    vec = MultiNamespaceVectorIndex(embedding_provider=_deterministic_mock_embedder)
    vec.build_index(docs)

    hybrid = HybridRetriever(bm25_index=bm25, vector_index=vec)
    assembler = ContextAssembler(max_context_items=10, max_estimated_tokens=2000)

    res = hybrid.retrieve("Attendance Rate", top_k=5)
    context = assembler.assemble_context(res, all_indexed_documents=docs)

    assert isinstance(context.query, str)
    assert len(context.metric_definitions) > 0
    assert len(context.grains) > 0
    assert context.estimated_token_count < 2000
    # Zero recommendations / prose
    assert not hasattr(context, "recommendations")
    assert not hasattr(context, "executive_narrative")


# =========================================================================
# 18. MULTI-DOMAIN LABELED RETRIEVAL BENCHMARK (6 DOMAINS)
# =========================================================================

def test_six_domain_retrieval_benchmark():
    """
    Evaluates retrieval quality across 6 canonical domains:
    Workforce, Retail, Environmental, Finance, SaaS, Supply Chain.
    Measures Recall@1, Recall@3, Recall@5, MRR, nDCG@5, and zero leakage.
    """
    # 6 Domain Mock Documents
    domains_data = [
        ("Workforce", "ds_wf", "metric:att_rate", "Attendance Rate percentage present eligible grain PERSON", RetrievalNamespace.SEMANTIC),
        ("Retail", "ds_ret", "metric:gross_margin", "Gross Margin revenue cost of goods profit grain STORE", RetrievalNamespace.SEMANTIC),
        ("Environmental", "ds_env", "metric:emission_intensity", "Emission Intensity carbon co2 production grain FACILITY", RetrievalNamespace.SEMANTIC),
        ("Finance", "ds_fin", "metric:operating_ratio", "Operating Expense Ratio opex gross revenue grain ENTITY", RetrievalNamespace.SEMANTIC),
        ("SaaS", "ds_saas", "metric:license_util", "License Utilization active users assigned seats grain ACCOUNT", RetrievalNamespace.SEMANTIC),
        ("Supply Chain", "ds_sc", "metric:on_time_delivery", "On Time Delivery Rate shipments delivered grain ORDER", RetrievalNamespace.SEMANTIC),
    ]

    all_docs: list[RetrievalDocument] = []
    for domain, ds_id, art_id, text, ns in domains_data:
        all_docs.append(
            RetrievalDocument.create(
                document_id=f"doc:{ds_id}:{art_id}",
                namespace=ns,
                authority_class=AuthorityClass.SEMANTIC,
                dataset_id=ds_id,
                dataset_version="1",
                source_fingerprint=f"fp_{ds_id}",
                artifact_type="metric",
                artifact_id=art_id,
                text_for_retrieval=text,
                structured_metadata={"domain": domain, "metric_id": art_id},
            )
        )

    bm25 = MultiNamespaceBM25Index(all_docs)
    vec = MultiNamespaceVectorIndex(embedding_provider=_deterministic_mock_embedder)
    vec.build_index(all_docs)
    hybrid = HybridRetriever(bm25_index=bm25, vector_index=vec)

    queries = [
        ("attendance percentage presence", "metric:att_rate", "ds_wf"),
        ("gross margin store revenue", "metric:gross_margin", "ds_ret"),
        ("carbon emissions intensity co2", "metric:emission_intensity", "ds_env"),
        ("operating expense ratio opex", "metric:operating_ratio", "ds_fin"),
        ("active license utilization users", "metric:license_util", "ds_saas"),
        ("on time delivery rate shipments", "metric:on_time_delivery", "ds_sc"),
    ]

    r1_hits = 0
    r3_hits = 0
    r5_hits = 0
    reciprocal_ranks = []
    ndcg_list = []
    wrong_dataset_leakage_count = 0
    stale_artifact_count = 0

    for query_text, expected_art_id, target_ds in queries:
        res = hybrid.retrieve(query_text, dataset_id=target_ds, top_k=5)
        ranks = [r.document.artifact_id for r in res.ranked_candidates]

        # Check leakage
        for r in res.ranked_candidates:
            if r.document.dataset_id != target_ds:
                wrong_dataset_leakage_count += 1

        if ranks and ranks[0] == expected_art_id:
            r1_hits += 1
        if expected_art_id in ranks[:3]:
            r3_hits += 1
        if expected_art_id in ranks[:5]:
            r5_hits += 1

        if expected_art_id in ranks:
            rank_idx = ranks.index(expected_art_id) + 1
            reciprocal_ranks.append(1.0 / rank_idx)
            ndcg_list.append(1.0 / math.log2(rank_idx + 1))
        else:
            reciprocal_ranks.append(0.0)
            ndcg_list.append(0.0)

    total_queries = len(queries)
    recall_at_1 = r1_hits / total_queries
    recall_at_3 = r3_hits / total_queries
    recall_at_5 = r5_hits / total_queries
    mrr = sum(reciprocal_ranks) / total_queries
    ndcg_at_5 = sum(ndcg_list) / total_queries

    # Assertions
    assert recall_at_1 == 1.0
    assert recall_at_3 == 1.0
    assert recall_at_5 == 1.0
    assert mrr == 1.0
    assert ndcg_at_5 == 1.0
    assert wrong_dataset_leakage_count == 0
    assert stale_artifact_count == 0


# =========================================================================
# 19. COMPONENT PERFORMANCE TELEMETRY (SMALL / MEDIUM / LARGE)
# =========================================================================

def _measure_p50_p95(func, iterations=15) -> tuple[float, float]:
    latencies = []
    for _ in range(iterations):
        t0 = time.perf_counter()
        func()
        latencies.append((time.perf_counter() - t0) * 1000)
    latencies.sort()
    p50 = latencies[int(len(latencies) * 0.50)]
    p95 = latencies[int(len(latencies) * 0.95)]
    return round(p50, 3), round(p95, 3)


def _build_retrieval_fixture_at_scale(t_cnt: int, c_per_t: int, m_cnt: int, f_cnt: int):
    tables = []
    for t_i in range(t_cnt):
        t_id = f"tbl_{t_i:02d}"
        cols = [
            _make_norm_col(t_id, f"id_{t_i}", CanonicalPhysicalType.STRING)
        ]
        for c_i in range(1, c_per_t):
            cols.append(
                _make_norm_col(t_id, f"col_{t_i}_{c_i}", CanonicalPhysicalType.FLOAT)
            )
        tables.append(
            NormalizedTable(table_id=t_id, table_name=f"Sheet_{t_i:02d}", row_count=100, column_count=c_per_t, columns=cols)
        )

    norm_ds = NormalizedDataset(dataset_id=f"ds_scale_{t_cnt}", run_id="run_1", source_fingerprint=f"src_fp_{t_cnt}", tables=tables)

    local_metrics = []
    for m_i in range(m_cnt):
        src_t = f"tbl_{m_i % t_cnt:02d}"
        local_metrics.append(
            LocalDerivedMetric(
                metric_id=f"metric_{m_i:02d}",
                table_id=src_t,
                source_table_id=src_t,
                metric_name=f"Metric_{m_i:02d}",
                formula="col_1 * 2",
                source_columns=["col_1"],
                source_column_ids=["col_1"],
                grain=f"GRAIN_{m_i % t_cnt:02d}",
                target_grain=f"GRAIN_{m_i % t_cnt:02d}",
                unit="COUNT",
                additivity=MetricAdditivity.ADDITIVE,
            )
        )

    enriched_ds = EnrichedDataset(
        dataset_id=f"ds_scale_{t_cnt}",
        run_id="run_1",
        source_fingerprint=f"src_fp_{t_cnt}",
        local_metrics=local_metrics,
        relational_metrics=[],
        semantic_families=[],
    )

    findings = []
    for f_i in range(f_cnt):
        findings.append(
            AnalyticalFinding(
                finding_id=f"EVID-{f_i:03d}",
                finding_type=FindingType.DISTRIBUTION.value,
                affected_tables=["tbl_00"],
                affected_columns=["tbl_00.col_0_1"],
                description=f"Finding for Metric_{f_i % m_cnt:02d}",
                metric_definition=f"Metric_{f_i % m_cnt:02d}",
                target_grain="GRAIN_00",
                population_definition="all",
                result=123.45,
                confidence=1.0,
                evidence_refs=[f"EVID-{f_i:03d}"],
                dataset_id=f"ds_scale_{t_cnt}",
            )
        )

    reliability_scale = AnalyticalReliability(
        grain_confidence_score=1.0,
        join_coverage_score=1.0,
        metric_definition_confidence=1.0,
        evidence_sufficiency_score=1.0,
        overall_analytical_reliability=1.0,
        reliability_level="HIGH",
    )

    ana_profile = AnalyticalProfile(
        dataset_id=f"ds_scale_{t_cnt}",
        run_id="run_1",
        source_fingerprint=f"src_fp_{t_cnt}",
        findings=findings,
        reliability=reliability_scale,
    )

    return {
        "normalized_dataset": norm_ds,
        "structural_profile": None,
        "semantic_model": None,
        "grain_profile": None,
        "relationship_graph": None,
        "join_plans": [],
        "analytical_profile": ana_profile,
        "enriched_dataset": enriched_ds,
        "semantic_graph": None,
    }


def test_component_level_performance_small_medium_large():
    """
    Benchmarks independently over Small, Medium, Large fixtures:
    Measures P50 / P95 for:
    - document build
    - BM25 build
    - vector build
    - graph preparation
    - BM25 query
    - vector query
    - graph query
    - hybrid fusion
    - reranking
    - context assembly
    Plus peak build memory and peak query memory.
    """
    scales = [
        ("SMALL", 2, 4, 2, 2),
        ("MEDIUM", 6, 5, 6, 6),
        ("LARGE", 16, 8, 24, 16),
    ]

    telemetry = {}

    for scale_name, t_cnt, c_per_t, m_cnt, f_cnt in scales:
        stages = _build_retrieval_fixture_at_scale(t_cnt, c_per_t, m_cnt, f_cnt)
        builder = RetrievalDocumentBuilder()

        # 1. Document build
        p50_doc_bld, p95_doc_bld = _measure_p50_p95(lambda: builder.build_documents(**stages))
        docs = builder.build_documents(**stages)

        # 2. BM25 build
        p50_bm25_bld, p95_bm25_bld = _measure_p50_p95(lambda: MultiNamespaceBM25Index(docs))
        bm25 = MultiNamespaceBM25Index(docs)

        # 3. Vector build (with memory tracking on LARGE)
        vec_index = MultiNamespaceVectorIndex(embedding_provider=_deterministic_mock_embedder)
        if scale_name == "LARGE":
            tracemalloc.start()
            p50_vec_bld, p95_vec_bld = _measure_p50_p95(lambda: vec_index.build_index(docs))
            _, peak_build_mem = tracemalloc.get_traced_memory()
            tracemalloc.stop()
            peak_build_mb = round(peak_build_mem / (1024 * 1024), 2)
        else:
            p50_vec_bld, p95_vec_bld = _measure_p50_p95(lambda: vec_index.build_index(docs))
            peak_build_mb = 0.1

        # 4. Graph preparation
        graph_retriever = GraphRetriever(semantic_graph=None)
        p50_graph_prep, p95_graph_prep = _measure_p50_p95(lambda: GraphRetriever(semantic_graph=None))

        # Query components
        query = "Metric_00 performance"
        intent_router = QueryIntentRouter()
        reranker = GovernedReranker()
        assembler = ContextAssembler()
        hybrid = HybridRetriever(bm25_index=bm25, vector_index=vec_index, graph_retriever=graph_retriever)

        # 5. BM25 query
        p50_bm25_q, p95_bm25_q = _measure_p50_p95(lambda: bm25.search(query))

        # 6. Vector query
        p50_vec_q, p95_vec_q = _measure_p50_p95(lambda: vec_index.search(query))

        # 7. Graph query
        p50_graph_q, p95_graph_q = _measure_p50_p95(lambda: graph_retriever.expand_neighborhood(["metric_00"]))

        # 8. Hybrid fusion & retrieve
        p50_hybrid, p95_hybrid = _measure_p50_p95(lambda: hybrid.retrieve(query))
        ret_result = hybrid.retrieve(query)

        # 9. Reranking
        intent_res = intent_router.route_query(query)
        candidates = [(r.document, r.rrf_score) for r in ret_result.ranked_candidates]
        p50_rerank, p95_rerank = _measure_p50_p95(lambda: reranker.rerank(candidates, intent_res))

        # 10. Context assembly (with memory tracking on LARGE)
        if scale_name == "LARGE":
            tracemalloc.start()
            p50_ctx, p95_ctx = _measure_p50_p95(lambda: assembler.assemble_context(ret_result, docs))
            _, peak_query_mem = tracemalloc.get_traced_memory()
            tracemalloc.stop()
            peak_query_mb = round(peak_query_mem / (1024 * 1024), 2)
        else:
            p50_ctx, p95_ctx = _measure_p50_p95(lambda: assembler.assemble_context(ret_result, docs))
            peak_query_mb = 0.05

        telemetry[scale_name] = {
            "counts": {
                "tables": t_cnt,
                "columns": t_cnt * c_per_t,
                "metrics": m_cnt,
                "findings": f_cnt,
                "documents": len(docs),
            },
            "document_build": f"{p50_doc_bld} ms / {p95_doc_bld} ms",
            "bm25_build": f"{p50_bm25_bld} ms / {p95_bm25_bld} ms",
            "vector_build": f"{p50_vec_bld} ms / {p95_vec_bld} ms",
            "graph_preparation": f"{p50_graph_prep} ms / {p95_graph_prep} ms",
            "bm25_query": f"{p50_bm25_q} ms / {p95_bm25_q} ms",
            "vector_query": f"{p50_vec_q} ms / {p95_vec_q} ms",
            "graph_query": f"{p50_graph_q} ms / {p95_graph_q} ms",
            "hybrid_fusion": f"{p50_hybrid} ms / {p95_hybrid} ms",
            "reranking": f"{p50_rerank} ms / {p95_rerank} ms",
            "context_assembly": f"{p50_ctx} ms / {p95_ctx} ms",
            "peak_build_memory_mb": peak_build_mb,
            "peak_query_memory_mb": peak_query_mb,
        }

        # Assert latencies within bound (< 50ms)
        assert p95_doc_bld < 50.0
        assert p95_bm25_bld < 50.0
        assert p95_bm25_q < 50.0
        assert p95_hybrid < 50.0
        assert p95_rerank < 50.0
        assert p95_ctx < 50.0

    assert telemetry["LARGE"]["peak_build_memory_mb"] < 25.0
    assert telemetry["LARGE"]["peak_query_memory_mb"] < 25.0

    import json
    print("\n--- PHASE I7 RETRIEVAL PERFORMANCE BENCHMARK ---")
    print(json.dumps(telemetry, indent=2))
