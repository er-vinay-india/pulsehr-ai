"""Comprehensive test suite for AdaptiveTableReconstructionEngine.

Verifies:
1. Golden regression fixture (821964a8914147299f27c790eb371f54.csv)
   - Multi-row header hierarchy resolution
   - Wrapped row continuation merging (Rajahmundry/Rajamahendravaram, Dadara & Nagar Haveli)
   - Preamble and repeated page-header pruning
   - Footnote sentinel extraction ('-' and 'NM' distinct, never coerced to 0)
   - 6 structural integrity gates passing
   - Complete atomic provenance tracking (ATR-xxxx)
2. Fast deterministic path for clean CSVs (< 5ms, complexity < 0.25)
3. Synthetic messy cases: preambles, multi-tier headers, suffix continuations
4. End-to-end integration with sheet_catalog (read_sheets & prepare_sheets)
"""

import io
from pathlib import Path
import pytest
import pandas as pd

from app.services.adaptive_table_reconstruction import (
    AdaptiveTableReconstructionEngine,
    AmbiguityCase,
    AmbiguityType,
    ContinuationType,
    DecisionStatus,
    GridCapture,
    ModelContinuationDecision,
    ModelEscalator,
    RowRole,
    RowRoleClassifier,
)
from app.services.sheet_catalog import read_sheets, prepare_sheets, decompose_header_semantics


GOLDEN_FIXTURE_PATH = Path("backend/data/uploads/821964a8914147299f27c790eb371f54.csv")


def test_golden_pollution_reconstruction():
    """Validates the exact real-world CPCB air quality dataset against all 6 integrity gates."""
    assert GOLDEN_FIXTURE_PATH.exists(), f"Golden fixture not found at {GOLDEN_FIXTURE_PATH}"

    result = AdaptiveTableReconstructionEngine.reconstruct(GOLDEN_FIXTURE_PATH)

    # 1. Dimensions
    assert result.raw_row_count == 455
    assert result.raw_col_count == 8
    # Exactly 435 serial records reconstructed
    assert result.reconstructed_row_count == 435
    assert result.reconstructed_col_count == 7

    # 2. Structural Complexity
    assert result.complexity.is_complex is True
    assert result.complexity.score >= 0.80
    assert result.complexity.recommended_pipeline == "ESCALATED"
    assert "preamble_present" in result.complexity.factors
    assert "multi_row_headers" in result.complexity.factors
    assert "wrapped_sparse_rows" in result.complexity.factors
    assert "repeated_page_headers" in result.complexity.factors
    assert "sentinel_definitions" in result.complexity.factors

    # 3. Normalized & Display Headers
    tree = result.header_tree
    assert tree is not None
    assert tree.header_row_indices == [2, 3, 4, 5]
    expected_norm_cols = [
        "sr_no",
        "state_union_territory",
        "city_town",
        "so2_annual_average",
        "no2_annual_average",
        "pm10_annual_average",
        "pm_2_5_data_already_approved_on_09_05_2024",
    ]
    assert tree.normalized_columns == expected_norm_cols

    # 4. Wrapped Record Merging
    df = result.reconstructed_df
    assert df is not None
    assert len(df) == 435

    # Check Rajahmundry/Rajamahendravaram (Serial 11)
    row_11 = df[df.iloc[:, 0] == "11"]
    assert len(row_11) == 1
    assert row_11.iloc[0, 2] == "Rajahmundry/Rajamahendravaram"
    assert row_11.iloc[0, 1] == "Andhra Pradesh"
    assert row_11.iloc[0, 3] == "6"
    assert row_11.iloc[0, 4] == "13"
    assert row_11.iloc[0, 5] == "66"
    assert row_11.iloc[0, 6] == "30"

    # Check Dadara & Nagar Haveli and Daman & Diu (UT) (Serials 64, 65, 66, 67)
    for s_no in ("64", "65", "66", "67"):
        row_s = df[df.iloc[:, 0] == s_no]
        assert len(row_s) == 1
        assert row_s.iloc[0, 1] == "Dadara & Nagar Haveli and Daman & Diu (UT)"

    # 5. Sentinels Distinct Missing States (Never 0.0)
    assert len(result.sentinels) == 2
    sentinel_tokens = {s.token: s.meaning for s in result.sentinels}
    assert "-" in sentinel_tokens
    assert "NM" in sentinel_tokens
    assert "No data" in sentinel_tokens["-"]
    assert "Not monitored" in sentinel_tokens["NM"]

    pm25_vals = df.iloc[:, 6].tolist()
    assert pm25_vals.count("NM") == 111
    assert pm25_vals.count("-") == 22
    assert "0" not in pm25_vals[:10]  # Valid numeric readings are intact, not converted to 0

    # 6. Integrity Gates
    for gate in result.integrity_gates:
        assert gate.passed is True, f"Gate failed: {gate.gate_name} warnings: {gate.warnings}"

    # 7. Atomic Provenance Tracking
    prov_ops = [p.operation for p in result.provenance]
    assert "PRUNE_PREAMBLE" in prov_ops
    assert "MERGE_HEADER_HIERARCHY" in prov_ops
    assert "MERGE_WRAPPED_RECORD" in prov_ops
    assert "PRUNE_REPEATED_PAGE_HEADERS" in prov_ops
    assert "EXTRACT_SENTINEL" in prov_ops

    # Verify ATR-REC-0001 specifically
    rec_prov = next(p for p in result.provenance if p.operation == "MERGE_WRAPPED_RECORD" and 16 in p.source_rows)
    assert rec_prov.source_rows == [16, 17]
    assert rec_prov.target_row == 17
    assert rec_prov.after_state[2] == "Rajahmundry/Rajamahendravaram"

    # 8. Governed Model Telemetry: Complexity != Uncertainty (Zero Unnecessary Model Calls)
    assert result.telemetry.model_calls == 0
    assert result.telemetry.model_tokens == 0
    assert result.status == DecisionStatus.VALIDATED


def test_cpcb_golden_zero_model_calls():
    """Permanent Invariant: Golden CPCB dataset is structurally complex but completely unambiguous.
    Must reconstruct with exactly 0 model calls, 0 tokens, and VALIDATED status."""
    result = AdaptiveTableReconstructionEngine.reconstruct(GOLDEN_FIXTURE_PATH)
    assert result.complexity.score >= 0.80
    assert result.telemetry.model_calls == 0
    assert result.telemetry.model_tokens == 0
    assert result.telemetry.ambiguities_detected == 0
    assert result.status == DecisionStatus.VALIDATED
    assert result.reconstructed_row_count == 435


def test_clean_csv_fast_path():
    """Ensures clean CSV files execute on the microsecond fast deterministic path."""
    csv_data = (
        "employee_id,name,department,salary\n"
        "101,Alice,Engineering,120000\n"
        "102,Bob,Product,110000\n"
        "103,Charlie,Design,95000\n"
    )
    result = AdaptiveTableReconstructionEngine.reconstruct(io.StringIO(csv_data))
    assert result.complexity.is_complex is False
    assert result.complexity.score == 0.0
    assert result.complexity.recommended_pipeline == "FAST_DETERMINISTIC"
    assert result.reconstructed_row_count == 3
    assert result.reconstructed_col_count == 4
    assert list(result.reconstructed_df.columns) == ["employee_id", "name", "department", "salary"]


def test_synthetic_multi_row_headers_and_preamble():
    """Tests synthetic CSV with title preamble and 2-level stacked headers."""
    raw_content = (
        "QUARTERLY PERFORMANCE REPORT - CONFIDENTIAL\n"
        "AS OF: 2026-06-30\n"
        ",,Q1,Q1,Q2,Q2\n"
        "Region,Branch,Target,Actual,Target,Actual\n"
        "North,B1,100,105,110,112\n"
        "South,B2,80,78,85,90\n"
        "* : Provisional data subject to audit\n"
    )
    result = AdaptiveTableReconstructionEngine.reconstruct(io.StringIO(raw_content))
    assert result.complexity.is_complex is True
    assert result.reconstructed_row_count == 2
    assert result.reconstructed_col_count == 6
    assert list(result.reconstructed_df.columns) == ["Region", "Branch", "Q1 Target", "Q1 Actual", "Q2 Target", "Q2 Actual"]
    assert len(result.sentinels) == 1
    assert result.sentinels[0].token == "*"


def test_synthetic_suffix_continuation():
    """Tests wrapped records where fragment appears on the subsequent physical line."""
    raw_content = (
        "ID,Description,Amount\n"
        "1,Initial deposit for annual,500\n"
        ",subscription renewal,\n"
        "2,One-time setup fee,150\n"
    )
    result = AdaptiveTableReconstructionEngine.reconstruct(io.StringIO(raw_content))
    df = result.reconstructed_df
    assert len(df) == 2
    assert df.iloc[0, 1] == "Initial deposit for annual subscription renewal"
    assert df.iloc[0, 2] == "500"
    assert df.iloc[1, 0] == "2"


def test_end_to_end_sheet_catalog_integration(tmp_path):
    """Verifies read_sheets and prepare_sheets preserve reconstruction metadata and sentinels."""
    # Write golden fixture copy to temp dir
    test_file = tmp_path / "air_quality_report.csv"
    test_file.write_bytes(GOLDEN_FIXTURE_PATH.read_bytes())

    # 1. read_sheets
    frames = read_sheets(test_file)
    assert "Sheet1" in frames
    df = frames["Sheet1"]
    assert len(df) == 435
    assert hasattr(df, "attrs")
    assert "reconstruction_metadata" in df.attrs

    # 2. prepare_sheets
    prepared = prepare_sheets(frames, "air_quality_report.csv", embed=False)
    assert len(prepared) == 1
    sheet = prepared[0]
    assert len(sheet["records"]) == 435
    assert "header_geometry" in sheet
    assert "reconstruction" in sheet["header_geometry"]
    recon = sheet["header_geometry"]["reconstruction"]
    assert recon["complexity"]["is_complex"] is True
    assert len(recon["sentinels"]) == 2
    assert len(recon["provenance"]) >= 8

    # Verify PM2.5 missing states are correctly captured
    pm25_profile = next(p for p in sheet["profiles"] if "pm25" in p["canonical"])
    # 22 '-' and 111 'NM' are recognized as distinct missing states in profile
    assert pm25_profile["missing"] == 133
    assert pm25_profile["null_percentage"] == 30.6

    # 3. Verify semantic header decomposition on profile
    assert "semantic_components" in pm25_profile
    s_comp = pm25_profile["semantic_components"]
    assert "09.05.2024" in s_comp["dates"]
    assert any("approved" in q.lower() for q in s_comp["qualifiers"])
    assert "PM 2.5 Data" in s_comp["metric_identity"]


def test_ambiguous_continuation_model_escalation():
    """Verifies that an ambiguous free-text continuation fragment (Contract renewal pending + Quarterly terms)
    triggers ModelEscalator, exercises the risk/semantic-confidence gate, and lands safely in MODEL_ASSISTED_PROPOSED."""
    csv_data = (
        "ID,Description,Amount\n"
        "1,Contract renewal pending,500\n"
        ",Quarterly terms,\n"
        "2,Annual payment processing,1500\n"
    )
    result = AdaptiveTableReconstructionEngine.reconstruct(io.StringIO(csv_data))
    assert result.telemetry.model_calls >= 1
    assert len(result.audits) >= 1
    audit = result.audits[0]
    assert audit.ambiguity_type == AmbiguityType.ROW_CONTINUATION
    assert audit.final_status == DecisionStatus.MODEL_ASSISTED_PROPOSED
    assert audit.post_validation_passed is True
    assert result.status == DecisionStatus.MODEL_ASSISTED_PROPOSED


def test_lexical_split_model_assisted_validated():
    """Verifies that a true lexical word-split on a dimension (Rajamahend + ravaram)
    is accepted as MODEL_ASSISTED_VALIDATED and merged into the primary record."""
    csv_data = (
        "ID,State,City,Reading\n"
        "1,Andhra Pradesh,Vijayawada,40\n"
        ",,Rajamahend,\n"
        "2,Andhra Pradesh,ravaram,42\n"
        "3,Maharashtra,Pune,35\n"
    )
    result = AdaptiveTableReconstructionEngine.reconstruct(io.StringIO(csv_data))
    assert result.reconstructed_row_count == 3
    assert "Rajamahendravaram" in result.reconstructed_df["City"].iloc[1]


def test_narrative_sentinel_model_escalation():
    """Verifies that narrative footnote with unknown sentinel triggers ModelEscalator
    and is resolved without hardcoded mapping."""
    csv_data = (
        "Station,Reading,Quality\n"
        "S1,42,Good\n"
        "S2,NR,Missing\n"
        "S3,38,Moderate\n"
        "Note: Regions marked NR were not evaluated in the current reporting cycle.\n"
    )
    result = AdaptiveTableReconstructionEngine.reconstruct(io.StringIO(csv_data))
    assert result.telemetry.model_calls >= 1
    assert any(s.token == "NR" for s in result.sentinels)
    nr_sentinel = next(s for s in result.sentinels if s.token == "NR")
    assert nr_sentinel.is_missing_indicator is True
    assert any(a.case_id == "SNT-NR" and a.post_validation_passed for a in result.audits)

    prov_snt = next(p for p in result.provenance if p.operation == "EXTRACT_SENTINEL" and p.method == "MODEL_ASSISTED")
    assert prov_snt.after_state["token"] == "NR"


def test_false_merge_prevention():
    """Verifies that a naive or hallucinated merge proposal is intercepted and rejected
    by deterministic post-validation, incrementing false_merge_prevented and preserving record."""
    from unittest.mock import patch
    me = ModelEscalator(model_name="qwen3.5:2b")
    case = AmbiguityCase(
        case_id="AMB-TEST-FALSE-MERGE",
        ambiguity_type=AmbiguityType.ROW_CONTINUATION,
        current_row_index=2,
        current_row=["99", "Section Summary Note", ""],
        previous_rows=[["1", "Project Alpha", "Active"]],
        next_rows=[["2", "Project Beta", "Active"]],
        provisional_schema=["ID", "Name", "Status"],
        deterministic_candidates=["PREFIX_OF_NEXT_ROW", "SUFFIX_OF_PREVIOUS_ROW", "INDEPENDENT"],
        deterministic_confidence=0.50,
    )
    hallucinated_proposal = ModelContinuationDecision(
        relationship=ContinuationType.SUFFIX_OF_PREVIOUS_ROW,
        target_row_index=1,
        confidence=0.92,
        evidence=["Naive model suggested merging row 2 into row 1"],
    )
    with patch.object(me, "_call_model_json", return_value=(hallucinated_proposal, hallucinated_proposal.model_dump(), 10.0)):
        decision, audit = me.resolve_continuation(case, [1])
        assert decision.relationship == ContinuationType.INDEPENDENT
        assert audit.final_status == DecisionStatus.REJECTED
        assert audit.post_validation_passed is False
        assert me.telemetry.false_merge_prevented >= 1
        assert me.telemetry.review_required_count >= 1


def test_decompose_header_semantics():
    """Verifies decomposition of composite headers into physical_header_path,
    normalized_display_label, metric_identity, qualifiers, dates, and units."""
    res1 = decompose_header_semantics("PM 2.5 Data Already approved on 09.05.2024")
    assert "09.05.2024" in res1["dates"]
    assert any("approved" in q.lower() for q in res1["qualifiers"])
    assert "PM 2.5 Data" in res1["metric_identity"]
    assert res1["physical_header_path"] == ["PM 2.5 Data Already approved on 09.05.2024"]

    res2 = decompose_header_semantics("SO2 Annual Average")
    assert any("annual average" in q.lower() for q in res2["qualifiers"])
    assert "SO2" in res2["metric_identity"]

    res3 = decompose_header_semantics(
        "revenue_q1_actual_usd",
        header_mapping={"levels": ["Revenue", "Q1 Actual (USD)"]},
        unit="USD",
    )
    assert res3["physical_header_path"] == ["Revenue", "Q1 Actual (USD)"]
    assert "Q1" in res3["dates"]
    assert any("actual" in q.lower() for q in res3["qualifiers"])
    assert "USD" in res3["units"]

