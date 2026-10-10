"""SentinelResolver: Footnote sentinel extraction and missing-state preservation.

Identifies explicit domain sentinels (e.g. '-' : No data, 'NM'-Not monitored) from footnotes
and ensures they remain distinct, uncoerced missing-data states rather than being flattened to 0.
Supports ModelEscalator for unstructured narrative footnotes (e.g. 'Note: NR indicates not recorded').
"""

import re
from typing import Any, Dict, List, Optional, Set, Tuple

from .contracts import (
    CanonicalMissingState,
    DecisionStatus,
    ModelResolutionAudit,
    ReconstructionProvenance,
    RowRole,
    RowRoleDecision,
    SentinelDefinition,
)
from .grid_capture import RawGrid


def map_canonical_missing_state(meaning: str, token: str) -> CanonicalMissingState:
    """Strictly maps missing token meaning to one of the 8 canonical missing states.
    
    Enforces that 'not evaluated' is never widened to 'not reported' or 'not monitored'.
    """
    text = (meaning or "").strip().lower()
    tok = (token or "").strip().lower()

    if "not evaluated" in text or "were not evaluated" in text or "unevaluated" in text:
        return CanonicalMissingState.NOT_EVALUATED
    if "not monitored" in text or "were not monitored" in text or "unmonitored" in text:
        return CanonicalMissingState.NOT_MONITORED
    if "not reported" in text or "not recorded" in text or "unreported" in text:
        return CanonicalMissingState.NOT_REPORTED
    if "not applicable" in text or tok == "n/a":
        return CanonicalMissingState.NOT_APPLICABLE
    if "insufficient" in text or "inadequate" in text:
        return CanonicalMissingState.INSUFFICIENT_DATA
    if "not available" in text or "unavailable" in text:
        return CanonicalMissingState.NOT_AVAILABLE
    if "no data" in text or "missing" in text or tok in ("-", "--", "*"):
        return CanonicalMissingState.MISSING
    return CanonicalMissingState.UNKNOWN_MISSING_STATE


SENTINEL_TOKEN_PATTERNS = [
    # E.g. "-" : No data / Inadequate data or 'N/A' : Not applicable
    re.compile(r'^\s*["\']?([A-Za-z0-9_\*\-\#\/]+)["\']?\s*[:=]\s*(.+)$', re.IGNORECASE),
    # E.g. NM-Not monitored
    re.compile(r'^\s*([A-Za-z0-9_\*#\/]+)\s*-\s*([A-Za-z].+)$', re.IGNORECASE),
    # E.g. "-" - No data
    re.compile(r'^\s*["\']([^"\']+)["\']\s*-\s*(.+)$', re.IGNORECASE),
]


class SentinelResolver:
    """Discovers footnote sentinel definitions and cross-references data occurrences."""

    @classmethod
    def resolve_sentinels(
        cls,
        grid: RawGrid,
        decisions: List[RowRoleDecision],
        reconstructed_rows: List[List[str]],
        column_names: List[str],
        model_escalator: Optional[Any] = None,
    ) -> Tuple[List[SentinelDefinition], List[ReconstructionProvenance], List[ModelResolutionAudit]]:
        """Extracts sentinel definitions from footnote rows and checks presence in data."""
        sentinels: List[SentinelDefinition] = []
        provenance_list: List[ReconstructionProvenance] = []
        audits: List[ModelResolutionAudit] = []
        seen_tokens: Set[str] = set()

        # Find rows classified as SENTINEL_DEFINITION or FOOTNOTE
        for dec in decisions:
            if dec.role not in (RowRole.SENTINEL_DEFINITION, RowRole.FOOTNOTE):
                continue

            row = grid.get_row(dec.row_index)
            non_empty = [c.strip() for c in row if c.strip()]
            for text in non_empty:
                token = ""
                meaning = ""
                is_model_assisted = False

                # Strip leading preamble prefixes like "Footnote:", "Note:", "Legend:"
                clean_text = re.sub(r'^(?:footnote|notes?|source|legend)\s*[:\-]\s*', '', text, flags=re.IGNORECASE).strip()

                for pattern in SENTINEL_TOKEN_PATTERNS:
                    m = pattern.match(clean_text) or pattern.match(text)
                    if m:
                        cand_token = m.group(1).strip().strip('"\'')
                        cand_meaning = m.group(2).strip().strip('"\'')
                        if cand_token.lower() not in ("footnote", "note", "notes", "source", "legend", "table", "report"):
                            token = cand_token
                            meaning = cand_meaning
                            break

                # If deterministic regex failed to extract token, but narrative text exists and model_escalator is present:
                if (not token or not meaning) and model_escalator is not None:
                    # Check for short alphanumeric tokens (e.g. 'NR', 'NA', '*', 'N/A') in the text
                    candidate_tokens = re.findall(r'\b([A-Z]{1,4}|[\*\#])\b', text)
                    # Filter to tokens that actually appear in reconstructed data
                    active_candidates = []
                    for cand in candidate_tokens:
                        if any(cand in row_vals for row_vals in reconstructed_rows[:100]):
                            active_candidates.append(cand)

                    for cand in active_candidates:
                        if cand not in seen_tokens:
                            data_sample = [v for r in reconstructed_rows for v in r if v.strip() == cand][:5]
                            m_dec, audit = model_escalator.resolve_sentinel(cand, text, data_sample)
                            audits.append(audit)
                            if m_dec and m_dec.is_missing_indicator:
                                token = m_dec.token
                                meaning = m_dec.meaning
                                is_model_assisted = True
                                break

                if token and meaning and token not in seen_tokens:
                    seen_tokens.add(token)
                    occurrences: Dict[str, int] = {}
                    for row_vals in reconstructed_rows:
                        for col_idx, val in enumerate(row_vals):
                            if val.strip() == token:
                                col_name = column_names[col_idx] if col_idx < len(column_names) else f"col_{col_idx}"
                                occurrences[col_name] = occurrences.get(col_name, 0) + 1

                    canonical_state = map_canonical_missing_state(meaning, token)
                    sentinel = SentinelDefinition(
                        token=token,
                        meaning=meaning,
                        source_row_index=dec.row_index,
                        canonical_state=canonical_state,
                        is_missing_indicator=True,
                        confidence=1.0 if not is_model_assisted else 0.95,
                    )
                    sentinels.append(sentinel)

                    prov_id = f"ATR-MDL-SNT-{len(sentinels):04d}" if is_model_assisted else f"ATR-SNT-{len(sentinels):04d}"
                    provenance_list.append(ReconstructionProvenance(
                        provenance_id=prov_id,
                        operation="EXTRACT_SENTINEL",
                        source_rows=[dec.row_index],
                        affected_columns=list(occurrences.keys()),
                        before_state=text,
                        after_state={"token": token, "meaning": meaning, "occurrences": occurrences},
                        confidence=1.0 if not is_model_assisted else 0.95,
                        method="MODEL_ASSISTED" if is_model_assisted else "DETERMINISTIC",
                        status=DecisionStatus.MODEL_ASSISTED_VALIDATED if is_model_assisted else DecisionStatus.VALIDATED,
                        explanation=f"Preserved distinct sentinel '{token}' ({meaning}); found in {sum(occurrences.values())} data cells ({'model-assisted' if is_model_assisted else 'deterministic'})",
                    ))

        return sentinels, provenance_list, audits
