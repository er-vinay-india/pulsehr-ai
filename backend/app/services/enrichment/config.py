"""Enrichment configuration and budget enforcement guard.

Guarantees hard resource bounds across derived columns, generated analytical tables,
maximum execution runtimes, and derivation recursion depths.
"""

from __future__ import annotations

import time
import logging
from typing import Any
from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)


class EnrichmentConfig(BaseModel):
    """Configurable resource budgets and algorithmic thresholds for semantic enrichment."""
    max_derived_columns: int = Field(default=1000, description="Hard ceiling on total derived columns.")
    max_generated_tables: int = Field(default=100, description="Hard ceiling on generated analytical tables.")
    max_runtime_seconds: float = Field(default=900.0, description="Maximum total execution time in seconds (15m default).")
    max_derivation_depth: int = Field(default=3, description="Maximum recursion depth for feature derivations.")
    max_formula_candidates_per_group: int = Field(default=50, description="Maximum formula candidates per semantic column group.")
    max_pairwise_candidates: int = Field(default=5000, description="Maximum column pairs evaluated for relationships.")
    min_feature_confidence: float = Field(default=0.70, description="Minimum statistical/semantic confidence to retain a feature.")
    min_relationship_score: float = Field(default=0.60, description="Minimum hybrid score to form a relationship edge.")
    min_table_utility_score: float = Field(default=0.65, description="Minimum analytical utility required to materialize a table.")
    min_feature_utility_score: float = Field(default=0.50, description="Minimum utility score for candidate feature acceptance.")
    max_dimensions_per_table: int = Field(default=4, description="Maximum dimensions allowed per analytical table to prevent explosion.")
    max_measures_per_table: int = Field(default=6, description="Maximum aggregated measures per analytical table.")
    featuretools_enabled: bool = Field(default=True, description="Enable Featuretools DFS feature derivation.")
    unit_processing_enabled: bool = Field(default=True, description="Enable Pint unit validation and dimensional analysis.")
    symbolic_regression_enabled: bool = Field(default=True, description="Enable PySR symbolic regression discovery.")
    visions_enabled: bool = Field(default=True, description="Enable Visions semantic type profiling.")

    @classmethod
    def from_dict(cls, data: dict[str, Any] | None) -> EnrichmentConfig:
        if not data:
            return cls()
        enrich_data = data.get("enrichment", data)
        return cls(**{k: v for k, v in enrich_data.items() if k in cls.model_fields})


class BudgetExceededException(Exception):
    """Raised when hard resource limits or runtime execution bounds are exceeded."""
    pass


class BudgetGuard:
    """Monitors and enforces resource budgets during feature discovery and dataset enrichment."""

    def __init__(self, config: EnrichmentConfig):
        self.config = config
        self.start_time = time.perf_counter()
        self.derived_columns_count = 0
        self.generated_tables_count = 0
        self.stopped_due_to_limit = False
        self.limit_reason: str | None = None

    @property
    def elapsed_seconds(self) -> float:
        return time.perf_counter() - self.start_time

    def check_runtime_budget(self) -> bool:
        """Checks if runtime budget is still valid. Returns True if okay, False if expired."""
        if self.elapsed_seconds > self.config.max_runtime_seconds:
            self.stopped_due_to_limit = True
            self.limit_reason = f"Maximum runtime exceeded: {self.elapsed_seconds:.2f}s > {self.config.max_runtime_seconds}s"
            logger.warning(self.limit_reason)
            return False
        return True

    def can_derive_column(self, count: int = 1) -> bool:
        """Determines if additional derived columns fit within the hard limit."""
        if not self.check_runtime_budget():
            return False
        if self.derived_columns_count + count > self.config.max_derived_columns:
            self.stopped_due_to_limit = True
            self.limit_reason = (
                f"Maximum derived columns ceiling reached: "
                f"{self.derived_columns_count} + {count} > {self.config.max_derived_columns}"
            )
            logger.warning(self.limit_reason)
            return False
        return True

    def record_derived_columns(self, count: int = 1) -> int:
        """Records derived column additions, clamping if necessary."""
        allowed = min(count, max(0, self.config.max_derived_columns - self.derived_columns_count))
        self.derived_columns_count += allowed
        return allowed

    def can_generate_table(self) -> bool:
        """Determines if another analytical table can be generated within budget."""
        if not self.check_runtime_budget():
            return False
        if self.generated_tables_count >= self.config.max_generated_tables:
            self.stopped_due_to_limit = True
            self.limit_reason = (
                f"Maximum generated tables ceiling reached: "
                f"{self.generated_tables_count} >= {self.config.max_generated_tables}"
            )
            logger.warning(self.limit_reason)
            return False
        return True

    def record_generated_table(self) -> bool:
        """Records an analytical table creation."""
        if self.can_generate_table():
            self.generated_tables_count += 1
            return True
        return False

    def remaining_column_budget(self) -> int:
        return max(0, self.config.max_derived_columns - self.derived_columns_count)

    def remaining_table_budget(self) -> int:
        return max(0, self.config.max_generated_tables - self.generated_tables_count)

    def get_summary(self) -> dict[str, Any]:
        return {
            "elapsed_seconds": round(self.elapsed_seconds, 3),
            "derived_columns_count": self.derived_columns_count,
            "max_derived_columns": self.config.max_derived_columns,
            "generated_tables_count": self.generated_tables_count,
            "max_generated_tables": self.config.max_generated_tables,
            "stopped_due_to_limit": self.stopped_due_to_limit,
            "limit_reason": self.limit_reason
        }


# Canonical alias
EnrichmentBudgetManager = BudgetGuard
