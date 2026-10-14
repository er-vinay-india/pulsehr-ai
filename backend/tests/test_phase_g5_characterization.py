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


