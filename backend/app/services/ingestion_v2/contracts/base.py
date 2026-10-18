"""
HighView Ingestion V2 — Base Contract
Stage: Common Foundation & Deterministic Fingerprinting
"""

import hashlib
import json
from datetime import datetime, timezone
from typing import Any
from pydantic import BaseModel, ConfigDict, Field

from app.services.ingestion_v2.contracts.provenance import SourceCoordinateRef


def compute_stage_fingerprint(data: Any, exclude_keys: set[str] | None = None) -> str:
    """
    Computes a deterministic SHA-256 fingerprint for contract payloads.
    Excludes non-deterministic, volatile, or transient metadata such as
    run_id, created_at, execution_duration_ms, and stage_fingerprint itself.
    """
    default_excludes = {
        "run_id",
        "created_at",
        "execution_duration_ms",
        "stage_fingerprint",
        "temporary_path",
        "temp_file",
    }
    excludes = default_excludes.union(exclude_keys or set())

    def _canonicalize(obj: Any) -> Any:
        if isinstance(obj, dict):
            return {k: _canonicalize(v) for k, v in sorted(obj.items()) if k not in excludes}
        elif isinstance(obj, (list, tuple)):
            return [_canonicalize(v) for v in obj]
        elif isinstance(obj, BaseModel):
            return _canonicalize(obj.model_dump(exclude=excludes))
        elif isinstance(obj, float):
            # Round floats to 6 decimal places to prevent platform float representation drift
            return round(obj, 6)
        elif isinstance(obj, (int, str, bool)) or obj is None:
            return obj
        else:
            return str(obj)

    canonical_obj = _canonicalize(data)
    canonical_json = json.dumps(canonical_obj, sort_keys=True, separators=(",", ":"), ensure_ascii=True)
    return hashlib.sha256(canonical_json.encode("utf-8")).hexdigest()


class IngestionContractBase(BaseModel):
    """
    Immutable, strictly typed base contract for all Ingestion V2 pipeline stages.
    Enforces zero-pollution: extra fields are forbidden, mutation is frozen.
    """
    model_config = ConfigDict(extra="forbid", frozen=True)

    pipeline_version: str = "v2"
    dataset_id: str
    run_id: str
    stage_name: str
    created_at: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

    source_fingerprint: str
    upstream_fingerprint: str | None = None
    stage_fingerprint: str | None = None

    contract_version: str = "1.0.0"
    warnings: list[str] = Field(default_factory=list)
    confidence: float = Field(default=1.0, ge=0.0, le=1.0)
    provenance: list[SourceCoordinateRef] = Field(default_factory=list)

    def with_fingerprint(self) -> "IngestionContractBase":
        """
        Returns a frozen copy with stage_fingerprint computed deterministically.
        """
        computed = compute_stage_fingerprint(self)
        # Using model_copy with update since frozen=True
        return self.model_copy(update={"stage_fingerprint": computed})
