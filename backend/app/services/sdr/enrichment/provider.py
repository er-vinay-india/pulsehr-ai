"""
HighView Semantic Data Refinery — Phase SDR-4
Enrichment Provider Base Class & Registry
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any, Sequence

from app.services.sdr.contracts.enrichment import (
    EnrichmentCandidate,
    EnrichmentProviderMetadata,
)
from app.services.sdr.contracts.profiles import SemanticColumnProfile


class EnrichmentProvider(ABC):
    """
    Abstract base interface for all SDR-4 enrichment providers.
    Generic, deterministic, offline-first.
    """

    def __init__(self, metadata: EnrichmentProviderMetadata):
        self.metadata = metadata

    @property
    def provider_id(self) -> str:
        return self.metadata.provider_id

    @property
    def provider_version(self) -> str:
        return self.metadata.provider_version

    @property
    def reference_data_version(self) -> str:
        return self.metadata.reference_data_version

    @abstractmethod
    def can_handle(self, profile: SemanticColumnProfile) -> bool:
        """Determines if the provider can propose enrichments for this column profile."""
        pass

    @abstractmethod
    def generate_candidates(
        self,
        dataset_id: str,
        sheet_id: str,
        profile: SemanticColumnProfile,
        sample_values: Sequence[Any] | None = None,
        policy_fingerprint: str = "",
        depth: int = 1,
        parent_enrichment_id: str | None = None,
    ) -> list[EnrichmentCandidate]:
        """Proposes enrichment candidates for an eligible column."""
        pass

    @abstractmethod
    def resolve(self, candidate: EnrichmentCandidate, values: Sequence[Any] | None = None) -> Any:
        """
        Executes or compiles the enrichment projection.
        Returns materialized sequence or deterministic SQL/virtual expression.
        """
        pass


class EnrichmentProviderRegistry:
    """Registry managing available enrichment providers."""

    def __init__(self):
        self._providers: dict[str, EnrichmentProvider] = {}

    def register_provider(self, provider: EnrichmentProvider) -> None:
        self._providers[provider.provider_id] = provider

    def unregister_provider(self, provider_id: str) -> None:
        if provider_id in self._providers:
            del self._providers[provider_id]

    def get_provider(self, provider_id: str) -> EnrichmentProvider | None:
        return self._providers.get(provider_id)

    def list_providers(self) -> list[EnrichmentProvider]:
        return list(self._providers.values())

    def find_providers_for_profile(self, profile: SemanticColumnProfile) -> list[EnrichmentProvider]:
        return [p for p in self._providers.values() if p.can_handle(profile)]
