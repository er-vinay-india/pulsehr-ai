"""Controlled Semantic Data Enrichment & Scientific Feature Discovery Pipeline Package."""

from .config import BudgetGuard, EnrichmentBudgetManager, EnrichmentConfig
from .models import (
    AnalyticalTable,
    CandidateFeature,
    ColumnRelationship,
    DerivedFeature,
    EnrichedDatasetPackage,
    EnrichmentColumnProfile,
    SemanticColumnGroup,
    SemanticRole,
)
from .formula_registry import FormulaRegistry, FormulaDefinition
from .profiler import EnrichmentProfiler
from .relationship_engine import ColumnRelationshipEngine
from .column_grouping import ColumnGroupingEngine
from .primitive_deriver import PrimitiveFeatureDeriver
from .formula_engine import ScientificFormulaEngine
from .interaction_engine import InteractionFeatureEngine
from .table_synthesizer import AnalyticalTableSynthesizer
from .utility_evaluator import FeatureUtilityEvaluator
from .pipeline import ControlledEnrichmentPipeline

__all__ = [
    "BudgetGuard",
    "EnrichmentBudgetManager",
    "EnrichmentConfig",
    "AnalyticalTable",
    "CandidateFeature",
    "ColumnRelationship",
    "DerivedFeature",
    "EnrichedDatasetPackage",
    "EnrichmentColumnProfile",
    "SemanticColumnGroup",
    "SemanticRole",
    "FormulaRegistry",
    "FormulaDefinition",
    "EnrichmentProfiler",
    "ColumnRelationshipEngine",
    "ColumnGroupingEngine",
    "PrimitiveFeatureDeriver",
    "ScientificFormulaEngine",
    "InteractionFeatureEngine",
    "AnalyticalTableSynthesizer",
    "FeatureUtilityEvaluator",
    "ControlledEnrichmentPipeline",
]
