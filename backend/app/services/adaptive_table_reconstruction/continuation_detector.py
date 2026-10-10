"""ContinuationDetector & LogicalRecordReconstructor:

Identifies wrapped physical rows and merges split text fragments into complete logical records.
Features an Ambiguity Gate that escalates uncertain cases (< 0.70 confidence or conflicting targets)
to ModelEscalator with deterministic post-validation.
Emits atomic ReconstructionProvenance audits for every merge operation.
"""

import re
from typing import Any, Dict, List, Optional, Set, Tuple

from .contracts import (
    AmbiguityCase,
    AmbiguityType,
    ContinuationDecision,
    ContinuationType,
    DecisionStatus,
    ModelResolutionAudit,
    ReconstructionProvenance,
    RowRole,
    RowRoleDecision,
)
from .grid_capture import RawGrid


def should_merge_without_space(prefix: str, fragment: str) -> bool:
    """Detects whether two strings represent a split word (no space) or separated words (space)."""
    p = prefix.strip()
    f = fragment.strip()
    if not p or not f:
        return True
    if p.endswith(('-', '/')):
        return True
    if ' ' in f or ' ' in p:
        last_word_p = p.split()[-1]
        first_word_f = f.split()[0]
        if not re.match(r'^[a-z]+$', first_word_f) or first_word_f in ('and', 'or', 'of', 'in', 'to', 'with'):
            return False
        if last_word_p[0].isupper() and first_word_f.islower() and len(first_word_f) <= 10:
            return True
        return False
    if p[0].isupper() and f.islower() and not f.startswith(('and', 'or', 'of')):
        return True
    return False


class ContinuationDetector:
    """Detects continuation relationships between sparse fragment rows and data records."""

    @classmethod
    def detect_continuations(
        cls,
        grid: RawGrid,
        decisions: List[RowRoleDecision],
        model_escalator: Optional[Any] = None,
        provisional_schema: Optional[List[str]] = None,
        active_col_indices: Optional[List[int]] = None,
    ) -> Tuple[List[ContinuationDecision], List[ModelResolutionAudit]]:
        """Scans grid for DATA_CONTINUATION rows with confidence gating and model escalation."""
        total_rows = len(decisions)
        continuation_decisions: List[ContinuationDecision] = []
        audits: List[ModelResolutionAudit] = []

        for idx, dec in enumerate(decisions):
            if dec.role != RowRole.DATA_CONTINUATION:
                continue

            row = grid.get_row(idx)
            non_empty_cols = [c for c, val in enumerate(row) if val.strip()]
            frag_val = " ".join([grid.get_cell(idx, c).strip() for c in non_empty_cols])

            # Case 1: Next data row candidate
            next_target_idx = -1
            for n_idx in range(idx + 1, min(total_rows, idx + 4)):
                if decisions[n_idx].role == RowRole.DATA:
                    next_target_idx = n_idx
                    break
                elif decisions[n_idx].role not in (RowRole.BLANK_SEPARATOR, RowRole.PAGE_HEADER):
                    break

            # Case 2: Previous data row candidate
            prev_target_idx = -1
            for p_idx in range(idx - 1, max(-1, idx - 4), -1):
                if decisions[p_idx].role == RowRole.DATA:
                    prev_target_idx = p_idx
                    break
                elif decisions[p_idx].role not in (RowRole.BLANK_SEPARATOR, RowRole.PAGE_HEADER):
                    break

            chosen_type = ContinuationType.PREFIX_OF_NEXT_ROW
            target_idx = next_target_idx
            confidence = 0.50
            is_model_assisted = False
            requires_review = False

            if next_target_idx != -1 and prev_target_idx != -1:
                # Linguistic continuation checks
                next_val = " ".join([grid.get_cell(next_target_idx, c).strip() for c in non_empty_cols])
                prev_val = " ".join([grid.get_cell(prev_target_idx, c).strip() for c in non_empty_cols])

                # Check strong prefix signal on next row (e.g. starts with lowercase or conjunction)
                next_starts_lower_or_conj = bool(
                    re.match(r'^[a-z]+', next_val) or next_val.startswith(('and ', 'or ', '&'))
                )
                # Check strong suffix signal on previous row (e.g. ends with unclosed word/preposition)
                prev_ends_incomplete = bool(
                    prev_val.endswith(('-', '/')) or
                    any(prev_val.lower().endswith(w) for w in (' annual', ' the', ' for', ' of', ' with', ' in', ' to'))
                )

                if next_starts_lower_or_conj and not prev_ends_incomplete:
                    target_idx = next_target_idx
                    chosen_type = ContinuationType.PREFIX_OF_NEXT_ROW
                    confidence = 0.98
                elif prev_ends_incomplete and not next_starts_lower_or_conj:
                    target_idx = prev_target_idx
                    chosen_type = ContinuationType.SUFFIX_OF_PREVIOUS_ROW
                    confidence = 0.95
                else:
                    # AMBIGUOUS: Conflicting or unclear target! Deterministic confidence drops
                    confidence = 0.50

            elif next_target_idx != -1:
                target_idx = next_target_idx
                chosen_type = ContinuationType.PREFIX_OF_NEXT_ROW
                confidence = 0.85
            elif prev_target_idx != -1:
                target_idx = prev_target_idx
                chosen_type = ContinuationType.SUFFIX_OF_PREVIOUS_ROW
                confidence = 0.85
            else:
                continue

            # AMBIGUITY GATE: If confidence < 0.70, invoke ModelEscalator
            if confidence < 0.70 and model_escalator is not None:
                case = AmbiguityCase(
                    case_id=f"AMB-REC-{idx:04d}",
                    ambiguity_type=AmbiguityType.ROW_CONTINUATION,
                    current_row_index=idx,
                    current_row=row,
                    previous_rows=[grid.get_row(r) for r in range(max(0, idx - 2), idx)],
                    next_rows=[grid.get_row(r) for r in range(idx + 1, min(total_rows, idx + 3))],
                    provisional_schema=provisional_schema or [],
                    deterministic_candidates=["PREFIX_OF_NEXT_ROW", "SUFFIX_OF_PREVIOUS_ROW", "INDEPENDENT"],
                    deterministic_confidence=confidence,
                )
                model_dec, audit = model_escalator.resolve_continuation(case, active_col_indices or [])
                audits.append(audit)

                if audit.final_status == DecisionStatus.MODEL_ASSISTED_VALIDATED:
                    chosen_type = model_dec.relationship
                    target_idx = (
                        next_target_idx if chosen_type == ContinuationType.PREFIX_OF_NEXT_ROW else prev_target_idx
                    )
                    confidence = model_dec.confidence
                    is_model_assisted = True
                elif audit.final_status == DecisionStatus.MODEL_ASSISTED_PROPOSED:
                    # Model proposed merge, but semantic risk gate held it as PROPOSED -> do not destructively merge!
                    # Preserved in audit/provenance for human review while row remains unmerged
                    continue
                elif audit.final_status == DecisionStatus.REJECTED:
                    # Model proposal rejected by deterministic post-validation -> do not merge!
                    continue
                else:
                    # REVIEW_REQUIRED: uncertain -> do not merge!
                    requires_review = True
                    continue

            # Determine merge strategy
            target_row = grid.get_row(target_idx)
            no_space_votes = 0
            for col in non_empty_cols:
                frag_c = grid.get_cell(idx, col)
                target_c = grid.get_cell(target_idx, col)
                if chosen_type == ContinuationType.PREFIX_OF_NEXT_ROW:
                    if should_merge_without_space(frag_c, target_c):
                        no_space_votes += 1
                else:
                    if should_merge_without_space(target_c, frag_c):
                        no_space_votes += 1

            merge_strategy = "concat_no_space" if no_space_votes > 0 else "concat_with_space"

            continuation_decisions.append(ContinuationDecision(
                continuation_row_index=idx,
                target_row_index=target_idx,
                continuation_type=chosen_type,
                affected_col_indices=non_empty_cols,
                merge_strategy=merge_strategy,
                confidence=confidence,
                reason=f"Row {idx} fragments merged into target record {target_idx} ({'model-assisted' if is_model_assisted else 'deterministic'})",
                requires_review=requires_review,
            ))

        return continuation_decisions, audits


class LogicalRecordReconstructor:
    """Merges continuation rows into logical records, producing clean rectangular data rows."""

    @classmethod
    def reconstruct_records(
        cls,
        grid: RawGrid,
        decisions: List[RowRoleDecision],
        continuations: List[ContinuationDecision],
        active_col_indices: List[int],
    ) -> Tuple[List[List[str]], List[ReconstructionProvenance]]:
        """Produces merged logical data rows and provenance records."""
        prefix_map: Dict[int, List[ContinuationDecision]] = {}
        suffix_map: Dict[int, List[ContinuationDecision]] = {}

        for c_dec in continuations:
            if c_dec.continuation_type == ContinuationType.PREFIX_OF_NEXT_ROW:
                prefix_map.setdefault(c_dec.target_row_index, []).append(c_dec)
            elif c_dec.continuation_type == ContinuationType.SUFFIX_OF_PREVIOUS_ROW:
                suffix_map.setdefault(c_dec.target_row_index, []).append(c_dec)

        reconstructed_rows: List[List[str]] = []
        provenance_list: List[ReconstructionProvenance] = []
        counter = 1

        for idx, dec in enumerate(decisions):
            if dec.role != RowRole.DATA:
                continue

            base_row = [grid.get_cell(idx, c) for c in active_col_indices]
            original_state = list(base_row)
            merged_row = list(base_row)
            source_rows = [idx]
            min_confidence = 1.0
            is_model_assisted = False

            # Apply prefixes
            if idx in prefix_map:
                for c_dec in prefix_map[idx]:
                    source_rows.append(c_dec.continuation_row_index)
                    min_confidence = min(min_confidence, c_dec.confidence)
                    if "model-assisted" in c_dec.reason:
                        is_model_assisted = True
                    for col_idx in c_dec.affected_col_indices:
                        if col_idx in active_col_indices:
                            pos = active_col_indices.index(col_idx)
                            prefix_val = grid.get_cell(c_dec.continuation_row_index, col_idx).strip()
                            target_val = merged_row[pos].strip()
                            if prefix_val and target_val:
                                if c_dec.merge_strategy == "concat_no_space" or should_merge_without_space(prefix_val, target_val):
                                    merged_row[pos] = f"{prefix_val}{target_val}"
                                else:
                                    merged_row[pos] = f"{prefix_val} {target_val}"
                            elif prefix_val:
                                merged_row[pos] = prefix_val

            # Apply suffixes
            if idx in suffix_map:
                for c_dec in suffix_map[idx]:
                    source_rows.append(c_dec.continuation_row_index)
                    min_confidence = min(min_confidence, c_dec.confidence)
                    if "model-assisted" in c_dec.reason:
                        is_model_assisted = True
                    for col_idx in c_dec.affected_col_indices:
                        if col_idx in active_col_indices:
                            pos = active_col_indices.index(col_idx)
                            suffix_val = grid.get_cell(c_dec.continuation_row_index, col_idx).strip()
                            target_val = merged_row[pos].strip()
                            if suffix_val and target_val:
                                if c_dec.merge_strategy == "concat_no_space" or should_merge_without_space(target_val, suffix_val):
                                    merged_row[pos] = f"{target_val}{suffix_val}"
                                else:
                                    merged_row[pos] = f"{target_val} {suffix_val}"
                            elif suffix_val:
                                merged_row[pos] = suffix_val

            reconstructed_rows.append(merged_row)

            # Record provenance if any merge occurred
            if len(source_rows) > 1:
                prov_id = f"ATR-MDL-{counter:04d}" if is_model_assisted else f"ATR-REC-{counter:04d}"
                provenance_list.append(ReconstructionProvenance(
                    provenance_id=prov_id,
                    operation="MERGE_WRAPPED_RECORD",
                    source_rows=sorted(source_rows),
                    target_row=idx,
                    affected_columns=active_col_indices,
                    before_state=original_state,
                    after_state=merged_row,
                    confidence=min_confidence,
                    method="MODEL_ASSISTED" if is_model_assisted else "DETERMINISTIC",
                    status=DecisionStatus.MODEL_ASSISTED_VALIDATED if is_model_assisted else DecisionStatus.VALIDATED,
                    explanation=f"Reconstructed logical record by merging physical rows {sorted(source_rows)} ({'model-assisted' if is_model_assisted else 'deterministic'})",
                ))
                counter += 1

        return reconstructed_rows, provenance_list
