"""
HighView Ingestion V2 — Phase I8.1 Shadow Parity & Disagreement Certification Tests
Boundary: Verifies that real V1 and V2 runtime side-by-side evaluation over the 6-domain
canonical benchmark corpus satisfies all certification gates before consumer cutover.
"""

from __future__ import annotations

import tempfile
from pathlib import Path
import pytest

from app.services.ingestion_v2.contracts.disagreement import (
    ComparisonClass,
    DisagreementType,
    ReviewStatus,
    Severity,
)
from app.services.ingestion_v2.shadow_parity_auditor import (
    ShadowParityAuditor,
    ShadowParityAuditReport,
)
from app.services.ingestion_v2.shadow_runner import ShadowStorageManager


@pytest.fixture
def audit_report() -> ShadowParityAuditReport:
    auditor = ShadowParityAuditor(run_id="test-audit-i8-1-real-runtime")
    return auditor.run_audit()


def test_shadow_parity_total_comparison_volume(audit_report):
    """Verifies that 60 comparisons are executed across 6 domains x 10 categories."""
    assert audit_report.total_comparisons == 60
    assert len(audit_report.comparisons) == 60
    assert len(audit_report.domain_summaries) == 6


def test_real_v1_and_v2_runtime_producers_and_fingerprints(audit_report):
    """Verifies that EVERY comparison record carries real V1 and V2 producers and fingerprints."""
    for rec in audit_report.comparisons:
        assert rec.v1_producer is not None and len(rec.v1_producer.strip()) > 0
        assert rec.v2_producer is not None and len(rec.v2_producer.strip()) > 0
        assert len(rec.v1_fingerprint) == 64, f"Invalid SHA-256 fingerprint for V1 in {rec.comparison_id}"
        assert len(rec.v2_fingerprint) == 64, f"Invalid SHA-256 fingerprint for V2 in {rec.comparison_id}"
        assert rec.benchmark_truth_source is not None and len(rec.benchmark_truth_source.strip()) > 0
        assert rec.review_status == ReviewStatus.APPROVED


def test_comparison_category_coverage(audit_report):
    """Verifies 10 categories are covered with exactly 6 comparisons each (1 per domain)."""
    expected_categories = [
        "schema",
        "semantic_role",
        "grain",
        "relationships",
        "join_plans",
        "metric_definitions",
        "analytical_values",
        "denominators",
        "evidence",
        "retrieval_context",
    ]
    for cat in expected_categories:
        cat_records = [c for c in audit_report.comparisons if c.category == cat]
        assert len(cat_records) == 6, f"Category {cat} must have exactly 6 comparisons (1 per domain)"


def test_shadow_parity_zero_blockers(audit_report):
    """Strict cutover gate: regressions = 0, unresolved = 0, critical = 0."""
    assert audit_report.regressions == 0, "Regressions must be strictly 0"
    assert audit_report.unresolved == 0, "Unresolved disagreements must be strictly 0"
    assert audit_report.critical == 0, "Critical severity items must be strictly 0"
    assert audit_report.ledger.blocks_cutover is False
    assert audit_report.ledger.requires_human_review is False


def test_shadow_parity_class_distribution(audit_report):
    """Verifies macro comparison classification across all 60 items."""
    assert audit_report.unchanged_count == 26
    assert audit_report.expected_improvements == 22
    assert audit_report.expected_differences == 12
    assert audit_report.unchanged_count + audit_report.expected_improvements + audit_report.expected_differences == 60


def test_shadow_parity_disagreement_type_distribution(audit_report):
    """Verifies micro disagreement types over the 34 non-UNCHANGED items."""
    assert len(audit_report.disagreement_records) == 34
    assert audit_report.expected_fixes == 20
    assert audit_report.expected_refactors == 14
    assert audit_report.expected_fixes + audit_report.expected_refactors == 34


def test_shadow_parity_per_domain_summaries(audit_report):
    """Verifies each domain completes exactly 10 comparisons with zero regressions."""
    expected_domains = [
        "Workforce",
        "Retail",
        "Environmental",
        "Finance",
        "SaaS",
        "Supply Chain",
    ]
    for d in expected_domains:
        assert d in audit_report.domain_summaries
        summary = audit_report.domain_summaries[d]
        assert summary.total_comparisons == 10
        assert summary.regressions == 0
        assert summary.unresolved == 0
        assert summary.critical == 0
        assert summary.unchanged_count + summary.expected_improvements + summary.expected_differences == 10


def test_all_expected_fixes_are_benchmark_grounded(audit_report):
    """All 20 EXPECTED_FIX cases must have benchmark truth, rationale, and APPROVED review status."""
    fix_records = [c for c in audit_report.comparisons if c.disagreement_type == DisagreementType.EXPECTED_FIX]
    assert len(fix_records) == 20
    for rec in fix_records:
        assert rec.benchmark_truth is not None
        assert len(str(rec.benchmark_truth).strip()) > 0
        assert rec.review_status == ReviewStatus.APPROVED
        assert len(rec.reason) > 10
        assert rec.evidence_ref.startswith("EVID-")


def test_all_expected_refactors_are_semantically_equivalent(audit_report):
    """All 14 EXPECTED_REFACTOR cases must preserve business meaning and carry APPROVED status."""
    refactor_records = [c for c in audit_report.comparisons if c.disagreement_type == DisagreementType.EXPECTED_REFACTOR]
    assert len(refactor_records) == 14
    for rec in refactor_records:
        assert rec.review_status == ReviewStatus.APPROVED
        assert rec.severity == Severity.INFO
        assert len(rec.reason) > 10
        assert rec.evidence_ref.startswith("EVID-")


def test_mathematical_safety_invariants(audit_report):
    """Verifies all six mathematical safety invariants are zero-defect."""
    ms = audit_report.mathematical_safety
    assert ms["wrong_denominator"] == 0
    assert ms["unsafe_join"] == 0
    assert ms["wrong_grain"] == 0
    assert ms["invented_evidence"] == 0
    assert ms["wrong_dataset"] == 0
    assert ms["stale_artifact"] == 0


def test_retrieval_invariants(audit_report):
    """Verifies all retrieval invariants are zero-defect."""
    ri = audit_report.retrieval_invariants
    assert ri["wrong_artifact"] == 0
    assert ri["orphan_context"] == 0
    assert ri["missing_dependency_closure"] == 0


def test_boundary_invariants_during_shadow_parity(audit_report):
    """Verifies that shadow parity run does not cut over or perform production writes."""
    bi = audit_report.boundary_invariants
    assert bi["production_writes"] == 0
    assert bi["consumer_cutover"] is False
    assert bi["feature_gates_activated"] is False
    assert bi["llm_calls"] == 0


def test_ledger_persistence_in_isolated_storage(audit_report):
    """Verifies that the disagreement ledger saves cleanly to isolated shadow store."""
    with tempfile.TemporaryDirectory() as tmpdir:
        storage = ShadowStorageManager(base_dir=tmpdir)
        saved_path = storage.save_ledger(audit_report.ledger)
        assert saved_path.exists()
        loaded = storage.load_ledger(audit_report.ledger.shadow_run_id)
        assert loaded is not None
        assert loaded.run_id == audit_report.ledger.run_id
        assert len(loaded.records) == 34
        assert loaded.blocks_cutover is False
