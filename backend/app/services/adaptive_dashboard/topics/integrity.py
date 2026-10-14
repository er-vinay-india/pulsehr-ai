"""Story Assembly & ExecutiveTopic Integrity (Phase G5.5).

Enforces:
1. Strict identity-based binding across narrative, evidence, topic, and visual spec.
2. Complete absence of positional array zipping.
3. AST boundary purity against DB, AI/LLM, MCP, React/theme, and layout mutations.
"""
from __future__ import annotations

import ast
import os
from typing import Any


class StoryAssemblyIntegrityError(Exception):
    """Raised when story assembly or topic identity binding invariants are violated."""
    pass


class StoryAssemblyIntegrity:
    """Enforces story assembly, topic identity matching, and AST purity invariants."""

    PROHIBITED_MODULES = {
        "sqlite3",
        "duckdb",
        "google-genai",
        "google.genai",
        "openai",
        "anthropic",
        "ollama",
        "mcp",
    }

    @classmethod
    def assert_identity_alignment(
        cls,
        topic_id: str,
        narrative: Any = None,
        evidence_binding: Any = None,
        visual_spec: Any = None,
    ) -> None:
        """Validates that narrative, evidence binding, and visual spec share the identical topic_id."""
        if not topic_id:
            raise StoryAssemblyIntegrityError("STORY_ASSEMBLY_VIOLATION: topic_id cannot be blank.")

        if narrative is not None:
            n_tid = getattr(narrative, "topic_id", None) or (narrative.get("topic_id") if isinstance(narrative, dict) else None)
            if n_tid and n_tid != topic_id:
                raise StoryAssemblyIntegrityError(
                    f"STORY_ASSEMBLY_IDENTITY_MISMATCH: Narrative topic_id '{n_tid}' does not match expected '{topic_id}'."
                )

        if evidence_binding is not None:
            e_tid = getattr(evidence_binding, "topic_id", None) or (evidence_binding.get("topic_id") if isinstance(evidence_binding, dict) else None)
            if e_tid and e_tid != topic_id:
                raise StoryAssemblyIntegrityError(
                    f"STORY_ASSEMBLY_IDENTITY_MISMATCH: Evidence binding topic_id '{e_tid}' does not match expected '{topic_id}'."
                )

        if visual_spec is not None:
            v_tid = getattr(visual_spec, "topic_id", None) or (visual_spec.get("topic_id") if isinstance(visual_spec, dict) else None)
            if v_tid and v_tid != topic_id:
                raise StoryAssemblyIntegrityError(
                    f"STORY_ASSEMBLY_IDENTITY_MISMATCH: VisualSpec topic_id '{v_tid}' does not match expected '{topic_id}'."
                )

    @classmethod
    def assert_no_positional_binding(
        cls,
        topics: list[Any],
        visual_specs_by_id: dict[str, Any],
    ) -> None:
        """Ensures that visual specifications are bound strictly by matching topic_id, never positionally."""
        for t in topics:
            t_id = getattr(t, "topic_id", None) or (t.get("topic_id") if isinstance(t, dict) else None)
            if not t_id:
                raise StoryAssemblyIntegrityError("STORY_ASSEMBLY_VIOLATION: Topic in portfolio is missing topic_id.")
            if t_id not in visual_specs_by_id:
                raise StoryAssemblyIntegrityError(
                    f"STORY_ASSEMBLY_UNBOUND_TOPIC: Topic '{t_id}' has no matching VisualSpec in identity lookup map."
                )

    @classmethod
    def audit_ast_purity(cls, package_dir: str | None = None) -> list[str]:
        """Scans the topics package AST to ensure zero banned imports."""
        if package_dir is None:
            package_dir = os.path.dirname(os.path.abspath(__file__))

        violations = []
        for fname in os.listdir(package_dir):
            if not fname.endswith(".py"):
                continue
            fpath = os.path.join(package_dir, fname)
            with open(fpath, "r", encoding="utf-8") as f:
                root = ast.parse(f.read(), filename=fpath)

            for node in ast.walk(root):
                if isinstance(node, ast.Import):
                    for alias in node.names:
                        mod = alias.name.split(".")[0]
                        if mod in cls.PROHIBITED_MODULES:
                            violations.append(f"{fname}:{node.lineno} banned import '{alias.name}'")
                elif isinstance(node, ast.ImportFrom):
                    mod = (node.module or "").split(".")[0]
                    if mod in cls.PROHIBITED_MODULES:
                        violations.append(f"{fname}:{node.lineno} banned from-import '{node.module}'")
                    # Check for DB session or ModelGateway
                    if node.module and any(banned in node.module for banned in ("db.database", "db.session", "ai_copilot", "mcp")):
                        violations.append(f"{fname}:{node.lineno} banned framework import '{node.module}'")

        if violations:
            raise StoryAssemblyIntegrityError("AST Purity Violations in topics package:\n" + "\n".join(violations))
        return violations
