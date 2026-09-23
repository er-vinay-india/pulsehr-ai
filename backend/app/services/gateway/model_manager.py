"""ModelManager tracking local model residency, availability, and execution performance metrics."""

import logging
import time
from typing import Any
import httpx

from ...core import config
from ...core.models_config import ModelRole, get_role_config

logger = logging.getLogger(__name__)


class ModelPerformanceStats:
    def __init__(self, model_name: str):
        self.model_name = model_name
        self.invocation_count = 0
        self.failure_count = 0
        self.total_duration_ms = 0.0

    @property
    def avg_duration_ms(self) -> float:
        if self.invocation_count == 0:
            return 0.0
        return self.total_duration_ms / self.invocation_count

    def record_call(self, duration_ms: float, success: bool):
        self.invocation_count += 1
        self.total_duration_ms += duration_ms
        if not success:
            self.failure_count += 1


class ModelManager:
    """Manages local model availability in Ollama and tracks latency performance."""

    def __init__(self):
        self._stats: dict[str, ModelPerformanceStats] = {}
        self._available_models: set[str] = set()
        self._last_refresh: float = 0.0
        self._refresh_ttl: float = 60.0  # seconds

    def refresh_available_models(self, force: bool = False) -> set[str]:
        """Polls local Ollama instance for installed models with TTL caching."""
        now = time.perf_counter()
        if not force and self._available_models and (now - self._last_refresh) < self._refresh_ttl:
            return self._available_models

        try:
            with httpx.Client(timeout=3.0) as client:
                resp = client.get(f"{config.OLLAMA_BASE_URL}/api/tags")
                if resp.status_code == 200:
                    models = [m.get("name", "") for m in resp.json().get("models", [])]
                    self._available_models = {m for m in models if m}
                    self._last_refresh = now
        except Exception as exc:
            logger.debug(f"Could not refresh Ollama tags: {exc}")

        return self._available_models

    def is_model_available(self, model_name: str) -> bool:
        """Checks if a model is installed in local Ollama."""
        available = self.refresh_available_models()
        if not available:
            # If Ollama check failed, assume configured model might be valid
            return True
        # Exact match or prefix match (e.g. 'qwen3.5:9b' matches 'qwen3.5:9b-instruct')
        base_name = model_name.split(":")[0]
        return any(model_name == m or m.startswith(f"{base_name}:") for m in available)

    def record_execution(self, model_name: str, duration_ms: float, success: bool):
        """Records latency and success statistics for an inference run."""
        if model_name not in self._stats:
            self._stats[model_name] = ModelPerformanceStats(model_name)
        self._stats[model_name].record_call(duration_ms, success)

    def get_stats(self) -> dict[str, Any]:
        """Returns snapshot of model latency and invocation counts."""
        return {
            name: {
                "invocations": s.invocation_count,
                "failures": s.failure_count,
                "avg_duration_ms": round(s.avg_duration_ms, 2)
            }
            for name, s in self._stats.items()
        }


model_manager = ModelManager()
