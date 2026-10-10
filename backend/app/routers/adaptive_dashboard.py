from typing import Any
from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, Field
from ..db.database import get_connection
from ..services.adaptive_dashboard import AdaptiveDashboardResponse, run_adaptive_dashboard
from ..services.adaptive_dashboard.dataset_orchestrator import DatasetIntelligenceResponse, run_dataset_intelligence
from ..services.adaptive_dashboard.findings import UnifiedFinding, get_shared_findings_for_sheet
from ..services.adaptive_dashboard.scenario_engine import (
    DeterministicScenarioEngine,
    GovernedScenarioParameters,
)

router = APIRouter(prefix="/api/adaptive-dashboard", tags=["adaptive dashboard"])


class SimulateScenarioRequest(BaseModel):
    dataset_id: int | None = None
    days_per_week: float = Field(default=3.0, ge=1.0, le=5.0, description="Governed in-office days per week")
    leave_exemption_ratio: float = Field(default=1.0, ge=0.0, le=1.0, description="Approved leave exemption credit ratio")
    target_compliance_threshold: float = Field(default=80.0, ge=10.0, le=100.0, description="Target organizational threshold")
    period_weeks: float = Field(default=5.0, ge=1.0, le=10.0, description="Reporting cycle length in weeks")
    department_targets: dict[str, float] = Field(default_factory=dict, description="Department-specific policy overrides")
    # Retail commercial levers
    promo_multiplier: float = Field(default=1.15, ge=0.5, le=3.0, description="Holiday promotion velocity multiplier")
    markdown_discount_pct: float = Field(default=10.0, ge=0.0, le=50.0, description="Targeted markdown discount depth %")
    fuel_price_sensitivity: float = Field(default=0.0, ge=-10.0, le=10.0, description="Macro fuel/CPI sensitivity buffer %")
    custom_name: str | None = None
    scenario_type: str = Field(default="POLICY_REPLAY", description="Scenario classification: POLICY_REPLAY, COUNTERFACTUAL, FORECAST, OPTIMIZATION, STRESS_TEST")


@router.get("/primary-element", response_model=AdaptiveDashboardResponse)
def get_primary_element(
    sheet_id: int | None = Query(None, description="Target sheet ID (resolves to parent dataset)"),
    dataset_id: int | None = Query(None, description="Target dataset ID"),
):
    """Returns verified dataset-level adaptive dashboard intelligence (WP-9.6)."""
    try:
        target_dataset_id = dataset_id
        if target_dataset_id is None and sheet_id is not None:
            conn = get_connection()
            try:
                row = conn.execute("SELECT dataset_id FROM sheets WHERE id = ?", (sheet_id,)).fetchone()
                if row and row[0]:
                    target_dataset_id = row[0]
            finally:
                conn.close()

        return run_adaptive_dashboard(
            sheet_id=sheet_id,
            dataset_id=target_dataset_id,
            include_dataset_intelligence=True,
        )
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Adaptive analysis error: {exc}") from exc


@router.get("/dataset/{dataset_id}", response_model=DatasetIntelligenceResponse)
def get_dataset_dashboard(dataset_id: int):
    """Returns authoritative dataset-wide intelligence, relationships, and globally ranked insights (WP-9.6)."""
    try:
        return run_dataset_intelligence(dataset_id=dataset_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Dataset intelligence error: {exc}") from exc


@router.get("/findings", response_model=list[UnifiedFinding])
def get_dashboard_findings(sheet_id: int = Query(..., description="Target sheet ID")):
    """Returns authoritative, immutable, deduplicated findings from the Shared Findings Store (T31, T33)."""
    try:
        return get_shared_findings_for_sheet(sheet_id=sheet_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Findings store error: {exc}") from exc


@router.get("/scenarios")
def get_dashboard_scenarios(
    dataset_id: int | None = Query(None, description="Target dataset ID"),
):
    """Returns domain-entitled benchmark policy scenarios for Phase 10 Scenario Explorer."""
    try:
        strategy, domain = DeterministicScenarioEngine.resolve_strategy_for_dataset(dataset_id)
        if strategy is None:
            return {
                "dataset_id": dataset_id or 99747,
                "domain": domain.value,
                "is_available": False,
                "message": f"Scenario Explorer is unavailable for domain: {domain.value}. Governed models are only enabled for authorized workforce and retail commercial domains.",
                "governed_levers": [],
                "benchmark_scenarios": [],
            }

        scenarios = strategy.get_benchmark_scenarios(dataset_id)
        levers = strategy.get_governed_levers()
        return {
            "dataset_id": dataset_id or 99747,
            "domain": domain.value,
            "is_available": True,
            "governed_levers": levers,
            "benchmark_scenarios": [s.to_dict() for s in scenarios],
        }
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Scenario explorer error: {exc}") from exc


@router.post("/scenarios/simulate")
def simulate_governed_scenario(payload: SimulateScenarioRequest):
    """Executes deterministic what-if scenario with governed business levers."""
    try:
        strategy, domain = DeterministicScenarioEngine.resolve_strategy_for_dataset(payload.dataset_id)
        if strategy is None:
            raise HTTPException(
                status_code=400,
                detail=f"Scenario simulation is unavailable for domain: {domain.value}. Governed models are only enabled for authorized workforce and retail commercial domains.",
            )

        params = GovernedScenarioParameters(
            days_per_week=payload.days_per_week,
            leave_exemption_ratio=payload.leave_exemption_ratio,
            target_compliance_threshold=payload.target_compliance_threshold,
            period_weeks=payload.period_weeks,
            department_targets=payload.department_targets,
            promo_multiplier=payload.promo_multiplier,
            markdown_discount_pct=payload.markdown_discount_pct,
            fuel_price_sensitivity=payload.fuel_price_sensitivity,
            custom_name=payload.custom_name,
            scenario_type=payload.scenario_type,
        )
        scenario_card = strategy.simulate_scenario(
            dataset_id=payload.dataset_id,
            params=params,
            scenario_code="SCEN-CUSTOM",
        )
        return scenario_card.to_dict()
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Simulation error: {exc}") from exc


class QueryRankingRequest(BaseModel):
    dataset_id: int
    entity_column: str
    measure_column: str
    sheet_id: int | None = None
    aggregation: str = "avg"
    direction: str = "TOP"  # TOP, BOTTOM, BOTH
    limit: Any = 5          # 5, 15, 25, 50, 100, 500, or "FULL"
    offset: int = 0
    filter_context: dict[str, Any] = Field(default_factory=dict)


@router.post("/ranking")
def query_entity_ranking(payload: QueryRankingRequest):
    """Executes server-side SQL group-by entity ranking with percentiles and benchmark comparison."""
    try:
        from ..services.adaptive_dashboard.ranking_engine import GenericEntityRankingEngine

        res = GenericEntityRankingEngine.execute_ranking_query(
            dataset_id=payload.dataset_id,
            entity_column=payload.entity_column,
            measure_column=payload.measure_column,
            sheet_id=payload.sheet_id,
            aggregation=payload.aggregation,
            direction=payload.direction,
            limit=payload.limit,
            offset=payload.offset,
            filter_context=payload.filter_context,
        )
        return res
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Ranking query error: {exc}") from exc


@router.get("/ranking/schema/{dataset_id}")
def get_ranking_schema(dataset_id: int):
    """Returns available rankable entities, measures, and initial default ranking story for a dataset."""
    try:
        from ..services.adaptive_dashboard.ranking_engine import GenericEntityRankingEngine

        entities, measures = GenericEntityRankingEngine.discover_rankable_entities_and_measures(dataset_id)
        story = GenericEntityRankingEngine.build_entity_ranking_story(dataset_id)
        return {
            "dataset_id": dataset_id,
            "entities": entities,
            "measures": measures,
            "default_story": story.model_dump() if story else None,
        }
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Ranking schema error: {exc}") from exc

