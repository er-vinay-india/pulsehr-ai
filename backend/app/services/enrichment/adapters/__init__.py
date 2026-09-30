"""
Enrichment Adapters Package.
Wraps third-party libraries behind clean internal interfaces with graceful fallbacks.
"""

from .unit_adapter import UnitSystemAdapter
from .statistical_adapter import StatisticalAdapter
from .feature_synthesis_adapter import FeatureSynthesisAdapter
from .profiling_adapter import ProfilingAdapter
from .symbolic_adapter import SymbolicRelationshipAdapter

__all__ = [
    "UnitSystemAdapter",
    "StatisticalAdapter",
    "FeatureSynthesisAdapter",
    "ProfilingAdapter",
    "SymbolicRelationshipAdapter",
]
