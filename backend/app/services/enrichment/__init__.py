"""Controlled Semantic Data Enrichment & Scientific Feature Discovery Pipeline Package."""

from .config import BudgetGuard, EnrichmentConfig
from .models import (
    AnalyticalTable,
    ColumnRelationship,
    DerivedFeature,
    EnrichedDatasetPackage,
    EnrichmentColumnProfile,
    SemanticColumnGroup,
    SemanticRole,
)
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
    "EnrichmentConfig",
    "AnalyticalTable",
    "ColumnRelationship",
    "DerivedFeature",
    "EnrichedDatasetPackage",
    "EnrichmentColumnProfile",
    "SemanticColumnGroup",
    "SemanticRole",
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
