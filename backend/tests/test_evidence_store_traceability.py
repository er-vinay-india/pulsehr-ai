"""Tests for the Evidence Store, Finding schemas, and bi-directional traceability."""

import pytest
from app.services.evidence.evidence_models import Finding, FindingType, Importance, EvidenceReference
from app.services.evidence.evidence_store import EvidenceStore
from app.services.analyst.analyst_agent import AnalystAgent
from app.services.data_engine.metric_engine import CandidateFact
from app.services.data_engine.profiler import DatasetProfile


@pytest.fixture
def populated_store():
    store = EvidenceStore()
    store.add_finding(Finding(
        finding_id="F-001",
        type=FindingType.OUTPERFORMER,
        metric="completion_rate",
        segment="Sales",
        segment_value=92.5,
        overall_value=85.0,
        difference=7.5,
        difference_percentage_points=8.8,
        importance=Importance.HIGH,
        headline="Sales records peak completion rate of 92.5%",
        business_implication="Sales practices should be audited for network replication",
        evidence=[EvidenceReference(
            source_sheet="Sheet1",
            metric="completion_rate",
            segment="Sales",
            row_count=120,
            proof={"mean": 92.5, "baseline": 85.0}
        )]
    ))
    store.add_finding(Finding(
        finding_id="F-002",
        type=FindingType.HEADWIND,
        metric="completion_rate",
        segment="Logistics",
        segment_value=74.0,
        overall_value=85.0,
        difference=-11.0,
        difference_percentage_points=-12.9,
        importance=Importance.HIGH,
        headline="Logistics trails network benchmark by 11.0 points",
        business_implication="Supply chain bottlenecks require operational intervention",
        evidence=[EvidenceReference(
            source_sheet="Sheet1",
            metric="completion_rate",
            segment="Logistics",
            row_count=85,
            proof={"mean": 74.0, "baseline": 85.0}
        )]
    ))
    return store


def test_evidence_store_retrieval(populated_store):
    """Verifies retrieval by ID and filtering by type/importance."""
    f1 = populated_store.get_finding("F-001")
    assert f1 is not None
    assert f1.type == FindingType.OUTPERFORMER
    assert f1.segment == "Sales"
    assert f1.difference == 7.5

    # Filter by type
    headwinds = populated_store.filter_by_type(FindingType.HEADWIND)
    assert len(headwinds) == 1
    assert headwinds[0].finding_id == "F-002"

    # Filter by importance
    high_imp = populated_store.filter_by_importance(Importance.HIGH)
    assert len(high_imp) == 2


def test_evidence_store_validate_ids(populated_store):
    """Verifies detection of hallucinated/invalid finding IDs."""
    valid, invalid = populated_store.validate_ids(["F-001", "F-999", "F-002", "FAKER"])
    assert valid == ["F-001", "F-002"]
    assert invalid == ["F-999", "FAKER"]


def test_evidence_store_export_ledger(populated_store):
    """Verifies that export_ledger includes all proofs and numeric values for auditing."""
    ledger = populated_store.export_ledger()
    assert len(ledger) == 2
    f1_ledger = next(item for item in ledger if item["finding_id"] == "F-001")
    assert f1_ledger["numeric_value"] == 92.5
    assert f1_ledger["baseline_value"] == 85.0
    assert len(f1_ledger["proof"]) == 1
    assert f1_ledger["proof"][0]["source_sheet"] == "Sheet1"


def test_analyst_agent_fallback_populates_store():
    """Verifies that AnalystAgent populates EvidenceStore even when LLM is unavailable."""
    candidate_facts = [
        CandidateFact(
            fact_id="FACT-001",
            fact_type="segment_gap",
            metric="attendance_rate",
            segment="Finance",
            observed_value=96.4,
            baseline_value=88.2,
            difference=8.2,
            percentage_gap=9.3,
            sample_size=45,
            significance_score=0.85
        )
    ]
    profile = DatasetProfile(
        dataset_name="Attendance Data",
        business_domain="Workforce Analytics",
        row_count=200,
        column_count=4
    )

    store = AnalystAgent.analyze(candidate_facts, profile)
    findings = store.get_all()
    assert len(findings) >= 1
    assert findings[0].finding_id.startswith("F-")
    assert findings[0].metric == "attendance_rate"
    assert findings[0].segment == "Finance"
    assert findings[0].segment_value == 96.4
