"""
HighView Ingestion V2 — Epistemic Dependency Guard
Component: Architectural Integrity Firewall
Enforces the fundamental architectural rule:
"A later stage may consume outputs from earlier stages.
An earlier stage may NEVER depend on intelligence that belongs to a later stage."
"""

import ast
from pathlib import Path
from app.services.ingestion_v2.contracts.shadow import InternalStage

# Epistemic rank of internal stages (1-indexed, strictly monotonic)
STAGE_EPISTEMIC_RANK: dict[InternalStage, int] = {
    InternalStage.RAW_INGESTION: 1,
    InternalStage.ADAPTIVE_RECONSTRUCTION: 2,
    InternalStage.SANITIZATION_NORMALIZATION: 3,
    InternalStage.STRUCTURAL_PROFILING_EDA_A: 4,
    InternalStage.SEMANTIC_MODELING_GRAIN: 5,
    InternalStage.RELATIONSHIP_DISCOVERY: 6,
    InternalStage.RELATIONSHIP_VALIDATION_JOIN_PLAN: 7,
    InternalStage.ANALYTICAL_EDA_B: 8,
    InternalStage.CONTROLLED_ENRICHMENT: 9,
    InternalStage.SEMANTIC_GRAPH: 10,
    InternalStage.VECTORIZATION_INDEXING: 11,
    InternalStage.CONTEXT_RECONCILIATION_PREWARM: 12,
}

# Contract module mapping to epistemic stages
MODULE_TO_STAGE: dict[str, InternalStage] = {
    "raw": InternalStage.RAW_INGESTION,
    "reconstruction": InternalStage.ADAPTIVE_RECONSTRUCTION,
    "normalization": InternalStage.SANITIZATION_NORMALIZATION,
    "profiling": InternalStage.STRUCTURAL_PROFILING_EDA_A,
    "semantics": InternalStage.SEMANTIC_MODELING_GRAIN,
    "grain": InternalStage.SEMANTIC_MODELING_GRAIN,
    "relationships": InternalStage.RELATIONSHIP_DISCOVERY,
    "joins": InternalStage.RELATIONSHIP_VALIDATION_JOIN_PLAN,
    "analytics": InternalStage.ANALYTICAL_EDA_B,
    "enrichment": InternalStage.CONTROLLED_ENRICHMENT,
    "semantic_graph": InternalStage.SEMANTIC_GRAPH,
    "retrieval": InternalStage.VECTORIZATION_INDEXING,
}


class EpistemicIntegrityViolation(Exception):
    """Raised when an earlier stage attempts to depend on a later stage."""
    pass


def validate_stage_transition(
    target_stage: InternalStage,
    consumed_stages: list[InternalStage],
) -> bool:
    """
    Runtime validation that target_stage only consumes outputs from earlier stages.
    Raises EpistemicIntegrityViolation if an inverted dependency is detected.
    """
    target_rank = STAGE_EPISTEMIC_RANK[target_stage]
    for consumed in consumed_stages:
        consumed_rank = STAGE_EPISTEMIC_RANK[consumed]
        if consumed_rank >= target_rank:
            raise EpistemicIntegrityViolation(
                f"Epistemic violation: Stage '{target_stage.value}' (rank {target_rank}) "
                f"cannot consume output from subsequent or concurrent stage '{consumed.value}' (rank {consumed_rank})."
            )
    return True


def audit_contract_ast_dependencies(contracts_dir: Path | str) -> list[str]:
    """
    Scans the contracts directory with Python's AST parser to ensure zero backward
    or inverted dependencies exist across stage contracts.
    """
    path = Path(contracts_dir)
    violations: list[str] = []

    for file_path in path.glob("*.py"):
        module_name = file_path.stem
        if module_name in {"__init__", "base", "provenance", "intent", "shadow", "disagreement"}:
            continue

        caller_stage = MODULE_TO_STAGE.get(module_name)
        if not caller_stage:
            continue

        caller_rank = STAGE_EPISTEMIC_RANK[caller_stage]

        try:
            tree = ast.parse(file_path.read_text(encoding="utf-8"), filename=str(file_path))
        except Exception as e:
            violations.append(f"Failed to parse AST for {file_path}: {e}")
            continue

        for node in ast.walk(tree):
            imported_mod: str | None = None
            if isinstance(node, ast.ImportFrom):
                if node.module and "contracts." in node.module:
                    imported_mod = node.module.split("contracts.")[-1]
                elif node.module:
                    imported_mod = node.module
            elif isinstance(node, ast.Import):
                for alias in node.names:
                    if "contracts." in alias.name:
                        imported_mod = alias.name.split("contracts.")[-1]

            if imported_mod and imported_mod in MODULE_TO_STAGE:
                target_stage = MODULE_TO_STAGE[imported_mod]
                target_rank = STAGE_EPISTEMIC_RANK[target_stage]
                if target_rank > caller_rank:
                    violations.append(
                        f"Inverted AST import in {file_path.name}: "
                        f"{caller_stage.value} (rank {caller_rank}) imports from later stage {target_stage.value} (rank {target_rank}) via {imported_mod}"
                    )

    return violations


def audit_code_dependencies(code_str: str, caller_stage: InternalStage) -> list[str]:
    """
    Parses arbitrary Python code string belonging to caller_stage and verifies that
    it contains zero imports from later epistemic stages.
    """
    violations: list[str] = []
    caller_rank = STAGE_EPISTEMIC_RANK[caller_stage]

    try:
        tree = ast.parse(code_str)
    except Exception as e:
        return [f"AST Parse Error: {e}"]

    for node in ast.walk(tree):
        imported_candidates: list[str] = []
        if isinstance(node, ast.ImportFrom):
            if node.module:
                imported_candidates.append(node.module.split(".")[-1])
            for alias in node.names:
                imported_candidates.append(alias.name)
        elif isinstance(node, ast.Import):
            for alias in node.names:
                imported_candidates.append(alias.name.split(".")[-1])

        for mod_candidate in imported_candidates:
            if mod_candidate in MODULE_TO_STAGE:
                target_stage = MODULE_TO_STAGE[mod_candidate]
                target_rank = STAGE_EPISTEMIC_RANK[target_stage]
                if target_rank > caller_rank:
                    violations.append(
                        f"Epistemic violation: {caller_stage.value} (rank {caller_rank}) "
                        f"imports from later stage {target_stage.value} (rank {target_rank}) via {mod_candidate}"
                    )

    return violations
