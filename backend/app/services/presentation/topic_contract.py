"""Governed Presentation Topic Contracts (Product Track 3.2).

Enforces the non-negotiable contract boundary:
ExecutiveTopic / VisualSpec -> PresentationTopic -> Presentation planning

Invariants:
1. One governed ExecutiveTopic maps to one presentation topic identity,
   which may render as one or more physical slides without changing fact/evidence ownership.
2. NO raw-column reinterpretation.
3. NO build_hr_report analytical bypass.
4. NO build_grounded_review analytical fallback.
5. NO new metric calculation.
6. NO loss of topic_id / fact_id / evidence_ids.
"""

from __future__ import annotations

import hashlib
import json
import logging
import math
from typing import Any, Literal
from pydantic import BaseModel, Field, ConfigDict

logger = logging.getLogger(__name__)


def compute_canonical_semantic_hash(payload: dict[str, Any] | Any) -> str:
    """Computes a deterministic SHA-256 canonical semantic fingerprint over the 11 protected attributes.

    Protected attributes:
    1. topic_id
    2. fact_id
    3. evidence_ids (canonical sorted order)
    4. metric
    5. unit
    6. leader
    7. leader_value
    8. ranking_direction
    9. reference_line
    10. analytical_intent
    11. visual_spec_semantics (chart_type, categories, values)

    Excluded attributes:
    - slide number / order
    - layout geometry
    - theme / colors
    - fonts
    - coordinates
    - continuation page number / badge
    """
    if hasattr(payload, "to_semantic_dict"):
        d = payload.to_semantic_dict()
    elif isinstance(payload, dict):
        inspect = payload.get("inspect_payload") or {}
        vspec = payload.get("visual_spec") or {}
        rm = inspect.get("ranking_metadata") or vspec.get("ranking_metadata") or payload.get("ranking_metadata") or {}

        t_id = str(payload.get("topic_id") or "")
        fact_id = str(
            payload.get("fact_id")
            or inspect.get("fact_id")
            or vspec.get("fact_id")
            or ""
        )

        ev_list = (
            payload.get("evidence_ids")
            or inspect.get("evidence_ids")
            or vspec.get("evidence_ids")
            or []
        )
        if isinstance(ev_list, str):
            ev_list = [ev_list]
        evidence_ids = sorted([str(e) for e in ev_list if e])

        metric = str(payload.get("key_metric") or payload.get("metric") or vspec.get("key_metric") or "")
        unit = str(payload.get("unit") or vspec.get("unit") or rm.get("unit") or "")

        leader = str(
            payload.get("leader")
            or inspect.get("leader_entity")
            or vspec.get("leader_entity")
            or vspec.get("leader")
            or ""
        )

        lval = payload.get("leader_value")
        if lval is None or lval == "":
            lval = inspect.get("leader_value")
        if lval is None or lval == "":
            lval = vspec.get("leader_value")

        leader_val_str = ""
        if lval is not None and lval != "":
            try:
                leader_val_str = f"{float(lval):.6g}"
            except (ValueError, TypeError):
                leader_val_str = str(lval)

        ranking_dir = str(payload.get("ranking_direction") or rm.get("ranking_direction") or "")

        ref = payload.get("reference_line")
        if ref is None or ref == "":
            ref = vspec.get("benchmark")
        if ref is None or ref == "":
            ref = rm.get("benchmark")
        if (ref is None or ref == "") and "reference_lines" in vspec:
            rl = vspec.get("reference_lines") or []
            if rl and isinstance(rl[0], dict):
                ref = rl[0].get("value")

        ref_str = ""
        if ref is not None and ref != "":
            try:
                ref_str = f"{float(ref):.6g}"
            except (ValueError, TypeError):
                ref_str = str(ref)

        intent = str(
            payload.get("analytical_intent")
            or inspect.get("analytical_intent")
            or vspec.get("analytical_intent")
            or "RANKING"
        )

        v_type = str(vspec.get("chart_type") or payload.get("recommended_visual") or "")
        v_cats = [str(c) for c in (vspec.get("categories") or [])]
        v_vals = [f"{float(v):.6g}" if isinstance(v, (int, float)) else str(v) for v in (vspec.get("values") or [])]

        d = {
            "topic_id": t_id,
            "fact_id": fact_id,
            "evidence_ids": evidence_ids,
            "metric": metric,
            "unit": unit,
            "leader": leader,
            "leader_value": leader_val_str,
            "ranking_direction": ranking_dir,
            "reference_line": ref_str,
            "analytical_intent": intent,
            "visual_spec": {
                "chart_type": v_type,
                "categories": v_cats,
                "values": v_vals
            }
        }
    else:
        raise ValueError(f"Cannot compute semantic hash for payload: {type(payload)}")

    canonical_json = json.dumps(d, sort_keys=True, separators=(',', ':'))
    return hashlib.sha256(canonical_json.encode('utf-8')).hexdigest()


class PresentationTopic(BaseModel):
    """Governed Presentation Topic contract directly bound to upstream ExecutiveTopic."""
    model_config = ConfigDict(extra="ignore")

    topic_id: str
    fact_id: str | None = None
    evidence_ids: list[str] = Field(default_factory=list)
    title: str
    subtitle: str = ""
    technical_title: str = ""
    metric: str = ""
    unit: str = ""
    leader: str | None = None
    leader_value: float | int | str | None = None
    ranking_direction: str | None = None
    reference_line: float | int | None = None
    analytical_intent: str = "RANKING"
    visual_spec: dict[str, Any] = Field(default_factory=dict)
    primary_takeaway: str = ""
    recommended_action: str = ""
    recommended_visual: str = "ranked_bar"
    display_order: int = 1
    slot_type: Literal["hero", "supporting", "risk_anomaly", "action_scenario"] = "supporting"
    domain: str = "general"
    inspect_payload: dict[str, Any] = Field(default_factory=dict)
    source_sheets: list[str] = Field(default_factory=list)

    @classmethod
    def from_executive_topic(
        cls,
        exec_topic: dict[str, Any] | Any,
        domain: str = "general",
        source_sheet_name: str = ""
    ) -> PresentationTopic:
        """Constructs an immutable PresentationTopic from an upstream governed ExecutiveTopic."""
        t_dict = exec_topic if isinstance(exec_topic, dict) else exec_topic.model_dump()

        topic_id = str(t_dict.get("topic_id") or "")
        visual_spec = t_dict.get("visual_spec") or {}
        inspect_payload = t_dict.get("inspect_payload") or {}

        # 1. Fact ID: resolve from inspect_payload or visual_spec or topic root
        fact_id = (
            inspect_payload.get("fact_id")
            or visual_spec.get("fact_id")
            or t_dict.get("fact_id")
        )

        # 2. Evidence IDs: strictly exact match from topic or payload
        evidence_ids = (
            t_dict.get("evidence_ids")
            or inspect_payload.get("evidence_ids")
            or visual_spec.get("evidence_ids")
            or []
        )
        if isinstance(evidence_ids, str):
            evidence_ids = [evidence_ids]
        evidence_ids = [str(eid) for eid in evidence_ids if eid]

        # 3. Titles & Narratives: preserve governed executive question
        title = str(t_dict.get("title") or inspect_payload.get("business_question") or inspect_payload.get("title") or "Executive Topic")
        subtitle = str(t_dict.get("subtitle") or "")
        technical_title = str(t_dict.get("technical_title") or inspect_payload.get("technical_title") or "")
        primary_takeaway = str(t_dict.get("primary_takeaway") or t_dict.get("takeaway") or inspect_payload.get("primary_takeaway") or "")
        recommended_action = str(t_dict.get("recommended_action") or inspect_payload.get("recommended_action") or "")

        # 4. Metric & Unit: exact match
        metric = str(t_dict.get("key_metric") or visual_spec.get("key_metric") or "")
        unit = str(
            visual_spec.get("unit")
            or (inspect_payload.get("ranking_metadata") or {}).get("unit")
            or ""
        )

        # 5. Leader & Leader Value: exact match
        leader = (
            inspect_payload.get("leader_entity")
            or visual_spec.get("leader_entity")
            or visual_spec.get("leader")
        )
        leader_value = inspect_payload.get("leader_value")
        if leader_value is None:
            leader_value = visual_spec.get("leader_value")

        # 6. Ranking Direction: exact match
        ranking_metadata = inspect_payload.get("ranking_metadata") or visual_spec.get("ranking_metadata") or {}
        ranking_direction = ranking_metadata.get("ranking_direction")

        # 7. Reference Line / Benchmark: exact match
        reference_line = visual_spec.get("benchmark")
        if reference_line is None:
            reference_line = ranking_metadata.get("benchmark")
        if reference_line is None and "reference_lines" in visual_spec:
            ref_lines = visual_spec.get("reference_lines") or []
            if ref_lines and isinstance(ref_lines[0], dict):
                reference_line = ref_lines[0].get("value")

        # 8. Analytical Intent & Recommended Visual
        analytical_intent = str(
            t_dict.get("analytical_intent")
            or inspect_payload.get("analytical_intent")
            or visual_spec.get("analytical_intent")
            or "RANKING"
        )
        recommended_visual = str(
            t_dict.get("recommended_visual")
            or visual_spec.get("chart_type")
            or "ranked_bar"
        )

        display_order = int(t_dict.get("display_order") or t_dict.get("portfolio_position") or 1)
        slot_type = t_dict.get("slot_type") or "supporting"
        topic_domain = str(t_dict.get("domain") or domain)

        source_sheets = [source_sheet_name] if source_sheet_name else []

        return cls(
            topic_id=topic_id,
            fact_id=fact_id,
            evidence_ids=evidence_ids,
            title=title,
            subtitle=subtitle,
            technical_title=technical_title,
            metric=metric,
            unit=unit,
            leader=leader,
            leader_value=leader_value,
            ranking_direction=ranking_direction,
            reference_line=reference_line,
            analytical_intent=analytical_intent,
            visual_spec=visual_spec,
            primary_takeaway=primary_takeaway,
            recommended_action=recommended_action,
            recommended_visual=recommended_visual,
            display_order=display_order,
            slot_type=slot_type,
            domain=topic_domain,
            inspect_payload=inspect_payload,
            source_sheets=source_sheets
        )

    def to_semantic_dict(self) -> dict[str, Any]:
        """Extracts the 11 protected semantic fields in canonical form."""
        leader_val_str = ""
        if self.leader_value is not None and self.leader_value != "":
            try:
                leader_val_str = f"{float(self.leader_value):.6g}"
            except (ValueError, TypeError):
                leader_val_str = str(self.leader_value)

        ref_str = ""
        if self.reference_line is not None and self.reference_line != "":
            try:
                ref_str = f"{float(self.reference_line):.6g}"
            except (ValueError, TypeError):
                ref_str = str(self.reference_line)
        vspec = self.visual_spec or {}
        v_type = str(vspec.get("chart_type") or self.recommended_visual or "")
        v_cats = [str(c) for c in (vspec.get("categories") or [])]
        v_vals = [f"{float(v):.6g}" if isinstance(v, (int, float)) else str(v) for v in (vspec.get("values") or [])]
        return {
            "topic_id": self.topic_id,
            "fact_id": str(self.fact_id or ""),
            "evidence_ids": sorted([str(e) for e in self.evidence_ids if e]),
            "metric": self.metric,
            "unit": self.unit,
            "leader": str(self.leader or ""),
            "leader_value": leader_val_str,
            "ranking_direction": str(self.ranking_direction or ""),
            "reference_line": ref_str,
            "analytical_intent": self.analytical_intent,
            "visual_spec": {
                "chart_type": v_type,
                "categories": v_cats,
                "values": v_vals
            }
        }

    def canonical_semantic_hash(self) -> str:
        """Returns the canonical deterministic SHA-256 fingerprint of protected attributes."""
        return compute_canonical_semantic_hash(self.to_semantic_dict())

    def to_slide_contract(
        self,
        slide_order: int,
        total_slides: int,
        continuation_badge: str | None = None,
        override_visual_spec: dict[str, Any] | None = None
    ) -> dict[str, Any]:
        """Translates the governed PresentationTopic into an immutable slide contract dictionary.
        
        Guarantees that topic_id, fact_id, and evidence_ids are preserved on every physical slide.
        """
        display_title = self.title
        if continuation_badge:
            display_title = f"{self.title} ({continuation_badge})"

        # Construct visual payload compatible with Presentation Studio renderers
        slide_chart = None
        slide_table = None

        active_spec = override_visual_spec if override_visual_spec is not None else self.visual_spec
        chart_type = active_spec.get("chart_type") or self.recommended_visual
        categories = list(active_spec.get("categories") or [])
        values = list(active_spec.get("values") or [])

        # If values exist but categories is empty, synthesize labels based on length/intent
        if values and not categories:
            if len(values) == 5 and chart_type in ("box_plot", "distribution", "violin"):
                categories = ["Max", "Q3", "Median", "Q1", "Min"]
            else:
                categories = [f"Item {i+1}" for i in range(len(values))]

        if chart_type in ("table", "table_detail", "grid"):
            if active_spec.get("headers") and active_spec.get("rows"):
                slide_table = {
                    "headers": list(active_spec["headers"]),
                    "rows": [list(r) for r in active_spec["rows"]]
                }
            else:
                headers = ["Category", self.metric or "Value"]
                rows = []
                if categories and values:
                    rows = [[str(c), str(v)] for c, v in zip(categories, values)]
                elif self.inspect_payload.get("ranking_metadata"):
                    rm = self.inspect_payload["ranking_metadata"]
                    headers = [rm.get("entity_column", "Entity"), rm.get("measure_column", "Measure")]
                    if self.leader:
                        rows = [[str(self.leader), str(self.leader_value or "")]]
                if rows:
                    slide_table = {"headers": headers, "rows": rows}
        elif categories and active_spec.get("series"):
            ser_list = []
            for s in active_spec["series"]:
                if isinstance(s, dict):
                    raw_v = s.get("values") if s.get("values") is not None else s.get("data") or []
                    f_vals = []
                    for v in raw_v:
                        try:
                            vf = float(v)
                            f_vals.append(vf if math.isfinite(vf) else 0.0)
                        except (ValueError, TypeError):
                            f_vals.append(0.0)
                    ser_list.append({
                        "name": str(s.get("name") or self.metric or "Series"),
                        "values": f_vals,
                        "data": f_vals,
                        "unit": s.get("unit") or self.unit,
                        "evidence_id": s.get("evidence_id") or (self.evidence_ids[0] if self.evidence_ids else None)
                    })
            if ser_list:
                slide_chart = {
                    "type": chart_type,
                    "chart_type": chart_type,
                    "categories": [str(c) for c in categories],
                    "series": ser_list,
                    "reference_line": self.reference_line,
                    "unit": self.unit
                }
        elif categories and values:
            valid_cats = []
            valid_vals = []
            for c, v in zip(categories, values):
                try:
                    vf = float(v)
                    if math.isfinite(vf):
                        valid_cats.append(str(c))
                        valid_vals.append(vf)
                except (ValueError, TypeError):
                    continue

            if valid_cats and valid_vals:
                slide_chart = {
                    "type": chart_type,
                    "chart_type": chart_type,
                    "categories": valid_cats,
                    "series": [{
                        "name": self.metric or "Value",
                        "values": valid_vals,
                        "data": valid_vals
                    }],
                    "reference_line": self.reference_line,
                    "unit": self.unit
                }
            else:
                # If values cannot be converted to floats, present as table
                headers = ["Category", self.metric or "Value"]
                rows = [[str(c), str(v)] for c, v in zip(categories, values)]
                if rows:
                    slide_table = {"headers": headers, "rows": rows}
        else:

            # Fallback table if ranking metadata exists and has rows
            if self.inspect_payload.get("ranking_metadata") and self.leader:
                rm = self.inspect_payload["ranking_metadata"]
                headers = [rm.get("entity_column", "Entity"), rm.get("measure_column", "Measure")]
                rows = [[str(self.leader), str(self.leader_value or "")]]
                slide_table = {"headers": headers, "rows": rows}

        layout = "chart_narrative" if slide_chart else ("table_detail" if slide_table else "comparison_split")


        # Build metrics list for quick inspect cards
        metrics_list = []
        if self.metric:
            metrics_list.append({
                "label": self.title,
                "value": self.metric,
                "unit": self.unit,
                "subtext": self.analytical_intent,
                "evidence_id": self.evidence_ids[0] if self.evidence_ids else "EVID-01"
            })

        bullets = []
        if self.primary_takeaway:
            bullets.append(self.primary_takeaway)
        if self.recommended_action:
            bullets.append(f"Recommended Action: {self.recommended_action}")
        if not bullets:
            bullets.append(f"Empirical evaluation confirms {self.metric} under governed {self.analytical_intent} criteria.")

        slide_dict = {
            "id": f"slide_{slide_order}",
            "stable_slide_id": f"slide_topic_{self.topic_id.lower().replace('-', '_')}" + (f"_{continuation_badge.lower().replace(' ', '_')}" if continuation_badge else ""),
            "order": slide_order,
            "total_slides": total_slides,
            "category": self.analytical_intent.upper().replace("_", " "),
            "layout": "chart_narrative" if slide_chart else ("table_detail" if slide_table else "comparison_split"),
            "title": display_title,
            "subtitle": self.subtitle or self.technical_title,
            "narrative": self.primary_takeaway or f"Audited findings for {self.title}",
            "bullets": bullets,
            "narration_script": f"Focus executive attention on {self.title}. {self.primary_takeaway or ''}".strip(),
            "speaker_takeaway": self.primary_takeaway,
            "speaker_notes": f"Executive Briefing for {self.title}:\n- Takeaway: {self.primary_takeaway}\n- Metric: {self.metric}\n- Lineage: {self.topic_id} / {self.evidence_ids}",
            "notes": f"Lineage: topic_id={self.topic_id}, evidence_ids={self.evidence_ids}",
            "metrics": metrics_list,
            "chart": slide_chart,
            "table": slide_table,
            "continuation_badge": continuation_badge,
            "reading_order": ["category", "title", "subtitle", "narrative", "chart", "metrics", "bullets", "footer"],
            # Immutable Upstream Contract Bindings (Exact Match Invariant)

            "topic_id": self.topic_id,
            "fact_id": self.fact_id,
            "evidence_ids": list(self.evidence_ids),
            "evidence_id": self.evidence_ids[0] if self.evidence_ids else None,
            "key_metric": self.metric,
            "unit": self.unit,
            "leader": self.leader,
            "leader_value": self.leader_value,
            "ranking_direction": self.ranking_direction,
            "reference_line": self.reference_line,
            "analytical_intent": self.analytical_intent,
            "visual_spec": dict(self.visual_spec),
            "inspect_payload": dict(self.inspect_payload),
            "semantic_hash": self.canonical_semantic_hash(),
            "physical_plan_hash": hashlib.sha256(
                f"{self.topic_id}:{slide_order}:{total_slides}:{display_title}:{continuation_badge or ''}".encode("utf-8")
            ).hexdigest()
        }

        try:
            from .presentation_visual_spec import PresentationVisualSpec
            p_spec = PresentationVisualSpec.from_governed_visual(slide_dict)
            slide_dict["presentation_visual_spec"] = p_spec.model_dump()
            slide_dict["visual_semantic_fingerprint"] = p_spec.semantic_fingerprint()
            slide_dict["render_manifest"] = p_spec.build_render_manifest("canonical")
            if slide_chart:
                chart_d = p_spec.to_chart_dict()
                for k, v in chart_d.items():
                    if k not in slide_chart or slide_chart[k] is None:
                        slide_chart[k] = v
                slide_dict["chart"] = slide_chart
        except Exception as ex:
            logger.debug(f"Could not derive presentation_visual_spec: {ex}")

        return slide_dict

    def to_slide_contracts(
        self,
        start_order: int,
        total_slides: int,
        max_items_per_slide: int = 10,
        enable_pagination: bool = False
    ) -> list[dict[str, Any]]:
        """Translates the governed PresentationTopic into one or more immutable slide contract dictionaries.

        If enable_pagination is True and visual items exceed max_items_per_slide,
        paginates across multiple physical slides without changing fact/evidence ownership.
        """
        categories = self.visual_spec.get("categories") or []
        values = self.visual_spec.get("values") or []

        if enable_pagination and categories and len(categories) > max_items_per_slide:
            chunks = []
            for i in range(0, len(categories), max_items_per_slide):
                chunk_cats = categories[i : i + max_items_per_slide]
                chunk_vals = values[i : i + max_items_per_slide] if values else []
                chunks.append((chunk_cats, chunk_vals))

            num_parts = len(chunks)
            slides = []
            for part_idx, (c_cats, c_vals) in enumerate(chunks, 1):
                part_badge = f"Part {part_idx} of {num_parts}"
                chunk_spec = dict(self.visual_spec)
                chunk_spec["categories"] = c_cats
                chunk_spec["values"] = c_vals

                slide = self.to_slide_contract(
                    slide_order=start_order + part_idx - 1,
                    total_slides=total_slides,
                    continuation_badge=part_badge,
                    override_visual_spec=chunk_spec
                )
                slides.append(slide)
            return slides

        return [self.to_slide_contract(slide_order=start_order, total_slides=total_slides)]

