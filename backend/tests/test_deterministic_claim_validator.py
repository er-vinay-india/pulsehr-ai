"""Unit tests for DeterministicClaimValidator."""

import pytest
from app.services.evidence.evidence_models import Finding, FindingType, Importance, EvidenceReference
from app.services.evidence.evidence_store import EvidenceStore
from app.services.reporting.writer_agent import WrittenSection
from app.services.critic.deterministic_claim_validator import (
    DeterministicClaimValidator,
    ClaimValidationStatus,
    ToleranceConfig
)


@pytest.fixture
def evidence_store():
    store = EvidenceStore()
    # F-001: Sales completion rate (higher is better, dropped by -10.45 points)
    store.add_finding(Finding(
        finding_id="F-001",
        type=FindingType.PERFORMANCE_GAP,
        metric="completion_rate",
        segment="Sales",
        segment_value=76.25,
        overall_value=86.70,
        difference=-10.45,
        difference_percentage_points=-12.1,
        importance=Importance.HIGH,
        headline="Sales recorded completion rate of 76.25%",
        business_implication="Underperforming baseline by 10.45 percentage points",
        evidence=[EvidenceReference(
            source_sheet="Sheet1",
            metric="completion_rate",
            segment="Sales",
            row_count=100
        )]
    ))
    # F-002: Engineering turnover (lower is better, turnover dropped by -35.0%)
    store.add_finding(Finding(
        finding_id="F-002",
        type=FindingType.TREND_SHIFT,
        metric="turnover_rate",
        segment="Engineering",
        segment_value=12.0,
        overall_value=18.5,
        difference=-6.5,
        difference_percentage_points=-35.0,
        importance=Importance.HIGH,
        headline="Engineering turnover dropped to 12.0%",
        business_implication="Retention improved significantly",
        evidence=[EvidenceReference(
            source_sheet="Sheet1",
            metric="turnover_rate",
            segment="Engineering",
            row_count=250
        )]
    ))
    return store


def test_unknown_evidence_id_fails_deterministically(evidence_store):
    """Claim citing F-999 must fail deterministically without LLM."""
    claim = "Sales recorded a 50% jump in completion [F-999]"
    res = DeterministicClaimValidator.validate_claim(claim, evidence_store)
    assert res.status == ClaimValidationStatus.INVALID
    assert res.requires_llm is False
    assert any("F-999" in v for v in res.violations)


def test_uncited_quantitative_assertion_fails(evidence_store):
    """Claim stating numerical metrics without citation tag must fail deterministically."""
    claim = "Turnover increased 17% across all key segments."
    res = DeterministicClaimValidator.validate_claim(claim, evidence_store)
    assert res.status == ClaimValidationStatus.INVALID
    assert res.requires_llm is False
    assert any("lacks evidence citation" in v for v in res.violations)


def test_wrong_numerical_figure_fails(evidence_store):
    """Claim with hallucinated numbers fails deterministically."""
    claim = "Sales completion rate was 34.8% [F-001]"
    res = DeterministicClaimValidator.validate_claim(claim, evidence_store)
    assert res.status == ClaimValidationStatus.INVALID
    assert res.requires_llm is False
    assert any("Unmatched numerical figure" in v for v in res.violations)


def test_rounding_within_tolerance_passes(evidence_store):
    """Claim with minor rounding (76.3% vs 76.25%) should pass deterministically."""
    claim = "Sales achieved approximately 76.3% completion rate, trailing baseline [F-001]"
    res = DeterministicClaimValidator.validate_claim(claim, evidence_store)
    assert res.status == ClaimValidationStatus.VERIFIED
    assert res.requires_llm is False


def test_numerical_direction_contradiction_fails(evidence_store):
    """Claim claiming completion rate rose when difference is -10.45 must fail."""
    claim = "Sales completion rate rose significantly to 76.25% [F-001]"
    res = DeterministicClaimValidator.validate_claim(claim, evidence_store)
    assert res.status == ClaimValidationStatus.INVALID
    assert res.requires_llm is False
    assert any("direction contradiction" in v.lower() for v in res.violations)


def test_lower_is_better_metric_direction_and_sentiment(evidence_store):
    """Engineering turnover dropped -35% (difference < 0). Decreased turnover is positive."""
    # 1. Stating turnover decreased by 35% is numerically and factually correct
    valid_claim = "Engineering turnover decreased by 35.0% [F-002]"
    res_valid = DeterministicClaimValidator.validate_claim(valid_claim, evidence_store)
    assert res_valid.status == ClaimValidationStatus.VERIFIED

    # 2. Stating turnover increased by 35% is a directional contradiction
    invalid_claim = "Engineering turnover increased by 35.0% [F-002]"
    res_invalid = DeterministicClaimValidator.validate_claim(invalid_claim, evidence_store)
    assert res_invalid.status == ClaimValidationStatus.INVALID
    assert any("direction contradiction" in v.lower() for v in res_invalid.violations)


def test_causal_overreach_marked_ambiguous_for_llm(evidence_store):
    """Claim making an unsubstantiated causal assertion must be marked AMBIGUOUS."""
    claim = "Engineering turnover decreased to 12.0% because management intervened on burnout [F-002]"
    res = DeterministicClaimValidator.validate_claim(claim, evidence_store)
    assert res.status == ClaimValidationStatus.AMBIGUOUS
    assert res.requires_llm is True
    assert res.details.get("ambiguity_type") == "causal_claim"


def test_subjective_statement_marked_ambiguous(evidence_store):
    """Claim containing subjective qualitative assessment routed to LLM."""
    claim = "Workforce morale is deteriorating and the team appears fragile"
    res = DeterministicClaimValidator.validate_claim(claim, evidence_store)
    assert res.status == ClaimValidationStatus.AMBIGUOUS
    assert res.requires_llm is True


def test_exact_verified_fast_pass(evidence_store):
    """Accurate claim with exact numbers and citation passes with 0 LLM calls."""
    claim = "Sales recorded completion rate of 76.25%, trailing the 86.70% baseline by 10.45 points [F-001]"
    res = DeterministicClaimValidator.validate_claim(claim, evidence_store)
    assert res.status == ClaimValidationStatus.VERIFIED
    assert res.requires_llm is False
    assert res.confidence == 1.0


def test_validate_section(evidence_store):
    """Validates an entire WrittenSection with mixed claims."""
    section = WrittenSection(
        section_id="SEC-01",
        title="Sales Review",
        key_takeaway="Performance trailed",
        bullet_points=[
            "Sales recorded completion rate of 76.25% [F-001]",
            "Turnover jumped 90% without reason",
            "Burnout caused the completion drop in Sales [F-001]"
        ],
        finding_ids=["F-001"]
    )
    results = DeterministicClaimValidator.validate_section(section, evidence_store)
    assert len(results) == 3
    assert results[0].status == ClaimValidationStatus.VERIFIED
    assert results[1].status == ClaimValidationStatus.INVALID  # uncited 90%
    assert results[2].status == ClaimValidationStatus.AMBIGUOUS  # causal "caused"
