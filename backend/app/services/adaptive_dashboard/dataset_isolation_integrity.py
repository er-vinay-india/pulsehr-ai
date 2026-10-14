"""Dataset Isolation Integrity & Cross-Domain Provenance Guard.

Enforces strict mathematical and provenance isolation across datasets:
1. Hard invariant: artifact.dataset_id == active_dataset_id.
2. Two-sheet relationships: left_sheet.dataset_id == right_sheet.dataset_id == active_dataset_id.
3. Cross-Domain Semantic Guard: Prevents environmental pollutants (SO2, NO2, PM10) from leaking
   into workforce datasets, and workforce concepts from leaking into environmental datasets.
"""
from __future__ import annotations

import logging
import re
from typing import Any

logger = logging.getLogger(__name__)


class DatasetIsolationViolation(Exception):
    """Raised when an analytical artifact violates dataset provenance or boundary isolation."""
    pass


class DatasetIsolationIntegrity:
    """Guards dataset boundaries and prevents cross-dataset contamination and leakage."""

    ENVIRONMENTAL_POLLUTANT_TOKENS = {
        "so2", "no2", "pm10", "pm2.5", "pm25", "aqi", "cpcb", "pollutant",
        "jharia", "brynihat", "amravati", "katihar", "saharsa"
    }

    WORKFORCE_TOKENS = {
        "attendance", "leaves", "employee", "wfo", "absenteeism", "headcount",
        "clock_in", "clock_out", "present_days", "leave_days"
    }

    RETAIL_TOKENS = {
        "store", "fuel_price", "fuel price", "weekly_sales", "weekly sales",
        "cpi", "unemployment", "markdown", "holiday_flag", "holiday flag",
        "foot traffic", "footfall"
    }

    @classmethod
    def validate_sheet_relationship(
        cls,
        rel_id: Any,
        left_sheet_id: int,
        right_sheet_id: int,
        sheet_dataset_map: dict[int, int],
        active_dataset_id: int,
    ) -> tuple[bool, str | None]:
        """Validates that a sheet relationship is strictly intra-dataset for active_dataset_id."""
        left_ds = sheet_dataset_map.get(left_sheet_id)
        right_ds = sheet_dataset_map.get(right_sheet_id)

        if left_ds != active_dataset_id or right_ds != active_dataset_id:
            reason = (
                f"DATASET_ISOLATION_VIOLATION: Relationship {rel_id} spans foreign datasets "
                f"(left_sheet={left_sheet_id} ds={left_ds}, right_sheet={right_sheet_id} ds={right_ds}, active={active_dataset_id})"
            )
            logger.error(reason)
            return False, reason

        if left_ds != right_ds:
            reason = (
                f"DATASET_ISOLATION_VIOLATION: Cross-dataset relationship {rel_id} between "
                f"dataset {left_ds} and {right_ds} is forbidden."
            )
            logger.error(reason)
            return False, reason

        return True, None

    @classmethod
    def validate_relationships(
        cls,
        relationships: list[dict[str, Any]],
        active_dataset_id: int,
        sheet_dataset_map: dict[int, int] | None = None,
    ) -> list[dict[str, Any]]:
        """Filters relationships to retain only those strictly intra-dataset for active_dataset_id."""
        valid = []
        for rel in relationships:
            left_ds = rel.get("left_dataset_id")
            right_ds = rel.get("right_dataset_id")
            if sheet_dataset_map:
                if left_ds is None:
                    left_ds = sheet_dataset_map.get(rel.get("left_sheet_id") or rel.get("left_sheet"))
                if right_ds is None:
                    right_ds = sheet_dataset_map.get(rel.get("right_sheet_id") or rel.get("right_sheet"))

            if left_ds == active_dataset_id and right_ds == active_dataset_id:
                valid.append(rel)
        return valid

    @classmethod
    def validate_evidence_node(
        cls,
        node: Any,
        active_dataset_id: int,
        active_domain: str,
        sheet_dataset_map: dict[int, int] | None = None,
    ) -> tuple[bool, str | None]:
        """Validates that an EvidenceItem belongs to active_dataset_id and active_domain."""
        tokens = getattr(node, "tokens", {}) or {}
        provenance = getattr(node, "provenance", "") or ""

        # 1. Dataset ID Scoping Check
        node_ds = tokens.get("dataset_id")
        if node_ds is not None and node_ds != active_dataset_id:
            reason = (
                f"DATASET_ISOLATION_VIOLATION: Evidence node '{node.evidence_id}' has dataset_id={node_ds}, "
                f"expected active_dataset_id={active_dataset_id}."
            )
            logger.warning(reason)
            return False, reason

        # 2. Source Sheet ID Check
        source_sids = tokens.get("source_sheet_ids", [])
        if sheet_dataset_map and source_sids:
            for sid in source_sids:
                s_ds = sheet_dataset_map.get(sid)
                if s_ds is not None and s_ds != active_dataset_id:
                    reason = (
                        f"DATASET_ISOLATION_VIOLATION: Evidence node '{node.evidence_id}' references "
                        f"foreign sheet {sid} (dataset {s_ds} != {active_dataset_id})."
                    )
                    logger.warning(reason)
                    return False, reason

        # 3. Cross-Domain Semantic Purity Check
        domain_norm = (active_domain or "").lower()
        node_text = " ".join([
            str(getattr(node, "subject", "") or ""),
            str(getattr(node, "metric", "") or ""),
            str(getattr(node, "calculation", "") or ""),
            str(tokens.get("x_measure", "") or ""),
            str(tokens.get("y_measure", "") or ""),
            " ".join(str(c) for c in tokens.get("source_columns", [])),
        ]).lower()

        if domain_norm in ("workforce", "workforce_hr", "hr"):
            for bad_tok in cls.ENVIRONMENTAL_POLLUTANT_TOKENS:
                if re.search(r'\b' + re.escape(bad_tok) + r'\b', node_text):
                    reason = f"FOREIGN_DATASET_EVIDENCE: Pollutant token '{bad_tok}' detected in workforce evidence '{node.evidence_id}'."
                    logger.warning(reason)
                    return False, reason
            for bad_tok in cls.RETAIL_TOKENS:
                if re.search(r'\b' + re.escape(bad_tok) + r'\b', node_text):
                    reason = f"FOREIGN_DATASET_EVIDENCE: Retail token '{bad_tok}' detected in workforce evidence '{node.evidence_id}'."
                    logger.warning(reason)
                    return False, reason

        elif "environmental" in domain_norm or "air" in domain_norm:
            for bad_tok in cls.WORKFORCE_TOKENS:
                if re.search(r'\b' + re.escape(bad_tok) + r'\b', node_text):
                    reason = f"FOREIGN_DATASET_EVIDENCE: Workforce token '{bad_tok}' detected in environmental evidence '{node.evidence_id}'."
                    logger.warning(reason)
                    return False, reason
            for bad_tok in cls.RETAIL_TOKENS:
                if re.search(r'\b' + re.escape(bad_tok) + r'\b', node_text):
                    reason = f"FOREIGN_DATASET_EVIDENCE: Retail token '{bad_tok}' detected in environmental evidence '{node.evidence_id}'."
                    logger.warning(reason)
                    return False, reason

        elif "retail" in domain_norm or "commercial" in domain_norm or "sales" in domain_norm:
            for bad_tok in cls.WORKFORCE_TOKENS:
                if re.search(r'\b' + re.escape(bad_tok) + r'\b', node_text):
                    reason = f"FOREIGN_DATASET_EVIDENCE: Workforce token '{bad_tok}' detected in retail evidence '{node.evidence_id}'."
                    logger.warning(reason)
                    return False, reason
            for bad_tok in cls.ENVIRONMENTAL_POLLUTANT_TOKENS:
                if re.search(r'\b' + re.escape(bad_tok) + r'\b', node_text):
                    reason = f"FOREIGN_DATASET_EVIDENCE: Pollutant token '{bad_tok}' detected in retail evidence '{node.evidence_id}'."
                    logger.warning(reason)
                    return False, reason

        return True, None

    @classmethod
    def filter_evidence_graph(
        cls,
        nodes: list[Any],
        active_dataset_id: int,
        active_domain: str,
        sheet_dataset_map: dict[int, int] | None = None,
    ) -> list[Any]:
        """Filters a collection of evidence nodes to retain strictly isolated, unpolluted nodes."""
        valid_nodes = []
        for n in nodes:
            ok, reason = cls.validate_evidence_node(
                node=n,
                active_dataset_id=active_dataset_id,
                active_domain=active_domain,
                sheet_dataset_map=sheet_dataset_map,
            )
            if ok:
                valid_nodes.append(n)
            else:
                logger.info("DatasetIsolationIntegrity: Suppressed contaminated node '%s': %s", getattr(n, "evidence_id", "?"), reason)
        return valid_nodes

    @classmethod
    def validate_story_purity(
        cls,
        story: Any,
        active_domain: str,
    ) -> tuple[bool, str | None]:
        """Ensures an AnalyticalStory does not emit foreign cross-domain tokens."""
        domain_norm = (active_domain or "").lower()
        if isinstance(story, dict):
            title = str(story.get("title", "") or "")
            question = str(story.get("business_question", "") or "")
            takeaway = str(story.get("takeaway", "") or "")
            narrative = str(story.get("narrative", "") or "")
            s_tokens = story.get("tokens", {}) or {}
            x_m = str(s_tokens.get("x_measure", "") or "")
            y_m = str(s_tokens.get("y_measure", "") or "")
            text_corpus = f"{title} {question} {takeaway} {narrative} {x_m} {y_m}".lower()
            story_title = title or "dict_story"
        else:
            title = (getattr(story, "title", "") or "").lower()
            question = (getattr(story, "business_question", "") or "").lower()
            takeaway = (getattr(story, "takeaway", "") or "").lower()
            s_tokens = getattr(story, "tokens", {}) or {}
            x_m = str(s_tokens.get("x_measure", "") or "").lower()
            y_m = str(s_tokens.get("y_measure", "") or "").lower()
            text_corpus = f"{title} {question} {takeaway} {x_m} {y_m}"
            story_title = getattr(story, "title", "story")

        if domain_norm in ("workforce", "workforce_hr", "hr"):
            for bad_tok in cls.ENVIRONMENTAL_POLLUTANT_TOKENS:
                if re.search(r'\b' + re.escape(bad_tok) + r'\b', text_corpus):
                    return False, f"FOREIGN_DATASET_EVIDENCE: Story '{story_title}' contains pollutant signature '{bad_tok}'."
            for bad_tok in cls.RETAIL_TOKENS:
                if re.search(r'\b' + re.escape(bad_tok) + r'\b', text_corpus):
                    return False, f"FOREIGN_DATASET_EVIDENCE: Story '{story_title}' contains retail signature '{bad_tok}'."

        elif "environmental" in domain_norm or "air" in domain_norm:
            for bad_tok in cls.WORKFORCE_TOKENS:
                if re.search(r'\b' + re.escape(bad_tok) + r'\b', text_corpus):
                    return False, f"FOREIGN_DATASET_EVIDENCE: Story '{story_title}' contains workforce signature '{bad_tok}'."
            for bad_tok in cls.RETAIL_TOKENS:
                if re.search(r'\b' + re.escape(bad_tok) + r'\b', text_corpus):
                    return False, f"FOREIGN_DATASET_EVIDENCE: Story '{story_title}' contains retail signature '{bad_tok}'."

        elif "retail" in domain_norm or "commercial" in domain_norm or "sales" in domain_norm:
            for bad_tok in cls.WORKFORCE_TOKENS:
                if re.search(r'\b' + re.escape(bad_tok) + r'\b', text_corpus):
                    return False, f"FOREIGN_DATASET_EVIDENCE: Story '{story_title}' contains workforce signature '{bad_tok}'."
            for bad_tok in cls.ENVIRONMENTAL_POLLUTANT_TOKENS:
                if re.search(r'\b' + re.escape(bad_tok) + r'\b', text_corpus):
                    return False, f"FOREIGN_DATASET_EVIDENCE: Story '{story_title}' contains pollutant signature '{bad_tok}'."

        return True, None


class TopicVisualBindingIntegrity:
    """Guards immutable topic identity and validates topic-to-visual binding integrity."""

    @classmethod
    def evaluate(cls, topic: Any) -> tuple[bool, str | None]:
        """Validates dataset_id, domain, topic_id alignment and vocabulary purity between topic and visual_spec."""
        v_spec = getattr(topic, "visual_spec", {}) or {}
        topic_id = getattr(topic, "topic_id", "")
        topic_ds = getattr(topic, "dataset_id", None)
        topic_dom = getattr(topic, "domain", "general")

        v_spec_topic_id = v_spec.get("topic_id")
        v_spec_ds = v_spec.get("dataset_id")
        v_spec_dom = v_spec.get("domain")

        # 1. Dataset ID scoping alignment
        if topic_ds is not None and v_spec_ds is not None and topic_ds != v_spec_ds:
            reason = f"TOPIC_VISUAL_BINDING_VIOLATION [DATASET_MISMATCH]: Topic dataset {topic_ds} != VisualSpec dataset {v_spec_ds}"
            logger.error(reason)
            return False, reason

        # 2. Domain alignment
        if topic_dom and v_spec_dom and topic_dom.lower() != v_spec_dom.lower():
            reason = f"TOPIC_VISUAL_BINDING_VIOLATION [DOMAIN_MISMATCH]: Topic domain {topic_dom} != VisualSpec domain {v_spec_dom}"
            logger.error(reason)
            return False, reason

        # 3. Topic ID alignment
        if topic_id and v_spec_topic_id and topic_id != v_spec_topic_id:
            reason = f"TOPIC_VISUAL_BINDING_VIOLATION [TOPIC_ID_MISMATCH]: Topic ID {topic_id} != VisualSpec topic_id {v_spec_topic_id}"
            logger.error(reason)
            return False, reason

        # 4. Domain vocabulary purity
        domain_norm = (topic_dom or v_spec_dom or "").lower()
        micro = getattr(topic, "visual_microcopy", None)
        texts = " ".join([
            str(getattr(topic, "title", "") or ""),
            str(getattr(topic, "subtitle", "") or ""),
            str(getattr(micro, "short_title", "") or "") if micro else "",
            str(getattr(topic, "primary_takeaway", "") or ""),
            str(getattr(topic, "takeaway", "") or ""),
        ]).lower()

        if "retail" in domain_norm or "commercial" in domain_norm or "sales" in domain_norm:
            for bad_tok in DatasetIsolationIntegrity.WORKFORCE_TOKENS:
                if re.search(r'\b' + re.escape(bad_tok) + r'\b', texts):
                    return False, f"FOREIGN_VOCABULARY_VIOLATION: Workforce token '{bad_tok}' in retail topic '{topic_id}'."
            for bad_tok in DatasetIsolationIntegrity.ENVIRONMENTAL_POLLUTANT_TOKENS:
                if re.search(r'\b' + re.escape(bad_tok) + r'\b', texts):
                    return False, f"FOREIGN_VOCABULARY_VIOLATION: Pollutant token '{bad_tok}' in retail topic '{topic_id}'."

        elif domain_norm in ("workforce", "workforce_hr", "hr"):
            for bad_tok in DatasetIsolationIntegrity.ENVIRONMENTAL_POLLUTANT_TOKENS:
                if re.search(r'\b' + re.escape(bad_tok) + r'\b', texts):
                    return False, f"FOREIGN_VOCABULARY_VIOLATION: Pollutant token '{bad_tok}' in workforce topic '{topic_id}'."
            for bad_tok in DatasetIsolationIntegrity.RETAIL_TOKENS:
                if re.search(r'\b' + re.escape(bad_tok) + r'\b', texts):
                    return False, f"FOREIGN_VOCABULARY_VIOLATION: Retail token '{bad_tok}' in workforce topic '{topic_id}'."

        elif "environmental" in domain_norm or "air" in domain_norm:
            for bad_tok in DatasetIsolationIntegrity.WORKFORCE_TOKENS:
                if re.search(r'\b' + re.escape(bad_tok) + r'\b', texts):
                    return False, f"FOREIGN_VOCABULARY_VIOLATION: Workforce token '{bad_tok}' in environmental topic '{topic_id}'."
            for bad_tok in DatasetIsolationIntegrity.RETAIL_TOKENS:
                if re.search(r'\b' + re.escape(bad_tok) + r'\b', texts):
                    return False, f"FOREIGN_VOCABULARY_VIOLATION: Retail token '{bad_tok}' in environmental topic '{topic_id}'."

        # 5. Leader Fact & Visual Parity for Ranking Stories (DEF-T2-04)
        intent = getattr(topic, "analytical_intent", "")
        chart_type = v_spec.get("chart_type") or getattr(topic, "recommended_visual", "")
        is_ranking = (intent == "RANKING" or v_spec.get("is_ranking_story") or chart_type in ("ranked_bar", "podium_top_3"))

        if is_ranking:
            # 5a. Visual rank #1 extraction
            v_cats = v_spec.get("categories") or []
            v_vals = v_spec.get("values") or []
            v_leader_ent = str(v_spec.get("leader_entity") or (v_cats[0] if v_cats else "")).strip()
            v_leader_val = v_spec.get("leader_value") if v_spec.get("leader_value") is not None else (v_vals[0] if v_vals else None)

            # 5b. Narrative leader extraction
            takeaway = str(getattr(topic, "primary_takeaway", "") or getattr(topic, "takeaway", "") or (getattr(topic, "narrative", {}) or {}).get("takeaway", "") or "")
            micro = getattr(topic, "visual_microcopy", None)
            short_finding = str(getattr(micro, "short_finding", "") or "") if micro else ""
            narrative_corpus = f"{takeaway} {short_finding}"

            # 5c. Check for contradiction: If a trailing category is claimed as leader or peak
            trailing_cats = [str(c).strip() for c in v_cats[1:] if str(c).strip()]
            for trailing in trailing_cats:
                trailing_lead_patterns = [
                    rf"\b{re.escape(trailing)}\b\s+(leads|records?\s+peak|is\s+the\s+leader|ranks?\s+#?1|takes?\s+first)",
                    rf"peak\s+.*?\b{re.escape(trailing)}\b",
                    rf"top:\s*{re.escape(trailing)}\b",
                ]
                for pat in trailing_lead_patterns:
                    if re.search(pat, narrative_corpus, flags=re.IGNORECASE):
                        reason = f"RANKING_LEADER_MISMATCH: Visual rank #1 '{v_leader_ent}' contradicts narrative claiming '{trailing}' as leader ({pat})."
                        logger.error(reason)
                        return False, reason

            # 5d. Check Fact ID parity if present
            v_fact_id = v_spec.get("fact_id") or v_spec.get("leader_fact_id")
            n_fact_id = getattr(topic, "fact_id", None) or (getattr(topic, "narrative", {}) or {}).get("fact_id") or (getattr(topic, "inspect_payload", {}) or {}).get("fact_id")
            if v_fact_id and n_fact_id and str(v_fact_id).strip() != str(n_fact_id).strip():
                reason = f"RANKING_FACT_ID_MISMATCH: Visual fact_id '{v_fact_id}' != Narrative fact_id '{n_fact_id}'."
                logger.error(reason)
                return False, reason

        return True, None


class AxisNarrativeIntegrity:
    """Enforces narrative and title consistency with visual axes for relationship / scatter cards."""

    @classmethod
    def evaluate(cls, topic: Any) -> tuple[bool, str | None]:
        """Validates that relationship / scatter titles match the underlying x and y axes."""
        v_spec = getattr(topic, "visual_spec", {}) or {}
        chart_type = v_spec.get("chart_type") or getattr(topic, "recommended_visual", "")
        intent = getattr(topic, "analytical_intent", "")

        if chart_type != "scatter" and intent != "RELATIONSHIP":
            return True, None

        x_label = str(v_spec.get("x_label", "") or "").strip()
        y_label = str(v_spec.get("y_label", "") or "").strip()
        if not x_label or not y_label:
            return True, None

        micro = getattr(topic, "visual_microcopy", None)
        short_title = str(getattr(micro, "short_title", "") or "").strip()
        title = str(getattr(topic, "title", "") or "").strip()
        text_corpus = f"{title} {short_title}".lower()

        # Check for cross-domain contamination between axes and narrative
        domain_norm = (getattr(topic, "domain", "") or v_spec.get("domain", "")).lower()
        axes_corpus = f"{x_label} {y_label}".lower()

        # If axes are retail/commercial, title must NEVER contain workforce or environmental terms
        is_retail_axes = any(k in axes_corpus for k in ["temperature", "fuel", "traffic", "revenue", "sales", "cpi", "store"])
        if is_retail_axes or "retail" in domain_norm:
            for bad_tok in DatasetIsolationIntegrity.WORKFORCE_TOKENS | DatasetIsolationIntegrity.ENVIRONMENTAL_POLLUTANT_TOKENS:
                if re.search(r'\b' + re.escape(bad_tok) + r'\b', text_corpus):
                    # Auto-repair title to clean axis narrative
                    x_clean = re.sub(r"[_\s]+", " ", x_label).strip().title()
                    y_clean = re.sub(r"[_\s]+", " ", y_label).strip().title()
                    repaired_title = f"{x_clean} vs {y_clean}"
                    if hasattr(topic, "title"):
                        topic.title = repaired_title
                    if micro and hasattr(micro, "short_title"):
                        micro.short_title = repaired_title
                    logger.warning("AxisNarrativeIntegrity: Repaired title from '%s' to '%s'", title, repaired_title)
                    return True, f"REPAIRED_AXIS_NARRATIVE: Repaired title to '{repaired_title}'"

        return True, None


class ExecutiveTopicBindingIntegrity:
    """Enforces cross-layer topic identity across Story, VisualSpec, EvidenceBinding, and CompositionItem."""

    @classmethod
    def evaluate_topic(
        cls,
        topic: Any,
        fail_closed: bool = True,
    ) -> tuple[bool, str | None]:
        """Validates that all facets of an assembled ExecutiveTopic share the identical topic_id.

        Verifies:
        - topic.topic_id == visual_spec.topic_id
        - topic.topic_id == story.topic_id (if present)
        - topic.topic_id == evidence_binding.topic_id (if present)
        - topic.topic_id == composition_item.topic_id (if present)
        """
        topic_id = getattr(topic, "topic_id", "") or (topic.get("topic_id") if isinstance(topic, dict) else "")
        if not topic_id:
            msg = "EXECUTIVE_TOPIC_INTEGRITY_VIOLATION: ExecutiveTopic is missing mandatory 'topic_id'."
            if fail_closed:
                raise DatasetIsolationViolation(msg)
            return False, msg

        mismatches: list[str] = []

        # 1. VisualSpec check
        v_spec = getattr(topic, "visual_spec", None) or (topic.get("visual_spec") if isinstance(topic, dict) else None)
        if v_spec:
            v_topic_id = getattr(v_spec, "topic_id", None) or (v_spec.get("topic_id") if isinstance(v_spec, dict) else None)
            if v_topic_id and v_topic_id != topic_id:
                mismatches.append(f"VisualSpec.topic_id ('{v_topic_id}') != topic_id ('{topic_id}')")

        # 2. Story check
        story = getattr(topic, "story", None) or (topic.get("story") if isinstance(topic, dict) else None)
        if story:
            s_topic_id = getattr(story, "topic_id", None) or (story.get("topic_id") if isinstance(story, dict) else None)
            if s_topic_id and s_topic_id != topic_id:
                mismatches.append(f"Story.topic_id ('{s_topic_id}') != topic_id ('{topic_id}')")

        # 3. EvidenceBinding check
        ev_binding = getattr(topic, "evidence_binding", None) or (topic.get("evidence_binding") if isinstance(topic, dict) else None)
        if ev_binding:
            eb_topic_id = getattr(ev_binding, "topic_id", None) or (ev_binding.get("topic_id") if isinstance(ev_binding, dict) else None)
            if eb_topic_id and eb_topic_id != topic_id:
                mismatches.append(f"EvidenceBinding.topic_id ('{eb_topic_id}') != topic_id ('{topic_id}')")

        # 4. CompositionItem check
        comp_item = getattr(topic, "composition_item", None) or (topic.get("composition_item") if isinstance(topic, dict) else None)
        if comp_item:
            ci_topic_id = getattr(comp_item, "topic_id", None) or (comp_item.get("topic_id") if isinstance(comp_item, dict) else None)
            if ci_topic_id and ci_topic_id != topic_id:
                mismatches.append(f"CompositionItem.topic_id ('{ci_topic_id}') != topic_id ('{topic_id}')")

        if mismatches:
            msg = f"EXECUTIVE_TOPIC_INTEGRITY_VIOLATION: Cross-layer topic mismatch: {'; '.join(mismatches)}"
            logger.error(msg)
            if fail_closed:
                raise DatasetIsolationViolation(msg)
            return False, msg

        return True, None

