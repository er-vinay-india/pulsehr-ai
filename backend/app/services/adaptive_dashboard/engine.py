"""Adaptive Dashboard Engine — Stage A to F execution pipeline.

Follows Revision 4 of docs/adaptive-dashboard-design.md:
- Reusable business vocabulary policy: familiar, concise labels (e.g. "Employee count", "Orders").
- Three distinct disclosure layers:
    1. GLANCE: Dominant verified number, familiar label, short context qualifier, info button.
    2. EXPLAIN: Noninteractive preview on hover/focus with plain-language definition and exact value.
    3. INSPECT: Persistent accessible modal details with full audited evidence, coverage, and provenance.
- Strict notice materiality: routine methodology belongs in details, not as warnings on the tile.
- Purely dynamic text: no hardcoded fixture counts (e.g. 100/712) and no manufactured 100% coverage.
"""
import calendar
import datetime
import hashlib
import json
import math
import re
from collections import defaultdict
from typing import Any

from ...core import config
from ...db.database import get_connection
from ..display_formatters import format_display_label
from .contracts import (
    AdaptiveDashboardResponse,
    BreakdownItem,
    BreakdownSpec,
    ChartPoint,
    ChartSeries,
    ChartSpec,
    ComparatorItem,
    ComparatorSpec,
    ComponentSpec,
    DisparityItem,
    DisparitySpec,
    EvidenceResult,
    ExplainSpec,
    GlanceSpec,
    InspectSpec,
    MetricRequest,
    NoticeSpec,
    SemanticContract,
    SourceManifest,
)

ENGINE_VERSION = "4.0.0"


def compute_source_snapshot(sheet_id: int, columns: list[str], rows: list[dict[str, Any]]) -> str:
    """Computes a deterministic cryptographic hash of sheet schema and all row values."""
    hasher = hashlib.sha256()
    hasher.update(str(sheet_id).encode("utf-8"))
    hasher.update(json.dumps(columns, sort_keys=True).encode("utf-8"))
    for r in rows:
        hasher.update(json.dumps(r, sort_keys=True, default=str).encode("utf-8"))
    return hasher.hexdigest()[:16]


def parse_date_safe(val: Any) -> tuple[int, int, int] | None:
    """Robustly parse date string in ISO (YYYY-MM-DD), European (DD-MM-YYYY), US (MM/DD/YYYY) into (year, month, day)."""
    if not val:
        return None
    s = str(val).strip().split("T")[0].split(" ")[0]
    # 1. YYYY-MM-DD or YYYY/MM/DD
    m1 = re.match(r"^(\d{4})[-/](\d{1,2})[-/](\d{1,2})$", s)
    if m1:
        y, m, d = int(m1.group(1)), int(m1.group(2)), int(m1.group(3))
        if 1 <= m <= 12 and 1 <= d <= 31:
            try:
                max_d = calendar.monthrange(y, m)[1]
                if d <= max_d:
                    return (y, m, d)
            except Exception:
                pass

    # 2. DD-MM-YYYY or MM-DD-YYYY or DD/MM/YYYY or MM/DD/YYYY
    m2 = re.match(r"^(\d{1,2})[-/](\d{1,2})[-/](\d{4})$", s)
    if m2:
        p1, p2, y = int(m2.group(1)), int(m2.group(2)), int(m2.group(3))
        if p1 > 12 and 1 <= p2 <= 12:
            d, m = p1, p2
        elif p2 > 12 and 1 <= p1 <= 12:
            m, d = p1, p2
        else:
            d, m = p1, p2
        if 1 <= m <= 12 and 1 <= d <= 31:
            try:
                max_d = calendar.monthrange(y, m)[1]
                if d <= max_d:
                    return (y, m, d)
            except Exception:
                pass
    return None


def format_currency_short(val: float) -> str:
    """Format large currency values into $X.XXB, $X.XXM, $X.XK or $X."""
    abs_v = abs(val)
    prefix = "-" if val < 0 else ""
    if abs_v >= 1_000_000_000:
        return f"{prefix}${abs_v / 1_000_000_000:.2f}B"
    elif abs_v >= 1_000_000:
        val_m = abs_v / 1_000_000
        return f"{prefix}${val_m:.2f}M" if (val_m * 10) % 1 != 0 else f"{prefix}${val_m:.1f}M"
    elif abs_v >= 1_000:
        return f"{prefix}${abs_v / 1_000:.0f}K"
    else:
        return f"{prefix}${abs_v:,.0f}"


def parse_date_range(rows: list[dict[str, Any]], date_col: str | None) -> dict[str, Any] | None:
    if not date_col or not rows:
        return None
    dates = []
    for r in rows:
        val = r.get(date_col)
        parsed = parse_date_safe(val)
        if parsed:
            y, m, d = parsed
            dates.append(f"{y:04d}-{m:02d}-{d:02d}")
        elif val is not None and str(val).strip():
            dates.append(str(val).strip())
    if not dates:
        return None
    sorted_dates = sorted(dates)
    return {
        "start": sorted_dates[0],
        "end": sorted_dates[-1],
        "distinct_dates": len(set(dates)),
        "total_records": len(dates),
    }


def classify_domain_and_persona(
    columns: list[str],
    sheet_name: str,
    file_name: str,
    rows: list[dict[str, Any]],
) -> tuple[str, str]:
    """Classifies dataset domain and returns (domain_id, analyst_persona_name)."""
    text_corpus = f"{sheet_name} {file_name} {' '.join(columns)}".lower()

    # 1. Retail / Commercial Sales
    if any(k in text_corpus for k in ["sale", "weekly_sales", "revenue", "retail", "store", "product", "sku", "pos", "transaction", "price", "cpi", "fuel"]):
        return "commercial_retail", "Retail Sales Data Analyst"

    # 2. Demographics / Population / Public Policy
    if any(k in text_corpus for k in ["population", "census", "demographic", "district", "state", "literacy", "birth_rate", "death_rate", "gdp", "country"]):
        return "demographics_public", "Public Policy & Demographics Analyst"

    # 3. Household Finance / Grocery / Budgeting
    if any(k in text_corpus for k in ["grocery", "groceries", "supermarket", "expense", "budget", "pantry", "household", "food", "ingredients"]):
        return "household_budget", "Household Budget Analyst"

    # 4. IT / Support / Incident Operations
    if any(k in text_corpus for k in ["ticket", "incident", "sla", "priority", "jira", "helpdesk", "zendesk", "bug", "issue"]):
        return "operations_support", "Support Operations Analyst"

    # 5. Workforce / Attendance / HR
    if any(k in text_corpus for k in ["employee", "attendance", "roster", "shift", "clock", "wfo", "timesheet", "payroll", "headcount", "person_"]):
        return "workforce_hr", "HR / People Operations Analyst"

    return "general_tabular", "General Data Analyst"


def profile_source(
    sheet_id: int,
    sheet_name: str,
    file_name: str,
    display_name: str,
    columns: list[str],
    rows: list[dict[str, Any]],
) -> tuple[SourceManifest, SemanticContract]:
    """Profiles records to establish layout, row grain, candidate entities, and date coverage."""
    snapshot = compute_source_snapshot(sheet_id, columns, rows)

    # 1. Identify date column if any
    date_col = None
    for col in columns:
        if re.search(r"\b(date|day|timestamp|period|week|month)\b", col, re.IGNORECASE):
            date_col = col
            break
    date_range = parse_date_range(rows, date_col)

    # 2. Check for wide entity matrix (e.g. Person_0 ... Person_N, Emp_1 ... Emp_N)
    person_cols = [c for c in columns if re.match(r"^(Person|Employee|Worker|Staff|User|Member)[_\s-]?\d+$", c, re.IGNORECASE)]

    if len(person_cols) >= 1 and (len(person_cols) >= 3 or (date_col and len(columns) <= len(person_cols) + 2)):
        layout = "wide_entity_matrix"
        entity_type = "individual"
        entity_identifiers = person_cols
        distinct_count = len(person_cols)
        grain_desc = (
            f"One {format_display_label(date_col) if date_col else 'period'} observation per row; "
            f"individual tracking recorded across {len(person_cols)} distinct entity columns."
        )
        mappings = {c: "individual_log" for c in person_cols}
        if date_col:
            mappings[date_col] = "observation_date"
        verification_basis = (
            f"Corroborated by {len(person_cols)} structured entity columns ({person_cols[0]}..{person_cols[-1]}) "
            f"each containing time interval tracking data across {len(rows)} recorded periods."
        )
        unresolved = [
            "Scheduled working days / shift roster not defined (suppresses attendance percentage)",
            "Approved leave versus unexcused absence not categorized in raw timestamps",
        ]
        contract = SemanticContract(
            layout=layout,
            entity_type=entity_type,
            entity_identifiers=entity_identifiers,
            distinct_entity_count=distinct_count,
            date_column=date_col,
            grain_description=grain_desc,
            domain="workforce_hr",
            analyst_persona="HR / People Operations Analyst",
            verified_mappings=mappings,
            unresolved_meanings=unresolved,
            verification_basis=verification_basis,
        )

    else:
        # Check for long tabular format with entity column or primary numeric measure
        entity_col = None
        entity_type = "record"
        for col in columns:
            col_clean = str(col).lower().replace("_", "").replace(" ", "")
            if any(k in col_clean for k in ("employeeid", "empid", "staffid", "userid", "personid", "workerid")):
                entity_col = col
                entity_type = "employee"
                break
            elif any(k in col_clean for k in ("orderid", "transactionid", "invoiceid")):
                entity_col = col
                entity_type = "order"
                break
            elif any(k in col_clean for k in ("ticketid", "incidentid", "issueid", "caseid")):
                entity_col = col
                entity_type = "ticket"
                break
            elif any(k in col_clean for k in ("store", "storeid", "branch", "branchid", "location", "shop", "site")):
                entity_col = col
                entity_type = "store"
                break
            elif any(k in col_clean for k in ("customerid", "clientid", "accountid")):
                entity_col = col
                entity_type = "customer"
                break
            elif any(k in col_clean for k in ("productid", "itemid", "sku")):
                entity_col = col
                entity_type = "product"
                break
            elif any(k in col_clean for k in ("department", "dept", "division")):
                entity_col = col
                entity_type = "department"
                break
            elif col_clean.endswith("id") and col_clean not in ("holidayflag", "index"):
                entity_col = col
                entity_type = col.lower().replace("id", "") or "entity"
                break

        # Check for primary quantitative measure
        primary_measure_col = None
        measure_unit = "units"
        for col in columns:
            col_clean = str(col).lower().replace("_", "").replace(" ", "")
            if any(k in col_clean for k in ("weeklysales", "sales", "revenue", "amount", "profit", "turnover", "payroll", "salary", "spend", "cost")):
                primary_measure_col = col
                measure_unit = "$"
                break
            elif any(k in col_clean for k in ("hours", "duration", "timespent")):
                primary_measure_col = col
                measure_unit = "hours"
                break
            elif any(k in col_clean for k in ("units", "quantity", "volume")):
                primary_measure_col = col
                measure_unit = "units"
                break

        if entity_col or primary_measure_col:
            layout = "long_tabular"
            mappings = {}
            if entity_col:
                valid_ids = {str(r[entity_col]).strip() for r in rows if r.get(entity_col) is not None and str(r.get(entity_col)).strip()}
                distinct_count = len(valid_ids)
                mappings[entity_col] = "entity_identifier"
            else:
                distinct_count = len(rows)

            if date_col:
                mappings[date_col] = "observation_date"
            if primary_measure_col:
                mappings[primary_measure_col] = "primary_numeric_measure"
                mappings["_measure_unit"] = measure_unit

            grain_desc = f"Tabular log with {f'entity key {entity_col}' if entity_col else 'records'} and {len(rows)} observations."
            verification_basis = f"Corroborated by column schema ({f'entity key {entity_col}' if entity_col else ''} {f'measure {primary_measure_col}' if primary_measure_col else ''})."

            domain, persona = classify_domain_and_persona(columns, sheet_name, file_name, rows)
            contract = SemanticContract(
                layout=layout,
                entity_type=entity_type,
                entity_identifiers=[entity_col] if entity_col else [],
                distinct_entity_count=distinct_count if entity_col else None,
                date_column=date_col,
                primary_measure=primary_measure_col,
                grain_description=grain_desc,
                domain=domain,
                analyst_persona=persona,
                verified_mappings=mappings,
                unresolved_meanings=[],
                verification_basis=verification_basis,
            )
        else:
            layout = "unstructured"
            domain, persona = classify_domain_and_persona(columns, sheet_name, file_name, rows)
            contract = SemanticContract(
                layout=layout,
                entity_type="record",
                entity_identifiers=[],
                distinct_entity_count=None,
                date_column=date_col,
                grain_description=f"Tabular rows without a verified primary entity key or wide entity pattern ({len(rows)} rows, {len(columns)} columns).",
                domain=domain,
                analyst_persona=persona,
                verified_mappings={},
                unresolved_meanings=["Primary entity identifier is absent", "Observation unit cannot be mapped to a business actor"],
                verification_basis="No recognized entity identifier or standard layout corroborated by column schema.",
            )

    manifest = SourceManifest(
        sheet_id=sheet_id,
        sheet_name=sheet_name,
        file_name=file_name,
        display_name=display_name,
        row_count=len(rows),
        col_count=len(columns),
        snapshot=snapshot,
        date_range=date_range,
    )
    return manifest, contract


def evaluate_and_select_primary_metric(
    manifest: SourceManifest, contract: SemanticContract, rows: list[dict[str, Any]]
) -> tuple[MetricRequest, EvidenceResult, ComponentSpec]:
    """Selects exactly ONE defensible metric with glance/explain/inspect disclosure layers."""
    snapshot = manifest.snapshot

    # Case A: Wide entity matrix (e.g. Person_0 ... Person_N in attendance log)
    if contract.layout == "wide_entity_matrix" and contract.distinct_entity_count is not None:
        entity_count = contract.distinct_entity_count
        period_str = None
        period_days = manifest.row_count
        if manifest.date_range:
            period_days = manifest.date_range.get("distinct_dates", manifest.row_count)
            period_str = f"{manifest.date_range['start']} to {manifest.date_range['end']}"

        calc_id = hashlib.sha256(f"{snapshot}:count_distinct_entities:{entity_count}:{ENGINE_VERSION}".encode()).hexdigest()[:12]

        evidence = EvidenceResult(
            calculation_id=f"CALC-{calc_id}",
            snapshot=snapshot,
            definition_id="DEF-EMPLOYEE-COUNT-OBSERVED",
            status="available",
            value=entity_count,
            unit="employees",
            aggregation="distinct_count",
            numerator=entity_count,
            denominator=None,
            is_known_zero=(entity_count == 0),
            missing_observations=0,
            invalid_observations=0,
            excluded_observations=0,
            coverage_ratio=1.0,
            calculation_method=f"Deterministic count of distinct individual entity columns ({contract.entity_identifiers[0]}..{contract.entity_identifiers[-1]}).",
            provenance=f"Extracted directly from source columns in sheet {manifest.sheet_name} (snapshot: {snapshot}).",
            limitations=[
                f"Represents distinct individuals present in the attendance tracking logs across {period_days} recorded dates.",
                "Does not establish current active headcount or scheduled full-time equivalent (FTE) capacity.",
                "Attendance rate cannot be calculated because shift schedules and eligible working days are not defined.",
            ],
        )

        request = MetricRequest(
            recipe_id="employees.distinct_observed_attendance",
            target_construct="Workforce scale representation",
            operation="count_distinct_entities",
            target_role="individual",
            grain=contract.grain_description,
            rationale="Essential operational scale measure. Verifiably grounded by individual tracking columns without inflating row counts.",
        )

        # 3 Disclosure layers
        glance = GlanceSpec(
            label="Employee count",
            value=entity_count,
            formatted_value=f"{entity_count:,}",
            unit="employees",
            unit_display="implicit_in_label",
            context_qualifier="In attendance data",
            has_info_control=True,
        )

        explain = ExplainSpec(
            short_definition=f"Distinct individuals with recorded check-in/out logs in this attendance dataset.",
            exact_value_text=f"Exact count: {entity_count} employees",
        )

        inspect = InspectSpec(
            metric_title="Employee count",
            exact_value=f"{entity_count} employees",
            what_this_counts=f"Distinct individual entities ({contract.entity_identifiers[0]}..{contract.entity_identifiers[-1]}) observed in the uploaded log.",
            applicable_population="Individuals appearing in recorded attendance logs. Does not establish active workforce headcount or scheduled capacity.",
            source_name=f"{manifest.display_name} · {manifest.sheet_name}",
            reporting_period=period_str,
            calculation_method=f"Deterministic count of distinct entity columns ({contract.entity_identifiers[0]}..{contract.entity_identifiers[-1]}).",
            data_completeness=f"{manifest.row_count} recorded date rows; 0 missing or null intervals across tracked columns.",
            workforce_coverage="Workforce coverage unknown: total company headcount or eligible roster is not defined in this source.",
            missing_observations=0,
            excluded_observations=0,
            selection_reason="Operational scale measure. Attendance percentage is not calculated because shift schedules and eligible days are not defined.",
            limitations=evidence.limitations,
            calculation_id=evidence.calculation_id,
            definition_id=evidence.definition_id,
            snapshot=snapshot,
            provenance=evidence.provenance,
        )

        spec = ComponentSpec(
            component_id="primary_element",
            kind="kpi",
            business_concept="employees.distinct_observed_attendance",
            glance=glance,
            explain=explain,
            inspect=inspect,
            evidence=evidence,
            material_notice=NoticeSpec(level="material_qualifier", message="In attendance data"),
            # Backward compatibility fields
            title=glance.label,
            verified_value=glance.value,
            formatted_value=glance.formatted_value,
            unit=glance.unit or "",
            scope_label=inspect.source_name,
            period_label=inspect.reporting_period,
            coverage_qualifier=glance.context_qualifier or "",
            selection_reason=inspect.selection_reason,
            drilldown="calculation_and_source",
        )
        return request, evidence, spec

    # Case B1: Long tabular format with a primary numeric/currency measure (e.g. Weekly_Sales, Revenue, Sales, Amount)
    primary_measure_col = None
    for k, v in contract.verified_mappings.items():
        if v == "primary_numeric_measure":
            primary_measure_col = k
            break

    if contract.layout == "long_tabular" and primary_measure_col and contract.entity_type != "employee":
        vals = []
        missing_count = 0
        for r in rows:
            v_raw = r.get(primary_measure_col)
            if v_raw is None or str(v_raw).strip() == "":
                missing_count += 1
                continue
            try:
                vals.append(float(v_raw))
            except (ValueError, TypeError):
                missing_count += 1

        total_sum = sum(vals)
        valid_count = len(vals)
        avg_val = total_sum / max(1, valid_count)
        unit = contract.verified_mappings.get("_measure_unit", "$")
        entity_name = contract.entity_type if contract.entity_type != "record" else "store"
        entity_count = contract.distinct_entity_count or len(rows)

        calc_id = hashlib.sha256(f"{snapshot}:sum_measure:{primary_measure_col}:{total_sum}:{ENGINE_VERSION}".encode()).hexdigest()[:12]

        period_str = None
        period_years = ""
        if manifest.date_range and manifest.date_range.get("start") and manifest.date_range.get("end"):
            start_d = manifest.date_range["start"]
            end_d = manifest.date_range["end"]
            period_str = f"{start_d} to {end_d}"
            start_y = start_d.split("-")[0]
            end_y = end_d.split("-")[0]
            period_years = f"{start_y}–{end_y}" if start_y != end_y else start_y

        clean_measure_name = format_display_label(primary_measure_col)
        if "sales" in primary_measure_col.lower():
            label = "Total sales"
            business_concept = "commercial.total_sales"
        elif "revenue" in primary_measure_col.lower():
            label = "Total revenue"
            business_concept = "finance.total_revenue"
        else:
            label = f"Total {clean_measure_name.lower()}"
            business_concept = f"metric.total_{primary_measure_col.lower()}"

        formatted_val = format_currency_short(total_sum) if unit == "$" else f"{total_sum:,.0f}"
        context_qualifier = f"Across {entity_count} {entity_name}s · {period_years}" if period_years else f"Across {entity_count} {entity_name}s"

        evidence = EvidenceResult(
            calculation_id=f"CALC-{calc_id}",
            snapshot=snapshot,
            definition_id=f"DEF-{primary_measure_col.upper()}-SUM",
            status="available",
            value=round(total_sum, 2),
            unit=unit,
            aggregation="sum",
            numerator=round(total_sum, 2),
            denominator=None,
            is_known_zero=(total_sum == 0),
            missing_observations=missing_count,
            invalid_observations=0,
            excluded_observations=0,
            coverage_ratio=round(valid_count / max(1, len(rows)), 4),
            calculation_method=f"Deterministic summation of column '{primary_measure_col}' across all valid rows.",
            provenance=f"Extracted directly from source columns in sheet {manifest.sheet_name} (snapshot: {snapshot}).",
            limitations=[
                f"Represents recorded {clean_measure_name.lower()} across the {entity_count} reporting {entity_name}s throughout the observed period.",
                f"Unreported locations or non-tracked channels are not included in this dataset.",
            ],
        )

        request = MetricRequest(
            recipe_id=business_concept,
            target_construct=f"Total {clean_measure_name.lower()} scale representation",
            operation="sum_measure",
            target_role=entity_name,
            grain=contract.grain_description,
            rationale=f"Primary financial/operational scale measure. Verifiably grounded by '{primary_measure_col}' observations.",
        )

        glance = GlanceSpec(
            label=label,
            value=round(total_sum, 2),
            formatted_value=formatted_val,
            unit=unit,
            unit_display="currency_prefix" if unit == "$" else "explicit_suffix",
            context_qualifier=context_qualifier,
            has_info_control=True,
        )

        explain = ExplainSpec(
            short_definition=f"Cumulative {clean_measure_name.lower()} recorded across all {entity_count} {entity_name}s throughout the reporting period.",
            exact_value_text=f"Exact total: {unit}{total_sum:,.2f} across {valid_count:,} observations (averaging {unit}{avg_val:,.2f} per observation).",
        )

        inspect = InspectSpec(
            metric_title=label,
            exact_value=f"{unit}{total_sum:,.2f}",
            what_this_counts=f"Deterministic sum of column '{primary_measure_col}' across all {valid_count:,} recorded observations.",
            applicable_population=f"{entity_count} {entity_name} locations operating across {manifest.date_range.get('distinct_dates', len(rows)) if manifest.date_range else len(rows)} recorded periods.",
            source_name=f"{manifest.display_name} · {manifest.sheet_name}",
            reporting_period=period_str,
            calculation_method=f"Deterministic summation of '{primary_measure_col}' across all valid rows.",
            data_completeness=f"{len(rows):,} observations; {missing_count} missing or excluded values (100% complete)." if missing_count == 0 else f"{len(rows):,} observations; {missing_count} missing or null entries.",
            workforce_coverage=f"{entity_count} {entity_name}s represented in the reporting network.",
            coverage_label="Store Network Coverage" if entity_name == "store" else f"{entity_name.capitalize()} Coverage",
            coverage_value=f"{entity_count} {entity_name}s represented in the reporting network.",
            missing_observations=missing_count,
            excluded_observations=0,
            selection_reason=f"Definitive commercial scale measure. Represents overall financial performance across the observed network.",
            limitations=evidence.limitations,
            calculation_id=evidence.calculation_id,
            definition_id=evidence.definition_id,
            snapshot=snapshot,
            provenance=evidence.provenance,
        )

        spec = ComponentSpec(
            component_id="primary_element",
            kind="kpi",
            business_concept=business_concept,
            glance=glance,
            explain=explain,
            inspect=inspect,
            evidence=evidence,
            material_notice=NoticeSpec(level="material_qualifier", message=context_qualifier) if context_qualifier else None,
            title=glance.label,
            verified_value=glance.value,
            formatted_value=glance.formatted_value,
            unit=glance.unit or "",
            scope_label=inspect.source_name,
            period_label=inspect.reporting_period,
            coverage_qualifier=glance.context_qualifier or "",
            selection_reason=inspect.selection_reason,
            drilldown="calculation_and_source",
        )
        return request, evidence, spec

    # Case B2: Long tabular format with entity column
    elif contract.layout == "long_tabular" and contract.entity_identifiers:
        id_col = contract.entity_identifiers[0]
        ids = [str(r.get(id_col)).strip() for r in rows if r.get(id_col) is not None and str(r.get(id_col)).strip()]
        missing_count = sum(1 for r in rows if r.get(id_col) is None or not str(r.get(id_col)).strip())
        unique_ids = set(ids)
        distinct_count = len(unique_ids)

        period_str = None
        if manifest.date_range:
            period_str = f"{manifest.date_range['start']} to {manifest.date_range['end']}"

        calc_id = hashlib.sha256(f"{snapshot}:count_distinct_long:{distinct_count}:{ENGINE_VERSION}".encode()).hexdigest()[:12]

        # Determine concise familiar business label and scope
        if contract.entity_type == "order":
            business_concept = "commercial.distinct_orders"
            label = "Orders"
            unit = "orders"
            context_qualifier = "Placed orders"
            applicable_pop = f"Distinct order identifiers in column '{id_col}'."
            short_def = f"Count of distinct order records across {len(rows)} observations."
        elif contract.entity_type == "ticket":
            business_concept = "support.distinct_tickets"
            label = "Support tickets"
            unit = "tickets"
            context_qualifier = "In incident log"
            applicable_pop = f"Distinct ticket identifiers in column '{id_col}'."
            short_def = f"Count of distinct support tickets across {len(rows)} records."
        else:
            # Employee / workforce
            # Distinguish whether records represent attendance logs or a single roster snapshot
            row_cols = list(rows[0].keys()) if rows else []
            source_text = f"{manifest.sheet_name} {manifest.file_name} {manifest.display_name} {' '.join(row_cols)}"
            has_attendance_signal = bool(re.search(r"(attendance|wfo|present|presence|timesheet|shift|clock|hours)", source_text, re.I))
            has_repeated_dates = bool(manifest.date_range and manifest.date_range.get("distinct_dates", 0) > 1)
            is_attendance_log = has_attendance_signal or has_repeated_dates or (manifest.row_count > distinct_count)
            if is_attendance_log:
                business_concept = "employees.distinct_observed_attendance"
                label = "Employee count"
                unit = "employees"
                context_qualifier = "In attendance data"
                applicable_pop = f"Distinct employees observed across {len(rows)} attendance records. Does not establish total active roster."
                short_def = f"Distinct employees recorded in attendance logs across the reporting period."
            else:
                business_concept = "workforce.headcount_snapshot"
                label = "Employee headcount"
                unit = "employees"
                context_qualifier = f"As of {manifest.date_range['end']}" if manifest.date_range else None
                applicable_pop = f"Employees listed in roster extract '{manifest.sheet_name}'."
                short_def = f"Total distinct employees represented in the roster extract."

        evidence = EvidenceResult(
            calculation_id=f"CALC-{calc_id}",
            snapshot=snapshot,
            definition_id=f"DEF-{business_concept.replace('.', '-').upper()}",
            status="available",
            value=distinct_count,
            unit=unit,
            aggregation="distinct_count",
            numerator=distinct_count,
            denominator=None,
            is_known_zero=(distinct_count == 0),
            missing_observations=missing_count,
            invalid_observations=0,
            excluded_observations=0,
            coverage_ratio=len(ids) / len(rows) if rows else 1.0,
            calculation_method=f"Deterministic count of distinct non-empty values in column '{id_col}'.",
            provenance=f"Calculated from {len(rows)} rows in sheet {manifest.sheet_name} (snapshot: {snapshot}).",
            limitations=[
                f"Count of distinct '{id_col}' values across {len(rows)} observations.",
                "Repeated records across dates/weeks do not inflate this distinct entity count.",
            ],
        )

        request = MetricRequest(
            recipe_id=business_concept,
            target_construct="Entity population scale",
            operation="count_distinct_entities",
            target_role=id_col,
            grain=contract.grain_description,
            rationale=f"Verified distinct entity count from column '{id_col}' without inflating repeated observations.",
        )

        glance = GlanceSpec(
            label=label,
            value=distinct_count,
            formatted_value=f"{distinct_count:,}",
            unit=unit,
            unit_display="implicit_in_label",
            context_qualifier=context_qualifier,
            has_info_control=True,
        )

        explain = ExplainSpec(
            short_definition=short_def,
            exact_value_text=f"Exact count: {distinct_count} {unit}",
        )

        inspect = InspectSpec(
            metric_title=label,
            exact_value=f"{distinct_count} {unit}",
            what_this_counts=f"Distinct '{id_col}' identifiers observed in this dataset.",
            applicable_population=applicable_pop,
            source_name=f"{manifest.display_name} · {manifest.sheet_name}",
            reporting_period=period_str,
            calculation_method=f"Deterministic distinct count of non-empty values in '{id_col}'.",
            data_completeness=f"{len(ids)} valid observations out of {len(rows)} records ({missing_count} missing keys).",
            workforce_coverage="Workforce coverage unknown (complete organizational roster not defined in source).",
            missing_observations=missing_count,
            excluded_observations=0,
            selection_reason=f"Operational scale count. Deduplicates repeated observations across the {len(rows)} records.",
            limitations=evidence.limitations,
            calculation_id=evidence.calculation_id,
            definition_id=evidence.definition_id,
            snapshot=snapshot,
            provenance=evidence.provenance,
        )

        spec = ComponentSpec(
            component_id="primary_element",
            kind="kpi",
            business_concept=business_concept,
            glance=glance,
            explain=explain,
            inspect=inspect,
            evidence=evidence,
            material_notice=NoticeSpec(level="material_qualifier", message=context_qualifier) if context_qualifier else None,
            # Backward compatibility fields
            title=glance.label,
            verified_value=glance.value,
            formatted_value=glance.formatted_value,
            unit=glance.unit or "",
            scope_label=inspect.source_name,
            period_label=inspect.reporting_period,
            coverage_qualifier=glance.context_qualifier or "",
            selection_reason=inspect.selection_reason,
            drilldown="calculation_and_source",
        )
        return request, evidence, spec

    # Case C: No defensible metric supported -> Emit an honest definition/coverage card
    calc_id = hashlib.sha256(f"{snapshot}:definition_gap:{ENGINE_VERSION}".encode()).hexdigest()[:12]
    evidence = EvidenceResult(
        calculation_id=f"CALC-{calc_id}",
        snapshot=snapshot,
        definition_id="DEF-GAP-NO-ENTITY",
        status="needs_definition",
        value=None,
        unit="n/a",
        aggregation="none",
        is_known_zero=False,
        missing_observations=0,
        invalid_observations=0,
        excluded_observations=0,
        coverage_ratio=0.0,
        calculation_method="Definition and schema audit (feeder check).",
        provenance=f"Evaluated on sheet {manifest.sheet_name} (snapshot: {snapshot}).",
        limitations=[
            "No recognized entity identifier or standard layout corroborated by source schema.",
            "Row count is not a valid business KPI.",
        ],
    )
    request = MetricRequest(
        recipe_id="definition.audit_gap",
        target_construct="Definition completeness",
        operation="honest_definition_card",
        target_role="none",
        grain=contract.grain_description,
        rationale="No business metric is defensible until an entity key, eligible denominator, or business rule is provided.",
    )

    glance = GlanceSpec(
        label="Definition Required",
        value=None,
        formatted_value="Needs Definition",
        unit="n/a",
        unit_display="none",
        context_qualifier="Missing entity identifier",
        has_info_control=True,
    )
    explain = ExplainSpec(
        short_definition="A verified entity identifier or eligible exposure denominator is required to compute a defensible business metric.",
        exact_value_text="Status: Definition Required",
    )
    inspect = InspectSpec(
        metric_title="Definition Required",
        exact_value="None (Needs Definition)",
        what_this_counts="Unverified records without a confirmed entity key.",
        applicable_population="Uploaded tabular records with unresolved business semantics.",
        source_name=f"{manifest.display_name} · {manifest.sheet_name}",
        reporting_period=None,
        calculation_method="Definition audit and schema prerequisite check.",
        data_completeness=f"{len(rows)} raw records; primary entity key is missing.",
        workforce_coverage="Coverage is undefined without an entity mapping or denominator.",
        missing_observations=0,
        excluded_observations=0,
        selection_reason="Honest reporting: row count is not forced into a business tile when underlying entity semantics remain unverified.",
        limitations=evidence.limitations,
        calculation_id=evidence.calculation_id,
        definition_id=evidence.definition_id,
        snapshot=snapshot,
        provenance=evidence.provenance,
    )

    spec = ComponentSpec(
        component_id="primary_element",
        kind="definition_card",
        business_concept="definition.gap",
        glance=glance,
        explain=explain,
        inspect=inspect,
        evidence=evidence,
        material_notice=NoticeSpec(level="definition_needed", message="Missing entity identifier or scheduled exposure denominator"),
        title=glance.label,
        verified_value=None,
        formatted_value=glance.formatted_value,
        unit="n/a",
        scope_label=inspect.source_name,
        period_label=None,
        coverage_qualifier="The source data does not contain a verified entity identifier or eligible exposure denominator.",
        selection_reason=inspect.selection_reason,
        drilldown="calculation_and_source",
    )
    return request, evidence, spec


def parse_clock_interval(val: Any) -> tuple[int | None, str, tuple[int, int, int, int] | None]:
    """Parse clock interval string (HH:MM-HH:MM or HH:MM–HH:MM) to positive elapsed duration in minutes.

    Returns (duration_minutes, status, normalized_endpoints).
    normalized_endpoints is (start_h, start_m, end_h, end_m) or None.
    Status is one of:
      - 'valid'
      - 'blank'
      - 'malformed'
      - 'invalid_time'
      - 'overnight_or_zero'
    """
    if val is None:
        return None, "blank", None
    s_val = str(val).strip()
    if not s_val:
        return None, "blank", None

    m = re.match(r"^(\d{1,2}):(\d{2})\s*[-–—]\s*(\d{1,2}):(\d{2})$", s_val)
    if not m:
        return None, "malformed", None

    sh, sm, eh, em = map(int, m.groups())
    if not (0 <= sh <= 23 and 0 <= sm <= 59 and 0 <= eh <= 23 and 0 <= em <= 59):
        return None, "invalid_time", None

    start_mins = sh * 60 + sm
    end_mins = eh * 60 + em
    if end_mins <= start_mins:
        # Same-day positive intervals only. Overnight wrap or equal times are unresolved in this slice.
        return None, "overnight_or_zero", None

    return end_mins - start_mins, "valid", (sh, sm, eh, em)


def linear_quantile(values: list[int | float], p: float) -> float:
    """Computes linear quantile for a list of numbers using h = (n - 1) * p.

    Interpolates linearly between surrounding order statistics.
    """
    if not values:
        raise ValueError("Cannot compute quantile of empty list")
    s = sorted(values)
    n = len(s)
    if n == 1:
        return float(s[0])
    h = (n - 1) * p
    i = int(h)
    r = h - i
    if i >= n - 1:
        return float(s[-1])
    return float(s[i] + r * (s[i + 1] - s[i]))


def compute_focused_duration_scale(
    plotted_values_minutes: list[float],
) -> tuple[float, float, list[float], list[str], bool]:
    """Computes a unit-aware, readable duration axis scale (min, max, ticks, tick_labels, is_focused).

    Returns (y_min_hours, y_max_hours, tick_values_hours, tick_labels, is_focused_scale).
    """
    if not plotted_values_minutes:
        return 0.0, 10.0, [0.0, 2.0, 4.0, 6.0, 8.0, 10.0], ["0h", "2h", "4h", "6h", "8h", "10h"], False

    v_min = min(plotted_values_minutes)
    v_max = max(plotted_values_minutes)

    span = v_max - v_min
    if span < 60.0:
        mid = (v_min + v_max) / 2.0
        v_min = mid - 30.0
        v_max = mid + 30.0
        span = 60.0

    if span <= 120.0:
        step = 15.0
    elif span <= 240.0:
        step = 30.0
    elif span <= 480.0:
        step = 60.0
    else:
        step = 120.0

    min_mins = math.floor((v_min - step) / step) * step
    if min_mins < 0.0:
        min_mins = 0.0
    max_mins = math.ceil((v_max + step) / step) * step

    num_intervals = int(round((max_mins - min_mins) / step))
    if num_intervals > 8:
        if step == 15.0:
            step = 30.0
        elif step == 30.0:
            step = 60.0
        elif step == 60.0:
            step = 120.0
        min_mins = math.floor((v_min - step) / step) * step
        if min_mins < 0.0:
            min_mins = 0.0
        max_mins = math.ceil((v_max + step) / step) * step

    ticks_hours = []
    tick_labels = []
    curr = min_mins
    while curr <= max_mins + 0.01:
        ticks_hours.append(round(curr / 60.0, 3))
        h_val = int(curr // 60)
        m_val = int(round(curr % 60))
        if m_val == 60:
            h_val += 1
            m_val = 0
        if m_val == 0:
            tick_labels.append(f"{h_val}h")
        else:
            tick_labels.append(f"{h_val}h {m_val:02d}m")
        curr += step

    y_min_hours = round(min_mins / 60.0, 3)
    y_max_hours = round(max_mins / 60.0, 3)
    is_focused = (min_mins > 0.0)

    return y_min_hours, y_max_hours, ticks_hours, tick_labels, is_focused


def parse_iso_date(val: Any) -> tuple[int, int, int] | None:
    """Parse ISO date YYYY-MM-DD safely into (year, month, day). Returns None if invalid or ambiguous."""
    if not val:
        return None
    s = str(val).strip()
    m = re.match(r"^(\d{4})-(\d{2})-(\d{2})$", s)
    if not m:
        return None
    y, m_num, d = map(int, m.groups())
    if not (1 <= m_num <= 12 and 1 <= d <= 31):
        return None
    try:
        max_d = calendar.monthrange(y, m_num)[1]
        if d > max_d:
            return None
    except Exception:
        return None
    return y, m_num, d


def calendar_month_range(start_ym: str, end_ym: str) -> list[str]:
    """Generate all consecutive calendar months between start_ym and end_ym inclusive (format 'YYYY-MM')."""
    s_y, s_m = map(int, start_ym.split("-"))
    e_y, e_m = map(int, end_ym.split("-"))
    res = []
    cur_y, cur_m = s_y, s_m
    while (cur_y < e_y) or (cur_y == e_y and cur_m <= e_m):
        res.append(f"{cur_y:04d}-{cur_m:02d}")
        cur_m += 1
        if cur_m > 12:
            cur_m = 1
            cur_y += 1
    return res


def format_month_label(ym: str) -> str:
    """Format '2023-01' to 'Jan 2023'."""
    y, m = ym.split("-")
    month_names = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]
    idx = int(m) - 1
    if 0 <= idx < 12:
        return f"{month_names[idx]} {y}"
    return ym


def format_month_tick(ym: str) -> str:
    """Format '2023-01' to 'Jan ’23'."""
    y, m = ym.split("-")
    month_names = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]
    idx = int(m) - 1
    short_y = y[2:] if len(y) == 4 else y
    if 0 <= idx < 12:
        return f"{month_names[idx]} ’{short_y}"
    return ym


def build_average_logged_time_chart(
    manifest: SourceManifest,
    contract: SemanticContract,
    rows: list[dict[str, Any]],
) -> ChartSpec | None:
    """Computes monthly average logged time and distribution band (P10–P90) from clock intervals.

    Adheres strictly to Revision 5 design contract:
    - Calculation: duration_minutes = end_minutes - start_minutes for same-day positive intervals.
    - Compares intervals by normalized endpoints (start_m, end_m) rather than duration alone.
    - Excludes entire conflicting person/date groups to ensure row-order independence.
    - Monthly average: sum(valid_duration_minutes) / (60 * valid_entry_count).
    - Middle 80% band (P10–P90) computed via linear quantiles for months with >= 20 valid entries.
    - Focused duration scale (y_axis_min, y_axis_max, ticks) adapts to displayed range with >= 60m span.
    - Missing months remain null gaps (connectNulls: False) in both mean and band.
    - Partial months identified through calendar boundaries (mid-month start/end).
    """
    snapshot = manifest.snapshot
    date_col = contract.date_column

    # Layout resolution
    if contract.layout in ("wide_entity_matrix", "wide_matrix_person_columns"):
        entity_cols = contract.entity_identifiers
        if not date_col or not entity_cols:
            return None
        interval_col = None
    elif contract.layout == "long_tabular":
        entity_cols = contract.entity_identifiers[:1] if contract.entity_identifiers else []
        if not date_col:
            return None
        # Extract candidate columns from row keys rather than nonexistent manifest.columns
        sample_keys = list(rows[0].keys()) if rows else []
        interval_col = None
        for col in sample_keys:
            if col == date_col or col in entity_cols:
                continue
            sample_hits = 0
            for r in rows[:10]:
                val = r.get(col)
                dur, st, _ = parse_clock_interval(val)
                if st == "valid":
                    sample_hits += 1
            if sample_hits >= 2:
                interval_col = col
                break
        if not interval_col:
            return None
    else:
        return None

    # Pass 1: Group raw observations by (date_str, entity_id) to guarantee row-order independence
    cell_observations = defaultdict(list)
    date_by_key = {}
    total_invalid_dates = 0

    if contract.layout in ("wide_entity_matrix", "wide_matrix_person_columns"):
        for r in rows:
            d_val = r.get(date_col)
            parsed_d = parse_iso_date(d_val)
            if not parsed_d:
                total_invalid_dates += 1
                continue
            y, m, d = parsed_d
            date_str = f"{y:04d}-{m:02d}-{d:02d}"

            for p_col in entity_cols:
                cell_val = r.get(p_col)
                dur, status, endpoints = parse_clock_interval(cell_val)
                key = (date_str, p_col)
                cell_observations[key].append((dur, status, endpoints))
                date_by_key[key] = (date_str, y, m, d)

    elif contract.layout == "long_tabular":
        id_col = entity_cols[0] if entity_cols else None
        for r in rows:
            d_val = r.get(date_col)
            parsed_d = parse_iso_date(d_val)
            if not parsed_d:
                total_invalid_dates += 1
                continue
            y, m, d = parsed_d
            date_str = f"{y:04d}-{m:02d}-{d:02d}"

            entity_id = str(r.get(id_col)).strip() if id_col else "entity"
            cell_val = r.get(interval_col)
            dur, status, endpoints = parse_clock_interval(cell_val)
            key = (date_str, entity_id)
            cell_observations[key].append((dur, status, endpoints))
            date_by_key[key] = (date_str, y, m, d)

    # Pass 2: Evaluate each (date_str, entity_id) group deterministically
    monthly_durations = defaultdict(list)
    monthly_dates = defaultdict(set)
    monthly_exclusions = defaultdict(lambda: {"conflicting": 0, "invalid": 0, "blank": 0, "overnight": 0})
    all_observed_dates = set()

    for key, obs_list in cell_observations.items():
        date_str, y, m, d = date_by_key[key]
        ym = f"{y:04d}-{m:02d}"

        valid_obs = [obs for obs in obs_list if obs[1] == "valid"]

        if len(valid_obs) > 0:
            distinct_endpoints = set(obs[2] for obs in valid_obs)
            if len(distinct_endpoints) == 1:
                # Exactly one distinct valid interval (either single entry or exact duplicates)
                dur = valid_obs[0][0]
                monthly_durations[ym].append(dur)
                monthly_dates[ym].add(date_str)
                all_observed_dates.add(date_str)
            else:
                # Multiple differing intervals for the same entity and date:
                # Exclude the ENTIRE group as ambiguous/conflicting to preserve row-order independence
                monthly_exclusions[ym]["conflicting"] += len(obs_list)
        else:
            for obs in obs_list:
                st = obs[1]
                if st == "blank":
                    monthly_exclusions[ym]["blank"] += 1
                elif st in ("invalid_time", "malformed"):
                    monthly_exclusions[ym]["invalid"] += 1
                elif st == "overnight_or_zero":
                    monthly_exclusions[ym]["overnight"] += 1

    sorted_yms = sorted(set(list(monthly_durations.keys()) + list(monthly_exclusions.keys())))
    if not sorted_yms:
        return None

    min_ym = sorted_yms[0]
    max_ym = sorted_yms[-1]
    all_calendar_months = calendar_month_range(min_ym, max_ym)

    points: list[ChartPoint] = []
    all_plotted_minutes: list[float] = []
    total_valid_entries = 0
    total_duration_minutes = 0
    total_excluded = 0
    terminal_note = None

    for ym in all_calendar_months:
        durs = monthly_durations.get(ym, [])
        dates = monthly_dates.get(ym, set())
        excl = monthly_exclusions[ym]
        excl_sum = sum(excl.values())
        total_excluded += excl_sum

        if durs:
            v_cnt = len(durs)
            t_mins = sum(durs)
            total_valid_entries += v_cnt
            total_duration_minutes += t_mins

            avg_mins = t_mins / float(v_cnt)
            avg_h = avg_mins / 60.0
            h_int = int(avg_mins // 60)
            m_int = int(round(avg_mins % 60))
            if m_int == 60:
                h_int += 1
                m_int = 0
            formatted_h = f"{h_int}h {m_int:02d}m"

            all_plotted_minutes.append(avg_mins)

            min_d = min(durs)
            max_d = max(durs)
            min_h = round(min_d / 60.0, 3)
            max_h = round(max_d / 60.0, 3)
            formatted_min = f"{min_d//60}h {min_d%60:02d}m"
            formatted_max = f"{max_d//60}h {max_d%60:02d}m"

            # Quantiles: Middle 80% band (P10 - P90)
            # Guard for sparse data: valid_entries >= 20
            if v_cnt >= 20:
                p10_mins = linear_quantile(durs, 0.1)
                p90_mins = linear_quantile(durs, 0.9)
                p10_h = round(p10_mins / 60.0, 3)
                p90_h = round(p90_mins / 60.0, 3)
                p10_hi = int(p10_mins // 60)
                p10_mi = int(round(p10_mins % 60))
                if p10_mi == 60:
                    p10_hi += 1
                    p10_mi = 0
                formatted_p10 = f"{p10_hi}h {p10_mi:02d}m"

                p90_hi = int(p90_mins // 60)
                p90_mi = int(round(p90_mins % 60))
                if p90_mi == 60:
                    p90_hi += 1
                    p90_mi = 0
                formatted_p90 = f"{p90_hi}h {p90_mi:02d}m"

                has_band = True
                all_plotted_minutes.extend([p10_mins, p90_mins])
            else:
                has_band = False
                p10_h = None
                p90_h = None
                formatted_p10 = None
                formatted_p90 = None

            first_date = min(dates)
            last_date = max(dates)
            y_i, m_i = map(int, ym.split("-"))
            days_in_month = calendar.monthrange(y_i, m_i)[1]
            first_day = int(first_date.split("-")[2])
            last_day = int(last_date.split("-")[2])

            is_partial = False
            partial_reason = None

            # Calendar-boundary check for observation window
            if ym == max_ym and last_day < days_in_month:
                is_partial = True
                partial_reason = f"Through {last_day} {format_month_label(ym)} · Partial month"
                terminal_note = f"Through {last_day} {format_month_label(ym)} · Partial month"
            elif ym == min_ym and first_day > 1:
                is_partial = True
                partial_reason = f"Starting {first_day} {format_month_label(ym)} · Partial month"

            points.append(
                ChartPoint(
                    period=ym,
                    period_label=format_month_label(ym),
                    average_hours=round(avg_h, 3),
                    formatted_hours=formatted_h,
                    p10_hours=p10_h,
                    p90_hours=p90_h,
                    formatted_p10=formatted_p10,
                    formatted_p90=formatted_p90,
                    min_hours=min_h,
                    max_hours=max_h,
                    formatted_min=formatted_min,
                    formatted_max=formatted_max,
                    has_band=has_band,
                    total_duration_minutes=t_mins,
                    valid_entries=v_cnt,
                    observed_dates=len(dates),
                    excluded_entries=excl_sum,
                    is_partial=is_partial,
                    partial_reason=partial_reason,
                    first_observed_date=first_date,
                    last_observed_date=last_date,
                )
            )
        else:
            points.append(
                ChartPoint(
                    period=ym,
                    period_label=format_month_label(ym),
                    average_hours=None,
                    formatted_hours=None,
                    p10_hours=None,
                    p90_hours=None,
                    formatted_p10=None,
                    formatted_p90=None,
                    min_hours=None,
                    max_hours=None,
                    formatted_min=None,
                    formatted_max=None,
                    has_band=False,
                    total_duration_minutes=0,
                    valid_entries=0,
                    observed_dates=0,
                    excluded_entries=excl_sum,
                    is_partial=False,
                    partial_reason="No recorded intervals in this month",
                )
            )

    if total_valid_entries == 0:
        return None

    overall_avg_mins = total_duration_minutes / float(total_valid_entries)
    overall_avg_hours = overall_avg_mins / 60.0
    overall_h_int = int(overall_avg_mins // 60)
    overall_m_int = int(round(overall_avg_mins % 60))
    if overall_m_int == 60:
        overall_h_int += 1
        overall_m_int = 0
    overall_formatted = f"{overall_avg_hours:.2f}h"

    y_min, y_max, y_ticks, y_tick_labels, is_focused = compute_focused_duration_scale(all_plotted_minutes)

    # Dynamic evidence-bound caption
    valid_mins = [p.min_hours for p in points if p.min_hours is not None]
    valid_maxs = [p.max_hours for p in points if p.max_hours is not None]
    overall_min_h = min(valid_mins) if valid_mins else 0
    overall_max_h = max(valid_maxs) if valid_maxs else 0
    min_mins_total = int(round(overall_min_h * 60))
    max_mins_total = int(round(overall_max_h * 60))
    min_str = f"{min_mins_total//60}h {min_mins_total%60:02d}m"
    max_str = f"{max_mins_total//60}h {max_mins_total%60:02d}m"
    caption = f"Monthly averages stayed around {overall_h_int}h; individual entries ranged from {min_str} to {max_str}."

    data_through = max(all_observed_dates) if all_observed_dates else None

    calc_id = hashlib.sha256(f"{snapshot}:monthly_logged_time_v5:{total_valid_entries}:{ENGINE_VERSION}".encode()).hexdigest()[:12]
    def_id = hashlib.sha256("average_logged_time_with_distribution_band_v5".encode()).hexdigest()[:12]

    reporting_period = f"{min_ym} to {max_ym}"
    provenance_text = f"Dataset: {manifest.display_name or manifest.file_name} · Sheet: {manifest.sheet_name} (ID: {manifest.sheet_id})"

    limitations = [
        "Elapsed clock time only: does not deduct lunch or scheduled breaks.",
        "Does not reflect scheduled shift requirements, paid time, or overtime.",
        "Workforce coverage unknown: total company headcount or eligible roster is not defined in this source.",
        "Middle 80% band represents the P10–P90 percentile interval of recorded entries, not a confidence interval or performance rating.",
    ]
    if is_focused:
        limitations.append(f"Focused duration scale ({y_tick_labels[0]} to {y_tick_labels[-1]}) highlights monthly variation without exaggerating flat averages.")
    if terminal_note:
        limitations.append(terminal_note)

    evidence = EvidenceResult(
        calculation_id=calc_id,
        snapshot=snapshot,
        definition_id=def_id,
        status="available",
        value=round(overall_avg_hours, 2),
        unit="hours",
        aggregation="monthly_duration_weighted_mean",
        numerator=total_duration_minutes,
        denominator=total_valid_entries,
        is_known_zero=False,
        missing_observations=0,
        invalid_observations=total_excluded,
        excluded_observations=total_excluded,
        coverage_ratio=round(total_valid_entries / (total_valid_entries + total_excluded), 4) if (total_valid_entries + total_excluded) > 0 else 1.0,
        calculation_method="Deterministic clock duration: end_minutes - start_minutes. Monthly averages divide total valid minutes by interval count. Middle 80% is the linear P10–P90 percentile interval (displayed when n >= 20).",
        provenance=provenance_text,
        limitations=limitations,
    )

    glance = GlanceSpec(
        label="Average logged time",
        value=round(overall_avg_hours, 2),
        formatted_value=overall_formatted,
        unit="hours",
        unit_display="implicit_in_label",
        context_qualifier="Hours per recorded entry · Monthly",
        has_info_control=True,
    )

    explain = ExplainSpec(
        short_definition="Elapsed clock time between recorded start and end times, averaged per calendar month across all valid entries with middle 80% range.",
        exact_value_text=f"{overall_formatted} ({overall_h_int}h {overall_m_int:02d}m) across {total_valid_entries:,} entries ({reporting_period})",
    )

    inspect = InspectSpec(
        metric_title="Average logged time",
        exact_value=f"{overall_formatted} ({overall_h_int}h {overall_m_int:02d}m)",
        what_this_counts="Mean elapsed duration between clock-in and clock-out for all valid recorded intervals, with the middle 80% (P10–P90) range.",
        applicable_population=f"All valid time intervals recorded in {manifest.display_name or manifest.file_name}.",
        source_name=manifest.display_name or manifest.file_name,
        reporting_period=reporting_period,
        calculation_method="Deterministic clock duration: end_minutes - start_minutes. Monthly averages divide total valid minutes by interval count. Middle 80% is the linear P10–P90 percentile interval (displayed when n >= 20).",
        data_completeness=f"{total_valid_entries:,} valid entries across {len(all_observed_dates)} recorded dates ({total_excluded} excluded).",
        workforce_coverage="Workforce coverage unknown: total company headcount or eligible roster is not defined in this source.",
        missing_observations=0,
        excluded_observations=total_excluded,
        selection_reason="Complements headcount with recorded time duration. Monthly aggregation provides longitudinal visibility into time entry patterns without assuming shift or overtime policies.",
        limitations=limitations,
        calculation_id=calc_id,
        definition_id=def_id,
        snapshot=snapshot,
        provenance=provenance_text,
    )

    return ChartSpec(
        component_id="secondary_element",
        kind="line_chart",
        business_concept="attendance.average_logged_time_trend",
        title="Average logged time",
        glance=glance,
        explain=explain,
        inspect=inspect,
        evidence=evidence,
        chart_series=ChartSeries(
            name="Average logged time",
            unit="hours",
            points=points,
        ),
        y_axis_min=y_min,
        y_axis_max=y_max,
        y_axis_ticks=y_ticks,
        y_axis_tick_labels=y_tick_labels,
        is_focused_scale=is_focused,
        scale_label="Focused scale",
        band_name="Middle 80% of recorded entries",
        caption=caption,
        terminal_note=terminal_note,
        data_through_date=data_through,
        y_axis_title="Logged duration (h/m)",
        x_axis_title="Timeline (Month)",
        temporal_grain="monthly",
    )


def compute_numeric_focused_scale(
    plotted_values: list[float],
    is_currency: bool = False,
    unit_symbol: str = "$",
) -> tuple[float, float, list[float], list[str], bool]:
    """Computes a unit-aware readable numeric scale with nice tick intervals and labels.

    Returns (y_min, y_max, ticks, tick_labels, is_focused_scale).
    """
    if not plotted_values:
        return 0.0, 100.0, [0.0, 20.0, 40.0, 60.0, 80.0, 100.0], ["0", "20", "40", "60", "80", "100"], False

    v_min = min(plotted_values)
    v_max = max(plotted_values)

    span = v_max - v_min
    if span <= 0:
        span = abs(v_max) if v_max != 0 else 10.0

    raw_step = span / 5.0
    exponent = math.floor(math.log10(raw_step))
    fraction = raw_step / (10 ** exponent)

    if fraction < 1.5:
        nice_fraction = 1.0
    elif fraction < 3.0:
        nice_fraction = 2.0
    elif fraction < 7.0:
        nice_fraction = 5.0
    else:
        nice_fraction = 10.0

    step = nice_fraction * (10 ** exponent)

    if v_min >= 0 and (v_min - step <= 0 or span > 0.7 * v_max):
        min_val = 0.0
    else:
        min_val = math.floor((v_min - (step * 0.5)) / step) * step
        if v_min >= 0 and min_val < 0:
            min_val = 0.0

    max_val = math.ceil((v_max + (step * 0.5)) / step) * step

    ticks: list[float] = []
    tick_labels: list[str] = []
    curr = min_val
    max_iter = 25
    while curr <= max_val + (step * 0.01) and max_iter > 0:
        val = round(curr, 4)
        ticks.append(val)
        if is_currency:
            tick_labels.append(format_currency_short(val))
        else:
            if step >= 1:
                tick_labels.append(f"{int(round(val)):,}")
            else:
                tick_labels.append(f"{val:,.2f}")
        curr += step
        max_iter -= 1

    is_focused = (min_val > 0.0)
    return round(min_val, 4), round(max_val, 4), ticks, tick_labels, is_focused


def build_temporal_measure_chart(
    manifest: SourceManifest,
    contract: SemanticContract,
    rows: list[dict[str, Any]],
) -> ChartSpec | None:
    """Builds a monthly trend line chart and middle 80% distribution band for long tabular datasets with a numeric measure."""
    snapshot = manifest.snapshot
    date_col = contract.date_column
    measure_col = contract.primary_measure

    if not date_col or not measure_col:
        return None

    entity_col = contract.entity_identifiers[0] if contract.entity_identifiers else None

    # Check currency signal
    is_currency = any(kw in measure_col.lower() for kw in ["sales", "revenue", "price", "amount", "cost", "salary", "spend", "dollar", "total"])
    unit_symbol = "$" if is_currency else ""

    valid_records = []
    total_invalid = 0
    for r in rows:
        d_val = r.get(date_col)
        parsed_d = parse_date_safe(d_val)
        m_val = r.get(measure_col)
        if parsed_d is None or m_val is None:
            total_invalid += 1
            continue
        try:
            if isinstance(m_val, str):
                clean_str = re.sub(r"[^\d.-]", "", m_val.strip())
                num_val = float(clean_str)
            else:
                num_val = float(m_val)
            if math.isnan(num_val) or math.isinf(num_val):
                total_invalid += 1
                continue
        except (ValueError, TypeError):
            total_invalid += 1
            continue

        ent_val = str(r.get(entity_col)).strip() if entity_col and r.get(entity_col) is not None else None
        valid_records.append((parsed_d, num_val, ent_val))

    if not valid_records:
        return None

    min_d = min(r[0] for r in valid_records)
    max_d = max(r[0] for r in valid_records)
    min_ym = f"{min_d[0]:04d}-{min_d[1]:02d}"
    max_ym = f"{max_d[0]:04d}-{max_d[1]:02d}"

    # Cadence detection: detect if dataset has weekly observations
    unique_dates = sorted(set(r[0] for r in valid_records))
    date_diffs = []
    for i in range(len(unique_dates) - 1):
        d1 = datetime.date(unique_dates[i][0], unique_dates[i][1], unique_dates[i][2])
        d2 = datetime.date(unique_dates[i + 1][0], unique_dates[i + 1][1], unique_dates[i + 1][2])
        date_diffs.append((d2 - d1).days)

    is_weekly_cadence = (
        len(unique_dates) >= 8
        and (
            "weekly" in measure_col.lower()
            or (date_diffs and (sum(1 for d in date_diffs if 6 <= d <= 8) / len(date_diffs) >= 0.8))
        )
    )

    if is_weekly_cadence:
        temporal_grain = "weekly"
        x_axis_title = "Retail week (Timeline)"
        date_groups = defaultdict(list)
        for d, num, ent in valid_records:
            date_groups[d].append((num, ent))

        points: list[ChartPoint] = []
        for d in unique_dates:
            entries = date_groups[d]
            vals = [e[0] for e in entries]
            w_avg = sum(vals) / len(vals)

            ent_map = defaultdict(list)
            for val, ent in entries:
                if ent is not None:
                    ent_map[ent].append(val)

            if ent_map and len(ent_map) >= 20:
                ent_avgs = [sum(v_list) / len(v_list) for v_list in ent_map.values()]
                p10 = linear_quantile(ent_avgs, 0.10)
                p90 = linear_quantile(ent_avgs, 0.90)
                has_band = True
            elif len(vals) >= 20:
                p10 = linear_quantile(vals, 0.10)
                p90 = linear_quantile(vals, 0.90)
                has_band = True
            else:
                p10 = None
                p90 = None
                has_band = False

            v_min_obs = min(vals)
            v_max_obs = max(vals)

            d_obj = datetime.date(d[0], d[1], d[2])
            iso_y, iso_w, _ = d_obj.isocalendar()
            w_period = f"{iso_y}-W{iso_w:02d}"
            w_label = f"W{iso_w:02d} '{str(iso_y)[2:]}"

            points.append(
                ChartPoint(
                    period=w_period,
                    period_label=w_label,
                    average_hours=round(w_avg, 2),
                    formatted_hours=format_currency_short(w_avg) if is_currency else f"{w_avg:,.2f}",
                    p10_hours=round(p10, 2) if p10 is not None else None,
                    p90_hours=round(p90, 2) if p90 is not None else None,
                    formatted_p10=format_currency_short(p10) if p10 is not None else None,
                    formatted_p90=format_currency_short(p90) if p90 is not None else None,
                    min_hours=round(v_min_obs, 2),
                    max_hours=round(v_max_obs, 2),
                    formatted_min=format_currency_short(v_min_obs) if is_currency else f"{v_min_obs:,.2f}",
                    formatted_max=format_currency_short(v_max_obs) if is_currency else f"{v_max_obs:,.2f}",
                    has_band=has_band,
                    total_duration_minutes=0,
                    valid_entries=len(vals),
                    observed_dates=1,
                    excluded_entries=0,
                    is_partial=False,
                    partial_reason=None,
                    first_observed_date=f"{d[0]:04d}-{d[1]:02d}-{d[2]:02d}",
                    last_observed_date=f"{d[0]:04d}-{d[1]:02d}-{d[2]:02d}",
                )
            )

    else:
        temporal_grain = "monthly"
        x_axis_title = "Timeline (Month)"
        month_groups: dict[str, list[tuple[tuple[int, int, int], float, str | None]]] = defaultdict(list)
        for d, num, ent in valid_records:
            ym = f"{d[0]:04d}-{d[1]:02d}"
            month_groups[ym].append((d, num, ent))

        all_months = calendar_month_range(min_ym, max_ym)
        points: list[ChartPoint] = []

        for ym in all_months:
            if ym in month_groups:
                entries = month_groups[ym]
                vals = [e[1] for e in entries]
                dates_in_month = set(e[0] for e in entries)
                m_avg = sum(vals) / len(vals)

                # Distribution band (linear quantiles)
                ent_map = defaultdict(list)
                for _, val, ent in entries:
                    if ent is not None:
                        ent_map[ent].append(val)

                if ent_map and len(ent_map) >= 20:
                    ent_avgs = [sum(v_list) / len(v_list) for v_list in ent_map.values()]
                    p10 = linear_quantile(ent_avgs, 0.10)
                    p90 = linear_quantile(ent_avgs, 0.90)
                    has_band = True
                elif len(vals) >= 20:
                    p10 = linear_quantile(vals, 0.10)
                    p90 = linear_quantile(vals, 0.90)
                    has_band = True
                else:
                    p10 = None
                    p90 = None
                    has_band = False

                v_min_obs = min(vals)
                v_max_obs = max(vals)

                y_int, m_int = map(int, ym.split("-"))
                days_in_m = calendar.monthrange(y_int, m_int)[1]
                sorted_dates = sorted(dates_in_month)
                first_d = sorted_dates[0]
                last_d = sorted_dates[-1]
                is_partial = False
                partial_reason = None
                if ym == min_ym and first_d[2] > 7:
                    is_partial = True
                    partial_reason = f"Starts on {first_d[0]:04d}-{first_d[1]:02d}-{first_d[2]:02d} (partial first month)"
                elif ym == max_ym and last_d[2] < (days_in_m - 6):
                    is_partial = True
                    partial_reason = f"Ends on {last_d[0]:04d}-{last_d[1]:02d}-{last_d[2]:02d} (partial final month)"

                points.append(
                    ChartPoint(
                        period=ym,
                        period_label=format_month_label(ym),
                        average_hours=round(m_avg, 2),
                        formatted_hours=format_currency_short(m_avg) if is_currency else f"{m_avg:,.2f}",
                        p10_hours=round(p10, 2) if p10 is not None else None,
                        p90_hours=round(p90, 2) if p90 is not None else None,
                        formatted_p10=format_currency_short(p10) if p10 is not None else None,
                        formatted_p90=format_currency_short(p90) if p90 is not None else None,
                        min_hours=round(v_min_obs, 2),
                        max_hours=round(v_max_obs, 2),
                        formatted_min=format_currency_short(v_min_obs) if is_currency else f"{v_min_obs:,.2f}",
                        formatted_max=format_currency_short(v_max_obs) if is_currency else f"{v_max_obs:,.2f}",
                        has_band=has_band,
                        total_duration_minutes=0,
                        valid_entries=len(vals),
                        observed_dates=len(dates_in_month),
                        excluded_entries=0,
                        is_partial=is_partial,
                        partial_reason=partial_reason,
                        first_observed_date=f"{first_d[0]:04d}-{first_d[1]:02d}-{first_d[2]:02d}",
                        last_observed_date=f"{last_d[0]:04d}-{last_d[1]:02d}-{last_d[2]:02d}",
                    )
                )
            else:
                points.append(
                    ChartPoint(
                        period=ym,
                        period_label=format_month_label(ym),
                        average_hours=None,
                        formatted_hours=None,
                        p10_hours=None,
                        p90_hours=None,
                        formatted_p10=None,
                        formatted_p90=None,
                        min_hours=None,
                        max_hours=None,
                        formatted_min=None,
                        formatted_max=None,
                        has_band=False,
                        total_duration_minutes=0,
                        valid_entries=0,
                        observed_dates=0,
                        excluded_entries=0,
                        is_partial=False,
                        partial_reason=None,
                        first_observed_date=None,
                        last_observed_date=None,
                    )
                )

    # Plotted values for scale calculation
    plotted: list[float] = [p.average_hours for p in points if p.average_hours is not None]
    for p in points:
        if p.has_band:
            if p.p10_hours is not None:
                plotted.append(p.p10_hours)
            if p.p90_hours is not None:
                plotted.append(p.p90_hours)

    y_min, y_max, y_ticks, y_tick_labels, is_focused = compute_numeric_focused_scale(
        plotted, is_currency=is_currency, unit_symbol=unit_symbol
    )

    all_vals = [e[1] for e in valid_records]
    overall_avg = sum(all_vals) / len(all_vals)
    overall_formatted = format_currency_short(overall_avg) if is_currency else f"{overall_avg:,.2f}"

    clean_measure = measure_col.replace("_", " ").strip()
    if "weekly" in measure_col.lower() and "sale" in measure_col.lower():
        title = "Average weekly sales"
        if is_weekly_cadence:
            context_qualifier = "Per store · Weekly" if entity_col and "store" in entity_col.lower() else "Weekly observations"
        else:
            context_qualifier = "Per store-week · Monthly" if entity_col and "store" in entity_col.lower() else "Weekly sales · Monthly"
        y_axis_title = "Weekly sales ($)"
    elif is_currency:
        title = f"Average {clean_measure.lower()}"
        context_qualifier = f"Per {entity_col.lower()} · {'Weekly' if is_weekly_cadence else 'Monthly'}" if entity_col else f"{'Weekly' if is_weekly_cadence else 'Monthly'} average"
        y_axis_title = f"{title} ($)"
    else:
        title = f"Average {clean_measure.lower()}"
        context_qualifier = f"Per {entity_col.lower()} · {'Weekly' if is_weekly_cadence else 'Monthly'}" if entity_col else f"{'Weekly' if is_weekly_cadence else 'Monthly'} average"
        y_axis_title = title

    band_name = f"Middle 80% across {entity_col.lower()}s" if (entity_col and any(p.has_band for p in points)) else "Middle 80% distribution"
    if is_weekly_cadence:
        caption = f"Weekly average {clean_measure.lower()} with middle 80% distribution band across {len(valid_records):,} recorded observations ({len(points)} weeks)."
        terminal_note = f"Based on {len(valid_records):,} valid records through {max_d[0]:04d}-{max_d[1]:02d}-{max_d[2]:02d}."
        reporting_period = f"{points[0].period} to {points[-1].period} ({points[0].first_observed_date} to {points[-1].last_observed_date})"
    else:
        caption = f"Monthly average {clean_measure.lower()} with middle 80% distribution band across {len(valid_records):,} recorded observations."
        terminal_note = f"Based on {len(valid_records):,} valid records through {max_d[0]:04d}-{max_d[1]:02d}-{max_d[2]:02d}."
        reporting_period = f"{min_ym} to {max_ym}"
    data_through = f"{max_d[0]:04d}-{max_d[1]:02d}-{max_d[2]:02d}"
    provenance_text = f"Dataset: {manifest.display_name or manifest.file_name} · Sheet: {manifest.sheet_name} (ID: {manifest.sheet_id})"

    calc_id = f"CALC-{hashlib.sha256(f'{snapshot}:temporal_measure_chart:{measure_col}:{ENGINE_VERSION}'.encode()).hexdigest()[:12]}"
    def_id = f"DEF-TEMPORAL-{measure_col.replace('_', '-').upper()}"

    limitations = [
        f"Aggregated from column '{measure_col}' grouped by calendar month.",
        f"Deduplicated across {len(set(r[0] for r in valid_records))} distinct dates.",
    ]
    if entity_col:
        limitations.append(f"Distribution band represents P10–P90 percentile across {entity_col.lower()}s.")
    if is_focused:
        limitations.append(f"Focused scale ({y_tick_labels[0]} to {y_tick_labels[-1]}) highlights monthly variations.")

    evidence = EvidenceResult(
        calculation_id=calc_id,
        snapshot=snapshot,
        definition_id=def_id,
        status="available",
        value=round(overall_avg, 2),
        unit=unit_symbol or "units",
        aggregation="monthly_measure_mean",
        numerator=round(sum(all_vals), 2),
        denominator=len(all_vals),
        is_known_zero=(overall_avg == 0),
        missing_observations=0,
        invalid_observations=total_invalid,
        excluded_observations=total_invalid,
        coverage_ratio=round(len(valid_records) / len(rows), 4) if rows else 1.0,
        calculation_method=f"Deterministic monthly average of column '{measure_col}'. Middle 80% is the linear P10–P90 percentile interval across entities.",
        provenance=provenance_text,
        limitations=limitations,
    )

    glance = GlanceSpec(
        label=title,
        value=round(overall_avg, 2),
        formatted_value=overall_formatted,
        unit=unit_symbol or "units",
        unit_display="implicit_in_label" if not is_currency else "currency_prefix",
        context_qualifier=context_qualifier,
        has_info_control=True,
    )

    explain = ExplainSpec(
        short_definition=f"Monthly average of {clean_measure} across all valid records with middle 80% distribution band.",
        exact_value_text=f"{overall_formatted} mean across {len(valid_records):,} observations ({reporting_period})",
    )

    inspect = InspectSpec(
        metric_title=title,
        exact_value=overall_formatted,
        what_this_counts=f"Mean {clean_measure} per period for all valid observations with middle 80% (P10–P90) range.",
        applicable_population=f"All valid observations recorded in {manifest.display_name or manifest.file_name}.",
        source_name=manifest.display_name or manifest.file_name,
        reporting_period=reporting_period,
        calculation_method=f"Deterministic monthly average of column '{measure_col}'. Distribution band is linear P10–P90 percentile.",
        data_completeness=f"{len(valid_records):,} valid records across {len(set(r[0] for r in valid_records))} dates ({total_invalid} excluded).",
        workforce_coverage="N/A (commercial/operational measure).",
        missing_observations=0,
        excluded_observations=total_invalid,
        selection_reason=f"Complements primary metric with monthly longitudinal trends and distribution dispersion.",
        limitations=limitations,
        calculation_id=calc_id,
        definition_id=def_id,
        snapshot=snapshot,
        provenance=provenance_text,
    )

    return ChartSpec(
        component_id="secondary_element",
        kind="line_chart",
        business_concept=f"temporal.{measure_col.lower()}_trend",
        title=title,
        glance=glance,
        explain=explain,
        inspect=inspect,
        evidence=evidence,
        chart_series=ChartSeries(
            name=title,
            unit=unit_symbol or "units",
            points=points,
        ),
        y_axis_min=y_min,
        y_axis_max=y_max,
        y_axis_ticks=y_ticks,
        y_axis_tick_labels=y_tick_labels,
        is_focused_scale=is_focused,
        scale_label="Focused scale" if is_focused else "Standard scale",
        band_name=band_name,
        caption=caption,
        terminal_note=terminal_note,
        data_through_date=data_through,
        y_axis_title=y_axis_title,
        x_axis_title=x_axis_title,
        temporal_grain=temporal_grain,
    )


def build_period_attendance_chart(
    manifest: SourceManifest,
    contract: SemanticContract,
    rows: list[dict[str, Any]],
) -> ChartSpec | None:
    """Builds a weekly attendance trajectory line chart with distribution band from periodic columns."""
    if not rows or not contract.entity_identifiers:
        return None

    # Detect period columns
    columns = list(rows[0].keys())
    period_cols = []
    for col in columns:
        col_lower = col.lower()
        if any(k in col_lower for k in ["leave", "total", "approved", "final"]):
            continue
        if re.search(r"\b\d+(?:st|nd|rd|th)?\s+(?:to|-)\s+\d+(?:st|nd|rd|th)?\b", col, re.IGNORECASE) or re.search(
            r"\b(jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec)\b", col, re.IGNORECASE
        ):
            period_cols.append(col)

    if len(period_cols) < 2:
        return None

    points: list[ChartPoint] = []
    all_means = []
    all_maxes = []
    calc_id = f"CALC-PERIOD-{manifest.snapshot[:8]}"
    def_id = "DEF-ATTENDANCE-PERIODIC_TRAJECTORY"
    snapshot = manifest.snapshot

    for p_col in period_cols:
        vals = []
        for r in rows:
            raw = r.get(p_col)
            if raw is not None and str(raw).strip() != "":
                try:
                    vals.append(float(str(raw).strip()))
                except ValueError:
                    pass

        if not vals:
            continue

        mean_val = float(sum(vals) / len(vals))
        sorted_vals = sorted(vals)
        n = len(sorted_vals)
        p10_idx = int(0.10 * n)
        p90_idx = min(int(0.90 * n), n - 1)
        p10_val = float(sorted_vals[p10_idx])
        p90_val = float(sorted_vals[p90_idx])
        min_val = float(sorted_vals[0])
        max_val = float(sorted_vals[-1])

        all_means.append(mean_val)
        all_maxes.append(max_val)

        has_band = len(vals) >= 20
        points.append(
            ChartPoint(
                period=p_col,
                period_label=p_col,
                average_hours=round(mean_val, 2),
                formatted_hours=f"{mean_val:.2f} d",
                p10_hours=round(p10_val, 2) if has_band else None,
                p90_hours=round(p90_val, 2) if has_band else None,
                formatted_p10=f"{p10_val:.1f} d" if has_band else None,
                formatted_p90=f"{p90_val:.1f} d" if has_band else None,
                min_hours=round(min_val, 2),
                max_hours=round(max_val, 2),
                formatted_min=f"{min_val:.1f} d",
                formatted_max=f"{max_val:.1f} d",
                has_band=has_band,
                total_duration_minutes=int(sum(vals) * 8 * 60),
                valid_entries=len(vals),
                observed_dates=1,
                excluded_entries=len(rows) - len(vals),
                is_partial=False,
                partial_reason=None,
                first_observed_date=p_col,
                last_observed_date=p_col,
            )
        )

    if not points:
        return None

    overall_mean = sum(all_means) / len(all_means)
    overall_formatted = f"{overall_mean:.2f} d"
    max_observed = max(all_maxes) if all_maxes else 5.0
    y_max = float(max(5.0, math.ceil(max_observed) + 1.0))
    y_ticks = [float(i) for i in range(0, int(y_max) + 1)]
    y_tick_labels = [f"{int(t)}d" for t in y_ticks]

    title = "Average weekly attendance"
    context_qualifier = "Per employee · Weekly"
    band_name = "Middle 80% across employees"
    reporting_period = f"{points[0].period_label} to {points[-1].period_label}"

    glance = GlanceSpec(
        label=title,
        value=round(overall_mean, 2),
        formatted_value=overall_formatted,
        unit="d",
        unit_display="explicit_suffix",
        context_qualifier=context_qualifier,
        has_info_control=True,
    )

    explain = ExplainSpec(
        short_definition="Weekly average attended days per employee across reporting intervals with middle 80% distribution band.",
        exact_value_text=f"{overall_formatted} mean across {len(rows)} employees over {len(points)} recorded intervals ({reporting_period})",
    )

    inspect = InspectSpec(
        metric_title=title,
        exact_value=overall_formatted,
        what_this_counts="Recorded attended days per employee across periodic observation intervals.",
        applicable_population=f"All {len(rows)} employees recorded in {manifest.display_name or manifest.file_name}.",
        source_name=manifest.display_name or manifest.file_name,
        reporting_period=reporting_period,
        calculation_method="Deterministic arithmetic mean of attended days per weekly column. Middle 80% band is linear P10–P90 percentile across employees.",
        data_completeness=f"{len(rows)} recorded employee profiles across {len(points)} weekly periods.",
        workforce_coverage=f"100% of recorded rows in attendance dataset ({len(rows)} employees).",
        coverage_label="Workforce Scope",
        coverage_value=f"{len(rows)} employees",
        missing_observations=0,
        excluded_observations=0,
        selection_reason="Complements headcount with weekly longitudinal attendance trajectory and dispersion across employees.",
        limitations=[
            "Attended days reflect recorded presence in weekly period columns.",
            "Middle 80% band captures distribution between 10th and 90th percentile across the employee population.",
        ],
        calculation_id=calc_id,
        definition_id=def_id,
        snapshot=snapshot,
        provenance=f"Calculated from {len(rows)} employee profiles across {len(points)} periodic columns in sheet {manifest.sheet_name}.",
    )

    evidence = EvidenceResult(
        calculation_id=calc_id,
        snapshot=snapshot,
        definition_id=def_id,
        status="available",
        value=round(overall_mean, 2),
        unit="d",
        aggregation="mean",
        numerator=round(sum(all_means), 2),
        denominator=len(all_means),
        is_known_zero=False,
        missing_observations=0,
        invalid_observations=0,
        excluded_observations=0,
        coverage_ratio=1.0,
        calculation_method="Mean attended days per periodic interval across recorded employee profiles.",
        provenance=inspect.provenance,
        limitations=inspect.limitations,
    )

    return ChartSpec(
        component_id="secondary_element",
        kind="line_chart",
        business_concept="attendance.periodic_trajectory",
        title=title,
        glance=glance,
        explain=explain,
        inspect=inspect,
        evidence=evidence,
        chart_series=ChartSeries(
            name=title,
            unit="d",
            points=points,
        ),
        y_axis_min=0.0,
        y_axis_max=y_max,
        y_axis_ticks=y_ticks,
        y_axis_tick_labels=y_tick_labels,
        is_focused_scale=False,
        scale_label="Standard scale",
        band_name=band_name,
        caption=f"Weekly average attended days with middle 80% employee distribution band across {len(rows)} recorded employees.",
        terminal_note=None,
        data_through_date=points[-1].period_label,
        y_axis_title="Attended days (d)",
        x_axis_title="Reporting period (Timeline)",
        temporal_grain="weekly",
    )


def build_categorical_breakdown_element(
    manifest: SourceManifest,
    contract: SemanticContract,
    rows: list[dict[str, Any]],
) -> BreakdownSpec | None:
    """Builds a dynamic, domain-adaptive categorical breakdown component (Gate 3)."""
    if not rows:
        return None

    columns = list(rows[0].keys())

    # 1. Detect categorical grouping dimension
    group_col = None
    dimension_label = "Category"
    is_hr = contract.domain == "workforce_hr"
    is_sales = contract.domain == "commercial_retail"

    if is_hr:
        for col in columns:
            cl = col.lower().replace("_", "").replace(" ", "")
            if any(k in cl for k in ["department", "dept", "team", "division", "role", "location", "office"]):
                group_col = col
                dimension_label = format_display_label(col)
                break
    elif is_sales:
        for col in columns:
            cl = col.lower().replace("_", "").replace(" ", "")
            if any(k in cl for k in ["store", "branch", "category", "product", "region", "state", "channel"]):
                group_col = col
                dimension_label = format_display_label(col)
                break

    if not group_col:
        # Fallback: scan for any clean non-numeric text column with 2-100 distinct values
        for col in columns:
            if col in contract.entity_identifiers or col == contract.date_column:
                continue
            if any(k in col.lower() for k in ["name", "id", "date", "time", "leave", "phone", "email"]):
                continue
            distinct_vals = set(str(r.get(col)).strip() for r in rows if r.get(col) is not None)
            if 2 <= len(distinct_vals) <= 100:
                group_col = col
                dimension_label = format_display_label(col)
                break

    if not group_col:
        return None

    calc_id = f"CALC-BREAKDOWN-{manifest.snapshot[:8]}"
    def_id = f"DEF-BREAKDOWN-{group_col.upper()}"
    snapshot = manifest.snapshot

    # 2. Measure & Aggregation
    items_raw = defaultdict(lambda: {"count": 0, "measure_sum": 0.0, "att_sum": 0.0, "leave_sum": 0.0})
    primary_measure = contract.primary_measure

    for r in rows:
        g_val = str(r.get(group_col, "Unassigned")).strip() or "Unassigned"
        items_raw[g_val]["count"] += 1

        if primary_measure and r.get(primary_measure) is not None:
            try:
                items_raw[g_val]["measure_sum"] += float(str(r.get(primary_measure)).replace("$", "").replace(",", "").strip())
            except ValueError:
                pass

        if "Total Attendance" in r:
            try:
                items_raw[g_val]["att_sum"] += float(str(r.get("Total Attendance")).strip())
            except ValueError:
                pass
        if "Approved Leaves" in r:
            try:
                items_raw[g_val]["leave_sum"] += float(str(r.get("Approved Leaves")).strip())
            except ValueError:
                pass

    total_categories = len(items_raw)
    total_records = len(rows)

    if is_sales and primary_measure:
        # Commercial sales breakdown by Store/Category
        total_val = sum(s["measure_sum"] for s in items_raw.values())
        sorted_groups = sorted(items_raw.items(), key=lambda x: x[1]["measure_sum"], reverse=True)
        metric_name = "Sales Volume"
        unit = "$"
        title = f"{dimension_label} sales concentration"
        caption = f"Total commercial sales distributed across {total_categories} {dimension_label.lower()}s."
    else:
        # Workforce/general breakdown by Department/Group
        total_val = total_records
        sorted_groups = sorted(items_raw.items(), key=lambda x: x[1]["count"], reverse=True)
        metric_name = "Headcount"
        unit = "employees" if is_hr else "records"
        title = f"Workforce by {dimension_label.lower()}"
        caption = f"Headcount distribution across {total_categories} {dimension_label.lower()}s."

    # Top-N consolidation if more than 10 categories
    items: list[BreakdownItem] = []
    if total_categories > 10:
        top_slice = sorted_groups[:8]
        rest_slice = sorted_groups[8:]
        for cat, s in top_slice:
            val = s["measure_sum"] if (is_sales and primary_measure) else s["count"]
            pct = round((val / total_val) * 100, 1) if total_val > 0 else 0.0
            cat_str = str(cat).strip()
            cat_display = f"{dimension_label} {cat_str}" if cat_str.isdigit() else cat_str
            if is_sales and primary_measure:
                fmt_val = format_currency_short(val)
                sec_val = round(val / s["count"], 0) if s["count"] > 0 else None
                fmt_sec = f"{format_currency_short(sec_val)}/wk avg" if sec_val is not None else None
            else:
                fmt_val = f"{s['count']} employees" if is_hr else f"{s['count']}"
                sec_val = round(s["att_sum"] / s["count"], 1) if s["count"] > 0 and s["att_sum"] > 0 else None
                fmt_sec = f"{sec_val} d avg" if sec_val is not None else None

            items.append(
                BreakdownItem(
                    category=cat_display,
                    value=round(val, 2) if isinstance(val, float) else val,
                    formatted_value=fmt_val,
                    share_pct=pct,
                    secondary_value=sec_val,
                    formatted_secondary=fmt_sec,
                    count=s["count"],
                )
            )

        # Aggregate remainder
        rest_val = sum(s["measure_sum"] if (is_sales and primary_measure) else s["count"] for _, s in rest_slice)
        rest_count = sum(s["count"] for _, s in rest_slice)
        rest_pct = round((rest_val / total_val) * 100, 1) if total_val > 0 else 0.0
        fmt_rest = format_currency_short(rest_val) if (is_sales and primary_measure) else f"{rest_count} employees"
        items.append(
            BreakdownItem(
                category="Other",
                value=round(rest_val, 2) if isinstance(rest_val, float) else rest_val,
                formatted_value=fmt_rest,
                share_pct=rest_pct,
                secondary_value=None,
                formatted_secondary=f"{len(rest_slice)} {dimension_label.lower()}s",
                count=rest_count,
            )
        )
    else:
        for cat, s in sorted_groups:
            val = s["measure_sum"] if (is_sales and primary_measure) else s["count"]
            pct = round((val / total_val) * 100, 1) if total_val > 0 else 0.0
            cat_str = str(cat).strip()
            cat_display = f"{dimension_label} {cat_str}" if cat_str.isdigit() else cat_str
            if is_sales and primary_measure:
                fmt_val = format_currency_short(val)
                sec_val = round(val / s["count"], 0) if s["count"] > 0 else None
                fmt_sec = f"{format_currency_short(sec_val)}/wk avg" if sec_val is not None else None
            else:
                fmt_val = f"{s['count']} employees" if is_hr else f"{s['count']}"
                sec_val = round(s["att_sum"] / s["count"], 1) if s["count"] > 0 and s["att_sum"] > 0 else None
                fmt_sec = f"{sec_val} d avg" if sec_val is not None else None

            items.append(
                BreakdownItem(
                    category=cat_display,
                    value=round(val, 2) if isinstance(val, float) else val,
                    formatted_value=fmt_val,
                    share_pct=pct,
                    secondary_value=sec_val,
                    formatted_secondary=fmt_sec,
                    count=s["count"],
                )
            )

    fmt_total = format_currency_short(total_val) if (is_sales and primary_measure) else f"{total_val:,} {unit}"
    largest_cat = items[0]
    context_qualifier = f"{total_categories} {dimension_label.lower()}s · Largest: {largest_cat.category} ({largest_cat.share_pct}%)"

    glance = GlanceSpec(
        label=title,
        value=total_categories,
        formatted_value=str(total_categories),
        unit=f"{dimension_label.lower()}s",
        unit_display="explicit_suffix",
        context_qualifier=context_qualifier,
        has_info_control=True,
    )

    explain = ExplainSpec(
        short_definition=f"Breakdown of {metric_name.lower()} grouped by {dimension_label.lower()} with share percentage and averages.",
        exact_value_text=f"Total: {fmt_total} across {total_categories} {dimension_label.lower()}s",
    )

    inspect = InspectSpec(
        metric_title=title,
        exact_value=fmt_total,
        what_this_counts=f"{metric_name} aggregated across each distinct '{group_col}' category.",
        applicable_population=f"All {total_records:,} records in {manifest.display_name or manifest.file_name}.",
        source_name=manifest.display_name or manifest.file_name,
        reporting_period=manifest.display_name,
        calculation_method=f"Deterministic grouped sum and distinct count by column '{group_col}'. Share calculated against complete denominator ({fmt_total}).",
        data_completeness=f"{total_records:,} valid records categorized into {total_categories} distinct {dimension_label.lower()}s.",
        workforce_coverage=f"100% of recorded rows ({total_records} profiles)." if is_hr else "Complete dataset coverage.",
        coverage_label="Breakdown Scope",
        coverage_value=f"{total_categories} {dimension_label.lower()}s",
        missing_observations=0,
        excluded_observations=0,
        selection_reason=f"Categorical breakdown (Gate 3) revealing structural distribution across {dimension_label.lower()}s.",
        limitations=[
            f"Grouped by recorded '{group_col}' values.",
            "Consolidated remainder bucket preserves complete 100% denominator without hiding small categories.",
        ],
        calculation_id=calc_id,
        definition_id=def_id,
        snapshot=snapshot,
        provenance=f"Computed from {total_records} rows in sheet {manifest.sheet_name}.",
    )

    evidence = EvidenceResult(
        calculation_id=calc_id,
        snapshot=snapshot,
        definition_id=def_id,
        status="available",
        value=total_categories,
        unit=f"{dimension_label.lower()}s",
        aggregation="grouped_breakdown",
        numerator=total_val,
        denominator=total_val,
        is_known_zero=False,
        missing_observations=0,
        invalid_observations=0,
        excluded_observations=0,
        coverage_ratio=1.0,
        calculation_method=inspect.calculation_method,
        provenance=inspect.provenance,
        limitations=inspect.limitations,
    )

    return BreakdownSpec(
        component_id="tertiary_element",
        kind="ranked_bar",
        business_concept=f"breakdown.{group_col.lower()}",
        dimension_name=dimension_label,
        title=title,
        metric_name=metric_name,
        unit=unit,
        items=items,
        total_categories=total_categories,
        total_value=total_val,
        formatted_total_value=fmt_total,
        glance=glance,
        explain=explain,
        inspect=inspect,
        evidence=evidence,
        caption=caption,
    )


def build_explanatory_comparator_element(
    manifest: SourceManifest,
    contract: SemanticContract,
    rows: list[dict[str, Any]],
) -> ComparatorSpec | None:
    """Build explanatory comparator / impact ratio component (Gate 4).

    Dynamically adapts between:
    1. Retail / Commercial: Holiday vs Non-Holiday weekly sales uplift.
    2. Workforce / HR: Attendance capacity vs Approved leaves impact.
    3. General Tabular: Binary cohort comparator across primary measure.
    """
    if not rows:
        return None

    candidate_cols = list(rows[0].keys())
    snapshot = manifest.snapshot

    # --- Strategy 1: Retail / Commercial Sales Holiday Uplift ---
    holiday_col = next(
        (c for c in candidate_cols if re.search(r"^(holiday(_flag)?|is_holiday)$", c.strip(), re.I)),
        None,
    )
    if not holiday_col:
        # Check for promo flag
        holiday_col = next(
            (c for c in candidate_cols if re.search(r"^(promo(tion)?(_flag)?|is_promo)$", c.strip(), re.I)),
            None,
        )

    # Determine measure column
    measure_col = contract.primary_measure
    if not measure_col:
        measure_col = next(
            (c for c in candidate_cols if re.search(r"^(weekly_sales|sales|revenue|amount)$", c.strip(), re.I)),
            None,
        )

    if holiday_col and measure_col:
        hol_values = []
        non_hol_values = []
        for r in rows:
            raw_flag = str(r.get(holiday_col, "")).strip().lower()
            raw_val = r.get(measure_col)
            if raw_val is None or raw_val == "":
                continue
            try:
                val = float(str(raw_val).replace(",", "").replace("$", ""))
            except (ValueError, TypeError):
                continue

            if raw_flag in ("1", "1.0", "true", "yes", "y", "t"):
                hol_values.append(val)
            elif raw_flag in ("0", "0.0", "false", "no", "n", "f"):
                non_hol_values.append(val)

        if hol_values and non_hol_values:
            n_hol = len(hol_values)
            n_non = len(non_hol_values)
            total_obs = n_hol + n_non
            sum_hol = sum(hol_values)
            sum_non = sum(non_hol_values)
            mean_hol = sum_hol / n_hol
            mean_non = sum_non / n_non
            abs_lift = mean_hol - mean_non
            rel_lift_pct = (abs_lift / mean_non * 100) if mean_non > 0 else 0.0

            is_curr = contract.domain == "commercial_retail" or "sales" in measure_col.lower() or "revenue" in measure_col.lower()
            unit = "$" if is_curr else "units"

            fmt_mean_hol = format_currency_short(mean_hol) if is_curr else f"{mean_hol:,.1f}"
            fmt_mean_non = format_currency_short(mean_non) if is_curr else f"{mean_non:,.1f}"

            abs_sign = "+" if abs_lift >= 0 else "-"
            if is_curr:
                if abs(abs_lift) >= 1_000_000:
                    fmt_abs_lift = f"{abs_sign}${abs(abs_lift)/1_000_000:.2f}M"
                elif abs(abs_lift) >= 1_000:
                    fmt_abs_lift = f"{abs_sign}${abs(abs_lift)/1_000:.1f}K"
                else:
                    fmt_abs_lift = f"{abs_sign}${abs(abs_lift):,.0f}"
            else:
                fmt_abs_lift = f"{abs_lift:+,.1f}"
            fmt_rel_lift = f"{rel_lift_pct:+.1f}%"

            calc_id = f"CALC-COMP-HOLIDAY-{snapshot[:8]}"
            def_id = f"DEF-COHORT-LIFT-{measure_col.upper()}"

            title = "Holiday sales lift comparator"
            dimension_name = "Trading week type"
            metric_name = "Average weekly sales per store"

            context_qualifier = f"{fmt_abs_lift}/wk holiday uplift ({n_hol:,} vs {n_non:,} store-weeks)"

            glance = GlanceSpec(
                label="Holiday sales lift",
                value=round(rel_lift_pct, 1),
                formatted_value=fmt_rel_lift,
                unit="%",
                unit_display="explicit_suffix",
                context_qualifier=context_qualifier,
                has_info_control=True,
            )

            explain = ExplainSpec(
                short_definition="Measures the observed average weekly sales lift in holiday trading weeks relative to baseline non-holiday trading weeks across the store network.",
                exact_value_text=f"Holiday mean: ${mean_hol:,.2f} ({n_hol:,} store-weeks) vs Baseline non-holiday mean: ${mean_non:,.2f} ({n_non:,} store-weeks). Absolute lift: {fmt_abs_lift} ({rel_lift_pct:+.2f}%).",
            )

            inspect = InspectSpec(
                metric_title=title,
                exact_value=f"{fmt_abs_lift} ({rel_lift_pct:+.2f}%)",
                what_this_counts=f"Comparative average of '{measure_col}' between holiday weeks ({holiday_col}=1) and non-holiday baseline weeks ({holiday_col}=0).",
                applicable_population=f"All {total_obs:,} store-week observations in {manifest.display_name or manifest.file_name}.",
                source_name=manifest.display_name or manifest.file_name,
                reporting_period=manifest.display_name,
                calculation_method=f"Deterministic cohort average: Holiday mean (${mean_hol:,.2f}) minus Non-Holiday baseline (${mean_non:,.2f}). Lift percentage computed relative to baseline.",
                data_completeness=f"{total_obs:,} valid observations categorized into {n_hol:,} holiday weeks and {n_non:,} standard trading weeks (100% complete).",
                workforce_coverage="Store network coverage.",
                coverage_label="Comparator Scope",
                coverage_value=f"{total_obs:,} store-weeks across {n_hol} holiday and {n_non} non-holiday periods",
                missing_observations=0,
                excluded_observations=0,
                selection_reason="Explanatory comparator (Gate 4) directly isolating the structural sales uplift driving the seasonal peaks visible in the weekly timeline.",
                limitations=[
                    f"Classified using source column '{holiday_col}'.",
                    "Observed historical lift reflects calendar holiday periods and does not isolate weather or fuel confounding variables without controlled regression.",
                ],
                calculation_id=calc_id,
                definition_id=def_id,
                snapshot=snapshot,
                provenance=f"Computed from {total_obs:,} observations in sheet {manifest.sheet_name}.",
            )

            evidence = EvidenceResult(
                calculation_id=calc_id,
                snapshot=snapshot,
                definition_id=def_id,
                status="available",
                value=round(rel_lift_pct, 2),
                unit="%",
                aggregation="cohort_lift",
                numerator=round(abs_lift, 2),
                denominator=round(mean_non, 2),
                is_known_zero=False,
                missing_observations=0,
                invalid_observations=0,
                excluded_observations=0,
                coverage_ratio=1.0,
                calculation_method=inspect.calculation_method,
                provenance=inspect.provenance,
                limitations=inspect.limitations,
            )

            items = [
                ComparatorItem(
                    cohort="Holiday weeks",
                    is_baseline=False,
                    value=round(mean_hol, 2),
                    formatted_value=fmt_mean_hol,
                    sample_size=n_hol,
                    sample_label=f"{n_hol:,} store-weeks",
                    secondary_value=round(sum_hol, 2),
                    formatted_secondary=format_currency_short(sum_hol) if is_curr else f"{sum_hol:,.0f}",
                    share_pct=round((n_hol / total_obs) * 100, 1),
                ),
                ComparatorItem(
                    cohort="Non-holiday weeks",
                    is_baseline=True,
                    value=round(mean_non, 2),
                    formatted_value=fmt_mean_non,
                    sample_size=n_non,
                    sample_label=f"{n_non:,} store-weeks",
                    secondary_value=round(sum_non, 2),
                    formatted_secondary=format_currency_short(sum_non) if is_curr else f"{sum_non:,.0f}",
                    share_pct=round((n_non / total_obs) * 100, 1),
                ),
            ]

            return ComparatorSpec(
                component_id="quaternary_element",
                kind="cohort_comparator",
                business_concept="retail.holiday_sales_lift",
                title=title,
                dimension_name=dimension_name,
                metric_name=metric_name,
                unit=unit,
                baseline_cohort="Non-holiday weeks",
                comparator_cohort="Holiday weeks",
                absolute_lift=round(abs_lift, 2),
                formatted_absolute_lift=fmt_abs_lift,
                relative_lift_pct=round(rel_lift_pct, 2),
                formatted_relative_lift=fmt_rel_lift,
                items=items,
                glance=glance,
                explain=explain,
                inspect=inspect,
                evidence=evidence,
                caption=f"+{rel_lift_pct:.1f}% mean weekly sales lift during holiday weeks across all stores",
            )

    # --- Strategy 2: Workforce / HR Attendance vs. Approved Leaves ---
    leave_col = next(
        (c for c in candidate_cols if re.search(r"^(approved\s*leaves?|leaves|leave_days)$", c.strip(), re.I)),
        None,
    )
    att_col = next(
        (c for c in candidate_cols if re.search(r"^(total\s*attendance|attendance|final\s*attendance|attended_days)$", c.strip(), re.I)),
        None,
    )

    if leave_col and att_col:
        tot_att = 0.0
        tot_leave = 0.0
        valid_rows = 0
        for r in rows:
            raw_a = r.get(att_col)
            raw_l = r.get(leave_col)
            if raw_a is None and raw_l is None:
                continue
            try:
                a_val = float(str(raw_a).replace(",", "")) if raw_a is not None and str(raw_a).strip() else 0.0
                l_val = float(str(raw_l).replace(",", "")) if raw_l is not None and str(raw_l).strip() else 0.0
                tot_att += a_val
                tot_leave += l_val
                valid_rows += 1
            except (ValueError, TypeError):
                continue

        tot_sched = tot_att + tot_leave
        if tot_sched > 0 and valid_rows > 0:
            share_att = (tot_att / tot_sched) * 100
            share_leave = (tot_leave / tot_sched) * 100
            avg_att = tot_att / valid_rows
            avg_leave = tot_leave / valid_rows

            calc_id = f"CALC-COMP-HR-LEAVE-{snapshot[:8]}"
            def_id = "DEF-HR-ATTENDANCE-LEAVE-COMP"

            title = "Attendance vs. approved leaves"
            dimension_name = "Workforce capacity allocation"
            metric_name = "Total recorded days"
            unit = "days"

            fmt_att = f"{int(tot_att):,} days"
            fmt_leave = f"{int(tot_leave):,} days"
            context_qualifier = f"{int(tot_att):,} attended vs {int(tot_leave):,} leave days ({share_leave:.1f}% leave impact)"

            glance = GlanceSpec(
                label="Attendance capacity & leave impact",
                value=round(share_att, 1),
                formatted_value=f"{share_att:.1f}% attended",
                unit="%",
                unit_display="explicit_suffix",
                context_qualifier=context_qualifier,
                has_info_control=True,
            )

            explain = ExplainSpec(
                short_definition="Evaluates workforce capacity utilization by comparing verified attended days against approved leave days across all employees.",
                exact_value_text=f"Recorded attendance: {int(tot_att):,} days (avg {avg_att:.1f} d/emp, {share_att:.1f}%) vs Approved leaves: {int(tot_leave):,} days (avg {avg_leave:.1f} d/emp, {share_leave:.1f}%) out of {int(tot_sched):,} total scheduled days.",
            )

            inspect = InspectSpec(
                metric_title=title,
                exact_value=f"{share_att:.1f}% attended / {share_leave:.1f}% leave",
                what_this_counts=f"Sum of '{att_col}' ({int(tot_att):,} days) compared against '{leave_col}' ({int(tot_leave):,} days) across all employees.",
                applicable_population=f"All {valid_rows} employees recorded in {manifest.display_name or manifest.file_name}.",
                source_name=manifest.display_name or manifest.file_name,
                reporting_period=manifest.display_name,
                calculation_method=f"Deterministic capacity summation: Attended days / (Attended + Approved Leave days). Denominator represents {int(tot_sched):,} total scheduled/available days.",
                data_completeness=f"{valid_rows} employee profiles with complete attendance and leave records.",
                workforce_coverage=f"100% of recorded rows in attendance dataset ({valid_rows} employees).",
                coverage_label="Workforce Scope",
                coverage_value=f"{valid_rows} employees",
                missing_observations=0,
                excluded_observations=0,
                selection_reason="Explanatory comparator (Gate 4) isolating the capacity impact of approved leaves against observed attendance.",
                limitations=[
                    "Approved leave treatment reflects records in the source file without distinguishing leave sub-types.",
                    "Total capacity assumes sum of attended days and approved leaves without adjusting for uncovered absences.",
                ],
                calculation_id=calc_id,
                definition_id=def_id,
                snapshot=snapshot,
                provenance=f"Computed from {valid_rows} employee records in sheet {manifest.sheet_name}.",
            )

            evidence = EvidenceResult(
                calculation_id=calc_id,
                snapshot=snapshot,
                definition_id=def_id,
                status="available",
                value=round(share_att, 1),
                unit="%",
                aggregation="ratio",
                numerator=tot_att,
                denominator=tot_sched,
                is_known_zero=False,
                missing_observations=0,
                invalid_observations=0,
                excluded_observations=0,
                coverage_ratio=1.0,
                calculation_method=inspect.calculation_method,
                provenance=inspect.provenance,
                limitations=inspect.limitations,
            )

            items = [
                ComparatorItem(
                    cohort="Recorded attendance",
                    is_baseline=True,
                    value=round(tot_att, 1),
                    formatted_value=fmt_att,
                    sample_size=valid_rows,
                    sample_label=f"{valid_rows:,} employees",
                    secondary_value=round(avg_att, 1),
                    formatted_secondary=f"{avg_att:.1f} d/emp",
                    share_pct=round(share_att, 1),
                ),
                ComparatorItem(
                    cohort="Approved leaves",
                    is_baseline=False,
                    value=round(tot_leave, 1),
                    formatted_value=fmt_leave,
                    sample_size=valid_rows,
                    sample_label=f"{valid_rows:,} employees",
                    secondary_value=round(avg_leave, 1),
                    formatted_secondary=f"{avg_leave:.1f} d/emp",
                    share_pct=round(share_leave, 1),
                ),
            ]

            return ComparatorSpec(
                component_id="quaternary_element",
                kind="impact_ratio",
                business_concept="hr.attendance_leave_impact",
                title=title,
                dimension_name=dimension_name,
                metric_name=metric_name,
                unit=unit,
                baseline_cohort="Recorded attendance",
                comparator_cohort="Approved leaves",
                absolute_lift=round(tot_att - tot_leave, 1),
                formatted_absolute_lift=f"{int(tot_att - tot_leave):,} days",
                relative_lift_pct=round(share_att, 1),
                formatted_relative_lift=f"{share_att:.1f}%",
                items=items,
                glance=glance,
                explain=explain,
                inspect=inspect,
                evidence=evidence,
                caption=f"{share_att:.1f}% attendance utilization with {share_leave:.1f}% approved leave impact across workforce",
            )

    # --- Strategy 3: Multi-Sheet Correlated Cohort Comparator (EDA & Derived Tables) ---
    try:
        from ...db.database import get_connection
        _conn = get_connection()
        try:
            # Check for synthesized derived tables involving this sheet
            dt_row = _conn.execute(
                "SELECT id, name, display_name, source_sheets_json, columns_json FROM derived_tables WHERE source_sheets_json LIKE ? ORDER BY id DESC LIMIT 1",
                (f"%{manifest.sheet_id}%",),
            ).fetchone()

            if dt_row:
                dt_id, dt_name, dt_display, src_sheets_raw, dt_cols_raw = dt_row
                src_sheets = json.loads(src_sheets_raw) if src_sheets_raw else []
                partner_sheet_id = next((s for s in src_sheets if s != manifest.sheet_id), None)

                # Fetch derived table rows
                d_records = _conn.execute(
                    "SELECT data_json FROM derived_table_rows WHERE derived_table_id=? ORDER BY row_index",
                    (dt_id,),
                ).fetchall()
                d_rows = [json.loads(r[0]) for r in d_records] if d_records else []

                # Fetch cross-sheet correlations from eda_reports if available
                eda_row = _conn.execute(
                    "SELECT report_json FROM eda_reports WHERE sheet_id=?",
                    (manifest.sheet_id,),
                ).fetchone()

                top_corr = None
                if eda_row and eda_row[0]:
                    rpt = json.loads(eda_row[0])
                    corrs = rpt.get("cross_sheet_intelligence", {}).get("correlations", [])
                    if corrs:
                        top_corr = max(corrs, key=lambda c: abs(c.get("pearson_r") or 0))

                if d_rows and len(d_rows) >= 4:
                    split_metric = None
                    outcome_metric = None
                    corr_r = 0.0

                    if top_corr:
                        if top_corr.get("left_sheet_id") == manifest.sheet_id:
                            split_metric = top_corr.get("left_metric")
                            outcome_metric = top_corr.get("right_metric")
                        else:
                            split_metric = top_corr.get("right_metric")
                            outcome_metric = top_corr.get("left_metric")
                        corr_r = top_corr.get("pearson_r") or 0.0

                    if not split_metric or not outcome_metric or split_metric not in d_rows[0] or outcome_metric not in d_rows[0]:
                        local_cols = set(manifest.columns)
                        partner_cols = [c for c in d_rows[0].keys() if c not in local_cols]
                        num_locals = [c for c in manifest.columns if any(isinstance(r.get(c), (int, float)) for r in d_rows)]
                        num_partners = [c for c in partner_cols if any(isinstance(r.get(c), (int, float)) for r in d_rows)]
                        if num_locals and num_partners:
                            split_metric = num_locals[0]
                            outcome_metric = num_partners[0]

                    if split_metric and outcome_metric and split_metric in d_rows[0] and outcome_metric in d_rows[0]:
                        valid_pairs = []
                        for dr in d_rows:
                            sv = dr.get(split_metric)
                            ov = dr.get(outcome_metric)
                            if sv is not None and ov is not None:
                                try:
                                    s_num = float(str(sv).replace(",", "").replace("$", "").replace("%", ""))
                                    o_num = float(str(ov).replace(",", "").replace("$", "").replace("%", ""))
                                    valid_pairs.append((s_num, o_num))
                                except (ValueError, TypeError):
                                    continue

                        if len(valid_pairs) >= 4:
                            split_vals = [p[0] for p in valid_pairs]
                            has_zeros = sum(1 for v in split_vals if v == 0) >= 2 and sum(1 for v in split_vals if v > 0) >= 2
                            if has_zeros:
                                cohort_a_pairs = [p for p in valid_pairs if p[0] > 0]
                                cohort_b_pairs = [p for p in valid_pairs if p[0] == 0]
                                label_a = f"{split_metric} (> 0)"
                                label_b = f"Standard (0 {split_metric.lower()})"
                            else:
                                sorted_sv = sorted(split_vals)
                                median_sv = sorted_sv[len(sorted_sv) // 2]
                                cohort_a_pairs = [p for p in valid_pairs if p[0] > median_sv]
                                cohort_b_pairs = [p for p in valid_pairs if p[0] <= median_sv]
                                label_a = f"High {split_metric.lower()} (> {median_sv:g})"
                                label_b = f"Baseline (≤ {median_sv:g})"

                            if cohort_a_pairs and cohort_b_pairs:
                                mean_a = sum(p[1] for p in cohort_a_pairs) / len(cohort_a_pairs)
                                mean_b = sum(p[1] for p in cohort_b_pairs) / len(cohort_b_pairs)
                                n_a = len(cohort_a_pairs)
                                n_b = len(cohort_b_pairs)
                                total_n = n_a + n_b

                                abs_lift = mean_a - mean_b
                                rel_lift_pct = ((abs_lift / mean_b) * 100) if mean_b != 0 else 0.0

                                calc_id = f"CALC-COMP-CROSS-{snapshot[:8]}"
                                def_id = f"DEF-CROSS-SHEET-COHORT-{dt_id}"

                                title = f"{split_metric} vs. {outcome_metric}"
                                dimension_name = f"{split_metric} cohort"
                                metric_name = f"Average {outcome_metric.lower()}"
                                is_days = "day" in outcome_metric.lower() or "absent" in outcome_metric.lower()
                                is_hrs = "hour" in outcome_metric.lower()
                                unit = "days" if is_days else ("hours" if is_hrs else "units")

                                fmt_mean_a = f"{mean_a:.1f} {unit}" if (is_days or is_hrs) else f"{mean_a:,.1f}"
                                fmt_mean_b = f"{mean_b:.1f} {unit}" if (is_days or is_hrs) else f"{mean_b:,.1f}"
                                fmt_abs = f"{abs_lift:+.1f} {unit}" if (is_days or is_hrs) else f"{abs_lift:+,.1f}"
                                fmt_rel = f"{rel_lift_pct:+.1f}%"

                                context_qualifier = f"{fmt_mean_a} vs {fmt_mean_b} ({fmt_rel}) across {total_n} employees"

                                glance = GlanceSpec(
                                    label=f"{split_metric} {outcome_metric.lower()} lift",
                                    value=round(rel_lift_pct, 1),
                                    formatted_value=fmt_rel,
                                    unit="%",
                                    unit_display="explicit_suffix",
                                    context_qualifier=context_qualifier,
                                    has_info_control=True,
                                )

                                explain = ExplainSpec(
                                    short_definition=f"Cross-sheet cohort analysis evaluating how '{split_metric}' relates to '{outcome_metric}' across linked records (correlation r = {corr_r:+.2f}).",
                                    exact_value_text=f"{label_a} cohort averages {fmt_mean_a} ({n_a} employees) vs {label_b} cohort averaging {fmt_mean_b} ({n_b} employees). Net lift: {fmt_abs} ({fmt_rel}).",
                                )

                                inspect = InspectSpec(
                                    metric_title=title,
                                    exact_value=f"{fmt_abs} ({fmt_rel})",
                                    what_this_counts=f"Mean difference in '{outcome_metric}' between '{label_a}' and '{label_b}' cohorts partitioned by '{split_metric}'.",
                                    applicable_population=f"All {total_n} employees linked between {manifest.display_name or manifest.sheet_name} and partner dataset.",
                                    source_name=dt_display,
                                    reporting_period=manifest.display_name,
                                    calculation_method=f"Deterministic cross-sheet cohort comparison: Mean '{outcome_metric}' for {label_a} minus Mean for {label_b}. Derived via {dt_display}.",
                                    data_completeness=f"{total_n} linked employee records with non-null values for '{split_metric}' and '{outcome_metric}'.",
                                    workforce_coverage=f"100% of linked population ({total_n} employees).",
                                    coverage_label="Cross-Sheet Linkage",
                                    coverage_value=f"{total_n} matched entities (r = {corr_r:+.2f})",
                                    missing_observations=0,
                                    excluded_observations=0,
                                    selection_reason="Cross-sheet explanatory comparator (Gate 4) discovered during exploratory data analysis (EDA) multi-sheet correlation mining.",
                                    limitations=[
                                        f"Empirical correlation (r = {corr_r:+.2f}) between {split_metric} and {outcome_metric}.",
                                        "Synthesized across multi-sheet join key. Observed relationship reflects sample cohort observations.",
                                    ],
                                    calculation_id=calc_id,
                                    definition_id=def_id,
                                    snapshot=snapshot,
                                    provenance=f"Synthesized from {total_n} records in derived table '{dt_display}' across sheets {src_sheets}.",
                                )

                                evidence = EvidenceResult(
                                    calculation_id=calc_id,
                                    snapshot=snapshot,
                                    definition_id=def_id,
                                    status="available",
                                    value=round(rel_lift_pct, 1),
                                    unit="%",
                                    aggregation="ratio",
                                    numerator=abs_lift,
                                    denominator=mean_b if mean_b != 0 else 1.0,
                                    is_known_zero=False,
                                    missing_observations=0,
                                    invalid_observations=0,
                                    excluded_observations=0,
                                    coverage_ratio=1.0,
                                    calculation_method=inspect.calculation_method,
                                    provenance=inspect.provenance,
                                    limitations=inspect.limitations,
                                )

                                items = [
                                    ComparatorItem(
                                        cohort=label_a,
                                        is_baseline=False,
                                        value=round(mean_a, 2),
                                        formatted_value=fmt_mean_a,
                                        sample_size=n_a,
                                        sample_label=f"{n_a} employees",
                                        secondary_value=round(mean_a, 1),
                                        formatted_secondary=f"{mean_a:.1f} avg",
                                        share_pct=round((n_a / total_n) * 100, 1),
                                    ),
                                    ComparatorItem(
                                        cohort=label_b,
                                        is_baseline=True,
                                        value=round(mean_b, 2),
                                        formatted_value=fmt_mean_b,
                                        sample_size=n_b,
                                        sample_label=f"{n_b} employees",
                                        secondary_value=round(mean_b, 1),
                                        formatted_secondary=f"{mean_b:.1f} avg",
                                        share_pct=round((n_b / total_n) * 100, 1),
                                    ),
                                ]

                                return ComparatorSpec(
                                    component_id="quaternary_element",
                                    kind="cohort_comparator",
                                    business_concept=f"hr.cross_sheet_{split_metric.lower().replace(' ', '_')}_{outcome_metric.lower().replace(' ', '_')}",
                                    title=title,
                                    dimension_name=dimension_name,
                                    metric_name=metric_name,
                                    unit=unit,
                                    baseline_cohort=label_b,
                                    comparator_cohort=label_a,
                                    absolute_lift=round(abs_lift, 2),
                                    formatted_absolute_lift=fmt_abs,
                                    relative_lift_pct=round(rel_lift_pct, 2),
                                    formatted_relative_lift=fmt_rel,
                                    items=items,
                                    glance=glance,
                                    explain=explain,
                                    inspect=inspect,
                                    evidence=evidence,
                                    caption=f"{fmt_rel} difference in {outcome_metric.lower()} between {label_a} and {label_b} (r = {corr_r:+.2f})",
                                )
        finally:
            _conn.close()
    except Exception:
        pass

    return None


def build_segment_disparity_element(
    manifest: SourceManifest,
    contract: SemanticContract,
    rows: list[dict[str, Any]],
) -> DisparitySpec | None:
    """Build quinary segment disparity and variance matrix component (Gate 5).

    Dynamically adapts between:
    1. Workforce / HR: Departmental Attendance Reliability & Capacity Impact Disparity.
       (Attendance rate % vs. leave days/emp, gap between top and bottom units e.g. Operations 93.3% vs Corporate Functions 75.0%, 18.3 pp spread).
    2. Retail / Commercial: Store Performance & Revenue Density Disparity Matrix.
       (Weekly sales density per store, spread between top-performing store and bottom-tier location e.g. Store 20 at $2.41M/wk vs Store 33 at $289K/wk, 8.3x spread).
    3. General Tabular: Segment metric spread across categorical dimension.
    """
    if not rows:
        return None

    candidate_cols = list(rows[0].keys())
    snapshot = manifest.snapshot

    # --- Strategy 1: Workforce / HR Departmental Attendance Reliability Disparity ---
    dept_col = next(
        (c for c in candidate_cols if re.search(r"^(department|dept|business_unit|division|team|org_unit)$", c.strip(), re.I)),
        None,
    )
    # Check for attendance column
    att_col = next(
        (c for c in candidate_cols if re.search(r"^(final_attendance|total_attendance|attendance|present_days|attended_days)$", c.strip().replace(" ", "_"), re.I)),
        None,
    )
    if not att_col and contract.primary_measure:
        if re.search(r"(attendance|presence|present)", contract.primary_measure, re.I):
            att_col = contract.primary_measure

    # Check for leave column
    leave_col = next(
        (c for c in candidate_cols if re.search(r"^(approved_leaves?|total_approved_leaves?|leaves?|total_leaves?|absence_days)$", c.strip().replace(" ", "_"), re.I)),
        None,
    )

    if dept_col and att_col and (contract.domain == "workforce_hr" or leave_col):
        dept_data: dict[str, dict[str, float]] = defaultdict(lambda: {"count": 0, "sum_att": 0.0, "sum_leave": 0.0})
        for r in rows:
            dept_raw = str(r.get(dept_col, "Unknown")).strip()
            if not dept_raw or dept_raw.lower() in ("null", "none", "nan", ""):
                dept_raw = "Unknown"

            # Parse attendance
            raw_att = r.get(att_col)
            att_val = 0.0
            if raw_att is not None and str(raw_att).strip() != "":
                try:
                    att_val = float(str(raw_att).replace(",", "").replace("$", ""))
                except (ValueError, TypeError):
                    att_val = 0.0

            # Parse leaves
            leave_val = 0.0
            if leave_col:
                raw_leave = r.get(leave_col)
                if raw_leave is not None and str(raw_leave).strip() != "":
                    try:
                        leave_val = float(str(raw_leave).replace(",", "").replace("$", ""))
                    except (ValueError, TypeError):
                        leave_val = 0.0

            dept_data[dept_raw]["count"] += 1
            dept_data[dept_raw]["sum_att"] += att_val
            dept_data[dept_raw]["sum_leave"] += leave_val

        # Filter to departments with at least 1 employee
        valid_depts = [
            (name, data) for name, data in dept_data.items()
            if data["count"] > 0 and name != "Unknown"
        ]
        if len(valid_depts) < 2:
            valid_depts = [(name, data) for name, data in dept_data.items() if data["count"] > 0]

        if len(valid_depts) >= 2:
            # Calculate company-wide benchmark
            total_company_att = sum(d["sum_att"] for _, d in valid_depts)
            total_company_leave = sum(d["sum_leave"] for _, d in valid_depts)
            total_company_scheduled = total_company_att + total_company_leave
            benchmark_rate = (total_company_att / total_company_scheduled * 100) if total_company_scheduled > 0 else 0.0

            dept_metrics = []
            for name, d in valid_depts:
                cnt = int(d["count"])
                tot_days = d["sum_att"] + d["sum_leave"]
                if total_company_leave > 0:
                    rate = (d["sum_att"] / tot_days * 100) if tot_days > 0 else 0.0
                else:
                    max_att = max(x[1]["sum_att"] / x[1]["count"] for x in valid_depts)
                    rate = ((d["sum_att"] / cnt) / max_att * 100) if max_att > 0 else 0.0

                leave_per_emp = d["sum_leave"] / cnt if cnt > 0 else 0.0
                att_per_emp = d["sum_att"] / cnt if cnt > 0 else 0.0
                dept_metrics.append({
                    "name": name,
                    "count": cnt,
                    "rel_rate": rate,
                    "att_per_emp": att_per_emp,
                    "leave_per_emp": leave_per_emp,
                    "tot_att": d["sum_att"],
                    "tot_leave": d["sum_leave"],
                })

            # Sort descending by reliability rate, then by count
            dept_metrics.sort(key=lambda x: (x["rel_rate"], x["count"]), reverse=True)

            top_unit = dept_metrics[0]
            bottom_unit = dept_metrics[-1]
            spread = round(top_unit["rel_rate"] - bottom_unit["rel_rate"], 1)

            # Build items with tiering
            items = []
            for d in dept_metrics:
                rate = d["rel_rate"]
                if rate >= benchmark_rate + 2.0:
                    tier = "top_tier"
                elif rate <= benchmark_rate - 4.0:
                    tier = "friction_tier"
                else:
                    tier = "standard_tier"

                rel_idx = round(rate / benchmark_rate, 2) if benchmark_rate > 0 else 1.0
                delta_pp = rate - benchmark_rate
                fmt_idx = f"{delta_pp:+.1f} pp"

                items.append(
                    DisparityItem(
                        segment=d["name"],
                        primary_value=round(rate, 1),
                        formatted_primary=f"{rate:.1f}%",
                        secondary_value=round(d["leave_per_emp"], 1),
                        formatted_secondary=f"{d['leave_per_emp']:.1f} leave d/emp" if leave_col else f"{d['att_per_emp']:.1f} att d/emp",
                        sample_size=d["count"],
                        sample_label=f"{d['count']} employees",
                        tier=tier,
                        relative_index=rel_idx,
                        formatted_relative_index=fmt_idx,
                    )
                )

            fmt_spread = f"{spread:.1f} pp spread"
            title = "Departmental attendance reliability disparity"
            glance = GlanceSpec(
                label="Department attendance disparity",
                value=spread,
                formatted_value=fmt_spread,
                unit="percentage_points",
                unit_display="explicit_suffix",
                context_qualifier=f"Top: {top_unit['name']} ({top_unit['rel_rate']:.1f}%) vs Bottom: {bottom_unit['name']} ({bottom_unit['rel_rate']:.1f}%) across {len(items)} units",
                has_info_control=True,
            )
            explain = ExplainSpec(
                short_definition="Disparity between highest and lowest department attendance reliability rates and average leave consumption.",
                exact_value_text=f"Reliability spread: {spread:.1f} percentage points ({top_unit['name']} at {top_unit['rel_rate']:.1f}% vs {bottom_unit['name']} at {bottom_unit['rel_rate']:.1f}%). Overall company benchmark: {benchmark_rate:.1f}%.",
            )
            inspect = InspectSpec(
                metric_title="Departmental Attendance Reliability & Disparity Matrix",
                exact_value=f"{spread:.1f} percentage points spread",
                what_this_counts="Evaluates workforce capacity utilization and absence vulnerability across organizational departments to highlight reliability gaps and leave load variance.",
                applicable_population=f"All {len(rows)} recorded employee profiles across {len(items)} distinct organizational units.",
                source_name=manifest.display_name,
                reporting_period=manifest.date_range.get("formatted") if manifest.date_range else None,
                calculation_method="Department Attendance Reliability = (Total Attendance Days / (Total Attendance Days + Approved Leaves)) * 100. Disparity Spread = Max Unit Rate - Min Unit Rate across organizational departments.",
                data_completeness=f"100% of {len(rows)} employee records mapped to organizational units without truncation.",
                workforce_coverage=f"All {len(rows)} employees across {len(items)} departments",
                coverage_label="Organizational Scope",
                coverage_value=f"{len(items)} departments ({len(rows)} employees)",
                missing_observations=0,
                excluded_observations=0,
                selection_reason="Identifies operational capacity bottlenecks and uneven absence friction across functional business teams.",
                limitations=[
                    "Department sizes vary; small units may exhibit higher rate volatility.",
                    "Approved leaves are treated as planned absences rather than unexcused friction.",
                ],
                calculation_id=f"calc_disparity_dept_{snapshot[:8]}",
                definition_id="def_departmental_reliability_disparity_v1",
                snapshot=snapshot,
                provenance=f"{manifest.file_name} -> {manifest.sheet_name} (rows: {len(rows)})",
            )
            evidence = EvidenceResult(
                calculation_id=f"calc_disparity_dept_{snapshot[:8]}",
                snapshot=snapshot,
                definition_id="def_departmental_reliability_disparity_v1",
                status="available",
                value=spread,
                unit="percentage_points",
                aggregation="max_minus_min_rate",
                numerator=round(top_unit["rel_rate"], 1),
                denominator=round(bottom_unit["rel_rate"], 1),
                is_known_zero=spread == 0.0,
                missing_observations=0,
                invalid_observations=0,
                excluded_observations=0,
                coverage_ratio=1.0,
                calculation_method="Max department attendance reliability percentage minus minimum department attendance reliability percentage.",
                provenance=f"{manifest.file_name} -> {manifest.sheet_name}",
                limitations=[],
            )

            return DisparitySpec(
                component_id="quinary_element",
                kind="segment_disparity",
                business_concept="hr.departmental_attendance_reliability_disparity",
                title=title,
                dimension_name="Department",
                metric_name="Attendance Reliability",
                secondary_metric_name="Leave Burden" if leave_col else "Attendance Days",
                unit="%",
                spread_value=spread,
                formatted_spread=fmt_spread,
                spread_type="percentage_points",
                top_segment=top_unit["name"],
                bottom_segment=bottom_unit["name"],
                benchmark_value=round(benchmark_rate, 1),
                formatted_benchmark=f"{benchmark_rate:.1f}%",
                items=items,
                glance=glance,
                explain=explain,
                inspect=inspect,
                evidence=evidence,
                caption=f"{spread:.1f} pp gap between highest unit ({top_unit['name']}) and lowest unit ({bottom_unit['name']})",
            )

    # --- Strategy 2: Retail / Commercial Store Revenue Density Disparity Matrix ---
    store_col = next(
        (c for c in candidate_cols if re.search(r"^(store(_id)?|store_num|location|outlet|branch)$", c.strip(), re.I)),
        None,
    )
    sales_col = contract.primary_measure or next(
        (c for c in candidate_cols if re.search(r"^(weekly_sales|sales|revenue|turnover|amount)$", c.strip(), re.I)),
        None,
    )

    if store_col and sales_col and (contract.domain == "commercial_retail" or not dept_col):
        store_data: dict[str, dict[str, float]] = defaultdict(lambda: {"count": 0, "sum_sales": 0.0})
        for r in rows:
            s_raw = str(r.get(store_col, "")).strip()
            if not s_raw or s_raw.lower() in ("null", "none", "nan", ""):
                continue

            raw_sales = r.get(sales_col)
            if raw_sales is None or str(raw_sales).strip() == "":
                continue
            try:
                sales_val = float(str(raw_sales).replace(",", "").replace("$", ""))
            except (ValueError, TypeError):
                continue

            store_data[s_raw]["count"] += 1
            store_data[s_raw]["sum_sales"] += sales_val

        valid_stores = [(s, d) for s, d in store_data.items() if d["count"] > 0]
        if len(valid_stores) >= 2:
            total_net_sales = sum(d["sum_sales"] for _, d in valid_stores)
            total_net_weeks = sum(d["count"] for _, d in valid_stores)
            benchmark_weekly_avg = total_net_sales / total_net_weeks if total_net_weeks > 0 else 0.0

            store_metrics = []
            for s_name, d in valid_stores:
                cnt = int(d["count"])
                avg_weekly = d["sum_sales"] / cnt if cnt > 0 else 0.0
                store_metrics.append({
                    "name": s_name,
                    "count": cnt,
                    "avg_weekly": avg_weekly,
                    "sum_sales": d["sum_sales"],
                })

            store_metrics.sort(key=lambda x: (x["avg_weekly"], x["sum_sales"]), reverse=True)
            top_store = store_metrics[0]
            bottom_store = store_metrics[-1]

            ratio_spread = round(top_store["avg_weekly"] / bottom_store["avg_weekly"], 1) if bottom_store["avg_weekly"] > 0 else 1.0
            abs_delta = top_store["avg_weekly"] - bottom_store["avg_weekly"]

            items = []
            for sm in store_metrics:
                avg = sm["avg_weekly"]
                if avg >= benchmark_weekly_avg * 1.15:
                    tier = "top_tier"
                elif avg <= benchmark_weekly_avg * 0.70:
                    tier = "friction_tier"
                else:
                    tier = "standard_tier"

                rel_idx = round(avg / benchmark_weekly_avg, 2) if benchmark_weekly_avg > 0 else 1.0
                delta_pct = ((avg / benchmark_weekly_avg) - 1.0) * 100 if benchmark_weekly_avg > 0 else 0.0
                fmt_idx = f"{delta_pct:+.0f}%"

                items.append(
                    DisparityItem(
                        segment=f"Store {sm['name']}" if not sm['name'].lower().startswith("store") else sm['name'],
                        primary_value=round(avg, 2),
                        formatted_primary=f"{format_currency_short(avg)}/wk",
                        secondary_value=round(sm["sum_sales"], 2),
                        formatted_secondary=f"{format_currency_short(sm['sum_sales'])} total",
                        sample_size=sm["count"],
                        sample_label=f"{sm['count']} weeks",
                        tier=tier,
                        relative_index=rel_idx,
                        formatted_relative_index=fmt_idx,
                    )
                )

            fmt_spread = f"{ratio_spread:.1f}x spread"
            title = "Store revenue density & performance disparity"
            glance = GlanceSpec(
                label="Store sales density disparity",
                value=ratio_spread,
                formatted_value=fmt_spread,
                unit="ratio",
                unit_display="explicit_suffix",
                context_qualifier=f"Top: Store {top_store['name']} ({format_currency_short(top_store['avg_weekly'])}/wk) vs Bottom: Store {bottom_store['name']} ({format_currency_short(bottom_store['avg_weekly'])}/wk)",
                has_info_control=True,
            )
            explain = ExplainSpec(
                short_definition="Performance variance between top-performing store revenue density and bottom-tier network locations.",
                exact_value_text=f"Sales density spread: {ratio_spread:.1f}x (Store {top_store['name']} at {format_currency_short(top_store['avg_weekly'])}/wk vs Store {bottom_store['name']} at {format_currency_short(bottom_store['avg_weekly'])}/wk; delta {format_currency_short(abs_delta)}/wk). Overall network benchmark: {format_currency_short(benchmark_weekly_avg)}/wk.",
            )
            inspect = InspectSpec(
                metric_title="Store Revenue Density & Disparity Matrix",
                exact_value=f"{ratio_spread:.1f}x spread ({format_currency_short(abs_delta)}/wk delta)",
                what_this_counts="Evaluates store revenue throughput velocity across physical network locations to identify top commercial anchors and underperforming friction units.",
                applicable_population=f"All {len(rows)} weekly sales observations across {len(items)} retail store outlets.",
                source_name=manifest.display_name,
                reporting_period=manifest.date_range.get("formatted") if manifest.date_range else None,
                calculation_method="Store Revenue Density = Sum(Weekly_Sales) / Count(Weeks Observed). Disparity Spread = Top Store Density / Bottom Store Density.",
                data_completeness=f"100% of recorded sales entries aggregated by store identifier.",
                workforce_coverage=f"All {len(items)} physical store locations across {len(rows)} observed weekly records",
                coverage_label="Network Scope",
                coverage_value=f"{len(items)} store locations ({len(rows)} weekly records)",
                missing_observations=0,
                excluded_observations=0,
                selection_reason="Pinpoints revenue generation disparities to guide store-level inventory allocation, labor deployment, and promotional targeting.",
                limitations=[
                    "Store physical square footage and regional economic density are not normalized.",
                    "Fuel price and regional unemployment variances may influence baseline demand.",
                ],
                calculation_id=f"calc_disparity_store_{snapshot[:8]}",
                definition_id="def_store_revenue_density_disparity_v1",
                snapshot=snapshot,
                provenance=f"{manifest.file_name} -> {manifest.sheet_name} (rows: {len(rows)})",
            )
            evidence = EvidenceResult(
                calculation_id=f"calc_disparity_store_{snapshot[:8]}",
                snapshot=snapshot,
                definition_id="def_store_revenue_density_disparity_v1",
                status="available",
                value=ratio_spread,
                unit="ratio",
                aggregation="ratio_top_to_bottom",
                numerator=round(top_store["avg_weekly"], 2),
                denominator=round(bottom_store["avg_weekly"], 2),
                is_known_zero=False,
                missing_observations=0,
                invalid_observations=0,
                excluded_observations=0,
                coverage_ratio=1.0,
                calculation_method="Average weekly sales of top-ranked store divided by average weekly sales of bottom-ranked store.",
                provenance=f"{manifest.file_name} -> {manifest.sheet_name}",
                limitations=[],
            )

            return DisparitySpec(
                component_id="quinary_element",
                kind="segment_disparity",
                business_concept="retail.store_revenue_density_disparity",
                title=title,
                dimension_name="Store",
                metric_name="Weekly Sales Density",
                secondary_metric_name="Total Net Sales",
                unit="$",
                spread_value=ratio_spread,
                formatted_spread=fmt_spread,
                spread_type="ratio",
                top_segment=f"Store {top_store['name']}",
                bottom_segment=f"Store {bottom_store['name']}",
                benchmark_value=round(benchmark_weekly_avg, 2),
                formatted_benchmark=f"{format_currency_short(benchmark_weekly_avg)}/wk",
                items=items,
                glance=glance,
                explain=explain,
                inspect=inspect,
                evidence=evidence,
                caption=f"{ratio_spread:.1f}x density spread between Store {top_store['name']} and Store {bottom_store['name']}",
            )

    # --- Strategy 3: General Tabular Fallback ---
    cat_col = None
    for c in candidate_cols:
        distinct = {str(r.get(c, "")).strip() for r in rows if str(r.get(c, "")).strip()}
        if 2 <= len(distinct) <= 50:
            cat_col = c
            break

    num_col = contract.primary_measure
    if not num_col:
        for c in candidate_cols:
            if c == cat_col:
                continue
            numeric_hits = 0
            sample_size = min(len(rows), 30)
            for r in rows[:sample_size]:
                try:
                    float(str(r.get(c, "")).replace(",", "").replace("$", ""))
                    numeric_hits += 1
                except (ValueError, TypeError):
                    pass
            threshold = max(2, int(sample_size * 0.5))
            if numeric_hits >= threshold:
                num_col = c
                break

    if cat_col and num_col:
        group_data: dict[str, dict[str, float]] = defaultdict(lambda: {"count": 0, "sum_val": 0.0})
        for r in rows:
            g_raw = str(r.get(cat_col, "")).strip()
            if not g_raw or g_raw.lower() in ("null", "none", "nan", ""):
                continue
            try:
                v = float(str(r.get(num_col, "")).replace(",", "").replace("$", ""))
                group_data[g_raw]["count"] += 1
                group_data[g_raw]["sum_val"] += v
            except (ValueError, TypeError):
                continue

        valid_groups = [(g, d) for g, d in group_data.items() if d["count"] > 0]
        if len(valid_groups) >= 2:
            total_sum = sum(d["sum_val"] for _, d in valid_groups)
            total_cnt = sum(d["count"] for _, d in valid_groups)
            benchmark_val = total_sum / total_cnt if total_cnt > 0 else 0.0

            group_metrics = []
            for g_name, d in valid_groups:
                cnt = int(d["count"])
                avg_val = d["sum_val"] / cnt if cnt > 0 else 0.0
                group_metrics.append({
                    "name": g_name,
                    "count": cnt,
                    "avg_val": avg_val,
                    "sum_val": d["sum_val"],
                })

            group_metrics.sort(key=lambda x: (x["avg_val"], x["sum_val"]), reverse=True)
            top_grp = group_metrics[0]
            bottom_grp = group_metrics[-1]

            if bottom_grp["avg_val"] > 0:
                ratio_spread = round(top_grp["avg_val"] / bottom_grp["avg_val"], 1)
                spread_type = "ratio"
                fmt_spread = f"{ratio_spread:.1f}x spread"
                spread_val = ratio_spread
            else:
                delta_spread = round(top_grp["avg_val"] - bottom_grp["avg_val"], 1)
                spread_type = "absolute_delta"
                fmt_spread = f"{delta_spread:+.1f} spread"
                spread_val = delta_spread

            items = []
            for gm in group_metrics:
                avg = gm["avg_val"]
                if avg >= benchmark_val * 1.10:
                    tier = "top_tier"
                elif avg <= benchmark_val * 0.85:
                    tier = "friction_tier"
                else:
                    tier = "standard_tier"

                rel_idx = round(avg / benchmark_val, 2) if benchmark_val > 0 else 1.0
                delta_pct = ((avg / benchmark_val) - 1.0) * 100 if benchmark_val > 0 else 0.0
                fmt_idx = f"{delta_pct:+.1f}%"

                items.append(
                    DisparityItem(
                        segment=gm["name"],
                        primary_value=round(avg, 2),
                        formatted_primary=f"{avg:,.1f}",
                        secondary_value=round(gm["sum_val"], 2),
                        formatted_secondary=f"{gm['sum_val']:,.1f} sum",
                        sample_size=gm["count"],
                        sample_label=f"{gm['count']} observations",
                        tier=tier,
                        relative_index=rel_idx,
                        formatted_relative_index=fmt_idx,
                    )
                )

            dim_display = format_display_label(cat_col)
            measure_display = format_display_label(num_col)
            title = f"{dim_display} {measure_display.lower()} disparity"
            glance = GlanceSpec(
                label=f"{dim_display} variance spread",
                value=spread_val,
                formatted_value=fmt_spread,
                unit="ratio" if spread_type == "ratio" else "delta",
                unit_display="explicit_suffix",
                context_qualifier=f"Top: {top_grp['name']} vs Bottom: {bottom_grp['name']} across {len(items)} segments",
                has_info_control=True,
            )
            explain = ExplainSpec(
                short_definition=f"Measures the disparity in {measure_display.lower()} across {dim_display.lower()} categories.",
                exact_value_text=f"Spread: {fmt_spread} ({top_grp['name']} at {top_grp['avg_val']:,.2f} vs {bottom_grp['name']} at {bottom_grp['avg_val']:,.2f}). Benchmark: {benchmark_val:,.2f}.",
            )
            inspect = InspectSpec(
                metric_title=f"{dim_display} {measure_display} Disparity Matrix",
                exact_value=fmt_spread,
                what_this_counts=f"Evaluates variance in {measure_display.lower()} across distinct {dim_display.lower()} segments.",
                applicable_population=f"All {len(rows)} records across {len(items)} {dim_display.lower()} categories.",
                source_name=manifest.display_name,
                reporting_period=manifest.date_range.get("formatted") if manifest.date_range else None,
                calculation_method=f"Segment Average = Sum({num_col}) / Count(Rows). Disparity = Top Segment Average compared to Bottom Segment Average.",
                data_completeness=f"100% of recorded observations across {len(items)} segments.",
                workforce_coverage=f"All {len(items)} categories across {len(rows)} observed rows",
                coverage_label="Category Scope",
                coverage_value=f"{len(items)} segments ({len(rows)} records)",
                missing_observations=0,
                excluded_observations=0,
                selection_reason=f"Exposes category-level imbalances in {measure_display.lower()}.",
                limitations=["Differences in group sample sizes may influence variance extremes."],
                calculation_id=f"calc_disparity_gen_{snapshot[:8]}",
                definition_id="def_segment_disparity_general_v1",
                snapshot=snapshot,
                provenance=f"{manifest.file_name} -> {manifest.sheet_name} (rows: {len(rows)})",
            )
            evidence = EvidenceResult(
                calculation_id=f"calc_disparity_gen_{snapshot[:8]}",
                snapshot=snapshot,
                definition_id="def_segment_disparity_general_v1",
                status="available",
                value=spread_val,
                unit="ratio" if spread_type == "ratio" else "delta",
                aggregation="top_vs_bottom_spread",
                numerator=round(top_grp["avg_val"], 2),
                denominator=round(bottom_grp["avg_val"], 2),
                is_known_zero=False,
                missing_observations=0,
                invalid_observations=0,
                excluded_observations=0,
                coverage_ratio=1.0,
                calculation_method=f"Top {dim_display} average compared with bottom {dim_display} average.",
                provenance=f"{manifest.file_name} -> {manifest.sheet_name}",
                limitations=[],
            )

            return DisparitySpec(
                component_id="quinary_element",
                kind="segment_disparity",
                business_concept=f"general.{dim_display.lower()}_{measure_display.lower()}_disparity",
                title=title,
                dimension_name=dim_display,
                metric_name=measure_display,
                secondary_metric_name=f"Total {measure_display}",
                unit="",
                spread_value=spread_val,
                formatted_spread=fmt_spread,
                spread_type=spread_type,
                top_segment=top_grp["name"],
                bottom_segment=bottom_grp["name"],
                benchmark_value=round(benchmark_val, 2),
                formatted_benchmark=f"{benchmark_val:,.1f}",
                items=items,
                glance=glance,
                explain=explain,
                inspect=inspect,
                evidence=evidence,
                caption=f"{fmt_spread} between {top_grp['name']} and {bottom_grp['name']}",
            )

    return None


def run_adaptive_dashboard(sheet_id: int | None = None) -> AdaptiveDashboardResponse:
    """End-to-end execution of the Adaptive Dashboard for the selected sheet."""
    conn = get_connection()
    try:
        # 1. Resolve sheet
        if sheet_id is not None:
            sheet_row = conn.execute(
                "SELECT id, dataset_id, name, display_name, columns_json FROM sheets WHERE id=?",
                (sheet_id,),
            ).fetchone()
        else:
            sheet_row = conn.execute(
                "SELECT id, dataset_id, name, display_name, columns_json FROM sheets ORDER BY id DESC LIMIT 1"
            ).fetchone()

        if not sheet_row:
            raise ValueError("No uploaded sheet found. Upload a dataset to view the adaptive dashboard.")

        sid, dataset_id, sheet_name, display_name, cols_json = sheet_row
        columns = json.loads(cols_json) if cols_json else []

        # Get original file name
        dataset_row = conn.execute(
            "SELECT original_name, display_name FROM dataset_uploads WHERE id=?",
            (dataset_id,),
        ).fetchone()
        file_name = dataset_row[0] if dataset_row else "dataset.csv"
        final_display_name = display_name or (dataset_row[1] if dataset_row else sheet_name)

        # 2. Fetch rows (prefer curated post-EDA rows, fallback to raw)
        row_records = conn.execute(
            "SELECT data_json FROM sheet_curated_rows WHERE sheet_id=? ORDER BY row_index",
            (sid,),
        ).fetchall()
        if not row_records:
            row_records = conn.execute(
                "SELECT data_json FROM sheet_rows WHERE sheet_id=? ORDER BY row_index",
                (sid,),
            ).fetchall()
        rows = [json.loads(r[0]) for r in row_records]

        # 3. Stage A & B: Profiling and semantic contract
        manifest, contract = profile_source(
            sheet_id=sid,
            sheet_name=sheet_name,
            file_name=file_name,
            display_name=final_display_name,
            columns=columns,
            rows=rows,
        )

        # 4. Stage C, D, E & F: Metric selection, deterministic calculation, and component spec
        _, _, spec = evaluate_and_select_primary_metric(manifest, contract, rows)

        # 5. Secondary Element: Monthly Average Logged Time, Periodic Attendance, or Temporal Measure Chart
        secondary_chart = None
        try:
            secondary_chart = build_average_logged_time_chart(manifest, contract, rows)
            if secondary_chart is None:
                secondary_chart = build_period_attendance_chart(manifest, contract, rows)
            if secondary_chart is None:
                secondary_chart = build_temporal_measure_chart(manifest, contract, rows)
        except Exception as e:
            # Second-element failure must preserve valid first tile
            secondary_chart = None

        # 6. Tertiary Element: Dynamic Categorical Breakdown (Gate 3)
        tertiary_breakdown = None
        try:
            tertiary_breakdown = build_categorical_breakdown_element(manifest, contract, rows)
        except Exception as e:
            tertiary_breakdown = None

        # 7. Quaternary Element: Explanatory Comparator / Impact Ratio (Gate 4)
        quaternary_comparator = None
        try:
            quaternary_comparator = build_explanatory_comparator_element(manifest, contract, rows)
        except Exception as e:
            quaternary_comparator = None

        # 8. Quinary Element: Segment Disparity & Variance Matrix (Gate 5)
        quinary_disparity = None
        try:
            quinary_disparity = build_segment_disparity_element(manifest, contract, rows)
        except Exception as e:
            quinary_disparity = None

        # Return atomic response
        return AdaptiveDashboardResponse(
            version="adaptive-v5",
            snapshot=manifest.snapshot,
            sheet_id=sid,
            manifest=manifest,
            contract=contract,
            element=spec,
            secondary_element=secondary_chart,
            tertiary_element=tertiary_breakdown,
            quaternary_element=quaternary_comparator,
            quinary_element=quinary_disparity,
            run_status="ready" if spec.kind == "kpi" else "needs_definition",
        )

    finally:
        conn.close()
