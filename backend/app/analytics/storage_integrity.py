"""
Storage Isolation & Security Integrity Guard for Phase G3 Parquet Storage.
Prevents directory traversal, cross-dataset access, and external file queries.
"""
from __future__ import annotations

import os
from pathlib import Path
import re
from app.core.config import settings


class AnalyticalStorageIsolationIntegrity:
    """Fail-closed validator for Parquet storage isolation and path safety."""

    @classmethod
    def get_storage_base(cls) -> Path:
        base = settings.PARQUET_STORAGE_DIR.resolve()
        base.mkdir(parents=True, exist_ok=True)
        return base

    @classmethod
    def build_canonical_path(
        cls,
        dataset_id: int,
        dataset_version: int,
        logical_table_id: str,
    ) -> Path:
        """Constructs a deterministic, strictly validated canonical path."""
        if not isinstance(dataset_id, int) or dataset_id <= 0:
            raise ValueError(f"Invalid dataset_id for storage: {dataset_id}")
        if not isinstance(dataset_version, int) or dataset_version <= 0:
            raise ValueError(f"Invalid dataset_version: {dataset_version}")

        # Sanitize logical table identifier: only alphanumeric and underscores
        clean_table = re.sub(r"[^\w\-]", "_", str(logical_table_id)).strip("_")
        if not clean_table:
            clean_table = "table"

        base = cls.get_storage_base()
        target_dir = (base / str(dataset_id) / f"v{dataset_version}").resolve()
        target_path = (target_dir / f"{clean_table}.parquet").resolve()

        cls.validate_path(target_path, dataset_id=dataset_id, dataset_version=dataset_version)
        return target_path

    @classmethod
    def validate_path(
        cls,
        path: Path | str,
        dataset_id: int | None = None,
        dataset_version: int | None = None,
    ) -> Path:
        """Validates that a path is strictly inside PARQUET_STORAGE_DIR and matches dataset boundaries."""
        base = cls.get_storage_base()
        resolved = Path(path).resolve()

        # Enforce boundary: must be within PARQUET_STORAGE_DIR
        try:
            rel = resolved.relative_to(base)
        except ValueError as exc:
            raise PermissionError(
                f"Path Traversal Violation: {resolved} is outside Parquet root {base}"
            ) from exc

        # Check for traversal markers in original path string
        raw_str = str(path)
        if ".." in raw_str or "\x00" in raw_str:
            raise PermissionError(f"Directory traversal marker detected in path: {raw_str}")

        # If dataset_id provided, ensure path segments match
        parts = rel.parts
        if dataset_id is not None:
            if not parts or parts[0] != str(dataset_id):
                raise PermissionError(
                    f"Dataset Isolation Violation: Requested dataset {dataset_id} does not match path {resolved}"
                )

        if dataset_version is not None:
            if len(parts) < 2 or parts[1] != f"v{dataset_version}":
                raise PermissionError(
                    f"Version Isolation Violation: Requested v{dataset_version} does not match path {resolved}"
                )

        return resolved

    @classmethod
    def validate_metadata_alignment(
        cls,
        requested_dataset_id: int,
        requested_dataset_version: int,
        stored_metadata_dataset_id: int,
        stored_metadata_version: int,
        parquet_path: str,
    ) -> None:
        """Verifies that requested IDs match the stored metadata and file location."""
        if requested_dataset_id != stored_metadata_dataset_id:
            raise PermissionError(
                f"Dataset Mismatch: Request dataset {requested_dataset_id} != stored {stored_metadata_dataset_id}"
            )
        if requested_dataset_version != stored_metadata_version:
            raise PermissionError(
                f"Version Mismatch: Request version {requested_dataset_version} != stored {stored_metadata_version}"
            )
        cls.validate_path(parquet_path, dataset_id=requested_dataset_id, dataset_version=requested_dataset_version)
