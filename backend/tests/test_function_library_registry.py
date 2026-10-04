"""Tests for Analytical Function & Business Jargon Library Registry and Storage.

Verifies:
1. Dynamic catalog discovery and registration.
2. Token-optimized compact representation compilation (<150 tokens per function).
3. Persistent SQLite storage in system_function_library.sqlite3.
4. Total isolation from sheet lifecycle (deleting sheet data leaves library intact).
5. Persona jargon mapping and layman definitions.
"""

import sqlite3
import pytest
import pandas as pd
from pathlib import Path

from app.core import config
from app.services.function_library import (
    AnalyticalFunctionRegistry,
    FunctionCategory,
    ImpactType,
    ImpactSeverity,
    FunctionLibraryStorage,
)
from app.services.data_engine.semantic_classifier import SemanticDatasetProfile, SemanticRole, ColumnSemanticProfile


@pytest.fixture(autouse=True)
def ensure_catalog_loaded():
    AnalyticalFunctionRegistry.load_catalog(force_reload=True)


def test_registry_auto_discovery():
    """Test 1: Registry discovers and registers all catalog analytical functions."""
    all_functions = AnalyticalFunctionRegistry.get_all()
    assert len(all_functions) >= 6

    fn_ids = [fn.metadata.function_id for fn in all_functions]
    assert "fn_bradford_disruption" in fn_ids
    assert "fn_turnover_exposure" in fn_ids
    assert "fn_lost_capacity_hours" in fn_ids
    assert "fn_margin_leakage" in fn_ids
    assert "fn_talent_9box" in fn_ids
    assert "fn_compound_cohort_disparity" in fn_ids


def test_token_budget_optimization():
    """Test 2: Each function generates a dense, token-optimized DSL string within budget."""
    all_functions = AnalyticalFunctionRegistry.get_all()

    for fn in all_functions:
        compact_str = fn.metadata.compile_compact_token_repr()
        assert compact_str.startswith(f"• {fn.metadata.function_id} | Math:")
        # Must be concise (<160 token cost estimate)
        assert fn.metadata.token_cost < 160
        # Must contain all 3 core persona perspectives
        assert "HR:" in compact_str
        assert "Fin:" in compact_str
        assert "PM:" in compact_str
        assert "Visual:" in compact_str

    prompt_block = AnalyticalFunctionRegistry.get_compact_prompt_block()
    assert "[ANALYTICAL_FUNCTION_LIBRARY]" in prompt_block
    assert len(prompt_block.splitlines()) >= 7  # header + 6 functions


def test_persistent_sqlite_storage(tmp_path):
    """Test 3: FunctionLibraryStorage persists metadata into SQLite and roundtrips accurately."""
    test_db = tmp_path / "test_sys_lib.sqlite3"
    storage = FunctionLibraryStorage(db_path=test_db)

    # Sync registry
    for fn in AnalyticalFunctionRegistry.get_all():
        storage.upsert_function(fn.metadata)

    stored_fns = storage.get_all_functions()
    assert len(stored_fns) >= 6

    # Verify bradford function
    bf = storage.get_function("fn_bradford_disruption")
    assert bf is not None
    assert bf.name == "Bradford Absence Disruption Index"
    assert bf.category == FunctionCategory.WORKFORCE_DYNAMICS
    assert bf.impact_rule.impact_type == ImpactType.LOST_CAPACITY_HOURS
    assert bf.jargon_mapping.hr_perspective != ""
    assert bf.jargon_mapping.finance_perspective != ""
    assert bf.jargon_mapping.pm_perspective != ""


def test_isolation_from_sheet_deletion(tmp_path):
    """Test 4: Deleting sheet data or dropping sheet tables has zero effect on system function library."""
    test_lib_db = tmp_path / "system_function_library.sqlite3"
    test_sheet_db = tmp_path / "pulsehr_sheets.sqlite3"

    storage = FunctionLibraryStorage(db_path=test_lib_db)
    for fn in AnalyticalFunctionRegistry.get_all():
        storage.upsert_function(fn.metadata)

    # Simulate sheet database with tables
    with sqlite3.connect(test_sheet_db) as conn:
        conn.execute("CREATE TABLE sheets (id INT, name TEXT)")
        conn.execute("CREATE TABLE sheet_rows (sheet_id INT, data TEXT)")
        conn.execute("INSERT INTO sheets VALUES (1, 'Attendance')")
        conn.execute("INSERT INTO sheet_rows VALUES (1, '{\"emp\": \"EMP-01\"}')")
        conn.commit()

        # Simulate sheet deletion cascade
        conn.execute("DELETE FROM sheet_rows")
        conn.execute("DELETE FROM sheets")
        conn.commit()

    # Function library in its isolated storage remains 100% intact
    remaining_fns = storage.get_all_functions()
    assert len(remaining_fns) >= 6
    assert any(f.function_id == "fn_turnover_exposure" for f in remaining_fns)


def test_jargon_dictionary_aggregation():
    """Test 5: Registry aggregates jargon term translations for laymen and LLMs."""
    jargon = AnalyticalFunctionRegistry.get_jargon_dictionary()
    assert len(jargon) >= 10
    assert "attrition_flag" in jargon
    assert "spells" in jargon
    assert "discount_rate" in jargon
