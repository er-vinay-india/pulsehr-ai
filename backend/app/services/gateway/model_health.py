"""Model Health & Circuit Breaker Service for HighView Model Gateway (Phase A).

Provides:
- Real-time availability and latency telemetry across installed local models.
- Fast circuit breaking: detects repeated model timeouts or server errors and
  routes around failing models without incurring repeated high-latency timeouts.
- Half-open probation: automatically re-tests degraded models after a cool-down window.
- Graceful offline detection: recognizes when the local Ollama daemon is down.
"""
from __future__ import annotations

import logging
import time
from typing import Any
import httpx

from ...core import config
from .contracts import ModelHealthState

logger = logging.getLogger(__name__)


class ModelMetrics:
    """Telemetry and circuit breaker state for a specific local LLM."""
    def __init__(self, model_name: str):
        self.model_name = model_name
        self.state: ModelHealthState = ModelHealthState.HEALTHY
        self.invocation_count = 0
        self.success_count = 0
        self.failure_count = 0
        self.consecutive_failures = 0
        self.total_latency_ms = 0.0
        self.last_failure_time: float | None = None
        self.last_success_time: float | None = None
        self.last_error: str | None = None
        self.circuit_tripped_at: float | None = None

    @property
    def avg_latency_ms(self) -> float:
        if self.success_count == 0:
            return 0.0
        return self.total_latency_ms / self.success_count

    def to_dict(self) -> dict[str, Any]:
        return {
            "model_name": self.model_name,
            "state": self.state.value,
            "invocations": self.invocation_count,
            "successes": self.success_count,
            "failures": self.failure_count,
            "consecutive_failures": self.consecutive_failures,
            "avg_latency_ms": round(self.avg_latency_ms, 1),
            "last_error": self.last_error,
        }


class ModelHealthService:
    """Fleet-wide health monitor and circuit breaker for HighView AI models."""

    def __init__(
        self,
        failure_threshold: int = 3,
        cool_down_seconds: float = 30.0,
        tags_cache_ttl: float = 60.0
    ):
        self.failure_threshold = failure_threshold
        self.cool_down_seconds = cool_down_seconds
        self.tags_cache_ttl = tags_cache_ttl

        self._metrics: dict[str, ModelMetrics] = {}
        self._installed_models: set[str] = set()
        self._last_tags_refresh: float = 0.0
        self._daemon_available: bool = True

    def _get_or_create(self, model_name: str) -> ModelMetrics:
        if model_name not in self._metrics:
            self._metrics[model_name] = ModelMetrics(model_name)
        return self._metrics[model_name]

    def refresh_installed_models(self, force: bool = False) -> set[str]:
        """Queries local Ollama tags endpoint to discover installed models."""
        now = time.perf_counter()
        if not force and self._installed_models and (now - self._last_tags_refresh) < self.tags_cache_ttl:
            return self._installed_models

        try:
            with httpx.Client(timeout=3.0) as client:
                resp = client.get(f"{config.OLLAMA_BASE_URL}/api/tags")
                if resp.status_code == 200:
                    models = [m.get("name", "") for m in resp.json().get("models", [])]
                    self._installed_models = {m for m in models if m}
                    self._last_tags_refresh = now
                    self._daemon_available = True
                    return self._installed_models
        except Exception as exc:
            logger.debug(f"Could not connect to Ollama daemon at {config.OLLAMA_BASE_URL}: {exc}")
            self._daemon_available = False

        return self._installed_models

    def is_daemon_online(self) -> bool:
        """Quick check whether local Ollama server is responding."""
        self.refresh_installed_models()
        return self._daemon_available

    def is_model_installed(self, model_name: str) -> bool:
        """Verifies if model is present in local Ollama installation."""
        installed = self.refresh_installed_models()
        if not installed:
            # If daemon check failed or tags not loaded, assume potentially available
            return True
        base = model_name.split(":")[0]
        return any(model_name == m or m.startswith(f"{base}:") for m in installed)

    def is_healthy(self, model_name: str) -> bool:
        """Determines if a model is ready for traffic without tripping breaker."""
        m = self._get_or_create(model_name)

        if m.state == ModelHealthState.HEALTHY:
            return True

        if m.state == ModelHealthState.DEGRADED:
            # Check if cool-down window has elapsed (half-open state allows a probe)
            now = time.perf_counter()
            if m.circuit_tripped_at and (now - m.circuit_tripped_at) >= self.cool_down_seconds:
                logger.info(f"Model '{model_name}' cool-down expired; entering half-open probation probe.")
                return True
            return False

        return False

    def record_success(self, model_name: str, latency_ms: float) -> None:
        """Records successful inference completion and restores healthy state."""
        m = self._get_or_create(model_name)
        m.invocation_count += 1
        m.success_count += 1
        m.consecutive_failures = 0
        m.total_latency_ms += latency_ms
        m.last_success_time = time.perf_counter()
        m.last_error = None
        if m.state != ModelHealthState.HEALTHY:
            logger.info(f"Model '{model_name}' restored to HEALTHY state.")
            m.state = ModelHealthState.HEALTHY
            m.circuit_tripped_at = None

    def record_failure(self, model_name: str, error: str) -> None:
        """Records model invocation failure and trips circuit breaker if threshold reached."""
        m = self._get_or_create(model_name)
        now = time.perf_counter()
        m.invocation_count += 1
        m.failure_count += 1
        m.consecutive_failures += 1
        m.last_failure_time = now
        m.last_error = error

        if m.consecutive_failures >= self.failure_threshold and m.state == ModelHealthState.HEALTHY:
            m.state = ModelHealthState.DEGRADED
            m.circuit_tripped_at = now
            logger.warning(
                f"Circuit breaker TRIPPED for model '{model_name}' "
                f"after {m.consecutive_failures} consecutive failures. "
                f"Cool-down: {self.cool_down_seconds}s. Error: {error}"
            )

    def get_fleet_health(self) -> dict[str, Any]:
        """Returns fleet-wide telemetry snapshot for administration & observability."""
        return {
            "daemon_available": self._daemon_available,
            "installed_count": len(self._installed_models),
            "models": {name: metrics.to_dict() for name, metrics in self._metrics.items()}
        }

    def reset(self) -> None:
        """Resets all metrics and circuit breakers for test isolation."""
        self._metrics.clear()
        self._installed_models.clear()
        self._last_tags_refresh = 0.0
        self._daemon_available = True


model_health_service = ModelHealthService()
