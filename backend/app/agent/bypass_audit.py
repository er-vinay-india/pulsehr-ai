"""LangGraph-Level Bypass Auditor (Phase C).

Enforces the core architectural boundary:
"LangGraph nodes and workflows MUST call capabilities strictly through GovernedMCPGateway
and AI inference strictly through ModelGateway. They must never directly import raw SQLite
connections, low-level ranking engines, or raw Ollama endpoints."

Target:
LangGraphBypassCount == 0
"""
from __future__ import annotations

import os
import re
from typing import Any
from pydantic import BaseModel, ConfigDict, Field


class LangGraphBypassHit(BaseModel):
    model_config = ConfigDict(extra="ignore")

    file_path: str
    line_number: int
    line_content: str
    violation_type: str
    rationale: str


class LangGraphBypassAuditResult(BaseModel):
    model_config = ConfigDict(extra="ignore")

    total_scanned_files: int
    violation_count: int
    violations: list[LangGraphBypassHit] = Field(default_factory=list)
    is_compliant: bool = True


class LangGraphBypassAuditor:
    """Audits the agent orchestration layer to ensure zero direct engine/database bypasses."""

    PROHIBITED_IMPORT_PATTERNS = [
        (re.compile(r'from\s+\.\.?\.?db\.database\s+import\s+get_connection'), "direct_database_import"),
        (re.compile(r'import\s+sqlite3\b'), "direct_sqlite3_import"),
        (re.compile(r'from\s+\.\.?\.?services\.adaptive_dashboard\.engine\s+import\s+run_adaptive_dashboard'), "direct_engine_import"),
        (re.compile(r'from\s+\.\.?\.?services\.adaptive_dashboard\.evidence_graph\s+import'), "direct_evidence_graph_import"),
        (re.compile(r'from\s+\.\.?\.?services\.adaptive_dashboard\.scenario_engine\s+import'), "direct_scenario_engine_import"),
        (re.compile(r'/' + r'api/chat\b'), "direct_ollama_endpoint"),
        (re.compile(r'/' + r'api/generate\b'), "direct_ollama_endpoint"),
    ]

    @classmethod
    def audit_agent_directory(cls, agent_root: str) -> LangGraphBypassAuditResult:
        """Scans all python files in the agent directory for prohibited direct imports."""
        total_files = 0
        violations: list[LangGraphBypassHit] = []

        if not os.path.exists(agent_root):
            return LangGraphBypassAuditResult(
                total_scanned_files=0,
                violation_count=0,
                is_compliant=True,
            )

        for dirpath, _, filenames in os.walk(agent_root):
            if "tests" in dirpath or "__pycache__" in dirpath or ".venv" in dirpath:
                continue

            for fname in filenames:
                if not fname.endswith(".py"):
                    continue
                # Skip the auditor file itself
                if fname == "bypass_audit.py":
                    continue

                total_files += 1
                fpath = os.path.join(dirpath, fname)

                with open(fpath, "r", encoding="utf-8", errors="ignore") as f:
                    lines = f.readlines()

                for line_idx, line in enumerate(lines, start=1):
                    line_clean = line.strip()
                    if line_clean.startswith("#"):
                        continue

                    for pattern, vtype in cls.PROHIBITED_IMPORT_PATTERNS:
                        if pattern.search(line_clean):
                            violations.append(LangGraphBypassHit(
                                file_path=fpath,
                                line_number=line_idx,
                                line_content=line_clean,
                                violation_type=vtype,
                                rationale="LangGraph nodes must call GovernedMCPGateway, never internal DB/engines directly.",
                            ))

        return LangGraphBypassAuditResult(
            total_scanned_files=total_files,
            violation_count=len(violations),
            violations=violations,
            is_compliant=(len(violations) == 0),
        )
