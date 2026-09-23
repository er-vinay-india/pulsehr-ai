"""Role-based model configuration and routing definitions for PulseHR AI."""

import os
from enum import Enum
from pydantic import BaseModel, Field


class ModelRole(str, Enum):
    """Logical model roles governing AI responsibilities."""
    FAST = "FAST"              # Lightweight classification, schema identification, quick metadata
    ANALYST = "ANALYST"        # Pattern discovery, statistical interpretation, metric prioritization
    REASONER = "REASONER"      # Multi-step business logic, root cause analysis, strategic trade-offs
    WRITER = "WRITER"          # Executive narrative, slide bullet points, management-friendly synthesis
    CRITIC = "CRITIC"          # Factual claim verification, hallucination checks, contradiction detection


class RoleModelConfig(BaseModel):
    """Configuration for a single logical model role."""
    primary: str
    fallback: str
    temperature: float = 0.2
    max_tokens: int = 4096
    timeout_seconds: float = 45.0


# Default mappings optimized for the installed local models on Apple Silicon
DEFAULT_ROLE_CONFIGS: dict[ModelRole, RoleModelConfig] = {
    ModelRole.FAST: RoleModelConfig(
        primary=os.getenv("MODEL_ROLE_FAST_PRIMARY", "phi4-mini:latest"),
        fallback=os.getenv("MODEL_ROLE_FAST_FALLBACK", "llama3.1:8b"),
        temperature=0.1,
        max_tokens=2048,
        timeout_seconds=25.0
    ),
    ModelRole.ANALYST: RoleModelConfig(
        primary=os.getenv("MODEL_ROLE_ANALYST_PRIMARY", "qwen3.5:9b"),
        fallback=os.getenv("MODEL_ROLE_ANALYST_FALLBACK", "gemma4:12b"),
        temperature=0.15,
        max_tokens=4096,
        timeout_seconds=45.0
    ),
    ModelRole.REASONER: RoleModelConfig(
        primary=os.getenv("MODEL_ROLE_REASONER_PRIMARY", "deepseek-r1:7b"),
        fallback=os.getenv("MODEL_ROLE_REASONER_FALLBACK", "qwen3.5:9b"),
        temperature=0.2,
        max_tokens=4096,
        timeout_seconds=60.0
    ),
    ModelRole.WRITER: RoleModelConfig(
        primary=os.getenv("MODEL_ROLE_WRITER_PRIMARY", "gemma4:12b"),
        fallback=os.getenv("MODEL_ROLE_WRITER_FALLBACK", "qwen3.5:9b"),
        temperature=0.2,
        max_tokens=4096,
        timeout_seconds=45.0
    ),
    ModelRole.CRITIC: RoleModelConfig(
        primary=os.getenv("MODEL_ROLE_CRITIC_PRIMARY", "deepseek-r1:7b"),
        fallback=os.getenv("MODEL_ROLE_CRITIC_FALLBACK", "llama3.1:8b"),
        temperature=0.05,
        max_tokens=3072,
        timeout_seconds=50.0
    )
}


def get_role_config(role: ModelRole | str) -> RoleModelConfig:
    """Retrieves the configuration for a given model role with dynamic fallback."""
    if isinstance(role, str):
        try:
            role = ModelRole(role.upper())
        except ValueError:
            role = ModelRole.ANALYST
    return DEFAULT_ROLE_CONFIGS.get(role, DEFAULT_ROLE_CONFIGS[ModelRole.ANALYST])
