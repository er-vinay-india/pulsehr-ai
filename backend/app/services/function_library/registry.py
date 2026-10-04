"""Central Registry for Analytical Functions & Business Impact Translation.

Discovers, registers, and executes self-describing mathematical functions.
Generates token-optimized DSL representations for system prompts and syncs
with permanent isolated SQLite storage.
"""

import importlib
import logging
import pkgutil
from pathlib import Path
from typing import Any, Type

from ..data_engine.semantic_classifier import SemanticDatasetProfile
from .base import (
    BaseAnalyticalFunction,
    AnalyticalFunctionMetadata,
    BusinessImpactAssessment,
)
from .storage import FunctionLibraryStorage

logger = logging.getLogger(__name__)


class AnalyticalFunctionRegistry:
    """Singleton registry coordinating analytical function discovery, execution, and storage."""

    _instance: "AnalyticalFunctionRegistry | None" = None
    _functions: dict[str, BaseAnalyticalFunction] = {}
    _storage: FunctionLibraryStorage | None = None
    _catalog_loaded: bool = False

    def __new__(cls) -> "AnalyticalFunctionRegistry":
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._functions = {}
            cls._instance._storage = FunctionLibraryStorage()
            cls._instance._catalog_loaded = False
        return cls._instance

    @classmethod
    def register(cls, func_instance: BaseAnalyticalFunction) -> BaseAnalyticalFunction:
        """Registers a concrete AnalyticalFunction instance in the registry."""
        registry = cls()
        meta = func_instance.metadata
        registry._functions[meta.function_id] = func_instance

        # Sync to permanent storage
        if registry._storage:
            registry._storage.upsert_function(meta)

        logger.debug(f"Registered analytical function '{meta.function_id}' ({meta.name})")
        return func_instance

    @classmethod
    def load_catalog(cls, force_reload: bool = False) -> None:
        """Discovers and imports all analytical functions in the catalog package."""
        registry = cls()
        if registry._catalog_loaded and not force_reload:
            return

        import app.services.function_library.catalog as catalog_pkg

        package_path = Path(catalog_pkg.__file__).parent

        for module_info in pkgutil.walk_packages([str(package_path)], prefix="app.services.function_library.catalog."):
            try:
                importlib.import_module(module_info.name)
            except Exception as e:
                logger.warning(f"Failed to auto-load catalog module {module_info.name}: {e}")

        registry._catalog_loaded = True
        logger.info(f"Loaded {len(registry._functions)} analytical functions into registry.")

    @classmethod
    def get_function(cls, function_id: str) -> BaseAnalyticalFunction | None:
        """Retrieves an analytical function instance by ID."""
        cls.load_catalog()
        return cls()._functions.get(function_id)

    @classmethod
    def get_all(cls) -> list[BaseAnalyticalFunction]:
        """Returns all registered function instances."""
        cls.load_catalog()
        return list(cls()._functions.values())

    @classmethod
    def find_admissible(cls, profile: SemanticDatasetProfile) -> list[BaseAnalyticalFunction]:
        """Returns all functions whose preconditions match the dataset profile."""
        cls.load_catalog()
        return [fn for fn in cls()._functions.values() if fn.matches_profile(profile)]

    @classmethod
    def evaluate_business_impact(
        cls,
        fact: Any,
        df: Any,
        profile: SemanticDatasetProfile
    ) -> BusinessImpactAssessment | None:
        """Evaluates business impact for a candidate fact using registered functions."""
        cls.load_catalog()
        registry = cls()

        # 1. Try direct function_id if tagged on fact
        fn_id = getattr(fact, "function_id", None)
        if fn_id and fn_id in registry._functions:
            res = registry._functions[fn_id].evaluate_impact(fact, df, profile)
            if res:
                return res

        # 2. Iterate matching registered functions
        for fn in registry._functions.values():
            try:
                assessment = fn.evaluate_impact(fact, df, profile)
                if assessment:
                    return assessment
            except Exception as e:
                logger.debug(f"Function {fn.metadata.function_id} skipped evaluation for fact: {e}")

        return None

    @classmethod
    def get_compact_prompt_block(cls) -> str:
        """Retrieves token-optimized compact prompt block (<400 tokens total)."""
        cls.load_catalog()
        registry = cls()
        if registry._storage:
            return registry._storage.get_compact_token_block()

        lines = [fn.metadata.compile_compact_token_repr() for fn in registry._functions.values()]
        return "[ANALYTICAL_FUNCTION_LIBRARY]\n" + "\n".join(lines)

    @classmethod
    def get_jargon_dictionary(cls) -> dict[str, str]:
        """Returns combined jargon translation dictionary across all registered functions."""
        cls.load_catalog()
        combined = {}
        for fn in cls()._functions.values():
            combined.update(fn.metadata.jargon_mapping.term_translations)
        return combined


def register_function(func_cls: Type[BaseAnalyticalFunction]) -> Type[BaseAnalyticalFunction]:
    """Decorator to auto-instantiate and register an AnalyticalFunction."""
    instance = func_cls()
    AnalyticalFunctionRegistry.register(instance)
    return func_cls
