"""Tests for the Critic Agent, Claim Validation, and Automated Repair Loop."""

import pytest
from unittest.mock import patch, MagicMock

from app.services.evidence.evidence_models import Finding, FindingType, Importance, EvidenceReference
from app.services.evidence.evidence_store import EvidenceStore
from app.services.reporting.writer_agent import WrittenSection
from app.services.critic.critic_agent import CriticAgent, ClaimVerdict, SectionAuditResult, ClaimAuditItem


@pytest.fixture
def evidence_store():
    store = EvidenceStore()
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
    return store


def test_critic_flags_unsupported_claims(evidence_store):
    """Verifies that an unsupported quantitative claim triggers a failure in audit."""
    failing_section = WrittenSection(
        section_id="SEC-01",
        title="Sales Review",
        key_takeaway="Performance dropped severely",
        bullet_points=[
            "Sales completion rate fell by 45.2% over previous year [F-001]",  # 45.2% is hallucinated
            "Revenue crashed to $1.2M without explanation"                    # $1.2M is unsupported
        ],
        finding_ids=["F-001"]
    )

    mock_audit = SectionAuditResult(
        section_id="SEC-01",
        passed=False,
        claims=[
            ClaimAuditItem(
                sentence="Sales completion rate fell by 45.2% over previous year [F-001]",
                verdict=ClaimVerdict.UNSUPPORTED,
                reason="The dataset does not contain historical previous-year figures; 45.2% is hallucinated.",
                unsupported_numbers=["45.2%"]
            ),
            ClaimAuditItem(
                sentence="Revenue crashed to $1.2M without explanation",
                verdict=ClaimVerdict.UNSUPPORTED,
                reason="No revenue metric exists in evidence F-001.",
                unsupported_numbers=["$1.2M"]
            )
        ],
        repair_feedback="Remove the 45.2% and $1.2M claims. State that Sales completion rate was 76.25% vs 86.70% baseline."
    )

    with patch.object(CriticAgent, "audit_section", return_value=mock_audit):
        audit = CriticAgent.audit_section(failing_section, evidence_store)
        assert audit.passed is False
        assert len(audit.claims) == 2
        assert audit.claims[0].verdict == ClaimVerdict.UNSUPPORTED
        assert "45.2%" in audit.claims[0].unsupported_numbers


def test_critic_audit_and_repair_loop(evidence_store):
    """Verifies that when a section fails Critic audit, it triggers a repair and passes."""
    failing_section = WrittenSection(
        section_id="SEC-01",
        title="Sales Review",
        key_takeaway="Performance fell",
        bullet_points=["Sales plummeted by 38.0% [F-001]"],
        finding_ids=["F-001"]
    )

    audit_fail = SectionAuditResult(
        section_id="SEC-01",
        passed=False,
        claims=[
            ClaimAuditItem(
                sentence="Sales plummeted by 38.0% [F-001]",
                verdict=ClaimVerdict.UNSUPPORTED,
                reason="38.0% is not in the evidence. Actual gap is -10.45 points.",
                unsupported_numbers=["38.0%"]
            )
        ],
        repair_feedback="Correct percentage gap to -10.45 points."
    )

    audit_pass = SectionAuditResult(
        section_id="SEC-01",
        passed=True,
        claims=[
            ClaimAuditItem(
                sentence="Sales recorded completion rate of 76.25%, 10.45 points below baseline [F-001]",
                verdict=ClaimVerdict.SUPPORTED,
                reason="Accurately reflects F-001 ground truth numbers."
            )
        ]
    )

    # First audit_section returns audit_fail, second returns audit_pass
    with patch.object(CriticAgent, "audit_section", side_effect=[audit_fail, audit_pass]):
        # Mock writer repair response
        from app.services.gateway.model_gateway import GatewayResult, ModelRole
        mock_repaired_section = WrittenSection(
            section_id="SEC-01",
            title="Sales Review",
            key_takeaway="Performance trailed baseline",
            bullet_points=["Sales recorded completion rate of 76.25%, 10.45 points below baseline [F-001]"],
            finding_ids=["F-001"]
        )

        with patch("app.services.gateway.model_gateway.ModelGateway.generate") as mock_gen:
            mock_gen.return_value = GatewayResult(
                raw_text="",
                parsed=mock_repaired_section,
                role=ModelRole.WRITER,
                success=True
            )

            final_section, final_audit = CriticAgent.audit_and_repair(
                failing_section,
                evidence_store,
                max_repair_attempts=2
            )

            assert final_audit.passed is True
            assert "76.25%" in final_section.bullet_points[0]
            assert "38.0%" not in final_section.bullet_points[0]
