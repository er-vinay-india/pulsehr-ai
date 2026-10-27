"""Presentation Typography Package.

Combines dedicated typography AI specialist (Phi-4 Mini + MLX-LM LoRA)
with deterministic layout and styling engine across PPTX, HTML, and future PDF.
"""
from .contracts import (
    DensityRisk,
    ImportantTextRun,
    ReflowPreference,
    ResolvedTypographySpec,
    SemanticTypographyRole,
    TypographyBlockProvenance,
    TypographyColorRole,
    TypographyImportance,
    TypographyIntent,
    TypographyManifest,
    TypographyPreferredWeight,
    TypographyRelativeScale,
    normalize_semantic_role,
)
from .deterministic_engine import (
    POINT_SIZE_MATRIX,
    THEME_PALETTES,
    DeterministicTypographyEngine,
)
from .resolver import TypographyResolver
from .specialist import TypographyIntelligenceModel

__all__ = [
    "DensityRisk",
    "DeterministicTypographyEngine",
    "ImportantTextRun",
    "POINT_SIZE_MATRIX",
    "ReflowPreference",
    "ResolvedTypographySpec",
    "SemanticTypographyRole",
    "THEME_PALETTES",
    "TypographyBlockProvenance",
    "TypographyColorRole",
    "TypographyImportance",
    "TypographyIntelligenceModel",
    "TypographyIntent",
    "TypographyManifest",
    "TypographyPreferredWeight",
    "TypographyRelativeScale",
    "TypographyResolver",
    "normalize_semantic_role",
]
