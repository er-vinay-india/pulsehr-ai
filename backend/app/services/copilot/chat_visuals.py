"""Grounded aggregate visuals for chat, independent of the selected language model.

Conversation context stores calculation instructions, never authoritative values.
Every follow-up recomputes its series from the active sheet.
"""
import hashlib
import re
import time
from typing import Any

import pandas as pd

from ..data_engine.fact_visualizer import FactVisualizer
from ..data_engine.semantic_classifier import SemanticClassifier
from ..data_engine.visualization_models import ChartSeries, VisualChartSpec


def _normalized(text: Any) -> str:
    return re.sub(r"[^a-z0-9]+", " ", str(text).lower()).strip()


def is_visual_request(query: str) -> bool:
    return bool(re.search(r"\b(chart|charts|graph|plot|diagram|visualize|visualise|visualization|visualisation|draw|render)\b", query, re.I))


def _mentioned_columns(query: str, columns: list[str]) -> list[str]:
    text = f" {_normalized(query)} "
    matches = [c for c in columns if f" {_normalized(c)} " in text]
    # Prefer 'Math Score' over an overlapping column called 'Score'.
    return [c for c in matches if not any(c != other and f" {_normalized(c)} " in f" {_normalized(other)} " for other in matches)]


def _operation(query: str) -> str | None:
    for pattern, op in [(r"average|mean", "mean"), (r"median", "median"),
                        (r"sum|total", "sum"), (r"minimum|min", "min"),
                        (r"maximum|max", "max"), (r"count", "count")]:
        if re.search(rf"\b({pattern})\b", query, re.I):
            return op
    return None


def answer_chat_visual(
    query: str, df: pd.DataFrame | None, sheet_name: str, sheet_id: int | None,
    dataset_id: int | None = None, prior_context: dict[str, Any] | None = None,
) -> dict[str, Any] | None:
    """Handle explicit visuals and simple named aggregates; defer other analytics.

Unsupported filters/time windows are rejected for visuals rather than silently
replaced with a full-cohort mean. The existing planner handles richer queries.
"""
    start = time.perf_counter()
    visual = is_visual_request(query)
    op = _operation(query)
    if not visual and not op:
        return None
    prior = dict(prior_context or {})
    if ((prior.get("sheet_id") is not None and prior["sheet_id"] != sheet_id)
            or (dataset_id is not None and prior.get("dataset_id") is not None and prior["dataset_id"] != dataset_id)):
        prior = {}

    def response(answer, charts=None, status="success", context=None, evidence=None):
        return {
            "query": query, "answer": answer, "visual_charts": charts or [],
            "status": status, "engine": "chat_visuals", "model_used": "verified_chart_engine",
            "prior_context": {**prior, **(context or {}), "sheet_id": sheet_id,
                              "dataset_id": dataset_id, "last_query": query},
            "evidence": evidence, "related_rows": len(df) if df is not None else 0,
            "timings": {"total_ms": round((time.perf_counter() - start) * 1000, 1),
                        "llm_calls": 0, "is_deterministic": True},
        }

    def clarify(text):
        return response(text, status="clarification_required") if visual else None

    if df is None or df.empty:
        return clarify("Please select or upload a sheet before requesting a chart.")

    columns = list(df.columns)
    mentioned = _mentioned_columns(query, columns)
    descriptor = prior.get("visualization_context") or {}
    if not isinstance(descriptor, dict):
        descriptor = {}
    # Backward compatibility for an earlier council response: recover column and
    # operation from its question, but never read numerical values from its prose.
    history = prior.get("history") if isinstance(prior.get("history"), list) else []
    previous_queries = [prior.get("last_query", "")]
    previous_queries.extend(turn.get("content", "") for turn in reversed(history)
                            if isinstance(turn, dict) and turn.get("role") == "user")
    if not descriptor:
        for previous_query in previous_queries:
            if not isinstance(previous_query, str):
                continue
            previous_columns = _mentioned_columns(previous_query, columns)
            previous_op = _operation(previous_query)
            if previous_op and len(previous_columns) == 1:
                descriptor = {"metric": previous_columns[0], "operation": previous_op,
                              "source_query": previous_query}
                break
    if not descriptor:
        # An old chat may retain only chart requests and their ASCII answers.
        # Recover the explicit cohort heading as an intent hint; never reuse its
        # numbers, claimed range, sample size, or model-authored series.
        answer = _normalized(prior.get("last_answer", ""))
        for column in _mentioned_columns(answer, columns):
            heading = re.search(
                rf"\bcohort\s+(average|mean|median|total|sum|minimum|maximum|count)\s+(?:(?:for|of)\s+)?{re.escape(_normalized(column))}\b",
                answer,
            )
            if heading:
                descriptor = {"metric": column, "operation": _operation(heading.group(1)),
                              "source_query": f"{heading.group(1)} {column}"}
                break

    # Profiling also needs finite inputs; raw infinity otherwise reaches the
    # classifier's integer/ordinal cast before chart cleaning can exclude it.
    profile_frame = df.replace([float("inf"), -float("inf"), "inf", "-inf", "Infinity", "-Infinity"], None)
    profile = SemanticClassifier.profile_dataset(profile_frame, dataset_name=sheet_name)
    measures = set(profile.numeric_measures)
    metrics = [c for c in mentioned if c in measures]

    categorical_cols = [c for c in columns if c not in measures]
    mentioned_cats = [c for c in mentioned if c in categorical_cols]
    is_entity_count = bool(re.search(r'\b(students?|employees?|headcount|records?|rows?|people|items?|stores?|count|frequency|distribution|breakdown|split)\b', query, re.I))
    has_by_clause = bool(re.search(r'\b(by|across|breakdown|group|grouped)\b', query, re.I))

    # Also resolve dashboard or follow-up reference to previous chart query
    if not mentioned and re.search(r'\b(dashboard|available on dashboard|previous|that chart|same chart|the chart)\b', query, re.I):
        for prev_q in previous_queries:
            if not prev_q:
                continue
            prev_mentioned = _mentioned_columns(prev_q, columns)
            prev_cats = [c for c in prev_mentioned if c in categorical_cols]
            if prev_cats:
                mentioned_cats = prev_cats
                is_entity_count = True
                break
            prev_metrics = [c for c in prev_mentioned if c in measures]
            if prev_metrics:
                metrics = prev_metrics
                break

    # If no continuous numeric measures are requested, but a categorical dimension is requested for entity distribution:
    if not metrics and mentioned_cats and (is_entity_count or has_by_clause or op == "count"):
        dimension = mentioned_cats[0]
        q_check = (query + " " + (previous_queries[0] if previous_queries else "")).lower()
        entity_name = "Students" if any(w in q_check for w in ["student", "pupil"]) else (
            "Employees" if any(w in q_check for w in ["employee", "staff", "headcount", "worker"]) else (
                "Stores" if "store" in q_check else "Records"
            )
        )
        counts = df[dimension].fillna("(missing)").astype(str).value_counts()
        categories = list(counts.index)
        results = [float(v) for v in counts.values]
        title = f"{entity_name} by {dimension.title()}"
        chart_type = "donut" if len(categories) <= 6 else "column"
        disclosure = f"Total of {len(df):,} {entity_name.lower()} across {len(categories)} categories."
        chart = VisualChartSpec(
            chart_id="CHAT-" + hashlib.sha256(f"{sheet_id}:{entity_name}:{dimension}:count".encode()).hexdigest()[:12],
            chart_type=chart_type,
            title=title,
            subtitle=sheet_name,
            unit="",
            categories=categories,
            series=[ChartSeries(name=f"{entity_name} Count", values=results)],
            metric_col=entity_name,
            dimension_col=dimension,
            aggregation_disclosure=disclosure,
            metadata={"sheet_id": sheet_id, "operation": "count", "valid_rows": len(df)},
        )
        answer = f"### {title}\n\n**{len(df):,} total {entity_name.lower()}** broken down by **{dimension}**:\n\n" + "\n".join(
            [f"- **{cat}**: {int(val):,} ({round(val / max(1, len(df)) * 100, 1)}%)" for cat, val in zip(categories, results)]
        )
        context = {"visualization_context": {"metric": entity_name, "dimension": dimension, "operation": "count", "source_query": query}, "metric": entity_name}
        evidence = {"source_ids": [sheet_id], "metric_definition": entity_name, "calculation_method": "count", "coverage": {"total_rows": len(df), "used_rows": len(df), "missing_rows": 0}}
        return response(answer, [chart.model_dump()], context=context, evidence=evidence)

    if len(metrics) > 1:
        return clarify("Which metric should I chart: " + ", ".join(metrics) + "?")
    metric = metrics[0] if metrics else descriptor.get("metric") if visual else None
    if metric not in measures:
        return clarify("Which numeric metric should I chart? Please name a measure from the selected sheet.")
    op = op or descriptor.get("operation")
    if op not in {"mean", "median", "sum", "min", "max", "count"}:
        return clarify(f"Which calculation should I chart for {metric}: average, total, median, minimum, maximum, or count?")

    dimension = None
    if re.search(r"\b(by|across|breakdown|group)\b", query, re.I):
        dimensions = [c for c in mentioned if c != metric and c not in measures]
        if len(dimensions) != 1:
            return clarify("Which column should I use to group the chart?")
        dimension = dimensions[0]
    elif not metrics:
        dimension = descriptor.get("dimension")
    if dimension and dimension not in columns:
        return clarify("The previous grouping column is unavailable in this sheet. Please choose a grouping column.")

    # Only this bounded grammar is eligible for aggregate calculation. In
    # particular, never discard 'female only', a date window, or a threshold.
    source_query = query if metrics else descriptor.get("source_query", query)
    for text in (query, source_query):
        remainder = _normalized(text)
        for col in sorted(columns, key=lambda c: len(_normalized(c)), reverse=True):
            remainder = re.sub(rf"(?<!\w){re.escape(_normalized(col))}(?!\w)", " ", remainder)
        allowed = {"display", "show", "me", "in", "a", "an", "the", "of", "for", "please", "kindly",
                   "can", "could", "you", "give", "what", "is", "calculate", "compute", "cohort",
                   "overall", "average", "mean", "median", "sum", "total", "minimum", "min", "maximum", "max", "count",
                   "chart", "charts", "graph", "plot", "diagram", "format", "visualize", "visualise", "visualization", "visualisation",
                   "draw", "render", "make", "create", "generate", "based", "on", "using", "with",
                   "it", "this", "that", "these", "as", "bar", "horizontal", "column", "line", "pie", "donut",
                   "by", "across", "breakdown", "group", "grouped", "and", "instead", "now", "again", "to", "convert", "switch", "change"}
        if any(word not in allowed for word in remainder.split()):
            return clarify("This chart request includes a filter or calculation I couldn’t resolve. Please specify an overall metric and calculation, or a breakdown by one column.")

    values = df[metric].map(FactVisualizer._clean_series_value)
    valid = values.dropna()
    if valid.empty:
        return response(f"No valid numeric values are available for {metric}; a chart cannot be drawn.", status="no_data")
    if dimension:
        frame = pd.DataFrame({"category": df[dimension].fillna("(missing)").astype(str), "value": values})
        groups = frame.groupby("category", sort=True)["value"]
        grouped = groups.agg(op)[groups.count() > 0]
        categories, results = list(grouped.index), [float(v) for v in grouped]
    else:
        categories, results = ["Cohort"], [float(valid.agg(op))]

    labels = {"mean": "Average", "median": "Median", "sum": "Total", "min": "Minimum", "max": "Maximum", "count": "Count"}
    label = labels[op]
    title = f"{label} {metric} by {dimension}" if dimension else f"Cohort {label}: {metric}"
    chart_type = "bar" if dimension else "column"
    for word, family in [("column", "column"), ("bar", "bar"), ("line", "line"), ("pie", "pie"), ("donut", "donut")]:
        if re.search(rf"\b{word}\b", query, re.I):
            chart_type = family
    note = ""
    if chart_type in {"pie", "donut"} and (op not in {"sum", "count"} or any(v < 0 for v in results)):
        chart_type = "bar"
        note = " A bar chart is used because these values do not represent additive, non-negative parts of a whole."
    unit = "" if op == "count" else FactVisualizer._infer_unit(metric, profile)
    disclosure = f"{label} of {len(valid):,} valid records; {len(df) - len(valid):,} missing or non-finite values excluded."
    chart = VisualChartSpec(
        chart_id="CHAT-" + hashlib.sha256(f"{sheet_id}:{metric}:{dimension}:{op}".encode()).hexdigest()[:12],
        chart_type=chart_type, title=title, subtitle=sheet_name, unit=unit,
        categories=categories, series=[ChartSeries(name=f"{label} {metric}", values=results)],
        metric_col=metric, dimension_col=dimension, aggregation_disclosure=disclosure,
        metadata={"sheet_id": sheet_id, "operation": op, "valid_rows": len(valid)},
    )
    display_value = f"{results[0]:,.0f}" if op == "count" else f"{results[0]:,.2f}"
    display_value = f"{unit}{display_value}" if unit in {"$", "€", "£", "₹"} else display_value + (f" {unit}" if unit else "")
    answer = f"### {title}\n\n" + (f"**{display_value}**. " if not dimension else "") + disclosure + note
    context = {"visualization_context": {"metric": metric, "dimension": dimension, "operation": op,
                                         "source_query": source_query}, "metric": metric}
    evidence = {"source_ids": [sheet_id], "metric_definition": metric, "calculation_method": op,
                "coverage": {"total_rows": len(df), "used_rows": len(valid), "missing_rows": len(df) - len(valid)}}
    return response(answer, [chart.model_dump()] if visual else [], context=context, evidence=evidence)
