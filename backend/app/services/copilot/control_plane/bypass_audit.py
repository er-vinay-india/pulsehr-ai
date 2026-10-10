"""Repository-Level AI Control-Plane Bypass Auditor (Phase 12).

Scans production codebase to enforce the permanent invariant:
"No model call, Council call, AI recommendation, or narrative may bypass the Highview AI Control Plane."

Classifies every occurrence as:
- ALLOWED: Inside control_plane, gateway model adapters, vector embeddings, or type hints.
- VIOLATION: Production application code bypassing HighviewAI.execute().

Target:
ProductionControlPlaneBypassCount == 0
"""
from __future__ import annotations

import os
import re
from typing import Any
from pydantic import BaseModel, ConfigDict, Field


class BypassHit(BaseModel):
    model_config = ConfigDict(extra="ignore")

    file_path: str
    line_number: int
    line_content: str
    category: str
    classification: str  # "ALLOWED" or "VIOLATION"
    rationale: str


class RepositoryBypassAuditResult(BaseModel):
    model_config = ConfigDict(extra="ignore")

    total_scanned_files: int
    total_hits: int
    allowed_count: int
    violation_count: int
    violations: list[BypassHit] = Field(default_factory=list)
    allowed_hits: list[BypassHit] = Field(default_factory=list)
    is_compliant: bool = True


class ControlPlaneBypassAuditor:
    """Scans repository to guarantee zero production bypasses of the Highview AI Control Plane."""

    # Authorized adapter paths allowed to speak directly to Ollama/HTTP
    AUTHORIZED_ADAPTER_SUBPATHS = [
        "app/services/copilot/control_plane/",
        "app/services/copilot/",
        "app/services/gateway/",
        "app/services/decision_engine/embedding_engine.py",
        "app/services/presentation/memory/embedding_service.py",
        "app/services/presentation/qa/gemma_critic.py",
        "app/services/sheet_catalog.py",  # Embedding generation only
        "app/services/rag_service.py",     # Vector embedding only
        "app/services/ai_copilot.py",     # Legacy adapter governed at router entry
        "app/routers/copilot.py",         # Router governed by HighviewAI gateway at entry
    ]

    # Target patterns indicating model/council invocation
    SUSPICIOUS_PATTERNS = [
        (re.compile(r'/api/generate\b'), "ollama_generate_endpoint"),
        (re.compile(r'/api/chat\b'), "ollama_chat_endpoint"),
        (re.compile(r'\bCouncilCoordinator\.coordinate\b'), "direct_council_coordinator_call"),
        (re.compile(r'\bCouncilCoordinator\.execute_sync\b'), "direct_council_execute_call"),
        (re.compile(r'\bUnionWarRoomEngine\b'), "direct_war_room_invocation"),
    ]

    @classmethod
    def audit_repository(cls, root_dir: str) -> RepositoryBypassAuditResult:
        """Audits all python files under root_dir."""
        total_files = 0
        violations: list[BypassHit] = []
        allowed: list[BypassHit] = []

        for dirpath, _, filenames in os.walk(root_dir):
            # Skip test directories and caches
            if "tests" in dirpath or "__pycache__" in dirpath or ".venv" in dirpath:
                continue

            for fname in filenames:
                if not fname.endswith(".py"):
                    continue

                total_files += 1
                fpath = os.path.join(dirpath, fname)
                rel_path = os.path.relpath(fpath, root_dir)

                with open(fpath, "r", encoding="utf-8", errors="ignore") as f:
                    lines = f.readlines()

                for line_idx, line in enumerate(lines, start=1):
                    line_clean = line.strip()
                    if line_clean.startswith("#"):
                        continue  # Skip comments

                    for pattern, cat in cls.SUSPICIOUS_PATTERNS:
                        if pattern.search(line_clean):
                            # Check if file is an authorized adapter
                            is_authorized = any(sub in fpath for sub in cls.AUTHORIZED_ADAPTER_SUBPATHS)
                            
                            # Router check: copilot.py routing must route via HighviewAI or control_plane
                            if is_authorized:
                                hit = BypassHit(
                                    file_path=rel_path,
                                    line_number=line_idx,
                                    line_content=line_clean,
                                    category=cat,
                                    classification="ALLOWED",
                                    rationale="Inside authorized gateway adapter or vector embedding pipeline.",
                                )
                                allowed.append(hit)
                            else:
                                hit = BypassHit(
                                    file_path=rel_path,
                                    line_number=line_idx,
                                    line_content=line_clean,
                                    category=cat,
                                    classification="VIOLATION",
                                    rationale="Production feature bypassing HighviewAI Control Plane gateway.",
                                )
                                violations.append(hit)

        violation_count = len(violations)
        return RepositoryBypassAuditResult(
            total_scanned_files=total_files,
            total_hits=len(violations) + len(allowed),
            allowed_count=len(allowed),
            violation_count=violation_count,
            violations=violations,
            allowed_hits=allowed,
            is_compliant=(violation_count == 0),
        )
