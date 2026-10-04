"""Module Registry for Modular Test Architecture.

Defines the mapping between domain source directories and their corresponding test suites.
Used by the test runner and git impact analyzer to selectively execute only the tests
relevant to the changed modules.
"""

from dataclasses import dataclass, field
from typing import List, Dict

@dataclass(frozen=True)
class ModuleSpec:
    name: str
    description: str
    pytest_marker: str
    source_patterns: List[str]
    test_files: List[str]
    unit_only_keywords: List[str] = field(default_factory=list)

MODULE_REGISTRY: Dict[str, ModuleSpec] = {
    "enrichment": ModuleSpec(
        name="enrichment",
        description="Semantic data enrichment, typing, primitive derivation, and scientific formulas",
        pytest_marker="enrichment",
        source_patterns=[
            "backend/app/services/enrichment/",
        ],
        test_files=[
            "tests/test_enrichment_pipeline.py",
        ],
        unit_only_keywords=[
            "test_budget_guard",
            "test_data_profiling",
            "test_column_relationships",
            "test_primitive_feature_derivation",
            "test_scientific_formula_discovery",
            "test_interaction_features",
            "test_unit_system_adapter",
            "test_profiling_and_statistical",
            "test_formula_registry",
            "test_symbolic_relationship_adapter_fallback",
        ],
    ),
    "eda": ModuleSpec(
        name="eda",
        description="Exploratory Data Analysis, distributions, correlation matrix, temporal dynamics, and group-by analytics",
        pytest_marker="eda",
        source_patterns=[
            "backend/app/services/eda/",
            "backend/app/routers/eda.py",
        ],
        test_files=[
            "tests/test_eda_pipeline.py",
            "tests/test_walmart_sales_analytics.py",
            "tests/test_hr_executive_analytics.py",
            "tests/test_industrial_analytics.py",
        ],
        unit_only_keywords=[
            "test_normalizer_primitives",
            "test_normalize_dataset_statistical_profiling",
            "test_walmart_domain_detection",
            "test_walmart_chart_prerequisites",
            "test_walmart_prioritized_facts",
        ],
    ),
    "dashboard": ModuleSpec(
        name="dashboard",
        description="Adaptive decision dashboard, executive cards, KPI metrics, and cohort projections",
        pytest_marker="dashboard",
        source_patterns=[
            "backend/app/services/adaptive_dashboard/",
            "backend/app/routers/adaptive_dashboard.py",
        ],
        test_files=[
            "tests/test_adaptive_dashboard.py",
        ],
        unit_only_keywords=[
            "test_independent_calculation",
            "test_repeated_observations",
            "test_fixture_37_people",
            "test_unknown_workforce_coverage",
            "test_attendance_counts",
            "test_missing_values_not_treated_as_zero",
            "test_source_change_invalidates_snapshot",
            "test_undecidable_data_emits_honest_definition_card",
            "test_exactly_one_element_emitted",
        ],
    ),
    "presentation": ModuleSpec(
        name="presentation",
        description="Slide generation, presentation director, memory, narration, and visual layout",
        pytest_marker="presentation",
        source_patterns=[
            "backend/app/services/presentation/",
            "backend/app/services/presentation_*.py",
            "backend/app/routers/presentation.py",
            "backend/app/routers/presentations.py",
            "backend/app/services/pptx/",
        ],
        test_files=[
            "tests/test_presentation_director.py",
            "tests/test_presentation_memory.py",
            "tests/test_presentation_narration.py",
            "tests/test_presentation_orchestrator.py",
            "tests/test_presentation_pipeline.py",
            "tests/test_presentation_validation_hardening.py",
            "tests/test_presentation_visual.py",
            "tests/test_presentation_visual_qa.py",
            "tests/test_spatial_overflow_monitor.py",
            "tests/test_decision_deck.py",
            "tests/test_local_voiceover.py",
            "tests/test_slide_export_contrast.py",
            "tests/test_export_parity_guard.py",
            "tests/test_presentation_chatbot_mutations.py",
            "tests/test_e2e_conversational_visual_flow.py",
        ],
        unit_only_keywords=[
            "test_intent_extraction",
            "test_audience_adaptation",
            "test_slide_count",
            "test_information_unit",
            "test_strict_truth",
            "test_duplicate_concept",
        ],
    ),
    "copilot": ModuleSpec(
        name="copilot",
        description="Copilot conversational reasoning, intent triage, query planning, and tools",
        pytest_marker="copilot",
        source_patterns=[
            "backend/app/services/copilot/",
            "backend/app/services/ai_copilot.py",
            "backend/app/services/copilot_query_planner.py",
            "backend/app/services/copilot_tools.py",
            "backend/app/routers/copilot.py",
        ],
        test_files=[
            "tests/test_copilot_contextual_business.py",
            "tests/test_copilot_streaming.py",
            "tests/test_copilot_tools.py",
            "tests/test_generic_copilot_engine.py",
            "tests/test_chatbot_decision_integration.py",
            "tests/test_hybrid_retrieval.py",
        ],
    ),
    "ingestion": ModuleSpec(
        name="ingestion",
        description="Data upload, sheet catalog, context intelligence, CSV/Excel parsing, null pruning",
        pytest_marker="ingestion",
        source_patterns=[
            "backend/app/routers/upload.py",
            "backend/app/services/sheet_catalog.py",
            "backend/app/services/sheet_naming_pipeline.py",
            "backend/app/services/input_intelligence/",
            "backend/app/services/data_engine/",
        ],
        test_files=[
            "tests/test_sheet_catalog.py",
            "tests/test_sheet_naming_pipeline.py",
            "tests/test_ingestion_null_pruning.py",
            "tests/test_input_context_intelligence.py",
            "tests/test_workspace_context_integration.py",
            "tests/test_delete_pipeline.py",
            "tests/test_data_engine_deterministic.py",
            "tests/test_untrusted_data_safety.py",
            "tests/test_backend.py",
        ],
    ),
    "critic": ModuleSpec(
        name="critic",
        description="Factual claim validation, deterministic verification, and evidence store traceability",
        pytest_marker="critic",
        source_patterns=[
            "backend/app/services/critic/",
            "backend/app/services/evidence/",
        ],
        test_files=[
            "tests/test_critic_claim_verification.py",
            "tests/test_deterministic_claim_validator.py",
            "tests/test_evidence_grounded_interpretation.py",
            "tests/test_evidence_store_traceability.py",
        ],
    ),
    "decision_intelligence": ModuleSpec(
        name="decision_intelligence",
        description="Strategy reproduction, fact discovery, investigation service, and executive stories",
        pytest_marker="decision_intelligence",
        source_patterns=[
            "backend/app/services/decision_intelligence.py",
            "backend/app/services/decision_engine/",
            "backend/app/services/fact_discovery.py",
            "backend/app/services/investigation/",
            "backend/app/services/storytelling/",
            "backend/app/services/analyst/",
            "backend/app/services/reporting/",
        ],
        test_files=[
            "tests/test_decision_intelligence.py",
            "tests/test_insight_strategy_reproduction.py",
            "tests/test_investigation_service.py",
            "tests/test_leadership_report.py",
            "tests/test_executive_story.py",
            "tests/test_strategy_orchestrator_integration.py",
            "tests/test_workflow_orchestrator.py",
            "tests/test_generic_candidate_fact_discovery.py",
            "tests/test_generic_interestingness_ranker.py",
            "tests/test_generic_semantic_profiler.py",
            "tests/test_generic_workflow_orchestrator.py",
            "tests/test_analysis_brief_pipeline.py",
            "tests/test_chunked_overview.py",
            "tests/test_display_formatters.py",
            "tests/test_dynamic_charts_and_facts.py",
            "tests/test_fact_visualizer.py",
            "tests/test_visual_intelligence.py",
            "tests/test_model_architecture_benchmarks.py",
            "tests/test_model_gateway_roles.py",
        ],
    ),
}


def find_impacted_modules(changed_files: List[str]) -> List[ModuleSpec]:
    """Given a list of changed file paths, determine which modules are impacted."""
    impacted = set()
    for f in changed_files:
        normalized_f = f.replace("\\", "/")
        matched = False
        for mod_name, spec in MODULE_REGISTRY.items():
            for src_pattern in spec.source_patterns:
                if normalized_f.startswith(src_pattern) or src_pattern in normalized_f:
                    impacted.add(mod_name)
                    matched = True
                    break
            # Also check if a test file itself was modified
            for test_file in spec.test_files:
                if normalized_f.endswith(test_file) or test_file in normalized_f:
                    impacted.add(mod_name)
                    matched = True
                    break
    return [MODULE_REGISTRY[m] for m in sorted(impacted)]
