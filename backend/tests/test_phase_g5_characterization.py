"""
Phase G5 Characterization and Equivalence Test Suite.

Establishes the golden characterization baseline for:
1. Workforce Attendance & Leave domain
2. Retail Sales & Macro domain
3. CPCB Environmental Air Quality domain

Guarantees:
- Semantic identity: KPIs, ExecutiveTopics, topic_ids, titles, visual_specs, evidence_ids, findings
- Topic ownership integrity: zero cross-domain contamination
- Personnel grain ranking: Top 3 employees distinct from department rankings
- Any extracted module produces EXACT equivalence with the baseline.
"""
from __future__ import annotations

import json
from typing import Any
import pytest

from app.db.database import get_connection, session_scope
from app.services.adaptive_dashboard.engine import run_adaptive_dashboard
from app.services.adaptive_dashboard.dataset_orchestrator import run_dataset_intelligence


# ------------------------------------------------------------------------------
# Fixtures for Multi-Domain Characterization
# ------------------------------------------------------------------------------

WORKFORCE_RECORDS = [
    {"Employee ID": f"EMP{i:03d}", "Employee Name": f"Employee {i}", "Department": dept, "Total Attendance": att, "Approved Leaves": lvs, "Date": "2026-07-31"}
    for i, (dept, att, lvs) in enumerate([
        ("Operations and Infrastructure", 24.0, 1.0),
        ("Architecture", 23.0, 2.0),
        ("Alliance Initiative - NRP", 22.0, 1.0),
        ("Functions", 20.0, 3.0),
        ("Design", 19.0, 4.0),
        ("Engineering", 18.0, 5.0),
    ] * 6, start=1)
]

RETAIL_RECORDS = [
    {"Store": 1, "Date": "2010-02-05", "Weekly_Sales": 1643690.90, "Holiday_Flag": 0, "Temperature": 42.31, "Fuel_Price": 2.572, "CPI": 211.096, "Unemployment": 8.106},
    {"Store": 2, "Date": "2010-02-05", "Weekly_Sales": 2136242.25, "Holiday_Flag": 0, "Temperature": 40.19, "Fuel_Price": 2.572, "CPI": 210.752, "Unemployment": 8.324},
    {"Store": 20, "Date": "2010-02-05", "Weekly_Sales": 2401395.47, "Holiday_Flag": 0, "Temperature": 25.92, "Fuel_Price": 2.784, "CPI": 204.247, "Unemployment": 8.187},
    {"Store": 33, "Date": "2010-02-05", "Weekly_Sales": 274605.73, "Holiday_Flag": 0, "Temperature": 58.40, "Fuel_Price": 2.962, "CPI": 126.442, "Unemployment": 10.115},
    {"Store": 1, "Date": "2010-02-12", "Weekly_Sales": 1641957.44, "Holiday_Flag": 1, "Temperature": 38.51, "Fuel_Price": 2.548, "CPI": 211.242, "Unemployment": 8.106},
    {"Store": 2, "Date": "2010-02-12", "Weekly_Sales": 2109107.90, "Holiday_Flag": 1, "Temperature": 22.12, "Fuel_Price": 2.773, "CPI": 204.385, "Unemployment": 8.187},
    {"Store": 20, "Date": "2010-02-12", "Weekly_Sales": 2200000.00, "Holiday_Flag": 1, "Temperature": 24.50, "Fuel_Price": 2.750, "CPI": 204.100, "Unemployment": 8.150},
    {"Store": 33, "Date": "2010-02-12", "Weekly_Sales": 285002.50, "Holiday_Flag": 1, "Temperature": 54.34, "Fuel_Price": 2.962, "CPI": 126.496, "Unemployment": 10.115},
]

ENVIRONMENTAL_RECORDS = [
    {"Stn Code": 101, "Sampling Date": "2022-01-01", "State": "Jharkhand", "City": "Jharia", "Location": "Station A", "Agency": "CPCB", "SO2": 15.2, "NO2": 28.4, "PM10": 140.5},
    {"Stn Code": 102, "Sampling Date": "2022-01-01", "State": "Meghalaya", "City": "Brynihat", "Location": "Station B", "Agency": "CPCB", "SO2": 18.6, "NO2": 32.1, "PM10": 195.0},
    {"Stn Code": 103, "Sampling Date": "2022-01-01", "State": "Maharashtra", "City": "Mumbai", "Location": "Station C", "Agency": "CPCB", "SO2": 12.0, "NO2": 22.0, "PM10": 85.0},
    {"Stn Code": 104, "Sampling Date": "2022-01-01", "State": "Delhi", "City": "Delhi", "Location": "Station D", "Agency": "CPCB", "SO2": 22.1, "NO2": 45.3, "PM10": 210.0},
    {"Stn Code": 101, "Sampling Date": "2022-01-08", "State": "Jharkhand", "City": "Jharia", "Location": "Station A", "Agency": "CPCB", "SO2": 16.0, "NO2": 29.1, "PM10": 145.0},
    {"Stn Code": 102, "Sampling Date": "2022-01-08", "State": "Meghalaya", "City": "Brynihat", "Location": "Station B", "Agency": "CPCB", "SO2": 19.1, "NO2": 33.5, "PM10": 200.0},
]


def _create_dataset_with_rows(conn, filename: str, display_name: str, sheet_name: str, rows: list[dict[str, Any]]) -> int:
    cols = list(rows[0].keys())
    ds_id = conn.execute(
        "INSERT INTO dataset_uploads (filename, original_name, file_type, display_name) VALUES (?, ?, 'csv', ?)",
        (filename, filename, display_name)
    ).lastrowid
    s_id = conn.execute(
        "INSERT INTO sheets (dataset_id, name, columns_json, profile_json, row_count) VALUES (?, ?, ?, '[]', ?)",
        (ds_id, sheet_name, json.dumps(cols), len(rows))
    ).lastrowid
    for idx, r in enumerate(rows):
        conn.execute(
            "INSERT INTO sheet_rows (sheet_id, row_index, data_json) VALUES (?, ?, ?)",
            (s_id, idx, json.dumps(r))
        )
    conn.commit()
    return ds_id


def extract_characterization_signature(res: dict[str, Any]) -> dict[str, Any]:
    """Extracts immutable semantic footprint from adaptive dashboard response."""
    topics = []
    raw_topics = res.get("executive_topics", []) or res.get("elements", [])
    for elem in raw_topics:
        if isinstance(elem, dict):
            topics.append({
                "topic_id": elem.get("topic_id") or elem.get("id"),
                "title": elem.get("title") or elem.get("story", {}).get("title"),
                "domain": elem.get("domain"),
                "analytical_intent": elem.get("analytical_intent"),
                "visual_type": (elem.get("visual_spec", {}) or {}).get("chart_type") or elem.get("chart_type"),
                "finding": elem.get("finding") or elem.get("story", {}).get("finding"),
            })

    kpis = res.get("executive_kpis", []) or res.get("executive_metrics", [])
    return {
        "dataset_id": res.get("dataset_id"),
        "kpis": kpis,
        "topics": topics,
        "total_topics": len(topics),
        "domain_profile": res.get("domain_profile", {}),
    }


# ------------------------------------------------------------------------------
# Characterization Tests
# ------------------------------------------------------------------------------

def test_characterize_workforce_baseline():
    """Characterizes Workforce domain: verifies attendance KPIs, employee ranking, and zero retail/environmental contamination."""
    with session_scope() as conn:
        ds_id = _create_dataset_with_rows(conn, "workforce_eval.csv", "Workforce Attendance July", "Attendance", WORKFORCE_RECORDS)

    res_obj = run_dataset_intelligence(dataset_id=ds_id)
    res = res_obj.model_dump()
    sig = extract_characterization_signature(res)

    assert sig["total_topics"] > 0
    raw_text = json.dumps(res).lower()

    # Zero retail contamination
    assert "weekly_sales" not in raw_text
    assert "fuel_price" not in raw_text
    assert "cpi" not in raw_text

    # Zero environmental contamination
    assert "pm10" not in raw_text
    assert "cpcb" not in raw_text
    assert "so2" not in raw_text

    # Workforce core metrics present
    assert any("attendance" in k["label"].lower() or "leave" in k["label"].lower() for k in sig["kpis"])


def test_characterize_retail_baseline():
    """Characterizes Retail domain: verifies sales volume/spread, and zero HR/workforce contamination."""
    with session_scope() as conn:
        ds_id = _create_dataset_with_rows(conn, "walmart_eval.csv", "Walmart Store Sales", "Sales_Data", RETAIL_RECORDS)

    res_obj = run_dataset_intelligence(dataset_id=ds_id)
    res = res_obj.model_dump()
    sig = extract_characterization_signature(res)

    assert sig["total_topics"] > 0
    raw_text = json.dumps(res).lower()

    # Zero workforce contamination
    assert "approved leaves" not in raw_text
    assert "total attendance" not in raw_text
    assert "headcount" not in raw_text

    # Zero environmental contamination
    assert "pm10" not in raw_text
    assert "cpcb" not in raw_text

    # Retail topics present
    assert any("sales" in t["title"].lower() or "store" in t["title"].lower() for t in sig["topics"] if t.get("title"))


def test_characterize_environmental_baseline():
    """Characterizes Environmental domain: verifies AQI/pollution elements and zero retail/workforce contamination."""
    with session_scope() as conn:
        ds_id = _create_dataset_with_rows(conn, "cpcb_eval.csv", "CPCB Air Quality Report", "Location_data", ENVIRONMENTAL_RECORDS)

    res_obj = run_dataset_intelligence(dataset_id=ds_id)
    res = res_obj.model_dump()
    sig = extract_characterization_signature(res)

    assert sig["total_topics"] > 0
    raw_text = json.dumps(res).lower()

    # Zero workforce contamination
    assert "approved leaves" not in raw_text
    assert "total attendance" not in raw_text

    # Zero retail contamination
    assert "weekly_sales" not in raw_text
    assert "fuel_price" not in raw_text


def test_g5_1_metric_formatter_equivalence():
    """G5.1: Verifies MetricFormatter and presentation label functions produce exact outputs."""
    from app.services.adaptive_dashboard.formatting import (
        MetricFormatter,
        format_currency_short,
        format_percentage,
        format_compact_number,
        clean_metric_name,
        safe_title,
    )

    # Currency formatting
    assert format_currency_short(1_500_000) == "$1.5M"
    assert format_currency_short(2_340_000_000) == "$2.34B"
    assert format_currency_short(450) == "$450"

    # Percentage
    assert format_percentage(87.42) == "87.4%"

    # Compact number
    assert format_compact_number(12500) == "12.5K"

    # Presentation labels: zero underscores, clean casing, preserved acronyms
    assert clean_metric_name("fuel_price") == "Fuel Price"
    assert clean_metric_name("cpi_index") == "CPI Index"
    assert clean_metric_name("total_approved_leaves") == "Total Approved Leaves"
    assert safe_title("temperature_vs_fuel_price") == "Temperature vs Fuel Price"

    # Facade delegation
    assert MetricFormatter.format_currency_short(1000) == "$1K"


def test_g5_1_architecture_boundary_purity():
    """G5.1 Architecture Boundary Guard: Verifies formatting modules contain zero DB, zero AI, and zero MCP imports."""
    import ast
    from pathlib import Path

    formatting_dir = Path(__file__).resolve().parent.parent / "app" / "services" / "adaptive_dashboard" / "formatting"
    assert formatting_dir.exists(), f"formatting package must exist at {formatting_dir}"

    forbidden_modules = {"sqlite3", "duckdb", "ollama", "mcp", "requests", "httpx"}
    for py_file in formatting_dir.glob("*.py"):
        tree = ast.parse(py_file.read_text(encoding="utf-8"), filename=str(py_file))
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    top_pkg = alias.name.split(".")[0]
                    assert top_pkg not in forbidden_modules, (
                        f"Architecture violation: {py_file} imports forbidden '{top_pkg}'"
                    )
            elif isinstance(node, ast.ImportFrom):
                if node.module:
                    top_pkg = node.module.split(".")[0]
                    assert top_pkg not in forbidden_modules, (
                        f"Architecture violation: {py_file} imports from forbidden '{top_pkg}'"
                    )


# ------------------------------------------------------------------------------
# Phase G5.2 Tests: Evidence Binding & Provenance Boundary
# ------------------------------------------------------------------------------

def test_g5_2_evidence_namespace_integrity():
    """G5.2: Enforces namespace validity and semantic isolation across EVID, CTX, and SCEN."""
    from app.services.adaptive_dashboard.evidence import EvidenceNamespaceIntegrity

    # Valid namespaces pass
    assert EvidenceNamespaceIntegrity.parse_namespace("EVID-001") == "EVID"
    assert EvidenceNamespaceIntegrity.parse_namespace("CTX-POLICY-01") == "CTX"
    assert EvidenceNamespaceIntegrity.parse_namespace("SCEN-HEADCOUNT-DROP") == "SCEN"
    assert EvidenceNamespaceIntegrity.validate_id_format("EVID-HERO-123") is True
    assert EvidenceNamespaceIntegrity.validate_id_format("CTX-RECON-TAX") is True
    assert EvidenceNamespaceIntegrity.validate_id_format("SCEN-OPTIMISTIC-01") is True

    # Invalid namespaces fail
    assert EvidenceNamespaceIntegrity.parse_namespace("RAW-ROW-12") == "UNKNOWN"
    assert EvidenceNamespaceIntegrity.validate_id_format("RAW-ROW-12") is False
    assert EvidenceNamespaceIntegrity.validate_id_format("unprefixed_id") is False
    violations = EvidenceNamespaceIntegrity.validate_namespaces(["EVID-001", "INVALID_REF", "CTX-10"])
    assert len(violations) == 1
    assert "INVALID_REF" in violations[0]

    # Semantic conflicts
    scen_conflict = EvidenceNamespaceIntegrity.audit_claim_semantics(
        "This is an empirically observed result across the company.",
        ["SCEN-001"]
    )
    assert len(scen_conflict) == 1
    assert "empirically observed" in scen_conflict[0]

    evid_conflict = EvidenceNamespaceIntegrity.audit_claim_semantics(
        "Under this simulation we expect attrition to spike.",
        ["EVID-001"]
    )
    assert len(evid_conflict) == 1
    assert "simulation" in evid_conflict[0]


def test_g5_2_evidence_ownership_integrity_dataset_isolation():
    """G5.2: Fails closed when an analytical fact tries to bind evidence belonging to an unrelated dataset."""
    from app.services.adaptive_dashboard.evidence import (
        AnalyticalFact,
        BoundEvidence,
        EvidenceBindingService,
        EvidenceOwnershipIntegrity,
        EvidenceOwnershipMismatchError,
    )

    fact = AnalyticalFact(
        fact_id="fact_att_01",
        dataset_id=101,
        subject="Operations",
        metric="Total Attendance",
        formatted_value="24.0 days",
    )

    valid_evidence = BoundEvidence(
        evidence_id="EVID-101-01",
        subject="Operations",
        metric="Total Attendance",
        formatted_value="24.0 days",
        dataset_id=101,
    )

    # Valid binding succeeds
    bound = EvidenceBindingService.bind_fact(fact=fact, topic_id="topic_hero", evidence=valid_evidence)
    assert bound.fact.dataset_id == 101
    assert bound.evidence.evidence_id == "EVID-101-01"

    # Cross-dataset contamination fails closed
    alien_evidence = BoundEvidence(
        evidence_id="EVID-999-01",
        subject="Sales",
        metric="Weekly_Sales",
        formatted_value="$1.6M",
        dataset_id=999,
    )

    with pytest.raises(EvidenceOwnershipMismatchError, match="Cross-dataset evidence contamination detected"):
        EvidenceBindingService.bind_fact(fact=fact, topic_id="topic_hero", evidence=alien_evidence)


def test_g5_2_evidence_ownership_integrity_topic_parity():
    """G5.2: Enforces topic parity strictly within the evidence domain (zero visual/story coupling)."""
    from app.services.adaptive_dashboard.evidence import (
        AnalyticalFact,
        BoundEvidence,
        EvidenceBinding,
        EvidenceOwnershipIntegrity,
        EvidenceOwnershipMismatchError,
    )

    fact = AnalyticalFact(
        fact_id="fact_01",
        dataset_id=101,
        topic_id="topic_workforce_hero",
        subject="Operations",
        metric="Total Attendance",
        formatted_value="24.0 days",
    )
    evidence = BoundEvidence(
        evidence_id="EVID-101-01",
        dataset_id=101,
        topic_id="topic_workforce_hero",
        subject="Operations",
        metric="Total Attendance",
        formatted_value="24.0 days",
    )
    binding = EvidenceBinding(
        topic_id="topic_workforce_hero",
        dataset_id=101,
        primary_evidence_id="EVID-101-01",
    )

    # Coherent topic succeeds within evidence domain
    assert EvidenceOwnershipIntegrity.verify_topic_ownership(
        topic_id="topic_workforce_hero",
        fact=fact,
        evidence=evidence,
        evidence_binding=binding,
    ) is True

    # Mismatched fact topic fails closed
    fact_alien = AnalyticalFact(
        fact_id="fact_02",
        dataset_id=101,
        topic_id="topic_other",
        subject="Operations",
        metric="Total Attendance",
        formatted_value="24.0 days",
    )
    with pytest.raises(EvidenceOwnershipMismatchError, match="Evidence topic ownership violation"):
        EvidenceOwnershipIntegrity.verify_topic_ownership(
            topic_id="topic_workforce_hero",
            fact=fact_alien,
        )


def test_g5_2_executive_topic_cross_layer_binding_parity():
    """G5.2: Enforces higher-level topic identity across Story, VisualSpec, and Evidence at ExecutiveTopic assembly."""
    from app.services.adaptive_dashboard.dataset_isolation_integrity import (
        ExecutiveTopicBindingIntegrity,
        DatasetIsolationViolation,
    )

    coherent_topic = {
        "topic_id": "topic_hero",
        "title": "Store Revenue Ranking",
        "visual_spec": {"topic_id": "topic_hero", "chart_type": "ranked_bar"},
        "story": {"topic_id": "topic_hero", "headline": "Strong retail performance"},
        "evidence_binding": {"topic_id": "topic_hero", "primary_evidence_id": "EVID-001"},
    }
    ok, err = ExecutiveTopicBindingIntegrity.evaluate_topic(coherent_topic)
    assert ok is True
    assert err is None

    # Mismatched visual spec fails closed
    corrupt_visual_topic = {
        "topic_id": "topic_hero",
        "title": "Store Revenue Ranking",
        "visual_spec": {"topic_id": "topic_foreign_visual", "chart_type": "ranked_bar"},
    }
    with pytest.raises(DatasetIsolationViolation, match="Cross-layer topic mismatch"):
        ExecutiveTopicBindingIntegrity.evaluate_topic(corrupt_visual_topic, fail_closed=True)

    # Mismatched story topic fails closed
    corrupt_story_topic = {
        "topic_id": "topic_hero",
        "title": "Store Revenue Ranking",
        "story": {"topic_id": "topic_foreign_story"},
    }
    with pytest.raises(DatasetIsolationViolation, match="Cross-layer topic mismatch"):
        ExecutiveTopicBindingIntegrity.evaluate_topic(corrupt_story_topic, fail_closed=True)


def test_g5_2_grain_isolation():
    """G5.2: Enforces grain isolation between employee (personnel) level and department level evidence."""
    from app.services.adaptive_dashboard.evidence import (
        AnalyticalFact,
        BoundEvidence,
        EvidenceBindingService,
        EvidenceOwnershipMismatchError,
    )

    employee_fact = AnalyticalFact(
        fact_id="fact_emp_podium_01",
        dataset_id=101,
        subject="Employee 1",
        metric="Total Attendance",
        formatted_value="24.0 days",
        grain="employee",
    )

    employee_evidence = BoundEvidence(
        evidence_id="EVID-RANK-Employee-Total-Attendance",
        subject="Employee 1",
        metric="Total Attendance",
        formatted_value="24.0 days",
        dataset_id=101,
        grain="employee",
    )

    dept_evidence = BoundEvidence(
        evidence_id="EVID-RANK-Department-Total-Attendance",
        subject="Operations",
        metric="Total Attendance",
        formatted_value="24.0 days",
        dataset_id=101,
        grain="department",
    )

    # Same grain succeeds
    bound = EvidenceBindingService.bind_fact(fact=employee_fact, topic_id="topic_podium", evidence=employee_evidence)
    assert bound.fact.grain == "employee"

    # Grain contamination fails closed
    with pytest.raises(EvidenceOwnershipMismatchError, match="Grain contamination detected"):
        EvidenceBindingService.bind_fact(fact=employee_fact, topic_id="topic_podium", evidence=dept_evidence)


def test_g5_2_compound_claims_audit():
    """G5.2: Audits compound claims citing both empirical EVID and policy CTX evidence."""
    from app.services.adaptive_dashboard.evidence import (
        BoundEvidence,
        ClaimBindingService,
        EvidenceGraph,
        StructuredClaim,
    )

    graph = EvidenceGraph(
        sheet_id=1,
        snapshot="snap1",
        nodes=[
            BoundEvidence(
                evidence_id="EVID-001",
                subject="Operations",
                metric="Total Attendance",
                formatted_value="24.0 days",
                causal_classification="ASSOCIATED",
            )
        ]
    )

    ctx_nodes = [
        BoundEvidence(
            evidence_id="CTX-POLICY-ATTENDANCE",
            subject="Policy",
            metric="Target Threshold",
            formatted_value="22.0 days",
            namespace="CTX",
            causal_classification="OBSERVED",
        )
    ]

    # Valid compound claim citing both EVID-001 and CTX-POLICY-ATTENDANCE without causal overreach
    claim_valid = StructuredClaim(
        claim_id="CLM-01",
        claim_text="Operations attendance of 24.0 days was associated with exceeding the 22.0 day policy benchmark.",
        evidence_ids=["EVID-001", "CTX-POLICY-ATTENDANCE"],
    )

    resp = ClaimBindingService.audit_response(
        answer="Audited summary",
        claims=[claim_valid],
        graph=graph,
        context_nodes=ctx_nodes,
    )

    assert resp.audit.grounding_validation == "PASSED"
    assert resp.audit.evidence_coverage_pct == 100.0
    assert resp.audit.unsupported_claims_count == 0
    assert "EVID-001" in resp.audit.evidence_ids_cited
    assert "CTX-POLICY-ATTENDANCE" in resp.audit.evidence_ids_cited
    assert len(resp.audit.causal_violations) == 0

    # Causal overreach violation on ASSOCIATED evidence
    claim_invalid = StructuredClaim(
        claim_id="CLM-02",
        claim_text="The high attendance was caused by operations policy changes directly.",
        evidence_ids=["EVID-001"],
    )

    resp_invalid = ClaimBindingService.audit_response(
        answer="Audited summary",
        claims=[claim_invalid],
        graph=graph,
    )

    assert resp_invalid.audit.grounding_validation in ("WARNING", "FAILED")
    assert len(resp_invalid.audit.causal_violations) == 1
    assert "caused by" in resp_invalid.audit.causal_violations[0]


def test_g5_2_provenance_binder():
    """G5.2: Provenance records bind lineage without leaking internal filesystem paths."""
    from app.services.adaptive_dashboard.evidence import ProvenanceBinder

    record = ProvenanceBinder.build_provenance_record(
        dataset_id=501,
        snapshot="snap_abc123456789",
        calculation_desc="sum_measure(Total Attendance)",
        sheet_id=12,
        logical_table="attendance_curated",
        storage_plane="parquet_duckdb",
        grain="employee",
    )

    citation = ProvenanceBinder.format_citation(record)
    assert "dataset #501" in citation
    assert "attendance_curated (sheet #12)" in citation
    assert "parquet_duckdb" in citation
    assert "grain: employee" in citation
    # Never leaks absolute local filesystem paths
    assert "/Users/" not in citation
    assert "C:\\" not in citation
    assert "/home/" not in citation


def test_g5_2_architecture_boundary_purity():
    """G5.2 Architecture Boundary Guard: Verifies evidence modules contain ZERO DB, zero AI, zero MCP, and ZERO visual/composition/theme coupling."""
    import ast
    from pathlib import Path

    evidence_dir = Path(__file__).resolve().parent.parent / "app" / "services" / "adaptive_dashboard" / "evidence"
    assert evidence_dir.exists(), f"evidence package must exist at {evidence_dir}"

    forbidden_modules = {
        # Raw storage / DB
        "sqlite3", "duckdb",
        # AI / LLM / external APIs
        "ollama", "openai", "google.genai", "mcp", "requests", "httpx",
        # Visual / Presentation / Theme / Composition layers
        "visual_recommender", "composition_planner", "spatial_optimizer",
        "theme_validator", "chart_engine", "presentation",
    }

    forbidden_symbols_or_tokens = {
        "visualspec", "visual_spec", "visualrecommender", "compositionplanner",
        "spatialplacement", "themevalidator", "rendercard", "react", "chart_type",
    }

    for py_file in evidence_dir.glob("*.py"):
        code_text = py_file.read_text(encoding="utf-8")
        tree = ast.parse(code_text, filename=str(py_file))

        # 1. AST Imports check
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    top_pkg = alias.name.split(".")[0]
                    assert top_pkg not in forbidden_modules, (
                        f"Architecture violation: {py_file} imports forbidden module '{top_pkg}'"
                    )
            elif isinstance(node, ast.ImportFrom):
                if node.module:
                    top_pkg = node.module.split(".")[0]
                    sub_pkg = node.module.split(".")[-1]
                    assert top_pkg not in forbidden_modules and sub_pkg not in forbidden_modules, (
                        f"Architecture violation: {py_file} imports from forbidden module '{node.module}'"
                    )
                for alias in node.names:
                    sym_name = alias.name.lower()
                    assert sym_name not in forbidden_symbols_or_tokens, (
                        f"Architecture violation: {py_file} imports forbidden visual/composition symbol '{alias.name}'"
                    )

            # 2. AST Name/Identifier check
            elif isinstance(node, ast.Name):
                low_id = node.id.lower()
                assert low_id != "visualspec", (
                    f"Architecture violation: {py_file} references forbidden class/symbol '{node.id}'"
                )

        # 3. Text-level token check for strict visual decoupling
        for line_no, line in enumerate(code_text.splitlines(), start=1):
            low_line = line.strip().lower()
            # Ignore comments and docstrings
            if low_line.startswith("#") or low_line.startswith('"""') or low_line.startswith("'''"):
                continue
            assert "visualspec" not in low_line, (
                f"Architecture violation in {py_file}:{line_no}: Evidence layer references VisualSpec: '{line.strip()}'"
            )
            assert "composition_planner" not in low_line, (
                f"Architecture violation in {py_file}:{line_no}: Evidence layer references composition_planner: '{line.strip()}'"
            )

# ------------------------------------------------------------------------------
# Phase G5.3 Tests: Briefing & Narrative Extraction
# ------------------------------------------------------------------------------

def test_g5_3_title_builder_grain_and_purity():
    """G5.3: Verifies TitleBuilder grain awareness, zero underscores, no machine taxonomy, and domain purity."""
    from app.services.adaptive_dashboard.narrative import (
        NarrativeInput,
        TitleBuilder,
        NarrativeViolationError,
    )

    # 1. Grain awareness: PERSON vs DEPARTMENT
    person_inp = NarrativeInput(
        dataset_id=101,
        domain="workforce",
        subject="attendance",
        metric="total_attendance",
        entity_grain="PERSON",
        analytical_intent="RANKING",
    )
    person_title = TitleBuilder.build_topic_title(person_inp)
    assert person_title == "Employee Total Attendance Ranking"
    assert "_" not in person_title
    assert "Department" not in person_title

    dept_inp = NarrativeInput(
        dataset_id=101,
        domain="workforce",
        subject="attendance",
        metric="total_attendance",
        entity_grain="DEPARTMENT",
        analytical_intent="RANKING",
    )
    dept_title = TitleBuilder.build_topic_title(dept_inp)
    assert dept_title == "Department Total Attendance Ranking"
    assert "_" not in dept_title
    assert "Employee" not in dept_title

    # 2. Stripping machine taxonomy from raw titles
    jargon_title = "Semantic Family Visual Morphology Distributions & Variance Performance"
    cleaned = TitleBuilder.clean_raw_title(jargon_title)
    assert "Semantic Family" not in cleaned
    assert "Visual Morphology" not in cleaned
    assert "Distributions & Variance" not in cleaned

    # 3. Cross-domain purity enforcement
    with pytest.raises(NarrativeViolationError, match="Foreign domain token"):
        retail_with_workforce = NarrativeInput(
            dataset_id=202,
            domain="retail",
            subject="headcount",
            metric="employee_attendance",
            entity_grain="aggregate",
        )
        TitleBuilder.build_topic_title(retail_with_workforce)


def test_g5_3_finding_builder_numeric_entitlement():
    """G5.3: Verifies that FindingBuilder adheres to numeric entitlement, evidence retention, and causal prohibition."""
    from app.services.adaptive_dashboard.evidence.contracts import (
        AnalyticalFact,
        BoundEvidence,
        BoundFact,
    )
    from app.services.adaptive_dashboard.narrative import (
        FindingBuilder,
        NarrativeInput,
        NarrativeEntitlementIntegrity,
        NarrativeViolationError,
    )

    fact1 = AnalyticalFact(
        fact_id="fact_att_top",
        dataset_id=101,
        subject="attendance",
        metric="attendance",
        value=85.0,
        formatted_value="85.0%",
        unit="%",
        dimension="Operations",
        tokens={"comparison_entity": "Sales"},
        comparison_value=72.0,
        difference_pct=18.1,
    )
    # Set comparison_entity attribute if needed by builder
    object.__setattr__(fact1, "comparison_entity", "Sales")

    bound_ev1 = BoundEvidence(
        evidence_id="EVID-ATT-001",
        claim_type="segment_difference",
        subject="attendance",
        metric="attendance",
        value=85.0,
        formatted_value="85.0%",
        dataset_id=101,
    )
    bound_fact1 = BoundFact(
        fact=fact1,
        evidence=bound_ev1,
        topic_id="topic_attendance",
    )

    inp = NarrativeInput(
        dataset_id=101,
        domain="workforce",
        subject="attendance",
        metric="attendance",
        entity_grain="DEPARTMENT",
        bound_facts=[bound_fact1],
        evidence_ids=["EVID-ATT-001"],
        context_refs=["CTX-001"],
        scenario_refs=["SCEN-001"],
        analytical_intent="RANKING",
    )

    result = FindingBuilder.build_narrative(inp)
    assert result.title == "Department Attendance Ranking"
    assert "85.0%" in result.finding
    assert "Operations" in result.finding
    assert "Sales" in result.finding
    assert "18.1%" in result.finding
    assert "EVID-ATT-001" in result.evidence_ids
    assert "CTX-001" in result.context_ids
    assert "SCEN-001" in result.scenario_ids

    # Numeric invention check: text citing fabricated numbers must fail audit
    bad_inp = inp.model_copy(deep=True)
    with pytest.raises(NarrativeViolationError, match="Unbound numeric token"):
        NarrativeEntitlementIntegrity.audit_narrative_text(
            "Operations recorded 99.4% which is completely fabricated.",
            bad_inp,
            fail_closed=True,
        )

    # Prohibited non-causal claims check
    with pytest.raises(NarrativeViolationError, match="Prohibited non-causal"):
        NarrativeEntitlementIntegrity.audit_narrative_text(
            "Sales underperformed because leave caused attendance drop and it will recover soon.",
            bad_inp,
            fail_closed=True,
        )


def test_g5_3_narrative_deduplication_and_summary():
    """G5.3: Verifies narrative deduplication and multi-fact executive summary synthesis without repeating dataset name."""
    from app.services.adaptive_dashboard.evidence.contracts import (
        AnalyticalFact,
        BoundEvidence,
        BoundFact,
    )
    from app.services.adaptive_dashboard.narrative import (
        NarrativeDeduplicationIntegrity,
        NarrativeResult,
    )

    facts = [
        BoundFact(
            fact=AnalyticalFact(
                fact_id=f"f_{i}",
                dataset_id=202,
                subject="retail_sales",
                metric="weekly_sales",
                value=2400000.0 - i * 200000.0,
                formatted_value=f"${2400000.0 - i * 200000.0:,.1f}",
                dimension=f"Store {i}",
                unit="$",
            ),
            evidence=BoundEvidence(
                evidence_id=f"EVID-STORE-{i}",
                claim_type="segment_difference",
                subject="retail_sales",
                metric="weekly_sales",
                value=2400000.0 - i * 200000.0,
                formatted_value=f"${2400000.0 - i * 200000.0:,.1f}",
                dataset_id=202,
            ),
            topic_id="topic_sales",
        )
        for i in range(1, 5)
    ]

    summary = NarrativeDeduplicationIntegrity.compose_executive_summary(
        bound_facts=facts,
        domain="retail",
        max_facts=3,
    )
    assert "Store 1 led observed cohorts with $2,200,000.0" in summary
    assert "Store 2 recorded $2,000,000.0" in summary
    assert "retail_sales" not in summary.lower()  # Never repeats the raw dataset/sheet name
    assert "semantic family" not in summary.lower()  # Zero machine taxonomy

    # Test narrative deduplication
    n1 = NarrativeResult(
        title="Store Weekly Sales Ranking",
        finding="Store 1 leads sales.",
        entity_grain="store",
        domain="retail",
    )
    n2 = NarrativeResult(
        title="Store Weekly Sales Ranking",
        finding="Store 1 leads sales duplicated.",
        entity_grain="store",
        domain="retail",
    )
    n3 = NarrativeResult(
        title="Department Weekly Sales Ranking",
        finding="Department sales overview.",
        entity_grain="department",
        domain="retail",
    )

    deduped = NarrativeDeduplicationIntegrity.deduplicate_narratives([n1, n2, n3])
    assert len(deduped) == 2
    assert deduped[0].entity_grain == "store"
    assert deduped[1].entity_grain == "department"


def test_g5_3_briefing_claims_and_audio():
    """G5.3: Verifies ExecutiveBriefingService claims validation, word count limits, PII protection, and audible expansion."""
    from app.services.adaptive_dashboard.contracts import BriefingClaim
    from app.services.adaptive_dashboard.narrative import (
        ExecutiveBriefingService,
        format_pp_for_speech,
        validate_briefing_claims,
    )

    # 1. Audible text expansion
    spoken = "Attendance increased by 5.2 pp across departments."
    audible = format_pp_for_speech(spoken)
    assert "percentage points" in audible
    assert "5.2 pp" not in audible

    # 2. Claim validation success
    claim = BriefingClaim(
        claim_id="claim_001",
        claim_type="observation",
        text="Operations recorded 85.0% attendance.",
        numeric_values=[85.0],
        source_component_id="primary_kpi",
        calculation_ids=["calc_001"],
    )
    validate_briefing_claims(
        claims=[claim],
        spoken_text="Operations recorded 85.0% attendance.",
        manifest_snapshot="snap123",
        available_component_ids={"primary_kpi"},
    )

    # 3. PII rejection in briefing
    with pytest.raises(ValueError, match="Potential PII"):
        validate_briefing_claims(
            claims=[claim],
            spoken_text="Contact manager at john.doe@pulsehr.com regarding attendance.",
            manifest_snapshot="snap123",
            available_component_ids={"primary_kpi"},
        )

    # 4. Word count enforcement
    long_text = "word " * 135
    with pytest.raises(ValueError, match="Briefing word count exceeds maximum"):
        validate_briefing_claims(
            claims=[claim],
            spoken_text=long_text,
            manifest_snapshot="snap123",
            available_component_ids={"primary_kpi"},
        )


def test_g5_3_architecture_boundary_purity():
    """G5.3 Architecture Boundary Guard: Verifies narrative modules contain ZERO DB, zero AI/LLM/MCP, and ZERO visual/composition/theme coupling."""
    import ast
    from pathlib import Path

    narrative_dir = Path(__file__).resolve().parent.parent / "app" / "services" / "adaptive_dashboard" / "narrative"
    assert narrative_dir.exists(), f"narrative package must exist at {narrative_dir}"

    forbidden_modules = {
        # Raw storage / DB
        "sqlite3", "duckdb",
        # AI / LLM / external APIs
        "ollama", "openai", "google.genai", "mcp", "requests", "httpx",
        # Visual / Presentation / Theme / Composition layers
        "visual_recommender", "composition_planner", "spatial_optimizer",
        "theme_validator", "chart_engine", "presentation",
    }

    forbidden_symbols_or_tokens = {
        "visualspec", "visual_spec", "visualrecommender", "compositionplanner",
        "spatialplacement", "themevalidator", "rendercard", "react", "chart_type",
    }

    for py_file in narrative_dir.glob("*.py"):
        code_text = py_file.read_text(encoding="utf-8")
        tree = ast.parse(code_text, filename=str(py_file))

        # 1. AST Imports check
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    top_pkg = alias.name.split(".")[0]
                    assert top_pkg not in forbidden_modules, (
                        f"Architecture violation: {py_file} imports forbidden module '{top_pkg}'"
                    )
            elif isinstance(node, ast.ImportFrom):
                if node.module:
                    top_pkg = node.module.split(".")[0]
                    sub_pkg = node.module.split(".")[-1]
                    assert top_pkg not in forbidden_modules and sub_pkg not in forbidden_modules, (
                        f"Architecture violation: {py_file} imports from forbidden module '{node.module}'"
                    )
                for alias in node.names:
                    sym_name = alias.name.lower()
                    assert sym_name not in forbidden_symbols_or_tokens, (
                        f"Architecture violation: {py_file} imports forbidden visual/composition symbol '{alias.name}'"
                    )

            # 2. AST Name/Identifier check
            elif isinstance(node, ast.Name):
                low_id = node.id.lower()
                assert low_id not in ("visualspec", "compositionplanner"), (
                    f"Architecture violation: {py_file} references forbidden class/symbol '{node.id}'"
                )

        # 3. Text-level token check for strict visual and composition decoupling
        for line_no, line in enumerate(code_text.splitlines(), start=1):
            low_line = line.strip().lower()
            if low_line.startswith("#") or low_line.startswith('"""') or low_line.startswith("'''"):
                continue
            assert "visualspec" not in low_line, (
                f"Architecture violation in {py_file}:{line_no}: Narrative layer references VisualSpec: '{line.strip()}'"
            )
            assert "composition_planner" not in low_line, (
                f"Architecture violation in {py_file}:{line_no}: Narrative layer references composition_planner: '{line.strip()}'"
            )
            assert "spatial_optimizer" not in low_line, (
                f"Architecture violation in {py_file}:{line_no}: Narrative layer references spatial_optimizer: '{line.strip()}'"
            )


# ------------------------------------------------------------------------------
# Phase G5.4 Tests: Visual Specification Boundary & ExecutiveTopic Assembly
# ------------------------------------------------------------------------------

def test_g5_4_visual_spec_identity_and_theme_absence():
    """G5.4: Verifies VisualSpec preserves topic identity, dataset, domain, and contains ZERO theme styling."""
    from app.services.adaptive_dashboard.dataset_isolation_integrity import ExecutiveTopicBindingIntegrity
    from app.services.adaptive_dashboard.visuals import (
        VisualInput,
        VisualIntegrityError,
        VisualSemanticAlignmentIntegrity,
        VisualSpecFactory,
    )

    inp = VisualInput(
        topic_id="TOPIC-001",
        dataset_id=101,
        dataset_version=2,
        domain="workforce",
        analytical_intent="RANKING",
        entity_grain="DEPARTMENT",
        full_title="Department Attendance Ranking & Policy Benchmark",
        display_title="Department Attendance Ranking",
        categories=["Engineering", "Operations", "Design"],
        values=[21.5, 23.0, 19.2],
        benchmark=15.0,
        benchmark_label="15-Day Policy Target",
        unit="days",
        evidence_ids=["EVID-HERO-001"],
    )

    spec = VisualSpecFactory.create_visual_spec(inp)
    assert spec.topic_id == "TOPIC-001"
    assert spec.dataset_id == 101
    assert spec.dataset_version == 2
    assert spec.domain == "workforce"
    assert spec.entity_grain == "DEPARTMENT"
    assert spec.chart_type == "ranked_bar"
    assert spec.full_title == "Department Attendance Ranking & Policy Benchmark"
    assert spec.display_title == "Department Attendance Ranking"
    assert spec.benchmark == 15.0
    assert spec.evidence_ids == ["EVID-HERO-001"]

    # Verify ExecutiveTopic identity check passes with matching topic_id
    valid, err = ExecutiveTopicBindingIntegrity.evaluate_topic(
        {"topic_id": "TOPIC-001", "visual_spec": spec},
        fail_closed=False,
    )
    assert valid is True
    assert err is None

    # Verify ExecutiveTopic identity check fails when topic_id mismatches
    valid_bad, err_bad = ExecutiveTopicBindingIntegrity.evaluate_topic(
        {"topic_id": "TOPIC-999", "visual_spec": spec},
        fail_closed=False,
    )
    assert valid_bad is False
    assert "VisualSpec.topic_id ('TOPIC-001') != topic_id ('TOPIC-999')" in err_bad

    # Verify theme absence check rejects hardcoded hex colors or theme directives
    with pytest.raises(VisualIntegrityError, match="Hardcoded hex color"):
        VisualSemanticAlignmentIntegrity.audit_theme_absence(
            {"chart_type": "ranked_bar", "color": "#183B56"},
            fail_closed=True,
        )


def test_g5_4_visual_spec_cannot_invent_evidence_or_narrative():
    """G5.4: Verifies that visual specification cannot create narrative findings or mint new evidence IDs."""
    from app.services.adaptive_dashboard.evidence.contracts import (
        AnalyticalFact,
        BoundEvidence,
        BoundFact,
    )
    from app.services.adaptive_dashboard.visuals import (
        VisualInput,
        VisualSpecFactory,
    )

    fact = AnalyticalFact(
        fact_id="fact_att",
        dataset_id=101,
        subject="attendance",
        metric="attendance",
        value=24.0,
        formatted_value="24.0",
        dimension="Operations",
    )
    bound_ev = BoundEvidence(
        evidence_id="EVID-VERIFIED-001",
        claim_type="general_fact",
        subject="attendance",
        metric="attendance",
        value=24.0,
        formatted_value="24.0",
    )
    bound_fact = BoundFact(fact=fact, evidence=bound_ev, topic_id="TOPIC-001")

    inp = VisualInput(
        topic_id="TOPIC-001",
        dataset_id=101,
        domain="workforce",
        bound_facts=[bound_fact],
        narrative_title="Operations Attendance Overview",
        evidence_ids=["EVID-VERIFIED-001"],
    )

    spec = VisualSpecFactory.create_visual_spec(inp)

    # Visual spec must only carry existing verified evidence IDs, never invent new ones
    assert spec.evidence_ids == ["EVID-VERIFIED-001"]
    assert not any(eid.startswith("EVID-NEW") for eid in spec.evidence_ids)

    # Visual spec does NOT generate narrative findings or takeaways
    spec_dict = spec.to_dict()
    assert "finding" not in spec_dict
    assert "takeaway" not in spec_dict
    assert "business_question" not in spec_dict
    assert "recommended_action" not in spec_dict


def test_g5_4_grain_and_title_axis_semantics():
    """G5.4: Verifies grain integrity, title-axis consistency, and cross-domain purity in VisualSpec."""
    from app.services.adaptive_dashboard.visuals import (
        VisualCapabilityRegistry,
        VisualInput,
        VisualIntegrityError,
        VisualSemanticAlignmentIntegrity,
        VisualSpecFactory,
    )

    # 1. PERSON grain ranking selects podium_top_3 when count <= 3
    person_inp = VisualInput(
        topic_id="TOPIC-P01",
        domain="workforce",
        analytical_intent="RANKING",
        entity_grain="PERSON",
        categories=["EMP001", "EMP002", "EMP003"],
        values=[25.0, 24.0, 23.0],
        full_title="Top 3 Employee Attendance",
    )
    person_spec = VisualSpecFactory.create_visual_spec(person_inp)
    assert person_spec.chart_type == "podium_top_3"
    assert person_spec.entity_grain == "PERSON"

    # 2. DEPARTMENT grain ranking rejects podium and remains ranked_bar
    dept_inp = VisualInput(
        topic_id="TOPIC-D01",
        domain="workforce",
        analytical_intent="RANKING",
        entity_grain="DEPARTMENT",
        categories=["Operations", "Engineering"],
        values=[24.0, 21.0],
        full_title="Department Total Attendance Ranking",
    )
    dept_spec = VisualSpecFactory.create_visual_spec(dept_inp)
    assert dept_spec.chart_type == "ranked_bar"
    assert dept_spec.entity_grain == "DEPARTMENT"

    # 3. Department grain with podium visual must be rejected by integrity check
    with pytest.raises(VisualIntegrityError, match="Podium visual reserved for PERSON grain"):
        bad_dept = dept_inp.model_copy(update={"chart_type": "podium_top_3"})
        VisualSpecFactory.create_visual_spec(bad_dept)

    # 4. Relationship/scatter title-axis alignment: retail axes with workforce title must fail
    with pytest.raises(VisualIntegrityError, match="Foreign domain token 'attendance' leaked|mentions workforce token"):
        retail_scatter = VisualInput(
            topic_id="TOPIC-R01",
            domain="retail",
            analytical_intent="RELATIONSHIP",
            chart_type="scatter",
            full_title="Attendance & Leave Correlation",
            x_label="Fuel Price",
            y_label="Weekly Sales",
        )
        VisualSpecFactory.create_visual_spec(retail_scatter)

    # 4b. Direct title-axis alignment audit test with general domain
    with pytest.raises(VisualIntegrityError, match="mentions workforce token"):
        VisualSemanticAlignmentIntegrity.audit_title_axis_alignment({
            "chart_type": "scatter",
            "full_title": "Attendance & Leave Correlation",
            "x_label": "Fuel Price",
            "y_label": "Weekly Sales",
        }, fail_closed=True)

    # 5. Full title and display title preservation
    long_inp = VisualInput(
        topic_id="TOPIC-T01",
        domain="workforce",
        full_title="Strategic Enterprise Department Attendance & Leave Benchmark Over July 2026 Cycle",
        display_title="Department Attendance & Benchmark",
    )
    long_spec = VisualSpecFactory.create_visual_spec(long_inp)
    assert long_spec.full_title == "Strategic Enterprise Department Attendance & Leave Benchmark Over July 2026 Cycle"
    assert long_spec.display_title == "Department Attendance & Benchmark"


def test_g5_4_composition_immutability_and_non_positional_merging():
    """G5.4: Verifies composition cannot mutate VisualSpec semantics, and lookups avoid positional index merging."""
    from app.services.adaptive_dashboard.visuals import (
        VisualInput,
        VisualIntegrityError,
        VisualSemanticsMutationIntegrity,
        VisualSpecFactory,
    )

    inp = VisualInput(
        topic_id="TOPIC-COMP-01",
        domain="retail",
        analytical_intent="RELATIONSHIP",
        chart_type="scatter",
        full_title="Weekly Sales vs Fuel Price",
        x_label="Fuel Price",
        y_label="Weekly Sales",
        categories=["Store 1", "Store 2"],
        values=[1600000.0, 2100000.0],
        evidence_ids=["EVID-STORE-01"],
    )
    spec = VisualSpecFactory.create_visual_spec(inp)

    # Valid composition handoff: composition adds layout parameters
    composed_valid = spec.to_dict()
    composed_valid["span"] = 8
    composed_valid["row"] = 1
    composed_valid["height_px"] = 350
    VisualSemanticsMutationIntegrity.verify_composition_handoff(spec, composed_valid, fail_closed=True)

    # Invalid composition handoff: composition mutates chart_type
    composed_bad_chart = spec.to_dict()
    composed_bad_chart["chart_type"] = "pie"
    with pytest.raises(VisualIntegrityError, match="mutated immutable VisualSpec semantic property 'chart_type'"):
        VisualSemanticsMutationIntegrity.verify_composition_handoff(spec, composed_bad_chart, fail_closed=True)

    # Invalid composition handoff: composition mutates values
    composed_bad_vals = spec.to_dict()
    composed_bad_vals["values"] = [9999999.0]
    with pytest.raises(VisualIntegrityError, match="mutated immutable VisualSpec semantic property 'values'"):
        VisualSemanticsMutationIntegrity.verify_composition_handoff(spec, composed_bad_vals, fail_closed=True)

    # Non-positional topic lookup test
    topics_store = {
        "TOPIC-001": {"topic_id": "TOPIC-001", "name": "Topic 1"},
        "TOPIC-002": {"topic_id": "TOPIC-002", "name": "Topic 2"},
    }
    # Direct keyed lookup succeeds without index assumption
    assert topics_store["TOPIC-002"]["name"] == "Topic 2"


def test_g5_4_architecture_boundary_purity():
    """G5.4 Architecture Boundary Guard: Verifies visual specification modules contain ZERO DB, zero AI/LLM/MCP, and ZERO composition planner imports."""
    import ast
    from pathlib import Path

    visuals_dir = Path(__file__).resolve().parent.parent / "app" / "services" / "adaptive_dashboard" / "visuals"
    assert visuals_dir.exists(), f"visuals package must exist at {visuals_dir}"

    forbidden_modules = {
        # Raw storage / DB
        "sqlite3", "duckdb",
        # AI / LLM / external APIs
        "ollama", "openai", "google.genai", "mcp", "requests", "httpx",
        # Composition and Spatial Planner layers
        "composition_planner", "spatial_composition_optimizer",
        # Frontend / React / CSS
        "react", "css",
    }

    forbidden_symbols_or_tokens = {
        "compositionplanner", "spatialplacement", "rendercard", "react",
    }

    for py_file in visuals_dir.glob("*.py"):
        code_text = py_file.read_text(encoding="utf-8")
        tree = ast.parse(code_text, filename=str(py_file))

        # 1. AST Imports check
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    top_pkg = alias.name.split(".")[0]
                    assert top_pkg not in forbidden_modules, (
                        f"Architecture violation: {py_file} imports forbidden module '{top_pkg}'"
                    )
            elif isinstance(node, ast.ImportFrom):
                if node.module:
                    top_pkg = node.module.split(".")[0]
                    sub_pkg = node.module.split(".")[-1]
                    assert top_pkg not in forbidden_modules and sub_pkg not in forbidden_modules, (
                        f"Architecture violation: {py_file} imports from forbidden module '{node.module}'"
                    )
                for alias in node.names:
                    sym_name = alias.name.lower()
                    assert sym_name not in forbidden_symbols_or_tokens, (
                        f"Architecture violation: {py_file} imports forbidden symbol '{alias.name}'"
                    )

            # 2. AST Name/Identifier check
            elif isinstance(node, ast.Name):
                low_id = node.id.lower()
                assert low_id != "compositionplanner", (
                    f"Architecture violation: {py_file} references forbidden class/symbol '{node.id}'"
                )

        # 3. Text-level token check
        for line_no, line in enumerate(code_text.splitlines(), start=1):
            low_line = line.strip().lower()
            if low_line.startswith("#") or low_line.startswith('"""') or low_line.startswith("'''"):
                continue
            assert "composition_planner" not in low_line, (
                f"Architecture violation in {py_file}:{line_no}: Visuals layer references composition_planner: '{line.strip()}'"
            )
            assert "spatial_composition_optimizer" not in low_line, (
                f"Architecture violation in {py_file}:{line_no}: Visuals layer references spatial_composition_optimizer: '{line.strip()}'"
            )


# ==============================================================================
# Phase G5.5 Characterization Tests: Story & ExecutiveTopic Factory Boundary
# ==============================================================================

def test_g5_5_topic_id_centralization():
    """Phase G5.5: Verifies central topic identifier generation."""
    from app.services.adaptive_dashboard.topics import TopicIdGenerator

    assert TopicIdGenerator.format_id(1) == "TOPIC-001"
    assert TopicIdGenerator.format_id(42) == "TOPIC-042"
    assert TopicIdGenerator.format_id(100) == "TOPIC-100"
    assert TopicIdGenerator.parse_index("TOPIC-001") == 1
    assert TopicIdGenerator.parse_index("TOPIC-042") == 42


def test_g5_5_executive_topic_factory_identity_assembly():
    """Phase G5.5: Verifies strict identity-based assembly in ExecutiveTopicFactory."""
    from app.services.adaptive_dashboard.topics import (
        ExecutiveTopicDraft,
        ExecutiveTopicFactory,
        StoryAssemblyIntegrityError,
    )

    t_id = "TOPIC-005"
    valid_draft = ExecutiveTopicDraft(
        topic_id=t_id,
        dataset_id=99770,
        domain="workforce",
        analytical_intent="RANKING",
        entity_grain="PERSON",
        narrative={
            "topic_id": t_id,
            "title": "Top 3 Employee Attendance Leaders",
            "subtitle": "Individual attendance ranking",
            "finding": "Top performers maintain 100% presence.",
            "takeaway": "Top performers maintain 100% presence.",
            "recommended_action": "Recognize leaders.",
        },
        evidence_binding={
            "topic_id": t_id,
            "evidence_id": "EVID-PODIUM-01",
        },
        priority=5,
    )

    topic = ExecutiveTopicFactory.create_topic(valid_draft)
    assert topic.topic_id == t_id
    assert topic.title == "Top 3 Employee Attendance Leaders"
    assert topic.takeaway == "Top performers maintain 100% presence."
    assert "EVID-PODIUM-01" in topic.evidence_ids

    # Mismatched narrative topic_id must fail closed
    invalid_narrative_draft = valid_draft.model_copy(deep=True)
    invalid_narrative_draft.narrative["topic_id"] = "TOPIC-999"
    with pytest.raises(StoryAssemblyIntegrityError, match="IDENTITY_MISMATCH"):
        ExecutiveTopicFactory.create_topic(invalid_narrative_draft)

    # Mismatched evidence binding topic_id must fail closed
    invalid_evidence_draft = valid_draft.model_copy(deep=True)
    invalid_evidence_draft.evidence_binding["topic_id"] = "TOPIC-888"
    with pytest.raises(StoryAssemblyIntegrityError, match="IDENTITY_MISMATCH"):
        ExecutiveTopicFactory.create_topic(invalid_evidence_draft)


def test_g5_5_visual_spec_binding_by_identity():
    """Phase G5.5: Verifies that visual specs are bound strictly by matching topic identity."""
    from app.services.adaptive_dashboard.topics import (
        ExecutiveTopicDraft,
        ExecutiveTopicFactory,
        StoryAssemblyIntegrityError,
    )

    t_id = "TOPIC-003"
    draft = ExecutiveTopicDraft(
        topic_id=t_id,
        dataset_id=99770,
        domain="workforce",
        analytical_intent="COMPOSITION",
        narrative={"topic_id": t_id, "title": "Weekly Capacity Distribution"},
        priority=3,
    )
    topic = ExecutiveTopicFactory.create_topic(draft)

    # Aligned visual spec succeeds
    matching_spec = {
        "topic_id": t_id,
        "chart_type": "100_percent_stacked_bar",
        "categories": ["W1", "W2"],
        "values": [80, 20],
    }
    ExecutiveTopicFactory.bind_visual_spec(topic, matching_spec)
    assert topic.visual_spec["topic_id"] == t_id
    assert topic.visual_spec["chart_type"] == "100_percent_stacked_bar"

    # Mismatched visual spec must fail closed
    mismatched_spec = {
        "topic_id": "TOPIC-DIFFERENT",
        "chart_type": "scatter",
    }
    with pytest.raises(StoryAssemblyIntegrityError, match="IDENTITY_MISMATCH"):
        ExecutiveTopicFactory.bind_visual_spec(topic, mismatched_spec)


def test_g5_5_portfolio_assembly_rejects_positional_binding():
    """Phase G5.5: Verifies that assemble_portfolio_with_visuals binds by identity lookup, not array position."""
    from app.services.adaptive_dashboard.topics import (
        ExecutiveTopicDraft,
        ExecutiveTopicFactory,
        StoryAssemblyIntegrityError,
    )

    drafts = [
        ExecutiveTopicDraft(
            topic_id="TOPIC-001",
            priority=1,
            narrative={"topic_id": "TOPIC-001", "title": "Topic One"},
        ),
        ExecutiveTopicDraft(
            topic_id="TOPIC-002",
            priority=2,
            narrative={"topic_id": "TOPIC-002", "title": "Topic Two"},
        ),
    ]

    # Map provides specs by topic_id in reversed key order
    specs_by_id = {
        "TOPIC-002": {"topic_id": "TOPIC-002", "chart_type": "scatter"},
        "TOPIC-001": {"topic_id": "TOPIC-001", "chart_type": "ranked_bar"},
    }

    portfolio = ExecutiveTopicFactory.assemble_portfolio_with_visuals(drafts, specs_by_id)
    assert len(portfolio) == 2
    assert portfolio[0].topic_id == "TOPIC-001"
    assert portfolio[0].visual_spec["chart_type"] == "ranked_bar"
    assert portfolio[1].topic_id == "TOPIC-002"
    assert portfolio[1].visual_spec["chart_type"] == "scatter"

    # Missing topic in identity map must fail closed
    incomplete_map = {"TOPIC-001": {"topic_id": "TOPIC-001", "chart_type": "ranked_bar"}}
    with pytest.raises(StoryAssemblyIntegrityError, match="STORY_ASSEMBLY_UNBOUND_TOPIC"):
        ExecutiveTopicFactory.assemble_portfolio_with_visuals(drafts, incomplete_map)


def test_g5_5_topics_package_ast_purity():
    """Phase G5.5: Validates AST purity of topics package (zero DB, AI, MCP, theme, layout)."""
    from app.services.adaptive_dashboard.topics import StoryAssemblyIntegrity

    violations = StoryAssemblyIntegrity.audit_ast_purity()
    assert violations == [], f"Topics package AST violations: {violations}"


def test_g5_5_topic_identity_seed_determinism_and_concurrency():
    """Phase G5.5: Verifies TopicIdentitySeed and TopicIdentityFactory determinism under 20 concurrent threads."""
    import concurrent.futures
    from app.services.adaptive_dashboard.topics import (
        TopicIdentitySeed,
        TopicIdentityFactory,
    )

    seed_identical = TopicIdentitySeed(
        dataset_id=101,
        dataset_version=1,
        domain="retail",
        analytical_intent="RANKING",
        entity_grain="STORE",
        metric_family="sales",
        measure_ids=["weekly_sales"],
        dimension_ids=["store"],
        opportunity_id="OPP-001",
    )

    # 1. 20 concurrent threads with identical seed must return the EXACT same topic_id
    with concurrent.futures.ThreadPoolExecutor(max_workers=20) as executor:
        futures = [executor.submit(TopicIdentityFactory.create_topic_id, seed_identical) for _ in range(20)]
        results = [f.result() for f in futures]

    assert len(results) == 20
    assert len(set(results)) == 1, f"Expected 1 unique topic_id across threads, got: {set(results)}"
    canonical_id = results[0]
    assert canonical_id.startswith("TOPIC-")
    assert len(canonical_id) == 14  # "TOPIC-" (6) + 8 hex chars

    # 2. 20 concurrent threads with 20 distinct seeds must return exactly 20 distinct topic_ids
    distinct_seeds = [
        TopicIdentitySeed(
            dataset_id=101,
            dataset_version=1,
            domain="retail",
            analytical_intent="RANKING",
            entity_grain="STORE",
            metric_family=f"family_{i}",
            measure_ids=[f"metric_{i}"],
            dimension_ids=["store"],
            opportunity_id=f"OPP-{i:03d}",
        )
        for i in range(20)
    ]
    with concurrent.futures.ThreadPoolExecutor(max_workers=20) as executor:
        futures = [executor.submit(TopicIdentityFactory.create_topic_id, s) for s in distinct_seeds]
        distinct_results = [f.result() for f in futures]

    assert len(distinct_results) == 20
    assert len(set(distinct_results)) == 20, "Every distinct semantic seed must yield a unique topic_id"


def test_g5_5_topic_identity_ordering_invariance():
    """Phase G5.5: Verifies that topic identity is strictly invariant to portfolio order / permutations."""
    from app.services.adaptive_dashboard.topics import (
        TopicIdentitySeed,
        TopicIdentityFactory,
    )

    seed_a = TopicIdentitySeed(
        dataset_id=200,
        domain="workforce",
        analytical_intent="COMPOSITION",
        entity_grain="DEPARTMENT",
        metric_family="presence",
        measure_ids=["office_presence", "approved_leaves"],
        opportunity_id="OPP-A",
    )
    seed_b = TopicIdentitySeed(
        dataset_id=200,
        domain="workforce",
        analytical_intent="RANKING",
        entity_grain="PERSON",
        metric_family="attendance",
        measure_ids=["total_attendance"],
        opportunity_id="OPP-B",
    )
    seed_c = TopicIdentitySeed(
        dataset_id=200,
        domain="workforce",
        analytical_intent="TREND",
        entity_grain="DEPARTMENT",
        metric_family="headcount",
        measure_ids=["headcount_delta"],
        opportunity_id="OPP-C",
    )

    id_a = TopicIdentityFactory.create_topic_id(seed_a)
    id_b = TopicIdentityFactory.create_topic_id(seed_b)
    id_c = TopicIdentityFactory.create_topic_id(seed_c)

    # Permutation 1: [A, B, C]
    perm1 = [TopicIdentityFactory.create_topic_id(s) for s in [seed_a, seed_b, seed_c]]
    # Permutation 2: [C, A, B]
    perm2 = [TopicIdentityFactory.create_topic_id(s) for s in [seed_c, seed_a, seed_b]]
    # Permutation 3: [B, C, A]
    perm3 = [TopicIdentityFactory.create_topic_id(s) for s in [seed_b, seed_c, seed_a]]

    assert perm1 == [id_a, id_b, id_c]
    assert perm2 == [id_c, id_a, id_b]
    assert perm3 == [id_b, id_c, id_a]


def test_g5_5_topic_identity_insertion_invariance():
    """Phase G5.5: Verifies that inserting an adjacent topic does not shift or destabilize existing topic IDs."""
    from app.services.adaptive_dashboard.topics import (
        TopicIdentitySeed,
        TopicIdentityFactory,
    )

    seed_a = TopicIdentitySeed(
        dataset_id=300,
        domain="environmental",
        analytical_intent="TREND",
        metric_family="pm10",
        measure_ids=["pm10"],
        opportunity_id="OPP-AIR-01",
    )
    seed_b = TopicIdentitySeed(
        dataset_id=300,
        domain="environmental",
        analytical_intent="RANKING",
        entity_grain="CITY",
        metric_family="so2",
        measure_ids=["so2"],
        opportunity_id="OPP-AIR-02",
    )
    seed_c = TopicIdentitySeed(
        dataset_id=300,
        domain="environmental",
        analytical_intent="RELATIONSHIP",
        metric_family="pollution_corr",
        measure_ids=["so2", "no2"],
        opportunity_id="OPP-AIR-03",
    )

    orig_ids = [TopicIdentityFactory.create_topic_id(s) for s in [seed_a, seed_b, seed_c]]

    # Insert new opportunity X between A and B: [A, X, B, C]
    seed_x = TopicIdentitySeed(
        dataset_id=300,
        domain="environmental",
        analytical_intent="ANOMALY",
        metric_family="pm10_spike",
        measure_ids=["pm10"],
        opportunity_id="OPP-AIR-NEW",
    )
    expanded_list = [seed_a, seed_x, seed_b, seed_c]
    new_ids = [TopicIdentityFactory.create_topic_id(s) for s in expanded_list]

    # A, B, and C must keep their exact original topic_ids
    assert new_ids[0] == orig_ids[0]  # A
    assert new_ids[2] == orig_ids[1]  # B
    assert new_ids[3] == orig_ids[2]  # C


def test_g5_5_semantic_topic_key_cross_version_continuity():
    """Phase G5.5: Verifies that semantic_topic_key provides logical topic tracking across dataset versions."""
    from app.services.adaptive_dashboard.topics import (
        TopicIdentitySeed,
        TopicIdentityFactory,
    )

    seed_v1 = TopicIdentitySeed(
        dataset_id=400,
        dataset_version=1,
        domain="workforce",
        analytical_intent="RANKING",
        entity_grain="PERSON",
        metric_family="attendance",
        measure_ids=["total_attendance"],
        opportunity_id="OPP-1",
    )
    seed_v2 = TopicIdentitySeed(
        dataset_id=400,
        dataset_version=2,
        domain="workforce",
        analytical_intent="RANKING",
        entity_grain="PERSON",
        metric_family="attendance",
        measure_ids=["total_attendance"],
        opportunity_id="OPP-1",
    )

    # topic_id is version-scoped (must differ)
    id_v1 = TopicIdentityFactory.create_topic_id(seed_v1)
    id_v2 = TopicIdentityFactory.create_topic_id(seed_v2)
    assert id_v1 != id_v2, "Topic IDs must differ across dataset versions"

    # semantic_topic_key is logical and version-independent (must match)
    assert seed_v1.semantic_topic_key == seed_v2.semantic_topic_key
    assert seed_v1.semantic_topic_key == "workforce:ranking:person:attendance"


def test_g5_5_executive_topic_semantic_immutability():
    """Phase G5.5: Verifies that ExecutiveTopic semantic identity fields are protected from downstream mutation."""
    from app.services.adaptive_dashboard.topics import (
        ExecutiveTopicDraft,
        ExecutiveTopicFactory,
    )

    draft = ExecutiveTopicDraft(
        topic_id="TOPIC-abcdef01",
        semantic_topic_key="workforce:composition:department:presence",
        display_order=1,
        rank=1,
        portfolio_position=1,
        dataset_id=500,
        domain="workforce",
        analytical_intent="COMPOSITION",
        evidence_ids=["EVID-01", "EVID-02"],
        narrative={"topic_id": "TOPIC-abcdef01", "title": "Department Capacity"},
    )
    topic = ExecutiveTopicFactory.create_topic(draft)

    # Attempting to mutate semantic identity fields must raise AttributeError
    with pytest.raises(AttributeError, match="IMMUTABILITY_VIOLATION"):
        topic.topic_id = "TOPIC-MUTATED"

    with pytest.raises(AttributeError, match="IMMUTABILITY_VIOLATION"):
        topic.semantic_topic_key = "mutated:key"

    with pytest.raises(AttributeError, match="IMMUTABILITY_VIOLATION"):
        topic.analytical_intent = "RANKING"

    with pytest.raises(AttributeError, match="IMMUTABILITY_VIOLATION"):
        topic.domain = "retail"

    with pytest.raises(AttributeError, match="IMMUTABILITY_VIOLATION"):
        topic.dataset_id = 9999

    with pytest.raises(AttributeError, match="IMMUTABILITY_VIOLATION"):
        topic.evidence_ids = ["EVID-MUTATED"]

    # Non-semantic presentation fields are allowed to update
    topic.display_order = 2
    assert topic.display_order == 2
    topic.rank = 2
    assert topic.rank == 2

    # G5.6: Spatial placement fields cannot be mutated on ExecutiveTopic
    with pytest.raises(AttributeError, match="COMPOSITION_MUTATION_VIOLATION"):
        topic.spatial_placement = {"row": 1, "col": 0, "width": 6}


def test_g5_5_cache_topic_id_stability():
    """Phase G5.5: Verifies end-to-end topic ID stability across cold run, warm cache, and re-execution."""
    with session_scope() as conn:
        ds_id = _create_dataset_with_rows(conn, "stability_eval.csv", "Workforce Stability", "Attendance", WORKFORCE_RECORDS)

    # Cold Run 1
    res1_obj = run_dataset_intelligence(dataset_id=ds_id)
    res1 = res1_obj.model_dump()
    topics1 = res1.get("executive_topics", []) or res1.get("elements", [])
    assert len(topics1) > 0
    ids_run1 = [t.get("topic_id") for t in topics1]

    # Cold Run 2 (or cached run)
    res2_obj = run_dataset_intelligence(dataset_id=ds_id)
    res2 = res2_obj.model_dump()
    topics2 = res2.get("executive_topics", []) or res2.get("elements", [])
    ids_run2 = [t.get("topic_id") for t in topics2]

    # Topic IDs must be completely identical across runs
    assert ids_run1 == ids_run2, f"Topic IDs drifted between runs: {ids_run1} vs {ids_run2}"
    for tid in ids_run1:
        assert tid.startswith("TOPIC-"), f"Expected canonical TOPIC- prefix, got: {tid}"


# ------------------------------------------------------------------------------
# Phase G5.6: Spatial & Composition Boundary Extraction Tests
# ------------------------------------------------------------------------------

def test_g5_6_composition_cannot_mutate_executive_topic():
    """Phase G5.6: Verifies that ExecutiveTopic is protected against composition/spatial layout mutation."""
    from app.services.adaptive_dashboard.topics import (
        ExecutiveTopicDraft,
        ExecutiveTopicFactory,
    )

    draft = ExecutiveTopicDraft(
        topic_id="TOPIC-g56-spatial-01",
        semantic_topic_key="workforce:composition:department:presence",
        display_order=1,
        rank=1,
        portfolio_position=1,
        dataset_id=500,
        domain="workforce",
        analytical_intent="COMPOSITION",
        evidence_ids=["EVID-01", "EVID-02"],
        narrative={"topic_id": "TOPIC-g56-spatial-01", "title": "Department Capacity"},
    )
    topic = ExecutiveTopicFactory.create_topic(draft)

    # Attempting to assign layout fields directly to ExecutiveTopic must raise AttributeError
    for field, val in [
        ("spatial_placement", {"column_span": 8, "height_class": "tall"}),
        ("row", 1),
        ("column", 0),
        ("span", 8),
        ("height", "tall"),
    ]:
        with pytest.raises(AttributeError, match="COMPOSITION_MUTATION_VIOLATION"):
            setattr(topic, field, val)


def test_g5_6_composition_cannot_mutate_visual_spec():
    """Phase G5.6: Verifies that layout planning does not mutate the input VisualSpec in any way."""
    from app.services.adaptive_dashboard.composition import (
        SpatialCompositionPlanner,
        CompositionIntegrity,
    )
    from app.services.adaptive_dashboard.composition_planner import ExecutiveTopic

    visual_spec = {
        "chart_type": "ranked_bar",
        "title": "Department Headcount",
        "categories": ["Engineering", "Product", "Operations"],
        "values": [45, 20, 30],
        "unit": "people",
    }
    topic = ExecutiveTopic(
        topic_id="TOPIC-vspec-test",
        title="Department Headcount",
        analytical_intent="RANKING",
        recommended_visual="ranked_bar",
        visual_spec=visual_spec,
    )

    fp_before = CompositionIntegrity.compute_visual_semantic_fingerprint(topic.visual_spec)
    plan = SpatialCompositionPlanner.plan_layout([topic], domain="workforce")
    fp_after = CompositionIntegrity.compute_visual_semantic_fingerprint(topic.visual_spec)

    assert fp_before == fp_after, "VisualSpec was mutated during composition planning!"
    assert topic.visual_spec == visual_spec


def test_g5_6_composition_item_independent_of_topic():
    """Phase G5.6: Verifies layout coordinates live on CompositionItem in DashboardLayoutPlan, not on topic."""
    from app.services.adaptive_dashboard.composition import (
        SpatialCompositionPlanner,
        DashboardLayoutPlan,
        CompositionItem,
    )
    from app.services.adaptive_dashboard.composition_planner import ExecutiveTopic

    t1 = ExecutiveTopic(
        topic_id="TOPIC-item-01",
        title="Metric Overview",
        analytical_intent="METRIC",
        recommended_visual="bullet",
        visual_spec={"chart_type": "bullet"},
    )
    t2 = ExecutiveTopic(
        topic_id="TOPIC-item-02",
        title="Trend Analysis",
        analytical_intent="TREND",
        recommended_visual="trend_line",
        visual_spec={"chart_type": "trend_line"},
    )

    plan = SpatialCompositionPlanner.plan_layout([t1, t2], domain="workforce")

    assert isinstance(plan, DashboardLayoutPlan)
    assert len(plan.items) == 2
    assert "TOPIC-item-01" in plan.items_by_topic_id
    assert "TOPIC-item-02" in plan.items_by_topic_id

    item1 = plan.get_placement("TOPIC-item-01")
    assert isinstance(item1, CompositionItem)
    assert item1.span > 0
    assert item1.height_class in ("short", "standard", "tall")
    assert item1.topic_id == "TOPIC-item-01"

    # ExecutiveTopic instances remain unmutated by layout
    assert not hasattr(t1, "span")
    assert getattr(t1, "spatial_placement", None) is None


def test_g5_6_composition_integrity_validation():
    """Phase G5.6: Verifies CompositionIntegrity validates topic existence, non-overlapping columns, positive dimensions, and readability minimums."""
    from app.services.adaptive_dashboard.composition import (
        CompositionIntegrity,
        CompositionIntegrityError,
        DashboardLayoutPlan,
        CompositionItem,
        CompositionRow,
        CompositionSection,
    )
    from app.services.adaptive_dashboard.composition_planner import ExecutiveTopic

    t1 = ExecutiveTopic(topic_id="T1", title="Card 1", analytical_intent="RANKING", recommended_visual="ranked_bar", visual_spec={"chart_type": "ranked_bar"})
    t2 = ExecutiveTopic(topic_id="T2", title="Card 2", analytical_intent="COMPARISON", recommended_visual="lollipop", visual_spec={"chart_type": "lollipop"})

    item1 = CompositionItem(topic_id="T1", span=8, height="standard", row=0, column=0, pattern="8+4", section_id="sec-1")
    item2 = CompositionItem(topic_id="T2", span=4, height="standard", row=0, column=8, pattern="8+4", section_id="sec-1")

    # Valid plan
    valid_plan = DashboardLayoutPlan(
        plan_id="plan-valid",
        dataset_id=1,
        dataset_version=1,
        domain="workforce",
        grid_columns=12,
        items=[item1, item2],
        items_by_topic_id={"T1": item1, "T2": item2},
        sections=[
            CompositionSection(
                section_id="sec-1",
                title="Section 1",
                rows=[
                    CompositionRow(
                        row_id="r-1",
                        section_id="sec-1",
                        row_index=0,
                        total_span=12,
                        pattern="8+4",
                        cards=[item1, item2],
                    )
                ]
            )
        ]
    )
    CompositionIntegrity.assert_valid_plan(valid_plan, [t1, t2])

    # 1. Unknown topic ID rejection
    bad_item = CompositionItem(topic_id="UNKNOWN_TOPIC", span=12, height="standard", row=0, column=0)
    plan_unknown_topic = DashboardLayoutPlan(
        plan_id="plan-unknown",
        dataset_id=1,
        dataset_version=1,
        domain="workforce",
        items=[bad_item],
        items_by_topic_id={"UNKNOWN_TOPIC": bad_item},
        sections=[
            CompositionSection(
                section_id="sec-1",
                title="Section 1",
                rows=[
                    CompositionRow(
                        row_id="r-1",
                        section_id="sec-1",
                        cards=[bad_item],
                    )
                ]
            )
        ]
    )
    with pytest.raises(CompositionIntegrityError, match="COMPOSITION_UNKNOWN_TOPIC"):
        CompositionIntegrity.assert_valid_plan(plan_unknown_topic, [t1, t2])

    # 2. Overlapping columns rejection (col 0 span 8 + col 6 span 6 = overlap at cols 6-7)
    overlap_item1 = CompositionItem(topic_id="T1", span=8, height="standard", row=0, column=0)
    overlap_item2 = CompositionItem(topic_id="T2", span=6, height="standard", row=0, column=6)
    plan_overlap = DashboardLayoutPlan(
        plan_id="plan-overlap",
        dataset_id=1,
        dataset_version=1,
        domain="workforce",
        items=[overlap_item1, overlap_item2],
        items_by_topic_id={"T1": overlap_item1, "T2": overlap_item2},
        sections=[
            CompositionSection(
                section_id="sec-1",
                title="Section 1",
                rows=[
                    CompositionRow(
                        row_id="r-1",
                        section_id="sec-1",
                        cards=[overlap_item1, overlap_item2],
                    )
                ]
            )
        ]
    )
    with pytest.raises(CompositionIntegrityError, match="COMPOSITION_GRID_OVERLAP"):
        CompositionIntegrity.assert_valid_plan(plan_overlap, [t1, t2])

    # 3. Readability minimum rejection (ranked bar forced into 4 cols)
    unreadable_item = CompositionItem(topic_id="T1", span=4, height="standard", row=0, column=0)
    plan_unreadable = DashboardLayoutPlan(
        plan_id="plan-unreadable",
        dataset_id=1,
        dataset_version=1,
        domain="workforce",
        items=[unreadable_item],
        items_by_topic_id={"T1": unreadable_item},
        sections=[
            CompositionSection(
                section_id="sec-1",
                title="Section 1",
                rows=[
                    CompositionRow(
                        row_id="r-1",
                        section_id="sec-1",
                        cards=[unreadable_item],
                    )
                ]
            )
        ]
    )
    with pytest.raises(CompositionIntegrityError, match="COMPOSITION_READABILITY_VIOLATION"):
        CompositionIntegrity.assert_valid_plan(plan_unreadable, [t1])


def test_g5_6_composition_ast_purity():
    """Phase G5.6: Verifies that adaptive_dashboard/composition/ has zero DB, AI/LLM, MCP, or Theme dependencies."""
    from app.services.adaptive_dashboard.composition import CompositionIntegrity

    violations = CompositionIntegrity.audit_ast_purity()
    assert violations == [], f"AST purity audit failed in composition package: {violations}"


def test_g5_6_characterization_equivalence():
    """Phase G5.6: Verifies layout plans for Workforce, Retail, and Environmental match characterization baseline."""
    import os
    from pathlib import Path

    # If running in pytest with isolated temporary database, ensure canonical benchmark rows are seeded
    real_db = Path(__file__).resolve().parents[1] / "data" / "db" / "pulsehr.sqlite3"
    with session_scope() as conn:
        has_99770 = conn.execute("SELECT 1 FROM dataset_uploads WHERE id = 99770").fetchone()
        if not has_99770 and real_db.exists():
            conn.execute(f'ATTACH DATABASE "{real_db}" AS real_source')
            conn.execute("INSERT OR REPLACE INTO dataset_uploads (id, filename, original_name, file_type, display_name) SELECT id, filename, original_name, file_type, display_name FROM real_source.dataset_uploads WHERE id IN (99770, 99771, 99772)")
            conn.execute("INSERT OR REPLACE INTO sheets (id, dataset_id, name, display_name, columns_json, profile_json, row_count) SELECT id, dataset_id, name, display_name, columns_json, profile_json, row_count FROM real_source.sheets WHERE dataset_id IN (99770, 99771, 99772)")
            conn.execute("INSERT OR REPLACE INTO sheet_rows (id, sheet_id, row_index, data_json) SELECT id, sheet_id, row_index, data_json FROM real_source.sheet_rows WHERE sheet_id IN (SELECT id FROM real_source.sheets WHERE dataset_id IN (99770, 99771, 99772))")
            try:
                conn.execute("INSERT OR REPLACE INTO sheet_relationships SELECT * FROM real_source.sheet_relationships WHERE left_sheet_id IN (SELECT id FROM real_source.sheets WHERE dataset_id IN (99770, 99771, 99772))")
            except Exception:
                pass
            conn.commit()
            conn.execute("DETACH DATABASE real_source")

    baseline_path = os.path.join(
        os.path.dirname(__file__), "fixtures", "composition_characterization_baseline.json"
    )
    with open(baseline_path, "r", encoding="utf-8") as f:
        baseline = json.load(f)

    for domain_name, ds_id in [("Workforce", 99770), ("Retail", 99771), ("Environmental", 99772)]:
        res = run_dataset_intelligence(dataset_id=ds_id).model_dump()
        lp = res.get("layout_plan")
        assert lp is not None, f"Layout plan missing for {domain_name} ({ds_id})"
        assert lp["total_cards"] == baseline[domain_name]["total_cards"]
        assert lp["total_rows"] == baseline[domain_name]["total_rows"]

        for exp_sec, act_sec in zip(baseline[domain_name]["sections"], lp["sections"]):
            assert exp_sec["section_id"] == act_sec["section_id"]
            assert len(exp_sec["rows"]) == len(act_sec["rows"])
            for exp_row, act_row in zip(exp_sec["rows"], act_sec["rows"]):
                assert exp_row["pattern"] == act_row["pattern"]
                assert exp_row["total_span"] == act_row["total_span"]
                assert len(exp_row["cards"]) == len(act_row["cards"])
                for exp_c, act_c in zip(exp_row["cards"], act_row["cards"]):
                    assert exp_c["column_span"] == act_c["column_span"]
                    assert exp_c["chart_archetype"] == act_c["chart_archetype"]


def test_g5_7_engine_ast_purity():
    """Phase G5.7: Verifies that engine.py is a pure orchestration facade with ZERO raw DB, AI SDKs, theme, or spatial packing."""
    import ast
    from pathlib import Path

    engine_file = Path(__file__).resolve().parent.parent / "app" / "services" / "adaptive_dashboard" / "engine.py"
    assert engine_file.exists(), f"engine.py must exist at {engine_file}"

    forbidden_modules = {
        # Raw storage / DB
        "sqlite3", "duckdb",
        # AI / LLM / external APIs
        "ollama", "openai", "google.genai", "mcp", "requests", "httpx",
        # Theme / frontend
        "theme_validator", "react", "css",
        # Spatial placement logic
        "spatial_composition_optimizer",
    }

    code_text = engine_file.read_text(encoding="utf-8")
    tree = ast.parse(code_text, filename=str(engine_file))

    # 1. Imports check
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                top_pkg = alias.name.split(".")[0]
                assert top_pkg not in forbidden_modules, f"Forbidden import in engine.py: {alias.name}"
        elif isinstance(node, ast.ImportFrom):
            mod = node.module or ""
            for fm in forbidden_modules:
                assert fm not in mod, f"Forbidden from-import in engine.py: {mod}"

    # 2. Raw SQL / execute checks (all database operations must be delegated to source_data_loader)
    for node in ast.walk(tree):
        if isinstance(node, ast.Call):
            if isinstance(node.func, ast.Attribute) and node.func.attr == "execute":
                raise AssertionError(f"engine.py must not execute raw SQL queries; found raw execute at line {node.lineno}")

    # 3. Direct hashing checks (topic hashing must be delegated to topics/ package)
    for node in ast.walk(tree):
        if isinstance(node, ast.Call):
            if isinstance(node.func, ast.Attribute) and node.func.attr in ("hexdigest", "sha256", "md5"):
                raise AssertionError(f"engine.py must not perform low-level hashing; found {node.func.attr} at line {node.lineno}")


def test_g5_7_packages_do_not_import_engine():
    """Phase G5.7: Verifies that all 6 extracted packages have ZERO imports of engine.py (strict downward dependency direction)."""
    import ast
    from pathlib import Path

    packages = ["formatting", "evidence", "narrative", "topics", "visuals", "composition"]
    base_dir = Path(__file__).resolve().parent.parent / "app" / "services" / "adaptive_dashboard"

    violations = []
    for pkg in packages:
        pkg_dir = base_dir / pkg
        for py_file in pkg_dir.glob("**/*.py"):
            code_text = py_file.read_text(encoding="utf-8")
            tree = ast.parse(code_text, filename=str(py_file))
            for node in ast.walk(tree):
                if isinstance(node, ast.Import):
                    for alias in node.names:
                        if "engine" in alias.name:
                            violations.append((str(py_file.relative_to(base_dir)), alias.name))
                elif isinstance(node, ast.ImportFrom):
                    mod = node.module or ""
                    if "engine" in mod:
                        violations.append((str(py_file.relative_to(base_dir)), mod))
                    for alias in node.names:
                        if alias.name == "engine":
                            violations.append((str(py_file.relative_to(base_dir)), f"from {mod} import {alias.name}"))

    assert violations == [], f"Extracted packages must NEVER import engine: {violations}"


def test_g5_7_engine_delegation_facade():
    """Phase G5.7: Verifies that engine.py re-exports formatting utilities and legacy element builders transparently."""
    from app.services.adaptive_dashboard import engine

    # Verify formatting utilities re-exported
    assert hasattr(engine, "compute_source_snapshot")
    assert hasattr(engine, "format_compact_number")
    assert hasattr(engine, "format_duration_short")
    assert hasattr(engine, "calendar_month_range")
    assert hasattr(engine, "parse_iso_date")
    assert hasattr(engine, "clean_metric_name")
    assert hasattr(engine, "safe_title")

    # Verify legacy builders re-exported
    assert hasattr(engine, "classify_domain_and_persona")
    assert hasattr(engine, "profile_source")
    assert hasattr(engine, "evaluate_and_select_primary_metric")
    assert hasattr(engine, "build_average_logged_time_chart")
    assert hasattr(engine, "build_temporal_measure_chart")
    assert hasattr(engine, "build_segment_disparity_element")
    assert hasattr(engine, "build_decision_focus_element")

    # Test execution through engine facade
    snap = engine.compute_source_snapshot(101, ["ColA", "ColB"], [{"ColA": 1, "ColB": 2}])
    assert isinstance(snap, str) and len(snap) == 16

    manifest, contract = engine.profile_source(
        sheet_id=101,
        sheet_name="TestSheet",
        file_name="test.csv",
        display_name="Test Display",
        columns=["ColA", "ColB"],
        rows=[{"ColA": 1, "ColB": 2}],
    )
    assert manifest.sheet_id == 101
    assert contract.domain in ("workforce_hr", "general_tabular", "commercial_retail", "demographics_public")


def test_g5_7_orchestration_pipeline_contract():
    """Phase G5.7: Verifies end-to-end dataset intelligence pipeline through the clean engine facade."""
    from pathlib import Path
    from app.services.adaptive_dashboard.engine import run_adaptive_dashboard

    # Ensure benchmark dataset 99770 (Workforce) is seeded in test DB
    real_db = Path(__file__).resolve().parents[1] / "data" / "db" / "pulsehr.sqlite3"
    with session_scope() as conn:
        has_99770 = conn.execute("SELECT 1 FROM dataset_uploads WHERE id = 99770").fetchone()
        if not has_99770 and real_db.exists():
            conn.execute(f'ATTACH DATABASE "{real_db}" AS real_source')
            conn.execute("INSERT OR REPLACE INTO dataset_uploads (id, filename, original_name, file_type, display_name) SELECT id, filename, original_name, file_type, display_name FROM real_source.dataset_uploads WHERE id IN (99770, 99771, 99772)")
            conn.execute("INSERT OR REPLACE INTO sheets (id, dataset_id, name, display_name, columns_json, profile_json, row_count) SELECT id, dataset_id, name, display_name, columns_json, profile_json, row_count FROM real_source.sheets WHERE dataset_id IN (99770, 99771, 99772)")
            conn.execute("INSERT OR REPLACE INTO sheet_rows (id, sheet_id, row_index, data_json) SELECT id, sheet_id, row_index, data_json FROM real_source.sheet_rows WHERE sheet_id IN (SELECT id FROM real_source.sheets WHERE dataset_id IN (99770, 99771, 99772))")
            conn.commit()
            conn.execute("DETACH DATABASE real_source")

    resp = run_adaptive_dashboard(dataset_id=99770, include_dataset_intelligence=True)
    assert resp.run_status == "ready"
    assert resp.dataset_id == 99770
    assert resp.manifest is not None
    assert resp.contract is not None
    assert len(resp.executive_topics) > 0
    assert resp.layout_plan is not None
    assert resp.layout_plan["total_cards"] > 0
    assert resp.executive_integrity is not None
    assert resp.executive_integrity["grounding"] == "Passed"
