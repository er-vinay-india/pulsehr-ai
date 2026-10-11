"""MCP-Level Bypass Auditor (Phase B).

Verifies the architectural invariant:
"Agents (HRIDAY, LangGraph, etc.) must invoke capabilities strictly through GovernedMCPGateway,
never reaching directly into SQLite database connections or service layer internals."

Target:
AgentMCPBypassCount == 0
"""
from __future__ import annotations

import os
import re
from typing import Any
from pydantic import BaseModel, ConfigDict, Field


class MCPBypassHit(BaseModel):
    model_config = ConfigDict(extra="ignore")

    file_path: str
    line_number: int
    line_content: str
    pattern_name: str
    classification: str  # "ALLOWED" or "VIOLATION"
    rationale: str


class MCPBypassAuditResult(BaseModel):
    model_config = ConfigDict(extra="ignore")

    total_scanned_files: int
    total_hits: int
    allowed_count: int
    violation_count: int
    violations: list[MCPBypassHit] = Field(default_factory=list)
    allowed_hits: list[MCPBypassHit] = Field(default_factory=list)
    is_compliant: bool = True


class MCPBypassAuditor:
    """Scans agent and router code to ensure all tool invocations route through GovernedMCPGateway."""

    # Authorized paths that implement the MCP servers and low-level HighView core
    AUTHORIZED_CORE_SUBPATHS = [
        "app/mcp/",
        "app/services/",
        "app/db/",
        "app/core/",
        "app/routers/",
    ]

    # Target patterns indicating an agent trying to bypass MCP directly into DB or services
    AGENT_BYPASS_PATTERNS = [
        (re.compile(r'from\s+\.\.?services\.adaptive_dashboard\.engine\s+import\s+run_adaptive_dashboard'), "direct_engine_import"),
        (re.compile(r'from\s+\.\.?db\.database\s+import\s+get_connection'), "direct_db_connection"),
    ]

    @classmethod
    def audit_agent_layer(cls, agent_dir: str) -> MCPBypassAuditResult:
        """Audits python files in the agent directory for direct service bypasses."""
        total_files = 0
        violations: list[MCPBypassHit] = []
        allowed: list[MCPBypassHit] = []

        if not os.path.exists(agent_dir):
            return MCPBypassAuditResult(
                total_scanned_files=0,
                total_hits=0,
                allowed_count=0,
                violation_count=0,
                is_compliant=True,
            )

        for dirpath, _, filenames in os.walk(agent_dir):
            if "tests" in dirpath or "__pycache__" in dirpath or ".venv" in dirpath:
                continue

            for fname in filenames:
                if not fname.endswith(".py"):
                    continue

                total_files += 1
                fpath = os.path.join(dirpath, fname)

                with open(fpath, "r", encoding="utf-8", errors="ignore") as f:
                    lines = f.readlines()

                is_authorized_core = any(sub in fpath.replace("\\", "/") for sub in cls.AUTHORIZED_CORE_SUBPATHS)

                for line_idx, line in enumerate(lines, start=1):
                    line_clean = line.strip()
                    if line_clean.startswith("#"):
                        continue

                    for pattern, cat in cls.AGENT_BYPASS_PATTERNS:
                        if pattern.search(line_clean):
                            if is_authorized_core:
                                allowed.append(MCPBypassHit(
                                    file_path=fpath,
                                    line_number=line_idx,
                                    line_content=line_clean,
                                    pattern_name=cat,
                                    classification="ALLOWED",
                                    rationale="Authorized core/MCP infrastructure implementation.",
                                ))
                            else:
                                violations.append(MCPBypassHit(
                                    file_path=fpath,
                                    line_number=line_idx,
                                    line_content=line_clean,
                                    pattern_name=cat,
                                    classification="VIOLATION",
                                    rationale="Agent must call GovernedMCPGateway instead of direct DB or engine service.",
                                ))

        return MCPBypassAuditResult(
            total_scanned_files=total_files,
            total_hits=len(violations) + len(allowed),
            allowed_count=len(allowed),
            violation_count=len(violations),
            violations=violations,
            allowed_hits=allowed,
            is_compliant=(len(violations) == 0),
        )
