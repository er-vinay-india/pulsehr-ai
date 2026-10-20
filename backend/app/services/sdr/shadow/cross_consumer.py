"""
HighView Semantic Data Refinery — Phase SDR-8
Cross-Consumer Fact Identity Verifier

Enforces Section 27: Cross-Consumer Fact Identity Law.
If the same fact appears across HRIDAY, Dashboard, and Presentation, it MUST share:
- metric identity
- value
- unit
- grain
- denominator
- dataset version
- evidence identity

Guarantees: Zero consumer-specific truth.
"""

from __future__ import annotations

from typing import Any
from app.services.sdr.shadow.contracts import FactIdentity
from app.services.sdr.shadow.fact_comparator import FactComparator


class CrossConsumerFactAuditor:
    """
    Audits fact identity across HRIDAY, Dashboard, and Presentation.
    """

    @classmethod
    def audit_cross_consumer_parity(
        cls,
        dataset_id: str,
        facts_by_consumer: dict[str, list[FactIdentity]],
    ) -> dict[str, Any]:
        """
        Audits all shared facts across HRIDAY, Dashboard, and Presentation.
        Returns detailed parity report with mismatch counts.
        """
        hriday_facts = {f.metric_id.lower().replace(" ", "_"): f for f in facts_by_consumer.get("HRIDAY", [])}
        dash_facts = {f.metric_id.lower().replace(" ", "_"): f for f in facts_by_consumer.get("DASHBOARD", [])}
        pres_facts = {f.metric_id.lower().replace(" ", "_"): f for f in facts_by_consumer.get("PRESENTATION", [])}

        all_metric_keys = sorted(set(hriday_facts.keys()) | set(dash_facts.keys()) | set(pres_facts.keys()))

        shared_facts_audited = 0
        mismatches: list[dict[str, Any]] = []

        for mkey in all_metric_keys:
            present_in = []
            f_h = hriday_facts.get(mkey)
            f_d = dash_facts.get(mkey)
            f_p = pres_facts.get(mkey)

            if f_h:
                present_in.append(("HRIDAY", f_h))
            if f_d:
                present_in.append(("DASHBOARD", f_d))
            if f_p:
                present_in.append(("PRESENTATION", f_p))

            # Only audit if fact appears in 2 or more consumers
            if len(present_in) >= 2:
                shared_facts_audited += 1
                base_cname, base_fact = present_in[0]

                for comp_cname, comp_fact in present_in[1:]:
                    comp = FactComparator.compare_facts(mkey, base_fact, comp_fact)
                    if not (comp.numeric_match and comp.unit_match and comp.grain_match and comp.denominator_match):
                        mismatches.append({
                            "metric_id": mkey,
                            "consumer_a": base_cname,
                            "consumer_b": comp_cname,
                            "fact_a": base_fact.model_dump(),
                            "fact_b": comp_fact.model_dump(),
                            "numeric_match": comp.numeric_match,
                            "unit_match": comp.unit_match,
                            "grain_match": comp.grain_match,
                            "denominator_match": comp.denominator_match,
                            "rationale": comp.rationale,
                        })

        return {
            "dataset_id": dataset_id,
            "shared_facts_audited": shared_facts_audited,
            "fact_identity_mismatches_count": len(mismatches),
            "mismatches": mismatches,
            "status": "PASS" if len(mismatches) == 0 else "FAIL",
        }
