"""Scheduled obligation gaps (S01), meaningful change guards (S04), and blind spots (S18).

Follows Decision-Focused Insight Discovery recipes:
- S01: Scheduled obligation gaps (T01, T02, T03, T34)
- S04: Meaningful change & zero-baseline / flat series guards (T06, T07)
- S18: Decision blind spots & honest denominator coverage (T26)
"""
from __future__ import annotations

import math
from collections import defaultdict
from typing import Any
from pydantic import BaseModel, ConfigDict, Field


class ScheduledObligationResult(BaseModel):
    """Result of partitioning eligible obligations and calculating policy exposure (S01)."""
    model_config = ConfigDict(extra="forbid")

    total_calendar_days: int
    scheduled_days: float
    off_duty_days: float
    fulfilled_days: float
    excused_days: float
    explicit_absence_days: float
    unknown_days: float

    policy_excludes_excused: bool
    required_exposure: float

    covered_rate: float | None = None
    explicit_absence_rate: float | None = None
    unknown_rate: float | None = None
    is_applicable: bool = True

    what_it_establishes: str
    what_it_does_not_establish: str


def evaluate_scheduled_obligations(
    total_calendar_days: int,
    scheduled_days: float,
    fulfilled_days: float,
    excused_days: float = 0.0,
    explicit_absence_days: float = 0.0,
    unknown_days: float = 0.0,
    off_duty_days: float | None = None,
    policy_excludes_excused: bool = True,
) -> ScheduledObligationResult:
    """Evaluates scheduled obligation exposure under policy (S01 / T01–T03, T34).

    Partitions obligations into:
    - Fulfilled (worked / covered)
    - Excused (approved leave / policy exception)
    - Explicitly failed (unexcused absence)
    - Unknown (unresolved / missing records)

    Applies policy to determine required exposure.
    Calendar days never become duty days.
    If required exposure is zero, attendance rate is not applicable (never 0% or 100%).
    """
    if off_duty_days is None:
        off_duty_days = max(0.0, float(total_calendar_days) - scheduled_days)

    # Calculate required exposure under policy
    if policy_excludes_excused:
        required_exposure = max(0.0, scheduled_days - excused_days)
    else:
        required_exposure = max(0.0, scheduled_days)

    if required_exposure <= 0.0:
        # T34: Required exposure is zero (e.g. all off-duty or excused)
        # Rate is NOT applicable, never 0% or 100%!
        return ScheduledObligationResult(
            total_calendar_days=total_calendar_days,
            scheduled_days=scheduled_days,
            off_duty_days=off_duty_days,
            fulfilled_days=fulfilled_days,
            excused_days=excused_days,
            explicit_absence_days=explicit_absence_days,
            unknown_days=unknown_days,
            policy_excludes_excused=policy_excludes_excused,
            required_exposure=0.0,
            covered_rate=None,
            explicit_absence_rate=None,
            unknown_rate=None,
            is_applicable=False,
            what_it_establishes=(
                f"Zero required duty exposure across {total_calendar_days} calendar days: "
                f"{off_duty_days:.1f} off-duty days and {excused_days:.1f} approved excused days."
            ),
            what_it_does_not_establish=(
                "Attendance rate is not applicable when required exposure is zero under applicable policy."
            ),
        )

    # Reconciled rates against required exposure
    cov_rate = round((fulfilled_days / required_exposure) * 100.0, 1)
    abs_rate = round((explicit_absence_days / required_exposure) * 100.0, 1)
    unk_rate = round((unknown_days / required_exposure) * 100.0, 1)

    est_text = (
        f"{cov_rate}% of required duty exposure covered ({fulfilled_days:.1f} of {required_exposure:.1f} required days). "
        f"Explicit absence: {abs_rate}% ({explicit_absence_days:.1f}d); Unknown/unresolved: {unk_rate}% ({unknown_days:.1f}d)."
    )
    not_est_text = (
        f"Calendar days ({total_calendar_days}) do not equal duty days ({scheduled_days:.1f} scheduled, {off_duty_days:.1f} off-duty). "
        "Unknown records are isolated and not assumed to be absences."
    )

    return ScheduledObligationResult(
        total_calendar_days=total_calendar_days,
        scheduled_days=scheduled_days,
        off_duty_days=off_duty_days,
        fulfilled_days=fulfilled_days,
        excused_days=excused_days,
        explicit_absence_days=explicit_absence_days,
        unknown_days=unknown_days,
        policy_excludes_excused=policy_excludes_excused,
        required_exposure=required_exposure,
        covered_rate=cov_rate,
        explicit_absence_rate=abs_rate,
        unknown_rate=unk_rate,
        is_applicable=True,
        what_it_establishes=est_text,
        what_it_does_not_establish=not_est_text,
    )


class MeaningfulChangeResult(BaseModel):
    """Result of evaluating temporal trajectory and change (S04)."""
    model_config = ConfigDict(extra="forbid")

    current_value: float
    previous_value: float | None
    absolute_change: float | None
    relative_change_pct: float | None
    percentage_point_change: float | None
    relative_growth_available: bool
    is_flat: bool
    summary: str


def evaluate_meaningful_change(
    current_value: float,
    previous_value: float | None,
    is_rate_or_percentage: bool = False,
    historical_series: list[float] | None = None,
) -> MeaningfulChangeResult:
    """Evaluates change between periods with zero-baseline and flat-series guards (S04 / T06–T07).

    - If previous_value is 0.0, relative growth (%) is mathematically undefined.
    - If historical_series is flat (constant across all points), reports flat observation without claiming productivity growth.
    """
    is_flat = False
    if historical_series and len(historical_series) >= 2:
        val_range = max(historical_series) - min(historical_series)
        if val_range < 1e-6:
            is_flat = True

    if previous_value is None:
        return MeaningfulChangeResult(
            current_value=current_value,
            previous_value=None,
            absolute_change=None,
            relative_change_pct=None,
            percentage_point_change=None,
            relative_growth_available=False,
            is_flat=is_flat,
            summary=f"Current observation: {current_value:.2f}. No prior baseline available.",
        )

    abs_delta = round(current_value - previous_value, 2)
    pp_delta = round(current_value - previous_value, 2) if is_rate_or_percentage else None

    if abs(previous_value) < 1e-9:
        # Zero baseline: relative growth (%) is undefined
        return MeaningfulChangeResult(
            current_value=current_value,
            previous_value=0.0,
            absolute_change=abs_delta,
            relative_change_pct=None,
            percentage_point_change=pp_delta,
            relative_growth_available=False,
            is_flat=is_flat,
            summary=(
                f"Absolute change: {abs_delta:+.2f}. "
                "Relative growth rate is unavailable because baseline is zero."
            ),
        )

    rel_pct = round(((current_value - previous_value) / abs(previous_value)) * 100.0, 1)

    if is_flat:
        summary_text = f"Series remained flat at {current_value:.1f} across observed periods."
    elif is_rate_or_percentage:
        summary_text = f"Changed by {pp_delta:+.1f} percentage points ({rel_pct:+.1f}% relative change)."
    else:
        summary_text = f"Changed by {abs_delta:+.2f} ({rel_pct:+.1f}% relative change)."

    return MeaningfulChangeResult(
        current_value=current_value,
        previous_value=previous_value,
        absolute_change=abs_delta,
        relative_change_pct=rel_pct,
        percentage_point_change=pp_delta,
        relative_growth_available=True,
        is_flat=is_flat,
        summary=summary_text,
    )


class BlindSpotAuditResult(BaseModel):
    """Result of decision blind spots and denominator completeness screening (S18)."""
    model_config = ConfigDict(extra="forbid")

    observed_entity_count: int
    expected_population: int | None
    completeness_rate: float | None
    is_completeness_available: bool
    missing_fields: list[str] = Field(default_factory=list)
    declared_blind_spots: list[str] = Field(default_factory=list)
    recommended_next_evidence: str


def evaluate_decision_blind_spots(
    observed_entity_count: int,
    expected_population: int | None = None,
    unresolved_meanings: list[str] | None = None,
    missing_fields: list[str] | None = None,
) -> BlindSpotAuditResult:
    """Evaluates blind spots without fabricating completeness when expected population is unknown (S18 / T26)."""
    missing_fields = missing_fields or []
    blind_spots: list[str] = []

    if expected_population is not None and expected_population > 0:
        completeness_rate = round((observed_entity_count / expected_population) * 100.0, 1)
        is_available = True
    else:
        completeness_rate = None
        is_available = False
        blind_spots.append(
            "Expected population is unknown: complete organizational roster or eligible census is not defined in source."
        )

    if unresolved_meanings:
        blind_spots.extend(unresolved_meanings)

    if not is_available:
        next_ev = "Provide an official employee roster or organizational headcount census to establish workforce completeness."
    elif missing_fields:
        next_ev = f"Provide values for missing fields: {', '.join(missing_fields)}."
    else:
        next_ev = "All standard denominator fields corroborated by current upload."

    return BlindSpotAuditResult(
        observed_entity_count=observed_entity_count,
        expected_population=expected_population,
        completeness_rate=completeness_rate,
        is_completeness_available=is_available,
        missing_fields=missing_fields,
        declared_blind_spots=blind_spots,
        recommended_next_evidence=next_ev,
    )


class TargetCommitmentGapResult(BaseModel):
    """Result of evaluating explicit target vs actual performance (S05 / T08)."""
    model_config = ConfigDict(extra="forbid")

    metric_name: str
    target_name: str
    unit: str
    is_target_valid: bool
    is_computable: bool

    valid_paired_count: int
    missing_actual_count: int
    missing_target_count: int

    mean_actual: float | None = None
    mean_target: float | None = None
    aggregate_gap: float | None = None
    units_behind_count: int = 0
    pct_units_behind: float | None = None

    summary: str
    what_it_establishes: str
    what_it_does_not_establish: str


def evaluate_target_commitment_gap(
    metric_name: str,
    target_name: str,
    actual_values: list[float | None],
    target_values: list[float | None],
    unit: str = "units",
) -> TargetCommitmentGapResult:
    """Evaluates target and commitment gaps with strict semantic binding and missing actual preservation (S05 / T08).

    - Rejects mismatched targets (e.g. Recruitment_Target for Training_Hours).
    - Preserves missing actuals as unknown; never coerces to 0.0 to fabricate negative gaps.
    - Computes unit-level gap distribution (e.g. 40% of units behind even if aggregate meets target).
    """
    from .outlook import detect_target_column

    detected = detect_target_column([metric_name, target_name], metric_name)
    is_valid_target = detected == target_name

    if not is_valid_target:
        return TargetCommitmentGapResult(
            metric_name=metric_name,
            target_name=target_name,
            unit=unit,
            is_target_valid=False,
            is_computable=False,
            valid_paired_count=0,
            missing_actual_count=0,
            missing_target_count=0,
            summary=f"Mismatched target: '{target_name}' does not share semantic domain or concept with '{metric_name}'.",
            what_it_establishes="Target comparison rejected due to semantic domain mismatch.",
            what_it_does_not_establish="Cannot compute target attainment against an unrelated domain target.",
        )

    valid_actuals = []
    valid_targets = []
    missing_actual = 0
    missing_target = 0

    for a, t in zip(actual_values, target_values):
        if a is None:
            missing_actual += 1
            continue
        if t is None:
            missing_target += 1
            continue
        valid_actuals.append(float(a))
        valid_targets.append(float(t))

    valid_count = len(valid_actuals)
    if valid_count == 0:
        return TargetCommitmentGapResult(
            metric_name=metric_name,
            target_name=target_name,
            unit=unit,
            is_target_valid=True,
            is_computable=False,
            valid_paired_count=0,
            missing_actual_count=missing_actual,
            missing_target_count=missing_target,
            summary=f"Actual values for '{metric_name}' are missing/unknown across all {missing_actual} recorded target entries.",
            what_it_establishes="Explicit target exists, but actual performance observations are missing.",
            what_it_does_not_establish="Missing actuals are unknown, not zero; no artificial negative gap is fabricated.",
        )

    mean_a = float(sum(valid_actuals) / valid_count)
    mean_t = float(sum(valid_targets) / valid_count)
    agg_gap = round(mean_a - mean_t, 2)

    unit_gaps = [a - t for a, t in zip(valid_actuals, valid_targets)]
    units_behind = sum(1 for g in unit_gaps if g < 0)
    pct_behind = round((units_behind / valid_count) * 100.0, 1)

    if agg_gap >= 0 and units_behind > 0:
        summary = (
            f"Target met on average ({mean_a:.1f} vs {mean_t:.1f} {unit}), "
            f"but {units_behind} of {valid_count} units ({pct_behind:.0f}%) remain behind target."
        )
    elif agg_gap >= 0:
        summary = f"Target met across all {valid_count} observed units ({mean_a:.1f} vs target {mean_t:.1f} {unit})."
    else:
        summary = (
            f"Observed performance of {mean_a:.1f} {unit} is {abs(agg_gap):.1f} {unit} below target of {mean_t:.1f} {unit} "
            f"across {valid_count} units ({units_behind} of {valid_count} units behind target)."
        )

    return TargetCommitmentGapResult(
        metric_name=metric_name,
        target_name=target_name,
        unit=unit,
        is_target_valid=True,
        is_computable=True,
        valid_paired_count=valid_count,
        missing_actual_count=missing_actual,
        missing_target_count=missing_target,
        mean_actual=round(mean_a, 2),
        mean_target=round(mean_t, 2),
        aggregate_gap=agg_gap,
        units_behind_count=units_behind,
        pct_units_behind=pct_behind,
        summary=summary,
        what_it_establishes=f"Deterministic paired target variance across {valid_count} units ({missing_actual} missing actuals excluded).",
        what_it_does_not_establish="Does not establish forward pace beyond observed reporting period.",
    )


class SegmentMetric(BaseModel):
    """Segment data with dual total-burden and exposure-rate accounting (S09 / T13, T14)."""
    model_config = ConfigDict(extra="forbid")

    name: str
    sample_size: int
    total_burden: float
    exposure_rate: float | None = None
    is_suppressed: bool = False  # k < 5 small group privacy


class SegmentDisparityEvaluation(BaseModel):
    """Result of segment disparity comparison distinguishing total burden from exposure rate (S09 / T13, T14)."""
    model_config = ConfigDict(extra="forbid")

    metric_name: str
    segments: list[SegmentMetric]
    eligible_segments_count: int
    suppressed_segments_count: int

    benchmark_rate: float | None
    is_uniform: bool
    is_tie: bool
    tied_segments: list[str] = Field(default_factory=list)

    highest_burden_segment: str | None = None
    highest_burden_value: float | None = None
    lowest_rate_segment: str | None = None
    lowest_rate_value: float | None = None

    focus_segment: str | None = None
    focus_headline: str
    focus_explanation: str


def evaluate_comparable_segment_differences(
    metric_name: str,
    segments: list[dict[str, Any]],
    min_sample_size: int = 5,
) -> SegmentDisparityEvaluation:
    """Evaluates comparable segment differences (S09 / T13, T14).

    - Distinguishes greatest total burden (e.g. 50 absences in 500-person team) from highest rate / lowest reliability (e.g. 5 absences in 10-person team = 50%).
    - Avoids ambiguous 'worst-department' labels; names the exact metric and exposure denominator.
    - Suppresses sensitive small cohorts (n < 5) from public ranking to protect privacy.
    - Preserves ties and handles uniform/identical groups without claiming systematic differences.
    """
    evaluated_segments: list[SegmentMetric] = []
    eligible_segments: list[SegmentMetric] = []
    suppressed_count = 0

    for s in segments:
        cnt = int(s.get("sample_size") or s.get("count") or 0)
        burden = float(s.get("total_burden") or 0.0)
        rate = float(s["exposure_rate"]) if s.get("exposure_rate") is not None else None
        name = str(s.get("name") or "Unknown")

        is_supp = cnt < min_sample_size or name.lower() in ("unknown", "other", "null", "none", "")
        sm = SegmentMetric(
            name=name,
            sample_size=cnt,
            total_burden=burden,
            exposure_rate=rate,
            is_suppressed=is_supp,
        )
        evaluated_segments.append(sm)
        if not is_supp:
            eligible_segments.append(sm)
        else:
            suppressed_count += 1

    if not eligible_segments:
        return SegmentDisparityEvaluation(
            metric_name=metric_name,
            segments=evaluated_segments,
            eligible_segments_count=0,
            suppressed_segments_count=suppressed_count,
            benchmark_rate=None,
            is_uniform=False,
            is_tie=False,
            focus_headline="Decision focus unavailable",
            focus_explanation="All observed segments are below the minimum sample threshold (n < 5) or unassigned.",
        )

    # Calculate overall weighted benchmark rate if rates are present
    valid_rates = [s for s in eligible_segments if s.exposure_rate is not None]
    if valid_rates:
        tot_cnt = sum(s.sample_size for s in valid_rates)
        benchmark_rate = round(sum(s.exposure_rate * s.sample_size for s in valid_rates) / tot_cnt, 1) if tot_cnt > 0 else 0.0
    else:
        benchmark_rate = None

    # T13: Distinguish greatest total burden from highest rate / lowest reliability
    highest_burden = max(eligible_segments, key=lambda s: s.total_burden)

    if valid_rates:
        lowest_rate = min(valid_rates, key=lambda s: s.exposure_rate)
        ties = [s.name for s in valid_rates if abs(s.exposure_rate - lowest_rate.exposure_rate) < 0.01]
        is_tie = len(ties) > 1
        is_uniform = len(ties) == len(valid_rates)
    else:
        lowest_rate = None
        ties = []
        is_tie = False
        is_uniform = len(eligible_segments) > 1 and all(s.total_burden == eligible_segments[0].total_burden for s in eligible_segments)

    if is_uniform:
        headline = f"Consistent {metric_name.lower()} across all eligible units"
        explanation = f"All {len(eligible_segments)} evaluated units exhibit identical {metric_name.lower()} with no observed disparity."
        focus_seg = None
    elif is_tie:
        headline = f"Review {', '.join(ties)} {metric_name.lower()} (tied)"
        explanation = f"Multiple units share the lowest observed {metric_name.lower()} ({lowest_rate.exposure_rate:.1f}%). Neither is singled out as unique."
        focus_seg = ties[0]
    else:
        if lowest_rate and highest_burden.name != lowest_rate.name:
            focus_seg = lowest_rate.name
            headline = f"Review {lowest_rate.name} {metric_name.lower()} rate"
            explanation = (
                f"{lowest_rate.name} has the lowest {metric_name.lower()} rate ({lowest_rate.exposure_rate:.1f}% across {lowest_rate.sample_size} staff). "
                f"Note: {highest_burden.name} accounts for the greatest total burden ({highest_burden.total_burden:.0f} total count across {highest_burden.sample_size} staff)."
            )
        elif lowest_rate:
            focus_seg = lowest_rate.name
            headline = f"Review {lowest_rate.name} {metric_name.lower()}"
            explanation = f"{lowest_rate.name} observed at {lowest_rate.exposure_rate:.1f}% vs benchmark of {benchmark_rate:.1f}%."
        else:
            focus_seg = highest_burden.name
            headline = f"Review {highest_burden.name} total {metric_name.lower()} burden"
            explanation = f"{highest_burden.name} has the greatest observed burden ({highest_burden.total_burden:.0f} total count)."

    return SegmentDisparityEvaluation(
        metric_name=metric_name,
        segments=evaluated_segments,
        eligible_segments_count=len(eligible_segments),
        suppressed_segments_count=suppressed_count,
        benchmark_rate=benchmark_rate,
        is_uniform=is_uniform,
        is_tie=is_tie,
        tied_segments=ties if is_tie else [],
        highest_burden_segment=highest_burden.name,
        highest_burden_value=highest_burden.total_burden,
        lowest_rate_segment=lowest_rate.name if lowest_rate else None,
        lowest_rate_value=lowest_rate.exposure_rate if lowest_rate else None,
        focus_segment=focus_seg,
        focus_headline=headline,
        focus_explanation=explanation,
    )


class RecurrencePersistenceResult(BaseModel):
    """Result of recurrence, persistence, and unbroken streak analysis (S02 / T04)."""
    model_config = ConfigDict(extra="forbid")

    total_records_evaluated: int
    deduplicated_events_count: int
    duplicated_records_suppressed: int
    affected_entities_count: int
    repeat_entities_count: int
    recurrence_rate: float | None

    max_unbroken_streak: int
    streak_broken_by_unknown: bool
    episodes_count: int
    summary: str
    what_it_establishes: str
    what_it_does_not_establish: str


def evaluate_recurrence_and_persistence(
    events: list[dict[str, Any]],
    ordered_observations: list[str] | None = None,
) -> RecurrencePersistenceResult:
    """Evaluates event recurrence and persistence (S02 / T04).

    - Deduplicates identical events copied across multi-table exports.
    - An unknown status day cannot bridge or establish a continuous unbroken run.
    - Distinguishes event frequency from cumulative duration.
    """
    seen_events: set[tuple[str, str, str]] = set()
    deduped_events = []
    dup_count = 0

    for ev in events:
        eid = str(ev.get("entity_id") or ev.get("employee_id") or ev.get("id") or "")
        dt = str(ev.get("date") or ev.get("timestamp") or ev.get("day") or "")
        etype = str(ev.get("event_type") or ev.get("type") or "incident")
        key = (eid, dt, etype)
        if key in seen_events:
            dup_count += 1
            continue
        seen_events.add(key)
        deduped_events.append(ev)

    entity_counts: dict[str, int] = defaultdict(int)
    for ev in deduped_events:
        eid = str(ev.get("entity_id") or ev.get("employee_id") or ev.get("id") or "unknown")
        entity_counts[eid] += 1

    affected_entities = len(entity_counts)
    repeat_entities = sum(1 for cnt in entity_counts.values() if cnt > 1)
    rec_rate = round((repeat_entities / affected_entities) * 100.0, 1) if affected_entities > 0 else None

    max_streak = 0
    current_streak = 0
    episodes = 0
    in_episode = False
    broken_by_unknown = False

    if ordered_observations:
        for idx, obs in enumerate(ordered_observations):
            norm_obs = str(obs).strip().lower()
            if norm_obs in ("absent", "incident", "failure", "unfulfilled"):
                current_streak += 1
                if not in_episode:
                    episodes += 1
                    in_episode = True
                if current_streak > max_streak:
                    max_streak = current_streak
            else:
                if current_streak > 0 and norm_obs in ("unknown", "unrecorded", "missing"):
                    if idx + 1 < len(ordered_observations) and str(ordered_observations[idx + 1]).strip().lower() in ("absent", "incident", "failure", "unfulfilled"):
                        broken_by_unknown = True
                current_streak = 0
                in_episode = False
    elif deduped_events:
        episodes = len(deduped_events)
        max_streak = 1

    summary = (
        f"{len(deduped_events)} distinct operational events verified "
        f"({dup_count} duplicate exports suppressed) across {affected_entities} entities. "
        f"Maximum verified unbroken streak: {max_streak} day(s)."
    )
    if broken_by_unknown:
        summary += " Note: unrecorded interval between absence days prevents asserting an unbroken run."

    return RecurrencePersistenceResult(
        total_records_evaluated=len(events),
        deduplicated_events_count=len(deduped_events),
        duplicated_records_suppressed=dup_count,
        affected_entities_count=affected_entities,
        repeat_entities_count=repeat_entities,
        recurrence_rate=rec_rate,
        max_unbroken_streak=max_streak,
        streak_broken_by_unknown=broken_by_unknown,
        episodes_count=episodes,
        summary=summary,
        what_it_establishes=f"Deterministic deduplicated event accounting ({len(deduped_events)} events) with explicit streak bounds.",
        what_it_does_not_establish="Unknown intervals cannot be assumed to be continuous absence.",
    )


class ReasonConcentrationItem(BaseModel):
    model_config = ConfigDict(extra="forbid")
    reason: str
    count: int
    share_pct: float


class RecordedReasonsResult(BaseModel):
    """Result of recorded reasons concentration and Pareto analysis (S08 / T12)."""
    model_config = ConfigDict(extra="forbid")

    total_events: int
    total_known_events: int
    unknown_events_count: int
    is_multi_label: bool

    top_reasons: list[ReasonConcentrationItem]
    other_reasons_item: ReasonConcentrationItem | None = None
    unknown_item: ReasonConcentrationItem | None = None

    known_reasons_reconciled: bool
    summary: str
    what_it_establishes: str
    what_it_does_not_establish: str


def evaluate_recorded_reasons(
    reason_counts: dict[str, int],
    is_multi_label: bool = False,
    top_n: int = 5,
) -> RecordedReasonsResult:
    """Evaluates recorded reason concentration and Pareto distribution (S08 / T12).

    - Top five + Other reconcile known reasons.
    - Unknown reasons are preserved separately and not bundled into 'Other'.
    - Multi-label output is explicitly marked non-partitioned (shares may exceed 100%).
    """
    unknown_count = 0
    known_counts: dict[str, int] = {}

    for r_name, cnt in reason_counts.items():
        norm = str(r_name).strip().lower()
        if any(term in norm for term in ("unknown", "unrecorded", "unspecified", "not specified")) or norm in ("none", "null", ""):
            unknown_count += int(cnt)
        else:
            known_counts[str(r_name).strip()] = int(cnt)

    total_known = sum(known_counts.values())
    total_events = total_known + unknown_count

    sorted_known = sorted(known_counts.items(), key=lambda x: (-x[1], x[0]))

    top_list = sorted_known[:top_n]
    remaining_list = sorted_known[top_n:]

    divisor = total_events if is_multi_label or total_known == 0 else total_known

    top_items = [
        ReasonConcentrationItem(
            reason=name,
            count=cnt,
            share_pct=round((cnt / max(1, divisor)) * 100.0, 1),
        )
        for name, cnt in top_list
    ]

    other_item = None
    if remaining_list:
        other_cnt = sum(cnt for _, cnt in remaining_list)
        other_item = ReasonConcentrationItem(
            reason="Other Known Reasons",
            count=other_cnt,
            share_pct=round((other_cnt / max(1, divisor)) * 100.0, 1),
        )

    unknown_item = None
    if unknown_count > 0:
        unknown_item = ReasonConcentrationItem(
            reason="Unknown / Unspecified",
            count=unknown_count,
            share_pct=round((unknown_count / max(1, total_events)) * 100.0, 1),
        )

    top_and_other_sum = sum(it.count for it in top_items) + (other_item.count if other_item else 0)
    reconciled = (top_and_other_sum == total_known)

    summary = (
        f"Analyzed {total_events} events: {total_known} with recorded reasons and {unknown_count} unknown. "
        f"Top {len(top_items)} reasons account for {sum(it.share_pct for it in top_items):.1f}% of classified events."
    )
    if is_multi_label:
        summary += " Multi-label tagging applies; category shares represent non-exclusive incidence."

    return RecordedReasonsResult(
        total_events=total_events,
        total_known_events=total_known,
        unknown_events_count=unknown_count,
        is_multi_label=is_multi_label,
        top_reasons=top_items,
        other_reasons_item=other_item,
        unknown_item=unknown_item,
        known_reasons_reconciled=reconciled,
        summary=summary,
        what_it_establishes=(
            f"Taxonomy of {len(top_items)} primary recorded reasons reconciling exactly to {total_known} known events "
            f"with {unknown_count} unclassified events preserved separately."
        ),
        what_it_does_not_establish=(
            "Recorded reasons reflect reported explanations, not independently audited root causes. "
            "Unknown is an information gap, not a policy violation."
        ),
    )


class CapacityDemandResult(BaseModel):
    """Result of separating individual compliance from operational coverage shortfall (S14 / T19)."""
    model_config = ConfigDict(extra="forbid")

    required_shift_demand: float
    scheduled_headcount: float
    present_headcount: float
    excused_leave_headcount: float
    unexcused_absence_headcount: float

    employee_compliance_rate: float
    operational_coverage_rate: float
    shortfall: float
    backfill_needed: float

    is_compliant: bool
    is_understaffed: bool
    summary: str
    what_it_establishes: str
    what_it_does_not_establish: str


def evaluate_capacity_vs_demand(
    required_shift_demand: float,
    scheduled_headcount: float,
    present_headcount: float,
    excused_leave_headcount: float = 0.0,
    unexcused_absence_headcount: float = 0.0,
) -> CapacityDemandResult:
    """Evaluates capacity vs demand decoupling compliance from operational coverage (S14 / T19).

    - Approved leave is excluded from presence obligations (100% compliant).
    - Service shift still requires replacement capacity if present headcount < required demand.
    - Decouples policy compliance from operational shortfall.
    """
    compliant_headcount = present_headcount + excused_leave_headcount
    comp_rate = round((compliant_headcount / max(1.0, scheduled_headcount)) * 100.0, 1)

    cov_rate = round((present_headcount / max(1.0, required_shift_demand)) * 100.0, 1)
    shortfall = max(0.0, required_shift_demand - present_headcount)
    is_understaffed = shortfall > 0.0
    is_compliant = unexcused_absence_headcount == 0.0

    summary = (
        f"Employee compliance is {comp_rate:.1f}% ({excused_leave_headcount:.1f} approved leave excused under policy), "
        f"while operational shift coverage is {cov_rate:.1f}% ({present_headcount:.1f} present vs {required_shift_demand:.1f} required). "
        f"Operational shortfall: {shortfall:.1f} staff requiring replacement capacity."
    )

    return CapacityDemandResult(
        required_shift_demand=required_shift_demand,
        scheduled_headcount=scheduled_headcount,
        present_headcount=present_headcount,
        excused_leave_headcount=excused_leave_headcount,
        unexcused_absence_headcount=unexcused_absence_headcount,
        employee_compliance_rate=comp_rate,
        operational_coverage_rate=cov_rate,
        shortfall=shortfall,
        backfill_needed=shortfall,
        is_compliant=is_compliant,
        is_understaffed=is_understaffed,
        summary=summary,
        what_it_establishes=(
            f"Decouples individual attendance compliance ({comp_rate:.1f}%) from operational coverage strain "
            f"({shortfall:.1f} replacement backfill needed)."
        ),
        what_it_does_not_establish=(
            "Approved leave does not constitute an attendance infraction even when operational backfill is required."
        ),
    )


# ---------------------------------------------------------------------------
# S03 & S04: Calendar and shift patterns & temporal progression (T05, T06)
# ---------------------------------------------------------------------------


class CalendarShiftPatternResult(BaseModel):
    """Evaluation of calendar and shift aggregations (S03 / T05)."""
    model_config = ConfigDict(extra="forbid")

    source_grain: str
    bucket_lengths: list[int]
    is_uniform: bool
    allows_weekday_breakdown: bool
    unresolved_year_declared: bool
    source_intervals_preserved: bool
    summary: str
    what_it_establishes: str
    what_it_does_not_establish: str


def evaluate_calendar_shift_patterns(
    source_grain: str,
    bucket_lengths: list[int],
    has_explicit_year: bool = True,
) -> CalendarShiftPatternResult:
    """Evaluates calendar/shift intervals to prevent false weekday/uniform-week claims (T05)."""
    grain_lower = source_grain.lower()
    allows_weekday = grain_lower in ("daily", "shift", "hourly")
    is_uniform = len(set(bucket_lengths)) <= 1
    unresolved_year = not has_explicit_year

    summary = (
        f"Source data aggregated at {source_grain} grain with bucket lengths {bucket_lengths}. "
        f"Uniform weekly rate: {is_uniform}. Weekday breakdown supported: {allows_weekday}."
    )

    return CalendarShiftPatternResult(
        source_grain=source_grain,
        bucket_lengths=bucket_lengths,
        is_uniform=is_uniform,
        allows_weekday_breakdown=allows_weekday,
        unresolved_year_declared=unresolved_year,
        source_intervals_preserved=True,
        summary=summary,
        what_it_establishes=f"Preserves source intervals ({source_grain}) without artificial daily interpolation.",
        what_it_does_not_establish=(
            "Weekly totals cannot reveal weekday absence, shift concentration, or uniform daily distribution."
        ),
    )


class MonthlyProgressionPoint(BaseModel):
    model_config = ConfigDict(extra="forbid")

    year: int | None
    month: int
    period_label: str
    value: float
    is_partial: bool = False
    calendar_days: int = 30
    observed_days: int = 30


class TemporalProgressionResult(BaseModel):
    """Evaluation of multi-month temporal progression (S03/S04 / T06)."""
    model_config = ConfigDict(extra="forbid")

    points: list[MonthlyProgressionPoint]
    has_partial_period: bool
    has_missing_period_gap: bool
    chronological_ordering_verified: bool
    false_deterioration_suppressed: bool
    summary: str
    what_it_establishes: str
    what_it_does_not_establish: str


def evaluate_temporal_progression(
    points_data: list[dict[str, Any]],
) -> TemporalProgressionResult:
    """Evaluates multi-period progression, preserving chronological multi-year sequence,
    missing period gaps, and partial current month guards (T06).
    """
    points = []
    has_partial = False
    for p in points_data:
        cal_days = p.get("calendar_days", 30)
        obs_days = p.get("observed_days", cal_days)
        is_part = p.get("is_partial", obs_days < cal_days)
        if is_part:
            has_partial = True
        points.append(MonthlyProgressionPoint(
            year=p.get("year"),
            month=p.get("month", 1),
            period_label=p.get("period_label", f"{p.get('year', '')}-{p.get('month', 1):02d}"),
            value=float(p.get("value", 0.0)),
            is_partial=is_part,
            calendar_days=cal_days,
            observed_days=obs_days,
        ))

    # Sort strictly by (year, month)
    points.sort(key=lambda pt: (pt.year or 0, pt.month))
    chronological_ok = True

    # Detect gaps in periods
    has_gap = False
    for i in range(1, len(points)):
        prev = points[i - 1]
        curr = points[i]
        if prev.year is not None and curr.year is not None:
            month_diff = (curr.year - prev.year) * 12 + (curr.month - prev.month)
            if month_diff > 1:
                has_gap = True

    # Suppress false deterioration if current partial period is lower than full prior period
    false_deterioration_suppressed = False
    if len(points) >= 2 and points[-1].is_partial:
        last = points[-1]
        prev = points[-2]
        last_daily = last.value / max(1, last.observed_days)
        prev_daily = prev.value / max(1, prev.observed_days)
        if last.value < prev.value and last_daily >= prev_daily:
            false_deterioration_suppressed = True

    summary = (
        f"Evaluated {len(points)} chronological periods. "
        f"Partial periods detected: {has_partial}. Missing period gaps: {has_gap}. "
        f"False deterioration suppressed: {false_deterioration_suppressed}."
    )

    return TemporalProgressionResult(
        points=points,
        has_partial_period=has_partial,
        has_missing_period_gap=has_gap,
        chronological_ordering_verified=chronological_ok,
        false_deterioration_suppressed=false_deterioration_suppressed,
        summary=summary,
        what_it_establishes=(
            "Chronological multi-year progression with explicit missing-month gaps and partial-period guards."
        ),
        what_it_does_not_establish=(
            "Unadjusted partial current month values cannot establish performance deterioration."
        ),
    )


# ---------------------------------------------------------------------------
# S06: Funnel leakage & actual status values (T09, T10)
# ---------------------------------------------------------------------------


class FunnelStageItem(BaseModel):
    model_config = ConfigDict(extra="forbid")

    stage_name: str
    count: int
    open_count: int = 0
    abandoned_count: int = 0
    converted_count: int = 0


class FunnelLeakageResult(BaseModel):
    """Evaluation of funnel transitions and stage leakage (S06 / T09, T10)."""
    model_config = ConfigDict(extra="forbid")

    is_cohort_linked: bool
    is_keyword_inferred: bool
    stages: list[FunnelStageItem]
    open_opportunities_count: int
    confirmed_exits_count: int
    delivered_orders_count: int
    returned_orders_count: int
    summary: str
    what_it_establishes: str
    what_it_does_not_establish: str


def evaluate_funnel_leakage(
    records: list[dict[str, Any]],
    conversion_window_hours: float | None = None,
    as_of_timestamp: float | None = None,
    is_cohort_linked: bool = True,
) -> FunnelLeakageResult:
    """Evaluates funnel leakage by parsing actual status values, NOT column name keywords (T09, T10)."""
    delivered_count = 0
    returned_count = 0
    open_count = 0
    confirmed_exits = 0

    if not is_cohort_linked:
        stages = [
            FunnelStageItem(
                stage_name=r.get("stage_name", f"Stage {i}"),
                count=int(r.get("count", 0)),
                open_count=0,
                abandoned_count=0,
                converted_count=0,
            )
            for i, r in enumerate(records, 1)
        ]
        return FunnelLeakageResult(
            is_cohort_linked=False,
            is_keyword_inferred=False,
            stages=stages,
            open_opportunities_count=0,
            confirmed_exits_count=0,
            delivered_orders_count=0,
            returned_orders_count=0,
            summary="Independent unlinked stage volume counts. Conversion cohort unavailable.",
            what_it_establishes="Independent stage volume totals without entity linkage.",
            what_it_does_not_establish=(
                "Independent stage totals cannot become a conversion cohort or establish drop-off rates."
            ),
        )

    for r in records:
        order_status = str(r.get("Order_Status") or r.get("status") or "").lower().strip()
        ret_val = r.get("Return_Requested")
        is_returned = ret_val is True or str(ret_val).lower().strip() in ("true", "1", "yes")

        if "delivered" in order_status and "cancelled" not in order_status:
            delivered_count += 1

        if is_returned and "cancelled" not in order_status:
            returned_count += 1

        stage = str(r.get("stage") or "").lower().strip()
        cart_time = r.get("cart_timestamp")
        if stage == "cart" and cart_time is not None and as_of_timestamp is not None and conversion_window_hours is not None:
            elapsed_hours = (as_of_timestamp - float(cart_time)) / 3600.0
            if elapsed_hours <= conversion_window_hours:
                open_count += 1
            else:
                confirmed_exits += 1
        elif order_status == "cancelled":
            confirmed_exits += 1

    stages = [
        FunnelStageItem(stage_name="Delivered", count=delivered_count, converted_count=delivered_count),
        FunnelStageItem(stage_name="Returned", count=returned_count, abandoned_count=returned_count),
    ]

    summary = (
        f"Parsed actual status values: {delivered_count} delivered, {returned_count} returned. "
        f"Open opportunities in window: {open_count}, confirmed exits: {confirmed_exits}."
    )

    return FunnelLeakageResult(
        is_cohort_linked=True,
        is_keyword_inferred=False,
        stages=stages,
        open_opportunities_count=open_count,
        confirmed_exits_count=confirmed_exits,
        delivered_orders_count=delivered_count,
        returned_orders_count=returned_count,
        summary=summary,
        what_it_establishes="Parses explicit status values and preserves open opportunities within conversion window.",
        what_it_does_not_establish=(
            "Column existence does not imply delivery or return status; carts within window are not abandoned."
        ),
    )


# ---------------------------------------------------------------------------
# S07: Backlog, aging and SLA (T11)
# ---------------------------------------------------------------------------


class BacklogItemAging(BaseModel):
    model_config = ConfigDict(extra="forbid")

    item_id: str
    status: str
    age_or_duration_days: float
    is_chronology_valid: bool = True


class BacklogAgingResult(BaseModel):
    """Evaluation of backlog aging and SLA thresholds (S07 / T11)."""
    model_config = ConfigDict(extra="forbid")

    total_items: int
    open_items_count: int
    completed_items_count: int
    open_average_age_days: float | None = None
    completed_average_duration_days: float | None = None
    is_sla_defined: bool
    overdue_count: int | None = None
    chronology_error_count: int = 0
    items: list[BacklogItemAging]
    summary: str
    what_it_establishes: str
    what_it_does_not_establish: str


def evaluate_backlog_aging(
    items_data: list[dict[str, Any]],
    sla_days: float | None = None,
    as_of_days: float = 100.0,
) -> BacklogAgingResult:
    """Evaluates backlog aging, separating open backlog from completed items,
    flagging impossible chronology (closed < opened), and withholding overdue claims without SLA (T11).
    """
    open_items: list[BacklogItemAging] = []
    completed_items: list[BacklogItemAging] = []
    chronology_errors = 0

    for it in items_data:
        item_id = str(it.get("id") or it.get("item_id") or f"ITEM-{len(open_items) + len(completed_items) + 1}")
        status = str(it.get("status", "open")).lower().strip()
        opened = float(it.get("opened_day", 0.0))
        closed = it.get("closed_day")

        if status in ("completed", "closed", "resolved") and closed is not None:
            duration = float(closed) - opened
            is_valid = duration >= 0.0
            if not is_valid:
                chronology_errors += 1
            completed_items.append(BacklogItemAging(
                item_id=item_id,
                status="completed",
                age_or_duration_days=duration,
                is_chronology_valid=is_valid,
            ))
        else:
            age = max(0.0, as_of_days - opened)
            open_items.append(BacklogItemAging(
                item_id=item_id,
                status="open",
                age_or_duration_days=age,
                is_chronology_valid=True,
            ))

    open_avg = round(sum(i.age_or_duration_days for i in open_items) / len(open_items), 1) if open_items else None
    valid_completed = [i for i in completed_items if i.is_chronology_valid]
    completed_avg = round(sum(i.age_or_duration_days for i in valid_completed) / len(valid_completed), 1) if valid_completed else None

    is_sla = sla_days is not None
    overdue_count = None
    if is_sla and sla_days is not None:
        overdue_count = sum(1 for i in open_items if i.age_or_duration_days > sla_days)

    summary = (
        f"Evaluated {len(open_items) + len(completed_items)} items: {len(open_items)} open (avg age {open_avg or 0}d), "
        f"{len(completed_items)} completed (avg duration {completed_avg or 0}d). "
        f"SLA defined: {is_sla}. Chronology errors: {chronology_errors}."
    )

    return BacklogAgingResult(
        total_items=len(open_items) + len(completed_items),
        open_items_count=len(open_items),
        completed_items_count=len(completed_items),
        open_average_age_days=open_avg,
        completed_average_duration_days=completed_avg,
        is_sla_defined=is_sla,
        overdue_count=overdue_count,
        chronology_error_count=chronology_errors,
        items=open_items + completed_items,
        summary=summary,
        what_it_establishes=(
            "Distinguishes open backlog age from completed cycle duration; flags impossible chronology."
        ),
        what_it_does_not_establish=(
            "Without an explicit SLA agreement, aging does not establish overdue status or policy breach."
        ),
    )


# ---------------------------------------------------------------------------
# S10: Composition and fair comparison / Simpson's reversal (T15)
# ---------------------------------------------------------------------------


class CompositionReversalResult(BaseModel):
    """Evaluation of composition adjustment and Simpson's reversal (S10 / T15)."""
    model_config = ConfigDict(extra="forbid")

    group_a_raw_rate: float
    group_b_raw_rate: float
    raw_difference: float
    group_a_adjusted_rate: float
    group_b_adjusted_rate: float
    adjusted_difference: float
    is_reversal_detected: bool
    summary: str
    what_it_establishes: str
    what_it_does_not_establish: str


def evaluate_composition_reversal(
    group_a_strata: dict[str, tuple[int, int]],
    group_b_strata: dict[str, tuple[int, int]],
    reference_weights: dict[str, float] | None = None,
) -> CompositionReversalResult:
    """Evaluates raw vs composition-adjusted group comparisons, detecting Simpson's reversals (T15)."""
    # Raw rates
    a_success = sum(succ for succ, _ in group_a_strata.values())
    a_exposure = sum(exp for _, exp in group_a_strata.values())
    b_success = sum(succ for succ, _ in group_b_strata.values())
    b_exposure = sum(exp for _, exp in group_b_strata.values())

    a_raw = round((a_success / max(1, a_exposure)) * 100.0, 1)
    b_raw = round((b_success / max(1, b_exposure)) * 100.0, 1)
    raw_diff = round(a_raw - b_raw, 1)

    # Standardized weights across strata
    all_strata = sorted(set(group_a_strata.keys()) | set(group_b_strata.keys()))
    if not reference_weights:
        # Pooled exposure as reference population
        total_exp = {}
        for s in all_strata:
            total_exp[s] = group_a_strata.get(s, (0, 0))[1] + group_b_strata.get(s, (0, 0))[1]
        sum_exp = sum(total_exp.values())
        reference_weights = {s: total_exp[s] / max(1, sum_exp) for s in all_strata}

    # Stratum rates
    a_adj = 0.0
    b_adj = 0.0
    for s in all_strata:
        w = reference_weights.get(s, 0.0)
        a_succ, a_exp = group_a_strata.get(s, (0, 0))
        b_succ, b_exp = group_b_strata.get(s, (0, 0))
        rate_a = (a_succ / a_exp) if a_exp > 0 else 0.0
        rate_b = (b_succ / b_exp) if b_exp > 0 else 0.0
        a_adj += w * rate_a
        b_adj += w * rate_b

    a_adj = round(a_adj * 100.0, 1)
    b_adj = round(b_adj * 100.0, 1)
    adj_diff = round(a_adj - b_adj, 1)

    # Reversal occurs when raw difference sign opposes adjusted difference sign
    is_reversal = (raw_diff > 0 and adj_diff < 0) or (raw_diff < 0 and adj_diff > 0)

    summary = (
        f"Raw rates: Group A {a_raw}%, Group B {b_raw}% (gap: {raw_diff:+.1f} pp). "
        f"Standardized rates: Group A {a_adj}%, Group B {b_adj}% (gap: {adj_diff:+.1f} pp). "
        f"Simpson's reversal detected: {is_reversal}."
    )

    return CompositionReversalResult(
        group_a_raw_rate=a_raw,
        group_b_raw_rate=b_raw,
        raw_difference=raw_diff,
        group_a_adjusted_rate=a_adj,
        group_b_adjusted_rate=b_adj,
        adjusted_difference=adj_diff,
        is_reversal_detected=is_reversal,
        summary=summary,
        what_it_establishes=(
            f"Presents both raw ({raw_diff:+.1f} pp) and standardized ({adj_diff:+.1f} pp) results under a reference population."
        ),
        what_it_does_not_establish=(
            "Raw differences driven by internal subgroup shift composition do not establish systematic operational superiority."
        ),
    )


# ---------------------------------------------------------------------------
# S11: Contribution to overall change (T16)
# ---------------------------------------------------------------------------


class SegmentDeltaItem(BaseModel):
    model_config = ConfigDict(extra="forbid")

    segment_name: str
    delta: float
    contribution_pct: float | None = None


class ContributionToChangeResult(BaseModel):
    """Evaluation of segment contributions to overall change (S11 / T16)."""
    model_config = ConfigDict(extra="forbid")

    total_net_delta: float
    total_gross_delta: float
    is_near_zero_net_change: bool
    segment_deltas: list[SegmentDeltaItem]
    summary: str
    what_it_establishes: str
    what_it_does_not_establish: str


def evaluate_contribution_to_change(
    deltas: dict[str, float],
    near_zero_threshold: float = 5.0,
) -> ContributionToChangeResult:
    """Evaluates segment contributions, suppressing misleading percentages when net change is near zero (T16)."""
    net_delta = round(sum(deltas.values()), 2)
    gross_delta = round(sum(abs(d) for d in deltas.values()), 2)

    # Near-zero net change: cancelling large deltas produce unstable/misleading contribution %
    is_near_zero = abs(net_delta) <= near_zero_threshold and gross_delta > 5.0 * max(1.0, abs(net_delta))

    items = []
    for name, d in deltas.items():
        pct = None
        if not is_near_zero and abs(net_delta) > 0.001:
            pct = round((d / net_delta) * 100.0, 1)
        items.append(SegmentDeltaItem(
            segment_name=name,
            delta=d,
            contribution_pct=pct,
        ))

    summary = (
        f"Net change: {net_delta:+.1f}, Gross absolute movement: {gross_delta:.1f}. "
        f"Near-zero net change: {is_near_zero}."
    )

    return ContributionToChangeResult(
        total_net_delta=net_delta,
        total_gross_delta=gross_delta,
        is_near_zero_net_change=is_near_zero,
        segment_deltas=items,
        summary=summary,
        what_it_establishes="Reconciles exact segment deltas and discloses gross absolute movement.",
        what_it_does_not_establish=(
            "Contribution percentages are suppressed on near-zero net changes to prevent misleading proportions."
        ),
    )


# ---------------------------------------------------------------------------
# S12: Spread and tail burden (T17)
# ---------------------------------------------------------------------------


class SpreadTailBurdenResult(BaseModel):
    """Evaluation of distribution spread and tail concentration (S12 / T17)."""
    model_config = ConfigDict(extra="forbid")

    is_raw_distribution_available: bool
    mean: float
    median: float | None = None
    p90: float | None = None
    p99: float | None = None
    tail_burden_p90_pct: float | None = None
    summary: str
    what_it_establishes: str
    what_it_does_not_establish: str


def evaluate_spread_and_tail_burden(
    values: list[float] | None = None,
    mean_only: float | None = None,
) -> SpreadTailBurdenResult:
    """Reveals tail concentration when raw values support them, withholding fake quantiles from a bare mean (T17)."""
    if values is None or len(values) == 0:
        m = mean_only or 0.0
        return SpreadTailBurdenResult(
            is_raw_distribution_available=False,
            mean=m,
            median=None,
            p90=None,
            p99=None,
            tail_burden_p90_pct=None,
            summary=f"Only aggregate mean ({m:.2f}) is recorded. Raw distribution is unavailable.",
            what_it_establishes=f"Records aggregate mean ({m:.2f}).",
            what_it_does_not_establish=(
                "Quantiles and tail burden cannot be manufactured from a single aggregate mean."
            ),
        )

    import numpy as np
    arr = np.array(values, dtype=float)
    mean_val = round(float(np.mean(arr)), 2)
    median_val = round(float(np.median(arr)), 2)
    p90_val = round(float(np.percentile(arr, 90)), 2)
    p99_val = round(float(np.percentile(arr, 99)), 2)

    tot = float(np.sum(arr))
    tail_sum = float(np.sum(arr[arr >= p90_val])) if tot > 0 else 0.0
    tail_pct = round((tail_sum / max(1.0, tot)) * 100.0, 1)

    summary = (
        f"Distribution across n={len(arr)}: mean={mean_val}, median={median_val}, p90={p90_val}. "
        f"Top 10% accounts for {tail_pct}% of total burden."
    )

    return SpreadTailBurdenResult(
        is_raw_distribution_available=True,
        mean=mean_val,
        median=median_val,
        p90=p90_val,
        p99=p99_val,
        tail_burden_p90_pct=tail_pct,
        summary=summary,
        what_it_establishes=f"Discloses empirical distribution quantiles and tail burden ({tail_pct}% at P90).",
        what_it_does_not_establish=(
            "Aggregate averages do not describe operational risk when tail burden is heavily concentrated."
        ),
    )


# ---------------------------------------------------------------------------
# S13: Cohort retention and recovery (T18)
# ---------------------------------------------------------------------------


class CohortRetentionResult(BaseModel):
    """Evaluation of cohort retention across observation horizons (S13 / T18)."""
    model_config = ConfigDict(extra="forbid")

    cohort_id: str
    cohort_age_days: int
    target_horizon_days: int
    is_observable: bool
    retention_rate: float | None = None
    summary: str
    what_it_establishes: str
    what_it_does_not_establish: str


def evaluate_cohort_retention(
    cohort_id: str,
    cohort_age_days: int,
    target_horizon_days: int,
    retained_count: int | None = None,
    initial_count: int | None = None,
) -> CohortRetentionResult:
    """Evaluates cohort retention, treating unobservable horizons as unavailable rather than 0% (T18)."""
    if cohort_age_days < target_horizon_days:
        return CohortRetentionResult(
            cohort_id=cohort_id,
            cohort_age_days=cohort_age_days,
            target_horizon_days=target_horizon_days,
            is_observable=False,
            retention_rate=None,
            summary=(
                f"Cohort '{cohort_id}' age is {cohort_age_days} days; target horizon {target_horizon_days} days is unobservable."
            ),
            what_it_establishes=f"Records cohort age ({cohort_age_days}d) against required evaluation horizon ({target_horizon_days}d).",
            what_it_does_not_establish=(
                "Unobservable future retention horizons remain unavailable; they must never be scored as 0% retention."
            ),
        )

    ret_rate = 0.0
    if initial_count and retained_count is not None and initial_count > 0:
        ret_rate = round((retained_count / initial_count) * 100.0, 1)

    return CohortRetentionResult(
        cohort_id=cohort_id,
        cohort_age_days=cohort_age_days,
        target_horizon_days=target_horizon_days,
        is_observable=True,
        retention_rate=ret_rate,
        summary=f"Cohort '{cohort_id}' reached {target_horizon_days}d horizon with {ret_rate}% retention.",
        what_it_establishes=f"Verified empirical retention rate ({ret_rate}%) at mature observation horizon.",
        what_it_does_not_establish="Matured cohort rates do not guarantee identical retention for subsequent cohorts.",
    )


# ---------------------------------------------------------------------------
# S15: Efficiency and unit economics (T20)
# ---------------------------------------------------------------------------


class UnitEconomicsResult(BaseModel):
    """Evaluation of unit economics, mixed currencies, and line-item grain (S15 / T20)."""
    model_config = ConfigDict(extra="forbid")

    is_compatible: bool
    error_reason: str | None = None
    distinct_orders_count: int
    total_revenue: float | None = None
    total_cost: float | None = None
    unit_margin: float | None = None
    summary: str
    what_it_establishes: str
    what_it_does_not_establish: str


def evaluate_unit_economics(
    order_lines: list[dict[str, Any]],
    currencies: list[str],
) -> UnitEconomicsResult:
    """Evaluates unit economics, rejecting mixed currencies and deduplicating line-level order totals (T20)."""
    # 1. Currency compatibility
    unique_currencies = sorted(set(currencies))
    if len(unique_currencies) > 1:
        return UnitEconomicsResult(
            is_compatible=False,
            error_reason=f"Mixed currencies detected: {', '.join(unique_currencies)}. Arithmetic aggregation rejected.",
            distinct_orders_count=len(set(r.get('order_id') for r in order_lines)),
            total_revenue=None,
            total_cost=None,
            unit_margin=None,
            summary="Rejected aggregate economic calculation due to unstandardized multiple currencies.",
            what_it_establishes=f"Flags currency incompatibility ({', '.join(unique_currencies)}).",
            what_it_does_not_establish="Monetary totals cannot be summed across unadjusted currency denominations.",
        )

    # 2. Line-level vs order-level deduplication
    orders_seen = {}
    for line in order_lines:
        oid = line.get("order_id")
        rev = float(line.get("order_total", line.get("revenue", 0.0)))
        cost = float(line.get("order_cost", line.get("cost", 0.0)))
        if oid not in orders_seen:
            orders_seen[oid] = (rev, cost)

    tot_rev = sum(rev for rev, _ in orders_seen.values())
    tot_cost = sum(cost for _, cost in orders_seen.values())
    margin = tot_rev - tot_cost

    summary = (
        f"Evaluated {len(order_lines)} line items across {len(orders_seen)} distinct orders. "
        f"Currency: {unique_currencies[0]}. Total revenue: {tot_rev:.2f}, Margin: {margin:.2f}."
    )

    return UnitEconomicsResult(
        is_compatible=True,
        error_reason=None,
        distinct_orders_count=len(orders_seen),
        total_revenue=tot_rev,
        total_cost=tot_cost,
        unit_margin=margin,
        summary=summary,
        what_it_establishes=(
            f"Deduplicates line items to true order grain ({len(orders_seen)} distinct orders) in {unique_currencies[0]}."
        ),
        what_it_does_not_establish="Line-level repetitive order totals must not be summed as independent revenue.",
    )


# ---------------------------------------------------------------------------
# S16: Relationships worth investigating & safeguards (T21, T22)
# ---------------------------------------------------------------------------


class RelationshipInferenceResult(BaseModel):
    """Evaluation of statistical relationship safeguards (S16 / T21, T22)."""
    model_config = ConfigDict(extra="forbid")

    is_inference_valid: bool
    effective_sample_size: int
    is_spurious_trend_flagged: bool
    is_constant_variable: bool
    rejection_reasons: list[str]
    summary: str
    what_it_establishes: str
    what_it_does_not_establish: str


def evaluate_relationship_safeguards(
    x_series: list[float],
    y_series: list[float],
    entity_ids: list[str] | None = None,
    is_trending_x: bool = False,
    is_trending_y: bool = False,
    scanned_pairs_count: int = 1,
) -> RelationshipInferenceResult:
    """Applies trend, effective sample size, and constant variable guards to relationships (T21, T22)."""
    reasons = []

    # 1. Constant variable check
    is_constant = len(set(x_series)) <= 1 or len(set(y_series)) <= 1
    if is_constant:
        reasons.append("Zero variance: variable is constant across observations.")

    # 2. Effective sample size
    eff_n = len(set(entity_ids)) if entity_ids else len(x_series)
    if eff_n < 5:
        reasons.append(f"Insufficient independent effective sample size (n={eff_n} < 5).")

    # 3. Spurious trending series check
    is_spurious_trend = is_trending_x and is_trending_y
    if is_spurious_trend:
        reasons.append("Spurious correlation risk: both series exhibit independent time trends without detrending.")

    # 4. Multiplicity adjustment
    if scanned_pairs_count > 10:
        reasons.append(f"Multiplicity penalty: scanned across {scanned_pairs_count} pairs without family-wise correction.")

    is_valid = len(reasons) == 0

    summary = (
        f"Relationship evaluated (effective n={eff_n}). "
        f"Valid: {is_valid}. Flags: {len(reasons)}."
    )

    return RelationshipInferenceResult(
        is_inference_valid=is_valid,
        effective_sample_size=eff_n,
        is_spurious_trend_flagged=is_spurious_trend,
        is_constant_variable=is_constant,
        rejection_reasons=reasons,
        summary=summary,
        what_it_establishes="Enforces sample size, variance, detrending, and multiplicity safeguards.",
        what_it_does_not_establish="Statistical co-movement does not establish causal dependency or operational driver status.",
    )


# ---------------------------------------------------------------------------
# S20: Scenarios and sensitivity (T28)
# ---------------------------------------------------------------------------


class ScenarioSimulationResult(BaseModel):
    """Evaluation of scenario projections under capacity constraints (S20 / T28)."""
    model_config = ConfigDict(extra="forbid")

    baseline_volume: float
    capacity_limit: float
    conversion_lift_pct: float
    projected_demand: float
    realized_output: float
    capacity_shortfall: float
    is_input_feasible: bool
    rejection_reason: str | None = None
    summary: str
    what_it_establishes: str
    what_it_does_not_establish: str


def evaluate_scenario_simulation(
    baseline_volume: float,
    capacity_limit: float,
    conversion_lift_pct: float,
    min_feasible_lift: float = -100.0,
    max_feasible_lift: float = 500.0,
) -> ScenarioSimulationResult:
    """Evaluates scenario projections, enforcing physical capacity constraints and rejecting impossible inputs (T28)."""
    # 1. Feasibility check
    if conversion_lift_pct < min_feasible_lift or conversion_lift_pct > max_feasible_lift:
        return ScenarioSimulationResult(
            baseline_volume=baseline_volume,
            capacity_limit=capacity_limit,
            conversion_lift_pct=conversion_lift_pct,
            projected_demand=baseline_volume,
            realized_output=baseline_volume,
            capacity_shortfall=0.0,
            is_input_feasible=False,
            rejection_reason=(
                f"Assumed lift ({conversion_lift_pct:.1f}%) exceeds feasible boundaries "
                f"[{min_feasible_lift}%, {max_feasible_lift}%]."
            ),
            summary="Rejected simulation: assumption outside feasible domain bounds.",
            what_it_establishes="Enforces domain boundary checks on scenario assumptions.",
            what_it_does_not_establish="Arbitrary assumption values do not produce trustworthy operational projections.",
        )

    # 2. Demand projection and capacity constraint clamping
    proj_demand = round(baseline_volume * (1.0 + conversion_lift_pct / 100.0), 1)
    realized = min(proj_demand, capacity_limit)
    shortfall = max(0.0, proj_demand - capacity_limit)

    summary = (
        f"Baseline: {baseline_volume}, Lift: {conversion_lift_pct:+.1f}%. "
        f"Projected demand: {proj_demand}, Realized output: {realized} (capacity: {capacity_limit}). "
        f"Unserviced demand shortfall: {shortfall}."
    )

    return ScenarioSimulationResult(
        baseline_volume=baseline_volume,
        capacity_limit=capacity_limit,
        conversion_lift_pct=conversion_lift_pct,
        projected_demand=proj_demand,
        realized_output=realized,
        capacity_shortfall=shortfall,
        is_input_feasible=True,
        rejection_reason=None,
        summary=summary,
        what_it_establishes=(
            f"Clamps realized output to operational capacity limit ({capacity_limit:.1f}) and quantifies unserviced shortfall."
        ),
        what_it_does_not_establish=(
            "Conversion lift does not translate to realized output beyond hard operational capacity boundaries."
        ),
    )

