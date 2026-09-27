from __future__ import annotations

import hashlib
import logging
from typing import Sequence
import httpx

from ....core import config

logger = logging.getLogger(__name__)


class NomicEmbeddingService:
    """Provides local embedding generation using Nomic (via Ollama) with content-hash caching and batching."""

    def __init__(
        self,
        base_url: str | None = None,
        model_name: str | None = None,
        timeout_seconds: float = 30.0,
        max_cache_size: int = 2048,
    ):
        self.base_url = (base_url or config.OLLAMA_BASE_URL).rstrip("/")
        self.model_name = model_name or config.PRESENTATION_EMBEDDING_MODEL
        self.timeout_seconds = timeout_seconds
        self.max_cache_size = max_cache_size
        self._memory_cache: dict[str, list[float]] = {}

    @staticmethod
    def compute_content_hash(text: str) -> str:
        """Computes deterministic SHA-256 hash of normalized text."""
        normalized = text.strip()
        return hashlib.sha256(normalized.encode("utf-8")).hexdigest()

    def get_cached_embedding(self, content_hash: str) -> list[float] | None:
        return self._memory_cache.get(content_hash)

    def cache_embedding(self, content_hash: str, vector: list[float]) -> None:
        if len(self._memory_cache) >= self.max_cache_size:
            # Evict oldest 20%
            evict_keys = list(self._memory_cache.keys())[: max(1, self.max_cache_size // 5)]
            for k in evict_keys:
                self._memory_cache.pop(k, None)
        self._memory_cache[content_hash] = vector

    def embed_text(self, text: str) -> list[float] | None:
        """Embeds a single string, checking the content hash cache first."""
        if not text or not text.strip():
            return None

        h = self.compute_content_hash(text)
        cached = self.get_cached_embedding(h)
        if cached is not None:
            return cached

        res = self.embed_batch([text])
        if res and res[0] is not None:
            return res[0]
        return None

    def embed_batch(self, texts: Sequence[str]) -> list[list[float] | None]:
        """Embeds a batch of texts using Ollama with caching and graceful degradation."""
        if not texts:
            return []

        results: list[list[float] | None] = [None] * len(texts)
        missing_indices: list[int] = []
        missing_texts: list[str] = []
        hashes: list[str] = []

        for idx, t in enumerate(texts):
            clean = (t or "").strip()
            if not clean:
                continue
            h = self.compute_content_hash(clean)
            hashes.append(h)
            cached = self.get_cached_embedding(h)
            if cached is not None:
                results[idx] = cached
            else:
                missing_indices.append(idx)
                missing_texts.append(clean)

        if not missing_texts:
            return results

        # Call Ollama embedding endpoint
        endpoint = f"{self.base_url}/api/embeddings"
        for m_idx, text_chunk in zip(missing_indices, missing_texts):
            try:
                with httpx.Client(timeout=self.timeout_seconds) as client:
                    payload = {"model": self.model_name, "prompt": text_chunk}
                    resp = client.post(endpoint, json=payload)
                    if resp.status_code == 200:
                        data = resp.json()
                        vec = data.get("embedding")
                        if vec and isinstance(vec, list) and len(vec) == config.EMBEDDING_DIM:
                            results[m_idx] = vec
                            h = self.compute_content_hash(text_chunk)
                            self.cache_embedding(h, vec)
                        else:
                            logger.warning(f"Unexpected embedding format or dim from Ollama: {len(vec) if vec else 0}")
                    else:
                        logger.warning(f"Ollama embedding HTTP error {resp.status_code}: {resp.text[:120]}")
            except Exception as exc:
                logger.warning(f"Ollama embedding call failed for text chunk: {exc}")

        return results


# Global singleton
embedding_service = NomicEmbeddingService()
