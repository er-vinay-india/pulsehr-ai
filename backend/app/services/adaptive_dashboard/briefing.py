"""Evidence-bound executive briefing generator for the Adaptive Dashboard (Element 7 / Gate 7).

Synthesizes a short, natural, audible executive briefing (target 55-100 words, max 130 words / 1,200 chars)
strictly bound to verified calculations from Elements 1-6.
Zero fabricated causes, forecasts, targets, confidence scores, or unverified performance language.
"""
from __future__ import annotations

import re
from typing import Any, Literal
from .contracts import (
    BreakdownSpec,
    BriefingClaim,
    ChartSpec,
    ComparatorSpec,
    ComponentSpec,
    DecisionFocusSpec,
    DisparitySpec,
    EvidenceResult,
    ExecutiveBriefingSpec,
    ExplainSpec,
    GlanceSpec,
    InspectSpec,
    SemanticContract,
    SourceManifest,
)

PROHIBITED_WORDS = (
    "performing badly",
    "leave caused",
    "caused by",
    "will recover",
    "the business is healthy",
    "is healthy",
    "sales will increase",
    "will improve",
    "critical risk",
    "ai discovered",
    "machine learning discovered",
    "underperforming",
    "worst",
    "best",
    "poor",
)


def _count_words(text: str) -> int:
    return len(text.split())


def _format_pp_for_speech(text: str) -> str:
    """Expands shorthand 'pp' into audible 'percentage points' for spoken clarity."""
    return re.sub(r"\bpp\b", "percentage points", text)


def _detect_reporting_period(manifest: SourceManifest, secondary: ChartSpec | None) -> str | None:
    """Extracts a concise reporting period label from filename, display name, or secondary chart."""
    combined = (manifest.file_name or "") + " " + (manifest.display_name or "")
    m = re.search(r"\b(January|February|March|April|May|June|July|August|September|October|November|December)[_\s]+(20\d\d)\b", combined, re.IGNORECASE)
    if m:
        return f"{m.group(1).capitalize()} {m.group(2)}"
    if secondary and secondary.inspect.reporting_period:
        rp = secondary.inspect.reporting_period.strip()
        m2 = re.search(r"\b(January|February|March|April|May|June|July|August|September|October|November|December)[_\s]+(20\d\d)\b", rp, re.IGNORECASE)
        if m2:
            return f"{m2.group(1).capitalize()} {m2.group(2)}"
        m_month = re.search(r"\b(January|February|March|April|May|June|July|August|September|October|November|December)\b", rp, re.IGNORECASE)
        if m_month:
            return f"{m_month.group(1).capitalize()} 2026"
        if rp and len(rp) < 40:
            return rp
    return None


def _is_flat_time_series(chart: ChartSpec) -> bool:
    """Checks whether a timeline is nearly flat (relative variance < 2% or flat range)."""
    points = getattr(chart.chart_series, "points", []) if hasattr(chart, "chart_series") else []
    if not points or len(points) < 2:
        return True
    valid_vals = [p.average_hours for p in points if p.average_hours is not None]
    if len(valid_vals) < 2:
        return True
    avg = sum(valid_vals) / len(valid_vals)
    if avg == 0:
        return True
    val_range = max(valid_vals) - min(valid_vals)
    relative_spread = val_range / abs(avg)
    return relative_spread < 0.03


def validate_briefing_claims(
    claims: list[BriefingClaim],
    spoken_text: str,
    manifest_snapshot: str,
    available_component_ids: set[str],
) -> None:
    """Strict pre-publication validator. Raises ValueError on any contract or evidence violation."""
    # 1. Word and character bounds
    word_count = _count_words(spoken_text)
    if word_count > 130:
        raise ValueError(f"Briefing word count exceeds maximum: {word_count} words > 130 words limit.")
    if len(spoken_text) > 1200:
        raise ValueError(f"Briefing character count exceeds maximum: {len(spoken_text)} chars > 1200 limit.")

    # 2. Prohibited wording check
    lower_spoken = spoken_text.lower()
    for phrase in PROHIBITED_WORDS:
        if phrase in lower_spoken:
            raise ValueError(f"Prohibited non-causal or subjective phrase detected in briefing: '{phrase}'")

    # 3. PII check (emails, phone numbers)
    if "@" in spoken_text:
        raise ValueError("Potential PII (email address) detected in briefing text.")
    if re.search(r"\b\d{3}[-.]?\d{3}[-.]?\d{4}\b", spoken_text):
        raise ValueError("Potential PII (phone number) detected in briefing text.")

    # 4. Claim binding integrity
    for claim in claims:
        if claim.source_component_id not in available_component_ids:
            raise ValueError(f"Claim references missing source component: '{claim.source_component_id}'")
        if not claim.calculation_ids:
            raise ValueError(f"Claim '{claim.claim_id}' must reference at least one calculation ID.")

        # Extract numeric tokens from claim text, ignoring calendar dates, years (2020-2035), rankings (#1), ordinals (1st, 2nd, etc.)
        text_without_dates = re.sub(
            r"\b\d{1,2}(?:st|nd|rd|th)?\s+(?:Jan(?:uary)?|Feb(?:ruary)?|Mar(?:ch)?|Apr(?:il)?|May|Jun(?:e)?|Jul(?:y)?|Aug(?:ust)?|Sep(?:tember)?|Oct(?:ober)?|Nov(?:ember)?|Dec(?:ember)?)(?:\s+\d{4})?\b",
            " ",
            claim.text,
            flags=re.IGNORECASE,
        )
        text_without_dates = re.sub(
            r"\b(?:Jan(?:uary)?|Feb(?:ruary)?|Mar(?:ch)?|Apr(?:il)?|May|Jun(?:e)?|Jul(?:y)?|Aug(?:ust)?|Sep(?:tember)?|Oct(?:ober)?|Nov(?:ember)?|Dec(?:ember)?)\s+\d{1,2}(?:st|nd|rd|th)?(?:\s+\d{4})?\b",
            " ",
            text_without_dates,
            flags=re.IGNORECASE,
        )
        text_without_dates = re.sub(r"\b\d{4}-\d{2}(?:-\d{2})?\b", " ", text_without_dates)
        tokens = re.findall(r"(?<![\w#])[-+]?\$?\d{1,3}(?:,\d{3})*(?:\.\d+)?%?(?![\w])", text_without_dates)
        for token in tokens:
            clean_tok = token.replace(",", "").replace("$", "").rstrip("%").lstrip("+")
            try:
                val = float(clean_tok)
            except ValueError:
                continue
            # Ignore standard 4-digit years
            if 2000 <= val <= 2035 and "." not in clean_tok:
                continue
            # Verify value exists in claim.numeric_values within display rounding tolerance (0.15)
            matched = any(abs(val - num) < 0.15 or abs(abs(val) - abs(num)) < 0.15 for num in claim.numeric_values)
            if not matched:
                raise ValueError(
                    f"Unbound numeric value '{token}' in claim '{claim.claim_id}' not found in claim.numeric_values ({claim.numeric_values})."
                )


def build_executive_briefing_element(
    manifest: SourceManifest,
    contract: SemanticContract,
    primary: ComponentSpec,
    secondary: ChartSpec | None = None,
    tertiary: BreakdownSpec | None = None,
    quaternary: ComparatorSpec | None = None,
    quinary: DisparitySpec | None = None,
    decision: DecisionFocusSpec | None = None,
) -> ExecutiveBriefingSpec | None:
    """Builds a deterministic, evidence-grounded Executive Briefing specification."""
    # Verify snapshot integrity across all input components
    snapshot = manifest.snapshot
    available_components: dict[str, Any] = {}
    for comp in (primary, secondary, tertiary, quaternary, quinary, decision):
        if comp is not None:
            if comp.inspect.snapshot != snapshot:
                raise ValueError(
                    f"Snapshot mismatch: component '{comp.component_id}' has snapshot '{comp.inspect.snapshot}', expected '{snapshot}'"
                )
            available_components[comp.component_id] = comp

    claims: list[BriefingClaim] = []
    domain = contract.domain

    # Determine reporting period or scope descriptor
    reporting_period = _detect_reporting_period(manifest, secondary)
    period_phrase = f" across {reporting_period}" if reporting_period else ""

    # ==========================================
    # Part 1: Scope & State (Element 1 Headline)
    # ==========================================
    primary_calc_id = primary.inspect.calculation_id
    primary_val = primary.glance.value
    primary_formatted = primary.glance.formatted_value
    primary_unit = primary.glance.unit or "records"

    if domain == "workforce_hr":
        scope_text = f"The attendance data represents {primary_formatted} employees{period_phrase}."
        claims.append(
            BriefingClaim(
                claim_id="claim_scope_workforce",
                claim_type="scope",
                text=scope_text,
                source_component_id=primary.component_id,
                calculation_ids=[primary_calc_id],
                numeric_values=[primary_val],
                unit="employees",
            )
        )
    elif domain in ("commercial_retail", "retail_sales"):
        scope_text = f"The selected source covers {primary_formatted} {primary_unit}{period_phrase}."
        claims.append(
            BriefingClaim(
                claim_id="claim_scope_retail",
                claim_type="scope",
                text=scope_text,
                source_component_id=primary.component_id,
                calculation_ids=[primary_calc_id],
                numeric_values=[primary_val],
                unit=primary_unit,
            )
        )
    else:
        # General tabular / unknown domain
        scope_text = f"The uploaded source data contains {primary_formatted} {primary_unit}{period_phrase}."
        claims.append(
            BriefingClaim(
                claim_id="claim_scope_general",
                claim_type="scope",
                text=scope_text,
                source_component_id=primary.component_id,
                calculation_ids=[primary_calc_id],
                numeric_values=[primary_val],
                unit=primary_unit,
            )
        )

    # ==========================================
    # Part 2: Pattern (One explanatory fact from Elements 2-5)
    # ==========================================
    # Auditable selection priority:
    # 1. Decision focus supporting component (if distinct)
    # 2. Quaternary comparator
    # 3. Quinary disparity matrix
    # 4. Secondary timeline (if not flat)
    # 5. Tertiary breakdown concentration

    pattern_claim: BriefingClaim | None = None

    # Option 1: Supporting component from Element 6 (Quinary or Quaternary)
    if decision and decision.supporting_component_id == "quinary_element" and quinary:
        # Disparity anchor: top segment vs benchmark
        if quinary.top_segment and quinary.benchmark_value is not None:
            top_item = next((it for it in quinary.items if it.segment == quinary.top_segment), None)
            if top_item and top_item.segment != decision.subject_label:
                benchmark_context = "company attendance" if domain == "workforce_hr" else "the overall benchmark"
                pattern_text = (
                    f"{top_item.segment} recorded the highest {quinary.metric_name.lower()} at "
                    f"{top_item.formatted_primary}, while {benchmark_context} averaged {quinary.formatted_benchmark}."
                )
                pattern_claim = BriefingClaim(
                    claim_id="claim_pattern_disparity_top",
                    claim_type="comparison",
                    text=pattern_text,
                    source_component_id=quinary.component_id,
                    calculation_ids=[quinary.inspect.calculation_id],
                    numeric_values=[top_item.primary_value, quinary.benchmark_value],
                    unit=quinary.unit,
                )

    if pattern_claim is None and decision and decision.supporting_component_id == "quaternary_element" and quaternary:
        if quaternary.items and len(quaternary.items) >= 2:
            base_item = next((it for it in quaternary.items if it.is_baseline), quaternary.items[0])
            comp_item = next((it for it in quaternary.items if not it.is_baseline), quaternary.items[-1])
            pattern_text = (
                f"{comp_item.cohort} averaged {comp_item.formatted_value}, compared to "
                f"{base_item.formatted_value} for {base_item.cohort.lower()}."
            )
            pattern_claim = BriefingClaim(
                claim_id="claim_pattern_comparator",
                claim_type="comparison",
                text=pattern_text,
                source_component_id=quaternary.component_id,
                calculation_ids=[quaternary.inspect.calculation_id],
                numeric_values=[comp_item.value, base_item.value],
                unit=quaternary.unit,
            )

    # Option 2: Quaternary comparator independently
    if pattern_claim is None and quaternary and quaternary.items and len(quaternary.items) >= 2:
        base_item = next((it for it in quaternary.items if it.is_baseline), quaternary.items[0])
        comp_item = next((it for it in quaternary.items if not it.is_baseline), quaternary.items[-1])
        pattern_text = (
            f"{comp_item.cohort} averaged {comp_item.formatted_value}, compared to "
            f"{base_item.formatted_value} for {base_item.cohort.lower()}."
        )
        pattern_claim = BriefingClaim(
            claim_id="claim_pattern_comparator_direct",
            claim_type="comparison",
            text=pattern_text,
            source_component_id=quaternary.component_id,
            calculation_ids=[quaternary.inspect.calculation_id],
            numeric_values=[comp_item.value, base_item.value],
            unit=quaternary.unit,
        )

    # Option 3: Quinary disparity independently
    if pattern_claim is None and quinary and quinary.items and quinary.top_segment:
        top_item = next((it for it in quinary.items if it.segment == quinary.top_segment), None)
        if top_item and (not decision or top_item.segment != decision.subject_label):
            pattern_text = (
                f"{top_item.segment} recorded {top_item.formatted_primary} {quinary.metric_name.lower()}, "
                f"differing from the benchmark of {quinary.formatted_benchmark}."
            )
            pattern_claim = BriefingClaim(
                claim_id="claim_pattern_disparity_direct",
                claim_type="comparison",
                text=pattern_text,
                source_component_id=quinary.component_id,
                calculation_ids=[quinary.inspect.calculation_id],
                numeric_values=[top_item.primary_value, quinary.benchmark_value],
                unit=quinary.unit,
            )

    # Option 4: Secondary timeline (only if not nearly flat!)
    if pattern_claim is None and secondary and not _is_flat_time_series(secondary):
        pts = secondary.chart_series.points if hasattr(secondary, "chart_series") else []
        valid_pts = [p for p in pts if p.average_hours is not None]
        if len(valid_pts) >= 2:
            first_pt, last_pt = valid_pts[0], valid_pts[-1]
            diff = last_pt.average_hours - first_pt.average_hours
            direction = "increased" if diff > 0 else "decreased"
            pattern_text = (
                f"{secondary.glance.label} moved from {first_pt.formatted_hours} in {first_pt.period_label} "
                f"to {last_pt.formatted_hours} in {last_pt.period_label}."
            )
            pattern_claim = BriefingClaim(
                claim_id="claim_pattern_movement",
                claim_type="observation",
                text=pattern_text,
                source_component_id=secondary.component_id,
                calculation_ids=[secondary.inspect.calculation_id],
                numeric_values=[first_pt.average_hours, last_pt.average_hours],
                unit=secondary.glance.unit or "",
            )

    # Option 5: Tertiary breakdown concentration
    if pattern_claim is None and tertiary and tertiary.items:
        top_cat = tertiary.items[0]
        pattern_text = (
            f"{top_cat.category} accounts for {top_cat.formatted_value} of {tertiary.metric_name.lower()}, "
            f"representing {top_cat.share_pct:.1f}% of the total."
        )
        pattern_claim = BriefingClaim(
            claim_id="claim_pattern_concentration",
            claim_type="observation",
            text=pattern_text,
            source_component_id=tertiary.component_id,
            calculation_ids=[tertiary.inspect.calculation_id],
            numeric_values=[top_cat.value, round(top_cat.share_pct, 1)],
            unit=tertiary.unit or "",
        )

    if pattern_claim:
        claims.append(pattern_claim)

    # ==========================================
    # Part 3: Action / Decision Focus (Element 6)
    # ==========================================
    if decision:
        clean_gap = _format_pp_for_speech(decision.formatted_gap_value)
        sample_str = decision.sample_label if decision.sample_label.strip().startswith(str(decision.sample_size)) else f"{decision.sample_size} {decision.sample_label}"
        # Avoid double 'the' or formatting quirks
        action_text = (
            f"{decision.subject_label} records {decision.formatted_observed_value} {decision.metric_name.lower()}, "
            f"{clean_gap} across {sample_str}."
        )
        subj_nums = [float(n) for n in re.findall(r"\d+", decision.subject_label)]
        numeric_vals = [
            decision.observed_value,
            decision.comparator_value,
            decision.gap_value,
            abs(decision.gap_value),
            decision.sample_size,
        ] + subj_nums
        claims.append(
            BriefingClaim(
                claim_id="claim_action_decision_focus",
                claim_type="decision_focus",
                text=action_text,
                source_component_id=decision.component_id,
                calculation_ids=decision.supporting_calculation_ids or [decision.inspect.calculation_id],
                numeric_values=numeric_vals,
                unit=decision.unit or "",
            )
        )

        # Part 4: Next Check
        clean_next_step = decision.next_step.strip()
        if not clean_next_step.endswith("."):
            clean_next_step += "."
        # Ensure smooth phrasing: "The next check is to ..."
        first_word = clean_next_step.split()[0].lower()
        rest_words = " ".join(clean_next_step.split()[1:])
        if first_word in ("review", "compare", "evaluate", "inspect", "investigate", "audit"):
            next_check_text = f"The next check is to {first_word} {rest_words}"
        else:
            next_check_text = f"The next check is {clean_next_step}"

        claims.append(
            BriefingClaim(
                claim_id="claim_action_next_check",
                claim_type="next_check",
                text=next_check_text,
                source_component_id=decision.component_id,
                calculation_ids=decision.supporting_calculation_ids or [decision.inspect.calculation_id],
                numeric_values=[],
                unit="",
            )
        )

    # Optional Qualifier: Partial period warning if secondary timeline has partial points
    if secondary:
        pts = secondary.chart_series.points if hasattr(secondary, "chart_series") else []
        has_partial = any(p.is_partial for p in pts)
        if has_partial:
            claims.append(
                BriefingClaim(
                    claim_id="claim_qualifier_partial_period",
                    claim_type="limitation",
                    text="Note that the final observation period contains partial records.",
                    source_component_id=secondary.component_id,
                    calculation_ids=[secondary.inspect.calculation_id],
                    numeric_values=[],
                    unit="",
                    is_material_qualifier=True,
                )
            )

    if not claims:
        return None

    # Compose continuous spoken and transcript text
    spoken_text = " ".join(c.text for c in claims)
    transcript_text = spoken_text

    # Run strict pre-publication validation
    source_component_ids = list(dict.fromkeys(c.source_component_id for c in claims))
    calculation_ids = list(dict.fromkeys(cid for c in claims for cid in c.calculation_ids))

    validate_briefing_claims(
        claims=claims,
        spoken_text=spoken_text,
        manifest_snapshot=snapshot,
        available_component_ids=set(available_components.keys()),
    )

    estimated_word_count = _count_words(spoken_text)
    # Speaking rate: 150 words per minute -> 2.5 words per second
    estimated_duration_seconds = max(1, round(estimated_word_count * 60 / 150))

    context_line = (
        f"{manifest.display_name} · {reporting_period}"
        if reporting_period
        else f"{manifest.display_name} · {primary.glance.formatted_value} {primary_unit}"
    )

    glance = GlanceSpec(
        label="Executive briefing",
        value=estimated_duration_seconds,
        formatted_value=f"{estimated_duration_seconds}s",
        unit="seconds",
        unit_display="implicit_in_label",
        context_qualifier=f"{estimated_word_count} words",
        has_info_control=True,
    )

    explain = ExplainSpec(
        short_definition="Evidence-grounded executive briefing summarizing current state, standout pattern, and decision focus.",
        exact_value_text=f"{estimated_word_count} words · ~{estimated_duration_seconds}s audible briefing bound to current-snapshot calculations.",
    )

    inspect = InspectSpec(
        metric_title="Executive Briefing Audit",
        exact_value=f"{estimated_word_count} words (~{estimated_duration_seconds}s)",
        what_this_counts="Evidence-bound claims composed from Elements 1–6",
        applicable_population=primary.inspect.applicable_population,
        source_name=manifest.display_name,
        reporting_period=context_line,
        calculation_method="Deterministic 4-part claim synthesis bound to verified calculation IDs",
        data_completeness=primary.inspect.data_completeness,
        workforce_coverage=primary.inspect.workforce_coverage,
        coverage_label=primary.inspect.coverage_label,
        coverage_value=primary.inspect.coverage_value,
        selection_reason="Provides rapid executive consumption through readable and audible narration without reading every chart.",
        limitations=[
            "Narration is strictly bounded to verified snapshot calculations; no forward-looking forecasts or causal mechanisms are inferred.",
            "Voice synthesis uses local speech generation without cloud transmission.",
        ],
        calculation_id=f"calc_briefing_{snapshot[:8]}",
        definition_id="def_executive_briefing",
        snapshot=snapshot,
        provenance=f"Synthesized from {len(claims)} verified claims across {', '.join(source_component_ids)}",
    )

    return ExecutiveBriefingSpec(
        component_id="briefing_element",
        kind="executive_briefing",
        business_concept="briefing.executive_summary",
        title="Executive briefing",
        context_line=context_line,
        spoken_text=spoken_text,
        transcript_text=transcript_text,
        claims=claims,
        source_component_ids=source_component_ids,
        calculation_ids=calculation_ids,
        estimated_word_count=estimated_word_count,
        estimated_duration_seconds=estimated_duration_seconds,
        snapshot=snapshot,
        glance=glance,
        explain=explain,
        inspect=inspect,
        caption=None,
    )
