"""Presentation Validation & Hardening Package.

Provides end-to-end evaluation harness, golden test corpus, failure taxonomy,
model observability metrics, and mechanical theme integrity verification.
"""

from .validation_models import (
    FailureTaxonomy,
    ResponsibleLayer,
    ValidationIssue,
    DeckScorecard,
    ModelObservabilityReport,
    ThemeIntegrityCheckResult,
    PresentationValidationResult,
)
from .theme_integrity_gate import ThemeIntegrityGate
from .scenarios import (
    ScenarioDefinition,
    get_all_validation_scenarios,
    create_scenario_a_workforce,
    create_scenario_b_sales,
    create_scenario_c_finance,
    create_scenario_d_software_tech,
    create_scenario_e_educational,
    create_scenario_f_research,
    create_scenario_g_sparse_data,
    create_scenario_h_dense_multi_sheet,
)
from .validation_harness import RealWorldValidationHarness
from .golden_corpus import GOLDEN_CORPUS, GoldenTestCase

__all__ = [
    "FailureTaxonomy",
    "ResponsibleLayer",
    "ValidationIssue",
    "DeckScorecard",
    "ModelObservabilityReport",
    "ThemeIntegrityCheckResult",
    "PresentationValidationResult",
    "ThemeIntegrityGate",
    "ScenarioDefinition",
    "get_all_validation_scenarios",
    "create_scenario_a_workforce",
    "create_scenario_b_sales",
    "create_scenario_c_finance",
    "create_scenario_d_software_tech",
    "create_scenario_e_educational",
    "create_scenario_f_research",
    "create_scenario_g_sparse_data",
    "create_scenario_h_dense_multi_sheet",
    "RealWorldValidationHarness",
    "GOLDEN_CORPUS",
    "GoldenTestCase",
]
