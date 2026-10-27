"""Presentation Context Profile (PPT-L0).

Constructs a typed, deterministic PresentationContextProfile grounding the presentation
in the complete evidence universe before any audience or tone adaptation.
"""

from enum import Enum
import re
from typing import Any, Optional
from pydantic import BaseModel, Field

from ..storytelling.story_profiler import detect_sheet_domain


class AnalyticalDomain(str, Enum):
    DEMOGRAPHICS = "DEMOGRAPHICS"
    EDUCATION = "EDUCATION"
    RETAIL = "RETAIL"
    MARKETING = "MARKETING"
    FINANCE = "FINANCE"
    OPERATIONS = "OPERATIONS"
    WORKFORCE = "WORKFORCE"
    PUBLIC_ADMINISTRATION = "PUBLIC_ADMINISTRATION"
    SCIENTIFIC_RESEARCH = "SCIENTIFIC_RESEARCH"
    HEALTHCARE = "HEALTHCARE"
    GEOGRAPHIC_ANALYSIS = "GEOGRAPHIC_ANALYSIS"
    GENERAL_ANALYTICS = "GENERAL_ANALYTICS"


class PresentationContextProfile(BaseModel):
    """
    Deterministic dataset context profile.
    Grounds presentation generation in factual scope without corporate bias.
    """
    dataset_name: str
    dataset_id: Optional[int] = None
    sheet_ids: list[int] = Field(default_factory=list)

    inferred_domain: str
    domain_confidence: float = 0.85

    row_grain: str = "unspecified_record"
    grain_confidence: float = 0.50

    primary_entities: list[str] = Field(default_factory=list)

    time_scope_description: Optional[str] = None
    has_temporal_dimension: bool = False

    key_metrics: list[str] = Field(default_factory=list)
    monetary_metrics: list[str] = Field(default_factory=list)
    rate_metrics: list[str] = Field(default_factory=list)
    geographic_fields: list[str] = Field(default_factory=list)
    temporal_dimensions: list[str] = Field(default_factory=list)

    polarity_map: dict[str, str] = Field(default_factory=dict)

    derived_deck_title: str

    # Presentation framing & cover metadata (domain-neutral)
    presentation_title: Optional[str] = None
    presentation_subtitle: Optional[str] = None
    presenter_name: str = "[Presenter Name]"
    presenter_role: Optional[str] = None
    organization_name: str = "[Organization / Institution]"
    organization_logo: Optional[str] = None
    presentation_date: Optional[str] = None

    likely_audience: str
    audience_confidence: float = 0.75
    audience_reason: str

    likely_presentation_purpose: str
    purpose_confidence: float = 0.75
    purpose_reason: str

    suggested_focus_areas: list[str] = Field(default_factory=list)

    visual_asset_count: int = 0
    fact_count: int = 0
    table_count: int = 0
    scenario_models_present: bool = False


def _clean_title_stem(name: str) -> str:
    """Removes file extensions, hashes, underscores, and cleans name for titles."""
    if not name:
        return "Dataset"
    stem = re.sub(r"\.(csv|xlsx|xls|json|tsv)$", "", name, flags=re.IGNORECASE)
    stem = re.sub(r"^[0-9]+[_\s\-]+", "", stem)
    stem = stem.replace("_", " ").replace("-", " ")
    # Capitalize title words cleanly
    words = [w.capitalize() if not w.isupper() else w for w in stem.split()]
    cleaned = " ".join(words).strip()
    return cleaned or "Dataset"


def _map_to_analytical_domain(raw_domain: str, columns: list[str]) -> tuple[AnalyticalDomain, str]:
    """Maps freeform or rule-based domain strings into canonical AnalyticalDomain enum."""
    d_lower = (raw_domain or "").lower()
    cols_joined = " ".join([str(c).lower() for c in columns])

    if any(k in d_lower or k in cols_joined for k in ("population", "census", "density", "sex_ratio", "sexratio", "literacy", "demographic")):
        return AnalyticalDomain.DEMOGRAPHICS, "Demographics & Regional Demography"
    if any(k in d_lower or k in cols_joined for k in ("student", "school", "grade", "exam", "score", "gpa", "academic", "curriculum")):
        return AnalyticalDomain.EDUCATION, "Education & Academic Performance"
    if any(k in d_lower or k in cols_joined for k in ("sales", "store", "retail", "cpi", "weekly_sales", "orders", "pos")):
        return AnalyticalDomain.RETAIL, "Retail Sales & Commercial Operations"
    if any(k in d_lower or k in cols_joined for k in ("campaign", "clicks", "impressions", "ctr", "adspend", "marketing")):
        return AnalyticalDomain.MARKETING, "Marketing & Campaign Performance"
    if any(k in d_lower or k in cols_joined for k in ("patient", "clinical", "hospital", "diagnosis", "symptom", "treatment", "medical")):
        return AnalyticalDomain.HEALTHCARE, "Healthcare & Clinical Outcomes"
    if any(k in d_lower or k in cols_joined for k in ("municipal", "voter", "council", "civic", "taxpayer", "public_admin")):
        return AnalyticalDomain.PUBLIC_ADMINISTRATION, "Public Administration & Civic Governance"
    if any(k in d_lower or k in cols_joined for k in ("specimen", "sensor", "experiment", "wavelength", "species", "scientific")):
        return AnalyticalDomain.SCIENTIFIC_RESEARCH, "Scientific & Research Analytics"
    if any(k in d_lower or k in cols_joined for k in ("ebitda", "cashflow", "asset", "liability", "opex", "capex", "finance")):
        return AnalyticalDomain.FINANCE, "Financial Performance & Accounting"
    if any(k in d_lower or k in cols_joined for k in ("shipment", "warehouse", "logistics", "freight", "delivery", "transit")):
        return AnalyticalDomain.OPERATIONS, "Supply Chain & Operations"
    if any(k in d_lower or k in cols_joined for k in ("employee", "attrition", "turnover", "recruitment", "headcount", "payroll")):
        return AnalyticalDomain.WORKFORCE, "Workforce & Talent Analytics"
    if any(k in d_lower or k in cols_joined for k in ("latitude", "longitude", "spatial", "boundary", "coordinates")):
        return AnalyticalDomain.GEOGRAPHIC_ANALYSIS, "Geographic & Spatial Analysis"

    return AnalyticalDomain.GENERAL_ANALYTICS, "General Tabular Analytics"


def build_presentation_context_profile(
    dataset_context: dict[str, Any],
    semantic_profile: Any = None,
    user_objective: str = ""
) -> PresentationContextProfile:
    """Deterministically extracts and synthesizes the PresentationContextProfile."""
    target_sheet = dataset_context.get("target_sheet") or {}
    dataset_name = (
        target_sheet.get("original_name")
        or dataset_context.get("dataset_name")
        or target_sheet.get("name")
        or "Dataset"
    )
    dataset_id = dataset_context.get("dataset_id") or target_sheet.get("dataset_id")
    sheet_ids = [target_sheet["id"]] if target_sheet.get("id") else []

    columns = [str(c) for c in (dataset_context.get("columns") or [])]
    raw_domain = dataset_context.get("domain") or ""
    if not raw_domain and columns:
        raw_domain, _ = detect_sheet_domain(columns)

    domain_enum, domain_desc = _map_to_analytical_domain(raw_domain, columns)

    # Clean name for title derivation
    title_stem = _clean_title_stem(dataset_name)
    if title_stem.lower() in ("sheet", "sheet1", "data", "upload", "table"):
        # Use sheet name or columns for title
        if target_sheet.get("name") and target_sheet.get("name").lower() not in ("sheet", "sheet1"):
            title_stem = _clean_title_stem(target_sheet.get("name"))
        elif domain_enum == AnalyticalDomain.DEMOGRAPHICS:
            title_stem = "Demographic"
        elif domain_enum == AnalyticalDomain.RETAIL:
            title_stem = "Retail Sales"
        elif domain_enum == AnalyticalDomain.EDUCATION:
            title_stem = "Academic"
        else:
            title_stem = "Analytical"

    # Grain & Entities
    row_grain = "record"
    grain_confidence = 0.60
    primary_entities: list[str] = []
    geographic_fields: list[str] = []
    temporal_dimensions: list[str] = []
    numeric_measures: list[str] = []
    monetary_metrics: list[str] = []
    rate_metrics: list[str] = []
    polarity_map: dict[str, str] = {}

    if semantic_profile:
        row_grain = getattr(semantic_profile, "inferred_grain", row_grain)
        grain_confidence = getattr(semantic_profile, "grain_confidence", 0.60)
        primary_entities = getattr(semantic_profile, "grain_key_columns", []) or getattr(semantic_profile, "categorical_dimensions", [])[:3]
        geographic_fields = getattr(semantic_profile, "geographic_fields", [])
        temporal_dimensions = getattr(semantic_profile, "temporal_dimensions", [])
        numeric_measures = getattr(semantic_profile, "numeric_measures", [])
        monetary_metrics = getattr(semantic_profile, "monetary_measures", [])
        rate_metrics = getattr(semantic_profile, "percentage_rates", [])
        cols_dict = getattr(semantic_profile, "columns", {})
        for col_name, c_prof in cols_dict.items():
            pol = getattr(c_prof, "polarity", None)
            if pol:
                polarity_map[col_name] = getattr(pol, "value", str(pol))
    else:
        # Infer basic grain and roles from columns
        cols_lower = [c.lower() for c in columns]
        for c in columns:
            cl = c.lower()
            if any(k in cl for k in ("state", "district", "city", "region", "country", "zone", "territory")):
                geographic_fields.append(c)
                if not primary_entities:
                    primary_entities.append(c)
            elif any(k in cl for k in ("date", "week", "month", "year", "time", "period")):
                temporal_dimensions.append(c)
            elif any(k in cl for k in ("sales", "revenue", "price", "cost", "salary", "wage", "margin", "bonus", "spend")):
                monetary_metrics.append(c)
                numeric_measures.append(c)
            elif any(k in cl for k in ("pct", "rate", "percent", "ratio", "share", "proportion", "%")):
                rate_metrics.append(c)
                numeric_measures.append(c)
            elif any(k in cl for k in ("population", "density", "count", "score", "hours", "units", "volume", "quantity")):
                numeric_measures.append(c)

        if geographic_fields:
            row_grain = f"{geographic_fields[0].lower()} entity"
            grain_confidence = 0.85
        elif temporal_dimensions:
            row_grain = "sequential observation"
            grain_confidence = 0.75

    # Derive clean, domain-grounded deck title
    if domain_enum == AnalyticalDomain.DEMOGRAPHICS:
        derived_title = f"{title_stem} — Population & Regional Analysis"
        likely_audience = "Population and regional-analysis stakeholders"
        audience_reason = "Dataset comprises territorial demography, population distributions, and regional metrics."
        purpose = "Review regional population distribution, evaluate density patterns, and identify outlier concentrations."
    elif domain_enum == AnalyticalDomain.RETAIL:
        derived_title = f"{title_stem} — Retail Sales & Performance Review"
        likely_audience = "Retail sales and store-performance stakeholders"
        audience_reason = "Dataset tracks store sales, weekly performance, promotional impacts, and department metrics."
        purpose = "Assess sales trajectory, examine department variance, and model promotional/markdown scenarios."
    elif domain_enum == AnalyticalDomain.EDUCATION:
        derived_title = f"{title_stem} — Academic Performance & Student Outcomes"
        likely_audience = "Education and student-performance stakeholders"
        audience_reason = "Dataset records student academic outcomes, scores, and cohort achievements."
        purpose = "Analyze score distributions, evaluate cohort disparities, and identify academic intervention opportunities."
    elif domain_enum == AnalyticalDomain.HEALTHCARE:
        derived_title = f"{title_stem} — Healthcare & Clinical Outcome Analysis"
        likely_audience = "Healthcare operations and clinical stakeholders"
        audience_reason = "Dataset captures patient admissions, clinical indicators, and health outcomes."
        purpose = "Review patient treatment patterns, monitor clinical indicators, and evaluate care efficiency."
    elif domain_enum == AnalyticalDomain.WORKFORCE:
        derived_title = f"{title_stem} — Workforce & Operational Analysis"
        likely_audience = "Workforce and operational stakeholders"
        audience_reason = "Dataset contains workforce metrics, tenure, and organizational indicators."
        purpose = "Examine operational headcount, evaluate retention indicators, and review resource allocation."
    elif domain_enum == AnalyticalDomain.FINANCE:
        derived_title = f"{title_stem} — Financial Performance & Accounting Review"
        likely_audience = "Financial and operational performance stakeholders"
        audience_reason = "Dataset tracks financial metrics, expenses, margins, and operational profitability."
        purpose = "Analyze revenue and margin trajectories, assess cost variances, and review financial posture."
    elif domain_enum == AnalyticalDomain.OPERATIONS:
        derived_title = f"{title_stem} — Supply Chain & Logistics Performance"
        likely_audience = "Supply chain and operations stakeholders"
        audience_reason = "Dataset captures logistics turnaround, delivery routes, and throughput."
        purpose = "Track delivery efficiency, diagnose route bottlenecks, and evaluate fulfillment capacity."
    else:
        derived_title = f"{title_stem} — Empirical Analytical Review"
        likely_audience = "General stakeholders"
        audience_reason = "Dataset provides structured multi-attribute records for general quantitative analysis."
        purpose = "Examine data structure, analyze primary metric distributions, and highlight significant empirical findings."

    # Temporal scope description
    records = dataset_context.get("records") or []
    time_scope_desc = None
    has_temporal = len(temporal_dimensions) > 0
    if has_temporal and records:
        try:
            from .scope_detector import detect_sheet_date_range
            date_range = detect_sheet_date_range(records, columns)
            if date_range.get("has_date"):
                time_scope_desc = date_range.get("period_label")
        except Exception:
            pass
    if not time_scope_desc:
        time_scope_desc = f"{len(records):,} Recorded Observations" if records else "Snapshot Data"

    # Count existing artifacts
    visual_dashboard = dataset_context.get("visual_dashboard") or {}
    visuals = visual_dashboard.get("visualizations", []) or dataset_context.get("visuals", [])
    exec_topics = dataset_context.get("executive_topics", [])
    exec_kpis = dataset_context.get("executive_kpis", [])

    scenario_present = any(
        "scenario" in str(t).lower() or "policy" in str(t).lower()
        for t in exec_topics
    ) or (domain_enum == AnalyticalDomain.RETAIL)

    focus_areas = []
    if geographic_fields:
        focus_areas.append(f"Geographic Distribution across {geographic_fields[0]}")
    if numeric_measures:
        focus_areas.append(f"Variance & Benchmarks for {numeric_measures[0]}")
    if has_temporal:
        focus_areas.append("Temporal Trends & Trajectory")
    if scenario_present:
        focus_areas.append("Scenario & Sensitivity Impact")

    # Derive presentation framing & cover metadata (domain-neutral)
    p_title = dataset_context.get("presentation_title")
    if not p_title:
        if domain_enum == AnalyticalDomain.EDUCATION:
            p_title = "District Academic Performance & Student Outcomes" if ("district" in dataset_name.lower() or "pgi" in dataset_name.lower()) else f"{title_stem} — Academic Performance & Student Outcomes"
        elif domain_enum == AnalyticalDomain.DEMOGRAPHICS:
            p_title = f"{title_stem} — Population & Demographic Structure"
        elif domain_enum == AnalyticalDomain.RETAIL:
            p_title = f"{title_stem} — Retail Sales & Performance Review"
        else:
            p_title = derived_title

    p_subtitle = dataset_context.get("presentation_subtitle")
    if not p_subtitle:
        if time_scope_desc:
            p_subtitle = f"{title_stem} — {time_scope_desc} Analysis"
        else:
            p_subtitle = f"{title_stem} Analysis & Strategic Overview"

    pres_name = dataset_context.get("presenter_name") or "[Presenter Name]"
    pres_role = dataset_context.get("presenter_role") or None

    org_name = dataset_context.get("organization_name")
    if not org_name:
        if domain_enum == AnalyticalDomain.EDUCATION:
            org_name = "[Organization / Institution]"
        elif domain_enum in (AnalyticalDomain.PUBLIC_ADMINISTRATION, AnalyticalDomain.DEMOGRAPHICS):
            org_name = "[Public Agency / Institution]"
        elif domain_enum == AnalyticalDomain.HEALTHCARE:
            org_name = "[Healthcare System / Institution]"
        else:
            org_name = "[Organization / Institution]"

    org_logo = dataset_context.get("organization_logo") or None

    user_date = (
        dataset_context.get("presentation_date")
        or (dataset_context.get("metadata") or {}).get("presentation_date")
    )
    if user_date:
        pres_date = str(user_date).strip()
    else:
        raw_gen = (
            dataset_context.get("generated_at")
            or dataset_context.get("created_at")
            or (dataset_context.get("metadata") or {}).get("generated_at")
            or (dataset_context.get("metadata") or {}).get("created_at")
        )
        if raw_gen:
            try:
                import datetime
                clean_iso = str(raw_gen).replace("Z", "+00:00")
                dt = datetime.datetime.fromisoformat(clean_iso)
                pres_date = dt.strftime("%B %Y")
            except Exception:
                pres_date = str(raw_gen)[:10]
        else:
            pres_date = None

    return PresentationContextProfile(
        dataset_name=dataset_name,
        dataset_id=dataset_id,
        sheet_ids=sheet_ids,
        inferred_domain=domain_desc,
        domain_confidence=0.90 if domain_enum != AnalyticalDomain.GENERAL_ANALYTICS else 0.60,
        row_grain=row_grain,
        grain_confidence=grain_confidence,
        primary_entities=primary_entities,
        time_scope_description=time_scope_desc,
        has_temporal_dimension=has_temporal,
        key_metrics=numeric_measures[:5],
        monetary_metrics=monetary_metrics[:3],
        rate_metrics=rate_metrics[:3],
        geographic_fields=geographic_fields[:3],
        temporal_dimensions=temporal_dimensions[:3],
        polarity_map=polarity_map,
        derived_deck_title=derived_title,
        presentation_title=p_title,
        presentation_subtitle=p_subtitle,
        presenter_name=pres_name,
        presenter_role=pres_role,
        organization_name=org_name,
        organization_logo=org_logo,
        presentation_date=pres_date,
        likely_audience=likely_audience,
        audience_confidence=0.85 if domain_enum != AnalyticalDomain.GENERAL_ANALYTICS else 0.50,
        audience_reason=audience_reason,
        likely_presentation_purpose=purpose,
        purpose_confidence=0.80,
        purpose_reason="Grounded in dataset schema, entity grain, and available analytical visual assets.",
        suggested_focus_areas=focus_areas,
        visual_asset_count=len(visuals),
        fact_count=len(exec_topics) + len(exec_kpis),
        table_count=1,
        scenario_models_present=scenario_present,
    )
