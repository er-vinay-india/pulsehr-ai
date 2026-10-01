"""Unit tests for Controlled Semantic Data Enrichment & Scientific Feature Discovery Pipeline.

Tests all 11 stages and guarantees hard resource bounds, multi-role semantic typing,
relationship discovery, semantic grouping, primitive derivation, scientific formulas,
analytical tables, and utility pruning.
"""

import time
import pandas as pd
import pytest

from app.services.enrichment.config import BudgetGuard, EnrichmentConfig
from app.services.enrichment.models import SemanticRole
from app.services.enrichment.profiler import EnrichmentProfiler
from app.services.enrichment.relationship_engine import ColumnRelationshipEngine
from app.services.enrichment.column_grouping import ColumnGroupingEngine
from app.services.enrichment.primitive_deriver import PrimitiveFeatureDeriver
from app.services.enrichment.formula_engine import ScientificFormulaEngine
from app.services.enrichment.interaction_engine import InteractionFeatureEngine
from app.services.enrichment.table_synthesizer import AnalyticalTableSynthesizer
from app.services.enrichment.utility_evaluator import FeatureUtilityEvaluator
from app.services.enrichment.pipeline import ControlledEnrichmentPipeline

pytestmark = [pytest.mark.enrichment]


@pytest.fixture
def sample_multidomain_dataset() -> pd.DataFrame:
    """Creates an arbitrary input dataset S1 with motion, financial, temporal, and physical properties."""
    data = {
        "trip_id": [f"TRIP-{i:03d}" for i in range(1, 21)],
        "transaction_date": ["2026-09-30", "2026-10-01", "2026-10-02", "2026-10-03"] * 5,
        "department": ["Logistics", "Operations", "Freight", "Fleet"] * 5,
        "distance": ["8 km", "15 km", "42 km", "120 km"] * 5,
        "travel_time_hours": [0.5, 1.0, 2.5, 6.0] * 5,
        "fuel_consumption_liters": [1.2, 2.1, 5.8, 16.5] * 5,
        "mass_kg": [50.0, 120.0, 350.0, 800.0] * 5,
        "volume_m3": [0.2, 0.5, 1.4, 3.2] * 5,
        "service_charge": ["₹3500", "₹7200", "₹18000", "₹45000"] * 5,
        "discount_rate": ["10%", "15%", "5%", "20%"] * 5,
        "total_revenue": [5000.0, 10000.0, 25000.0, 60000.0] * 5,
        "total_cost": [3200.0, 6500.0, 16000.0, 38000.0] * 5,
    }
    return pd.DataFrame(data)


@pytest.mark.unit
def test_budget_guard_hard_limits():
    """Verifies that BudgetGuard strictly bounds derived columns, tables, and runtime."""
    cfg = EnrichmentConfig(
        max_derived_columns=5,
        max_generated_tables=2,
        max_runtime_seconds=0.5
    )
    guard = BudgetGuard(cfg)

    # Column budget checks
    assert guard.can_derive_column(4) is True
    assert guard.record_derived_columns(4) == 4
    assert guard.remaining_column_budget() == 1

    assert guard.can_derive_column(2) is False  # 4 + 2 > 5
    assert guard.stopped_due_to_limit is True
    assert "columns ceiling" in guard.limit_reason.lower()

    # Table budget checks
    guard_tables = BudgetGuard(cfg)
    assert guard_tables.record_generated_table() is True
    assert guard_tables.record_generated_table() is True
    assert guard_tables.can_generate_table() is False
    assert guard_tables.remaining_table_budget() == 0

    # Runtime expiration
    guard_time = BudgetGuard(EnrichmentConfig(max_runtime_seconds=0.01))
    time.sleep(0.02)
    assert guard_time.check_runtime_budget() is False
    assert "runtime exceeded" in guard_time.limit_reason.lower()


def test_data_profiling_and_multi_role_semantic_typing(sample_multidomain_dataset):
    """Verifies Stage 1 Data Profiling and Stage 2 Multi-Role Semantic Typing."""
    profiles = EnrichmentProfiler.profile_dataset(sample_multidomain_dataset)

    # 1. Identifier check
    id_prof = profiles["trip_id"]
    assert id_prof.cardinality == 20
    assert SemanticRole.IDENTIFIER in id_prof.roles

    # 2. Date check
    date_prof = profiles["transaction_date"]
    assert date_prof.pattern == "iso_date"
    assert SemanticRole.TIME in date_prof.roles

    # 3. Scientific Distance Measurement
    dist_prof = profiles["distance"]
    assert dist_prof.detected_unit == "km"
    assert dist_prof.pattern == "distance_measurement"
    assert SemanticRole.SCIENTIFIC_MEASURE in dist_prof.roles
    assert SemanticRole.QUANTITY in dist_prof.roles
    assert SemanticRole.MEASURE in dist_prof.roles

    # 4. Currency check
    curr_prof = profiles["service_charge"]
    assert curr_prof.detected_unit == "₹"
    assert curr_prof.pattern == "currency"
    assert curr_prof.possible_domain == "finance"

    # 5. Percentage check
    pct_prof = profiles["discount_rate"]
    assert pct_prof.detected_unit == "%"
    assert pct_prof.pattern == "percentage"

    # 6. Statistical Moments on continuous columns
    rev_prof = profiles["total_revenue"]
    assert rev_prof.mean_val is not None and rev_prof.mean_val > 0
    assert rev_prof.variance is not None and rev_prof.variance > 0
    assert rev_prof.min_val == 5000.0
    assert rev_prof.max_val == 60000.0


def test_column_relationships_and_semantic_grouping(sample_multidomain_dataset):
    """Verifies Stage 3 Hybrid Relationship Discovery and Stage 4 Graph Grouping G1...Gf."""
    cfg = EnrichmentConfig(min_relationship_score=0.40)
    profiles = EnrichmentProfiler.profile_dataset(sample_multidomain_dataset)
    relationships = ColumnRelationshipEngine.discover_relationships(sample_multidomain_dataset, profiles, cfg)

    assert len(relationships) > 0
    # Top relationship should have a strong score
    top_rel = relationships[0]
    assert 0.0 <= top_rel.relationship_score <= 1.0
    assert len(top_rel.reasons) > 0

    # Test clustering into groups G1...Gf
    groups = ColumnGroupingEngine.group_columns(
        list(sample_multidomain_dataset.columns), relationships, profiles, min_relationship_score=0.40
    )
    assert len(groups) >= 1
    for g in groups:
        assert g.group_id.startswith("G")
        assert len(g.columns) >= 1
        assert g.domain_interpretation is not None


def test_primitive_feature_derivation(sample_multidomain_dataset):
    """Verifies Stage 5 Normalization & Stage 6 Primitive Feature Derivation."""
    cfg = EnrichmentConfig(max_derived_columns=50)
    guard = BudgetGuard(cfg)
    profiles = EnrichmentProfiler.profile_dataset(sample_multidomain_dataset)

    derived_df, features = PrimitiveFeatureDeriver.derive_primitives(
        sample_multidomain_dataset, profiles, guard
    )

    feat_names = [f.name for f in features]

    # 1. Date primitive decomposition (year, quarter, month, week, day, weekday, is_weekend)
    assert "transaction_date_year" in feat_names
    assert "transaction_date_quarter" in feat_names
    assert "transaction_date_is_weekend" in feat_names
    assert derived_df["transaction_date_year"].iloc[0] == 2026

    # 2. Measurement primitive decomposition (value, unit, SI meters)
    assert "distance_value" in feat_names
    assert "distance_unit" in feat_names
    assert "distance_m" in feat_names
    assert derived_df["distance_value"].iloc[0] == 8.0
    assert derived_df["distance_m"].iloc[0] == 8000.0  # 8 km = 8000 m

    # 3. Currency primitive decomposition (amount, currency code INR)
    assert "service_charge_amount" in feat_names
    assert "service_charge_currency" in feat_names
    assert derived_df["service_charge_amount"].iloc[0] == 3500.0
    assert derived_df["service_charge_currency"].iloc[0] == "INR"

    # 4. Percentage normalization (10% -> 0.10)
    assert "discount_rate_ratio" in feat_names
    assert derived_df["discount_rate_ratio"].iloc[0] == 0.10


def test_scientific_formula_discovery(sample_multidomain_dataset):
    """Verifies Stage 7 & 8 Scientific Formula Discovery & Dimensional Consistency."""
    cfg = EnrichmentConfig(
        max_derived_columns=100,
        symbolic_regression_enabled=False,
        featuretools_enabled=False,
    )
    guard = BudgetGuard(cfg)
    profiles = EnrichmentProfiler.profile_dataset(sample_multidomain_dataset)

    # First derive primitives to have numeric distance
    df_prim, _ = PrimitiveFeatureDeriver.derive_primitives(sample_multidomain_dataset, profiles, guard)
    all_profiles = EnrichmentProfiler.profile_dataset(df_prim)
    groups = ColumnGroupingEngine.group_columns(list(df_prim.columns), [], all_profiles, min_relationship_score=0.0)

    # Force a physics motion group
    motion_group = next(
        (g for g in groups if any("distance" in c for c in g.columns)),
        groups[0]
    )
    motion_group.columns = ["distance_value", "travel_time_hours", "fuel_consumption_liters", "mass_kg", "volume_m3", "total_revenue", "total_cost"]

    df_form, formula_features = ScientificFormulaEngine.discover_formulas(
        df_prim, [motion_group], all_profiles, guard, cfg
    )

    feat_names = [f.name for f in formula_features]

    # Verify speed = distance / travel_time
    assert any("derived_speed_distance_value_per_travel_time_hours" in name for name in feat_names)
    speed_col = [n for n in feat_names if "distance_value" in n and "travel_time_hours" in n and "speed" in n][0]
    assert df_form[speed_col].iloc[0] == 16.0  # 8 km / 0.5 hr = 16 km/h

    # Verify density = mass / volume
    assert any("derived_density_mass_kg_per_volume_m3" in name for name in feat_names)
    dens_col = [n for n in feat_names if "mass_kg" in n and "volume_m3" in n and "density" in n][0]
    assert df_form[dens_col].iloc[0] == 250.0  # 50 kg / 0.2 m3 = 250 kg/m3

    # Verify profit = revenue - cost
    assert any("derived_profit_total_revenue_minus_total_cost" in name for name in feat_names)
    profit_col = [n for n in feat_names if "total_revenue" in n and "total_cost" in n and "profit" in n][0]
    assert df_form[profit_col].iloc[0] == 1800.0  # 5000 - 3200


def test_interaction_features_and_analytical_tables(sample_multidomain_dataset):
    """Verifies Stage 9 Interaction Features & Stage 10 Analytical Tables Synthesis."""
    cfg = EnrichmentConfig(max_derived_columns=50, max_generated_tables=10)
    guard = BudgetGuard(cfg)
    profiles = EnrichmentProfiler.profile_dataset(sample_multidomain_dataset)

    # Interaction Features
    df_inter, inter_features = InteractionFeatureEngine.derive_interactions(
        sample_multidomain_dataset, profiles, guard, cfg
    )
    assert len(inter_features) > 0
    # Group mean feature created
    assert any("interact_mean_" in f.name for f in inter_features)

    # Analytical Tables
    tables = AnalyticalTableSynthesizer.synthesize_tables(
        df_inter, profiles, guard, cfg
    )
    assert len(tables) >= 1
    t1 = tables[0]
    assert t1.row_count > 0
    assert len(t1.data_preview) > 0
    assert t1.utility_score >= cfg.min_table_utility_score


def test_end_to_end_controlled_enrichment_pipeline(sample_multidomain_dataset):
    """End-to-end integration test across all 11 stages strictly adhering to configurable resource limits."""
    cfg = EnrichmentConfig(
        max_derived_columns=25,
        max_generated_tables=5,
        max_runtime_seconds=60.0
    )

    final_df, package = ControlledEnrichmentPipeline.enrich_dataset(
        df=sample_multidomain_dataset,
        dataset_id="test_suite_dataset",
        config=cfg
    )

    # 1. Output shape expansion
    orig_rows, orig_cols = sample_multidomain_dataset.shape
    final_rows, final_cols = final_df.shape
    assert final_rows == orig_rows
    assert final_cols > orig_cols
    assert (final_cols - orig_cols) <= cfg.max_derived_columns

    # 2. Package metadata contracts
    assert package.dataset_id == "test_suite_dataset"
    assert package.original_col_count == orig_cols
    assert package.enriched_col_count == final_cols
    assert len(package.column_profiles) == orig_cols
    assert len(package.relationships) > 0
    assert len(package.semantic_groups) > 0
    assert len(package.derived_features) <= cfg.max_derived_columns
    assert len(package.analytical_tables) <= cfg.max_generated_tables

    # 3. Budget enforcement summary
    bs = package.budget_summary
    assert bs["elapsed_seconds"] < 60.0
    assert bs["derived_columns_count"] <= cfg.max_derived_columns
    assert bs["generated_tables_count"] <= cfg.max_generated_tables


@pytest.mark.integration
@pytest.mark.db
def test_upload_endpoint_semantic_enrichment_integration(sample_multidomain_dataset, monkeypatch):
    """Verifies that the /api/upload/file endpoint executes semantic enrichment and exposes results."""
    from unittest.mock import MagicMock
    from fastapi.testclient import TestClient
    from app.main import app

    mock_res = MagicMock()
    mock_res.success = True
    mock_res.raw_text = '{"display_name": "Logistics Fleet Operations", "description": "Fleet metrics."}'
    monkeypatch.setattr("app.services.gateway.model_gateway.ModelGateway.generate", lambda *a, **k: mock_res)

    client = TestClient(app)
    csv_bytes = sample_multidomain_dataset.to_csv(index=False).encode('utf-8')

    response = client.post(
        "/api/upload/file",
        files={"file": ("logistics_multidomain.csv", csv_bytes, "text/csv")},
        data={"user_objective": "Logistics and fleet operational performance"}
    )
    assert response.status_code == 200
    res_data = response.json()
    assert res_data["status"] == "success"
    assert "enrichment" in res_data
    enr = res_data["enrichment"]
    assert enr is not None
    assert enr["derived_features_count"] > 0
    assert len(enr["derived_features"]) > 0
    assert len(enr["semantic_groups"]) > 0

    dataset_id = res_data["dataset_id"]
    # Test GET /api/upload/datasets/{id}/enrichment
    get_res = client.get(f"/api/upload/datasets/{dataset_id}/enrichment")
    assert get_res.status_code == 200
    saved_enr = get_res.json().get("enrichment")
    assert saved_enr is not None
    assert saved_enr["derived_features_count"] == enr["derived_features_count"]


def test_unit_system_adapter_dimensional_analysis():
    """Verifies that UnitSystemAdapter enforces dimensional consistency and rejects invalid physics."""
    from app.services.enrichment.adapters.unit_adapter import UnitSystemAdapter

    adapter = UnitSystemAdapter(enabled=True)
    assert adapter.detect_unit_from_name("distance_km") == "kilometer"
    assert adapter.detect_unit_from_name("weight_kg") == "kilogram"
    assert adapter.detect_unit_from_name("travel_hours") == "hour"

    # Compatibility check
    assert adapter.are_compatible("kilometer", "meter") is True
    assert adapter.are_compatible("kilogram", "meter") is False

    # Incompatible addition: mass + distance must be rejected
    is_valid, _, explanation = adapter.validate_operation("+", "kilogram", "meter")
    assert is_valid is False
    assert "Incompatible dimensions" in explanation

    # Valid ratio: distance / time -> speed
    is_valid, resulting_unit, _ = adapter.validate_operation("/", "kilometer", "hour")
    assert is_valid is True
    assert "hour" in resulting_unit


def test_featuretools_synthesis_adapter():
    """Verifies that FeatureSynthesisAdapter generates DFS features bounded by quota."""
    from app.services.enrichment.adapters.feature_synthesis_adapter import FeatureSynthesisAdapter

    adapter = FeatureSynthesisAdapter(enabled=True)
    df = pd.DataFrame({
        "revenue": [100.0, 200.0, 300.0, 400.0],
        "cost": [60.0, 110.0, 150.0, 210.0]
    })
    synth_df, meta = adapter.synthesize_features_for_group(df, ["revenue", "cost"], max_features=3)
    assert synth_df.shape[1] > 0
    assert synth_df.shape[1] <= 3
    assert len(meta) == synth_df.shape[1]
    assert all(m["generator"] == "featuretools_dfs" for m in meta)


def test_profiling_and_statistical_adapters():
    """Verifies that ProfilingAdapter and StatisticalAdapter calculate advanced moments and visions types."""
    from app.services.enrichment.adapters.profiling_adapter import ProfilingAdapter
    from app.services.enrichment.adapters.statistical_adapter import StatisticalAdapter

    stat_adapter = StatisticalAdapter(enabled=True)
    s = pd.Series([1.0, 2.0, 3.0, 4.0, 5.0, 20.0])
    moments = stat_adapter.compute_moments(s)
    assert "skewness" in moments
    assert "kurtosis" in moments
    assert "iqr" in moments
    assert moments["skewness"] > 0  # right-skewed by 20.0

    prof_adapter = ProfilingAdapter(visions_enabled=True)
    prof = prof_adapter.profile_series(s)
    assert prof["is_numeric"] is True
    assert "visions_type" in prof


def test_formula_registry_domain_packs():
    """Verifies that FormulaRegistry registers physics, business, operations, and healthcare formulas."""
    from app.services.enrichment.formula_registry import FormulaRegistry

    reg = FormulaRegistry()
    all_formulas = reg.get_all()
    categories = {f.category for f in all_formulas}
    assert "physics" in categories
    assert "business" in categories
    assert "operations" in categories
    assert "healthcare" in categories

    # Verify physics speed
    speed_formula = next(f for f in all_formulas if f.formula_id == "physics_speed")
    res = speed_formula.eval_fn(pd.Series([100.0, 200.0]), pd.Series([2.0, 4.0]))
    assert (res == pd.Series([50.0, 50.0])).all()


def test_symbolic_relationship_adapter_fallback(monkeypatch):
    """Verifies that SymbolicRelationshipAdapter gracefully handles execution without crashing."""
    from app.services.enrichment.adapters.symbolic_adapter import SymbolicRelationshipAdapter

    # Test disabled flag
    disabled_adapter = SymbolicRelationshipAdapter(enabled=False)
    assert disabled_adapter.is_available() is False
    res = disabled_adapter.discover_symbolic_relationship(pd.DataFrame({"a": [1], "b": [2]}), ["a"], "b")
    assert res is None

    # Test live adapter initialization with mocked availability to avoid booting external Julia VM
    monkeypatch.setattr(SymbolicRelationshipAdapter, "_check_availability", lambda self: setattr(self, "_pysr_available", True))
    live_adapter = SymbolicRelationshipAdapter(enabled=True)
    assert isinstance(live_adapter.is_available(), bool)
    assert live_adapter.is_available() is True

