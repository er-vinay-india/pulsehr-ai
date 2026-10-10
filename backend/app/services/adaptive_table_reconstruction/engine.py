"""AdaptiveTableReconstructionEngine:

Main orchestrator for model-assisted and deterministic document-to-table reconstruction.
Extracts clean logical tables from semi-structured spreadsheets/CSVs with multi-row headers,
preambles, wrapped physical rows, and footnote sentinels BEFORE dataframe creation
and semantic profiling.
Features governed model escalation (ModelEscalator) with strict deterministic post-validation.
"""

import io
import logging
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple, Union
import pandas as pd

from .confidence_risk_engine import ConfidenceRiskEngine
from .contracts import (
    DecisionStatus,
    HeaderTree,
    ModelEscalationTelemetry,
    ModelResolutionAudit,
    ReconstructionConfidence,
    ReconstructionProvenance,
    ReconstructionRiskLevel,
    RowRole,
    RowRoleDecision,
    SentinelDefinition,
    StructuralComplexityScore,
    TableReconstructionResult,
)
from .continuation_detector import (
    ContinuationDetector,
    LogicalRecordReconstructor,
)
from .grid_capture import GridCapture, RawGrid
from .header_tree_builder import HeaderTreeBuilder
from .model_escalator import ModelEscalator
from .row_role_classifier import RowRoleClassifier
from .sentinel_resolver import SentinelResolver
from .structural_validator import StructuralValidator

logger = logging.getLogger(__name__)


class AdaptiveTableReconstructionEngine:
    """Pre-semantic document-to-table reconstruction intelligence engine."""

    @classmethod
    def reconstruct(
        cls,
        path_or_buffer: Union[str, Path, io.BytesIO, io.StringIO],
        filename_hint: Optional[str] = None,
        sheet_name: Optional[str] = None,
        enable_model_escalation: bool = True,
    ) -> TableReconstructionResult:
        """Executes adaptive table reconstruction on an arbitrary tabular source."""
        # Stage 0: Raw 2D grid capture
        grid = GridCapture.capture_file(path_or_buffer, filename_hint=filename_hint, sheet_name=sheet_name)
        if grid.raw_row_count == 0:
            empty_df = pd.DataFrame()
            return TableReconstructionResult(
                raw_row_count=0,
                raw_col_count=0,
                reconstructed_row_count=0,
                reconstructed_col_count=0,
                complexity=StructuralComplexityScore(
                    score=0.0,
                    is_complex=False,
                    recommended_pipeline="FAST_DETERMINISTIC",
                ),
                telemetry=ModelEscalationTelemetry(),
                audits=[],
                status=DecisionStatus.VALIDATED,
                reconstructed_df=empty_df,
            )

        # Stage 1: Structural complexity evaluation
        complexity = RowRoleClassifier.evaluate_complexity(grid)

        # FAST DETERMINISTIC PATH: Clean standard CSV/Excel (single header, uniform data)
        if not complexity.is_complex and complexity.score < 0.25:
            return cls._fast_path_reconstruct(grid, complexity)

        # ADAPTIVE RECONSTRUCTION PATH (Score >= 0.25)
        logger.info(f"Escalating to AdaptiveTableReconstructionEngine (complexity: {complexity.score:.2f})")
        return cls._adaptive_path_reconstruct(grid, complexity, enable_model_escalation=enable_model_escalation)

    @classmethod
    def _fast_path_reconstruct(
        cls,
        grid: RawGrid,
        complexity: StructuralComplexityScore,
    ) -> TableReconstructionResult:
        """Fast microsecond path for clean tabular data."""
        raw_header = grid.get_row(0)
        active_cols = [c for c, val in enumerate(raw_header) if val.strip()]
        if not active_cols:
            active_cols = list(range(grid.raw_col_count))

        tree, prov_hdr = HeaderTreeBuilder.build_tree(grid, [0], active_col_indices=active_cols)

        data_rows = []
        for r in range(1, grid.raw_row_count):
            row_vals = [grid.get_cell(r, c) for c in active_cols]
            data_rows.append(row_vals)

        df = pd.DataFrame(data_rows, columns=tree.column_names)

        provenance = [prov_hdr]
        gates = StructuralValidator.validate_all(
            grid=grid,
            decisions=[RowRoleDecision(row_index=0, role=RowRole.HEADER, confidence=1.0)],
            header_tree=tree,
            reconstructed_rows=data_rows,
            sentinels=[],
            provenance=provenance,
            active_col_indices=active_cols,
        )

        return TableReconstructionResult(
            raw_row_count=grid.raw_row_count,
            raw_col_count=grid.raw_col_count,
            reconstructed_row_count=len(df),
            reconstructed_col_count=len(df.columns),
            complexity=complexity,
            header_tree=tree,
            sentinels=[],
            provenance=provenance,
            integrity_gates=gates,
            metadata_extracted={},
            telemetry=ModelEscalationTelemetry(),  # Zero model calls on fast path
            audits=[],
            confidence_vector=ReconstructionConfidence(
                structural_confidence=1.0,
                semantic_confidence=1.0,
                source_fidelity_confidence=1.0,
                composite_confidence=1.0,
            ),
            risk_level=ReconstructionRiskLevel.LOW,
            status=DecisionStatus.VALIDATED,
            reconstructed_df=df,
        )

    @classmethod
    def _adaptive_path_reconstruct(
        cls,
        grid: RawGrid,
        complexity: StructuralComplexityScore,
        enable_model_escalation: bool = True,
    ) -> TableReconstructionResult:
        """Full adaptive multi-stage reconstruction with governed model escalation."""
        all_provenance: List[ReconstructionProvenance] = []
        all_audits: List[ModelResolutionAudit] = []

        # Initialize ModelEscalator if escalation is enabled
        model_escalator = ModelEscalator() if enable_model_escalation else None

        # Stage 2: 12-feature row role classification
        decisions = RowRoleClassifier.classify_all_rows(grid)

        # Extract metadata from preamble rows
        extracted_metadata: Dict[str, Any] = {}
        preamble_rows = [d.row_index for d in decisions if d.role in (RowRole.DOCUMENT_METADATA, RowRole.TITLE)]
        for p_idx in preamble_rows:
            p_cells = [c.strip() for c in grid.get_row(p_idx) if c.strip()]
            if p_cells:
                if decisions[p_idx].role == RowRole.TITLE:
                    extracted_metadata.setdefault("titles", []).append(" ".join(p_cells))
                else:
                    extracted_metadata.setdefault("metadata_tokens", []).extend(p_cells)

        if preamble_rows:
            all_provenance.append(ReconstructionProvenance(
                provenance_id="ATR-PRM-0001",
                operation="PRUNE_PREAMBLE",
                source_rows=preamble_rows,
                after_state=extracted_metadata,
                confidence=0.98,
                method="DETERMINISTIC",
                status=DecisionStatus.VALIDATED,
                explanation=f"Isolated {len(preamble_rows)} preamble/title rows and extracted document metadata",
            ))

        # Identify header rows
        header_row_indices = [
            d.row_index for d in decisions
            if d.role in (RowRole.HEADER, RowRole.HEADER_CONTINUATION)
        ]

        # Determine active data columns
        data_row_indices = [d.row_index for d in decisions if d.role == RowRole.DATA]
        active_cols: List[int] = []
        for c in range(grid.raw_col_count):
            has_hdr = any(bool(grid.get_cell(r, c).strip()) for r in header_row_indices)
            has_data = any(bool(grid.get_cell(r, c).strip()) for r in data_row_indices[:50])
            if has_hdr or has_data:
                active_cols.append(c)

        if not active_cols:
            active_cols = list(range(grid.raw_col_count))

        # Stage 3: Hierarchical header resolution
        header_tree, prov_hdr = HeaderTreeBuilder.build_tree(
            grid,
            header_row_indices,
            active_col_indices=active_cols,
        )
        all_provenance.append(prov_hdr)

        # Stage 4: Wrapped record continuation detection & reconstruction (with Ambiguity Gate)
        continuations, cont_audits = ContinuationDetector.detect_continuations(
            grid,
            decisions,
            model_escalator=model_escalator,
            provisional_schema=header_tree.column_names,
            active_col_indices=active_cols,
        )
        all_audits.extend(cont_audits)

        reconstructed_data_rows, prov_records = LogicalRecordReconstructor.reconstruct_records(
            grid,
            decisions,
            continuations,
            active_col_indices=active_cols,
        )
        all_provenance.extend(prov_records)

        # Pruned page headers provenance
        page_header_rows = [d.row_index for d in decisions if d.role == RowRole.PAGE_HEADER]
        if page_header_rows:
            all_provenance.append(ReconstructionProvenance(
                provenance_id="ATR-PGE-0001",
                operation="PRUNE_REPEATED_PAGE_HEADERS",
                source_rows=page_header_rows,
                after_state={"pruned_count": len(page_header_rows)},
                confidence=1.0,
                method="DETERMINISTIC",
                status=DecisionStatus.VALIDATED,
                explanation=f"Removed {len(page_header_rows)} embedded repeated page header/watermark rows",
            ))

        # Stage 5: Footnote sentinel extraction (with model resolution for unstructured footnotes)
        sentinels, prov_sentinels, sent_audits = SentinelResolver.resolve_sentinels(
            grid,
            decisions,
            reconstructed_data_rows,
            header_tree.column_names,
            model_escalator=model_escalator,
        )
        all_provenance.extend(prov_sentinels)
        all_audits.extend(sent_audits)

        # Stage 6: Build final clean pandas DataFrame
        df = pd.DataFrame(
            reconstructed_data_rows,
            columns=header_tree.column_names,
        )

        # Stage 7: The 6 structural integrity gates
        gates = StructuralValidator.validate_all(
            grid=grid,
            decisions=decisions,
            header_tree=header_tree,
            reconstructed_rows=reconstructed_data_rows,
            sentinels=sentinels,
            provenance=all_provenance,
            active_col_indices=active_cols,
        )

        # Stage 8: 3D Confidence Scoring & Risk Engine Evaluation
        conf_vector, table_risk = ConfidenceRiskEngine.compute_confidence_vector(
            grid=grid,
            decisions=decisions,
            header_tree=header_tree,
            continuations=continuations,
            audits=all_audits,
            reconstructed_rows_count=len(df),
        )

        # Determine overall table resolution status
        final_status = DecisionStatus.DETERMINISTIC_VALIDATED
        if any(a.final_status == DecisionStatus.REVIEW_REQUIRED for a in all_audits):
            final_status = DecisionStatus.REVIEW_REQUIRED
        elif any(a.final_status == DecisionStatus.MODEL_ASSISTED_PROPOSED for a in all_audits):
            final_status = DecisionStatus.MODEL_ASSISTED_PROPOSED
        elif any(a.final_status == DecisionStatus.MODEL_ASSISTED_VALIDATED for a in all_audits):
            final_status = DecisionStatus.MODEL_ASSISTED_VALIDATED

        telemetry = model_escalator.telemetry if model_escalator is not None else ModelEscalationTelemetry()

        return TableReconstructionResult(
            raw_row_count=grid.raw_row_count,
            raw_col_count=grid.raw_col_count,
            reconstructed_row_count=len(df),
            reconstructed_col_count=len(df.columns),
            complexity=complexity,
            header_tree=header_tree,
            sentinels=sentinels,
            provenance=all_provenance,
            integrity_gates=gates,
            metadata_extracted=extracted_metadata,
            telemetry=telemetry,
            audits=all_audits,
            confidence_vector=conf_vector,
            risk_level=table_risk,
            status=final_status,
            reconstructed_df=df,
        )

    @classmethod
    def reconstruct_to_dataframe(
        cls,
        path_or_buffer: Union[str, Path, io.BytesIO, io.StringIO],
        filename_hint: Optional[str] = None,
        sheet_name: Optional[str] = None,
        enable_model_escalation: bool = True,
    ) -> Tuple[pd.DataFrame, TableReconstructionResult]:
        """Convenience method returning (reconstructed_df, result)."""
        result = cls.reconstruct(
            path_or_buffer,
            filename_hint=filename_hint,
            sheet_name=sheet_name,
            enable_model_escalation=enable_model_escalation,
        )
        df = result.reconstructed_df if result.reconstructed_df is not None else pd.DataFrame()
        return df, result
