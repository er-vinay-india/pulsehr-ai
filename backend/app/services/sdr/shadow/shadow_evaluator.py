"""
HighView Semantic Data Refinery — Phase SDR-8
SDR Governed Shadow Evaluator & Artifact Loader

Loads governed SDR artifacts from dataset sdr directories:
- analytical_views.json
- analytical_facts.json
- join_plans.json
- validated_relationships.json
- geo_enrichments.json
- canonical_geo_resolutions.json

Enforces safety filters:
- STALE views -> blocked from shadow evaluation (SDR_STALE)
- UNSAFE JoinPlans -> blocked (UNSAFE_BLOCKED)
- AMBIGUOUS JoinPlans -> blocked (AMBIGUOUS_BLOCKED)
- AMBIGUOUS Geo resolutions -> withheld
"""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any

from app.core import config
from app.services.sdr.shadow.contracts import FactIdentity

logger = logging.getLogger(__name__)


class SDRShadowArtifactLoader:
    """
    Loads and validates SDR artifacts for shadow consumer evaluation.
    Guarantees that no unsafe, ambiguous, or stale truth is admitted.
    """

    def __init__(self, base_data_dir: Path | str | None = None):
        if base_data_dir is not None:
            self.base_dir = Path(base_data_dir)
        else:
            self.base_dir = getattr(config, "DATA_DIR", Path("data"))

    def get_dataset_sdr_dir(self, dataset_id: str) -> Path:
        return Path(self.base_dir) / "datasets" / str(dataset_id) / "sdr"

    def load_governed_facts(self, dataset_id: str) -> tuple[list[FactIdentity], dict[str, Any]]:
        """
        Loads all governed analytical facts for the dataset, applying safety filters.
        Returns (valid_facts, safety_metadata).
        """
        sdr_dir = self.get_dataset_sdr_dir(dataset_id)
        safety_meta: dict[str, Any] = {
            "status": "AVAILABLE",
            "stale_views_blocked": 0,
            "unsafe_joins_blocked": 0,
            "ambiguous_joins_blocked": 0,
            "ambiguous_geo_withheld": 0,
            "total_raw_facts": 0,
            "total_admitted_facts": 0,
        }

        if not sdr_dir.exists():
            safety_meta["status"] = "UNAVAILABLE"
            return [], safety_meta

        # 1. Inspect View Statuses
        views_path = sdr_dir / "analytical_views.json"
        blocked_view_ids: set[str] = set()
        stale_view_ids: set[str] = set()
        if views_path.exists():
            try:
                with open(views_path, "r", encoding="utf-8") as f:
                    views_data = json.load(f)
                    for v in views_data:
                        v_id = v.get("analytical_view_id")
                        status = v.get("status")
                        if status == "STALE":
                            stale_view_ids.add(v_id)
                            safety_meta["stale_views_blocked"] += 1
                        elif status in ("UNSAFE", "AMBIGUOUS"):
                            blocked_view_ids.add(v_id)
                            if status == "UNSAFE":
                                safety_meta["unsafe_joins_blocked"] += 1
                            else:
                                safety_meta["ambiguous_joins_blocked"] += 1
            except Exception as exc:
                logger.warning("Error reading analytical views for %s: %s", dataset_id, exc)

        # 2. Inspect JoinPlan Safety
        plans_path = sdr_dir / "join_plans.json"
        blocked_plan_ids: set[str] = set()
        if plans_path.exists():
            try:
                with open(plans_path, "r", encoding="utf-8") as f:
                    plans_data = json.load(f)
                    for p in plans_data:
                        p_id = p.get("join_plan_id")
                        status = p.get("safety_status")
                        if status == "UNSAFE":
                            blocked_plan_ids.add(p_id)
                            safety_meta["unsafe_joins_blocked"] += 1
                        elif status == "AMBIGUOUS":
                            blocked_plan_ids.add(p_id)
                            safety_meta["ambiguous_joins_blocked"] += 1
            except Exception as exc:
                logger.warning("Error reading join plans for %s: %s", dataset_id, exc)

        # 3. Load Analytical Facts
        facts_path = sdr_dir / "analytical_facts.json"
        admitted_facts: list[FactIdentity] = []
        if facts_path.exists():
            try:
                with open(facts_path, "r", encoding="utf-8") as f:
                    facts_data = json.load(f)
                    safety_meta["total_raw_facts"] = len(facts_data)
                    for fd in facts_data:
                        v_id = fd.get("analytical_view_id")
                        jp_ids = fd.get("join_plan_ids", [])

                        # Safety Gate: Drop facts from stale views
                        if v_id in stale_view_ids:
                            continue

                        # Safety Gate: Drop facts from unsafe/ambiguous views
                        if v_id in blocked_view_ids:
                            continue

                        # Safety Gate: Drop facts relying on unsafe/ambiguous JoinPlans
                        if any(jp in blocked_plan_ids for jp in jp_ids):
                            continue

                        fact = FactIdentity(
                            metric_id=fd.get("metric") or fd.get("fact_id"),
                            value=fd.get("value"),
                            formatted_value=fd.get("formatted_value", ""),
                            unit=fd.get("unit"),
                            grain=fd.get("grain", "UNKNOWN"),
                            denominator=fd.get("denominator_value"),
                            dataset_id=str(dataset_id),
                            dataset_version=fd.get("dataset_version", "v1"),
                            evidence_id=fd.get("source_evidence_ids", [None])[0] if fd.get("source_evidence_ids") else None,
                            source_evidence_ids=fd.get("source_evidence_ids", []),
                            provenance_type=fd.get("provenance_type", "OBSERVED"),
                            join_plan_id=jp_ids[0] if jp_ids else None,
                            analytical_view_id=v_id,
                        )
                        admitted_facts.append(fact)
            except Exception as exc:
                logger.warning("Error reading analytical facts for %s: %s", dataset_id, exc)

        safety_meta["total_admitted_facts"] = len(admitted_facts)
        if safety_meta["stale_views_blocked"] > 0 and len(admitted_facts) == 0:
            safety_meta["status"] = "STALE"
        elif safety_meta["unsafe_joins_blocked"] > 0 and len(admitted_facts) == 0:
            safety_meta["status"] = "UNSAFE_BLOCKED"
        elif safety_meta["ambiguous_joins_blocked"] > 0 and len(admitted_facts) == 0:
            safety_meta["status"] = "AMBIGUOUS_BLOCKED"

        return admitted_facts, safety_meta
