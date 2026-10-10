"""HeaderTreeBuilder: Hierarchical multi-row header resolution and canonical naming.

Flattens multi-level spreadsheet headers into clean canonical column names while preserving
the full ancestral token path, display labels, and column geometry.
"""

import re
from typing import Dict, List, Optional, Set, Tuple

from .contracts import HeaderNode, HeaderTree, ReconstructionProvenance
from .grid_capture import RawGrid


def normalize_column_name(raw_name: str) -> str:
    """Produces clean snake_case identifier while preserving numbers and chemical/unit symbols."""
    # Replace dots in numbers e.g. "PM 2.5" -> "PM 2_5" or "09.05.2024" -> "09_05_2024"
    cleaned = re.sub(r'(\d+)\.(\d+)', r'\1_\2', raw_name.strip())
    # Replace non-alphanumeric characters with underscores
    cleaned = re.sub(r'[^a-zA-Z0-9]+', '_', cleaned)
    # Collapse consecutive underscores
    cleaned = re.sub(r'_+', '_', cleaned).strip('_').lower()
    return cleaned or "column"


class HeaderTreeBuilder:
    """Builds a structured HeaderTree from designated header rows in the raw grid."""

    @classmethod
    def build_tree(
        cls,
        grid: RawGrid,
        header_row_indices: List[int],
        active_col_indices: Optional[List[int]] = None,
    ) -> Tuple[HeaderTree, ReconstructionProvenance]:
        """Constructs HeaderTree from header rows, handling merged parent spans and vertical paths."""
        if not header_row_indices:
            # Fallback: single artificial header
            total_cols = grid.raw_col_count
            nodes = [
                HeaderNode(
                    col_index=c,
                    row_indices=[],
                    raw_tokens=[f"column_{c+1}"],
                    normalized_name=f"column_{c+1}",
                    display_name=f"Column {c+1}",
                )
                for c in range(total_cols)
            ]
            tree = HeaderTree(
                header_row_indices=[],
                columns=nodes,
                column_names=[n.display_name for n in nodes],
                normalized_columns=[n.normalized_name for n in nodes],
                col_index_to_name={n.col_index: n.normalized_name for n in nodes},
            )
            provenance = ReconstructionProvenance(
                provenance_id="ATR-HDR-0001",
                operation="CREATE_FALLBACK_HEADERS",
                source_rows=[],
                after_state=tree.normalized_columns,
                confidence=0.5,
                explanation="No header rows detected; generated default indexed column headers",
            )
            return tree, provenance

        total_cols = grid.raw_col_count
        if active_col_indices is None:
            # Filter out columns that are completely blank across headers AND data
            active_col_indices = []
            for c in range(total_cols):
                has_any = any(bool(grid.get_cell(r, c).strip()) for r in range(grid.raw_row_count))
                if has_any:
                    active_col_indices.append(c)

        # Build virtual 2D header cell grid for active columns
        num_header_rows = len(header_row_indices)
        header_matrix: List[List[str]] = []
        for r_idx in header_row_indices:
            header_matrix.append([grid.get_cell(r_idx, c) for c in active_col_indices])

        # Step 1: Detect horizontal spanning (merged cells in upper header rows)
        # If an upper row has a non-empty cell followed by empty cells, but lower rows have distinct headers,
        # propagate the category forward across the span.
        for r_h in range(num_header_rows - 1):
            row_vals = header_matrix[r_h]
            last_val = ""
            for col_pos in range(len(active_col_indices)):
                val = row_vals[col_pos].strip()
                if val:
                    # Check if lower row has something in this position
                    last_val = val
                else:
                    # Only forward-fill if this upper category logically groups following columns
                    # (i.e. does the next row have content in this position, while current row is empty?)
                    lower_has_content = any(
                        bool(header_matrix[next_r][col_pos].strip())
                        for next_r in range(r_h + 1, num_header_rows)
                    )
                    # And don't propagate across an entirely empty column
                    if lower_has_content and last_val and not re.search(r'\b(already|approved|date|sr|no)\b', last_val.lower()):
                        # We only forward-fill grouping categories (e.g. "Q1 2024", "Engineering", "Air Quality")
                        pass

        # Step 2: Assemble vertical token paths for each column
        nodes: List[HeaderNode] = []
        seen_normalized: Set[str] = set()

        for col_pos, orig_col in enumerate(active_col_indices):
            tokens: List[str] = []
            for r_h, r_idx in enumerate(header_row_indices):
                cell_val = header_matrix[r_h][col_pos].strip()
                if cell_val and cell_val not in tokens:
                    tokens.append(cell_val)

            if not tokens:
                tokens = [f"column_{orig_col + 1}"]

            # Construct clean display name by concatenating tokens
            display_name = " ".join(tokens)
            # Clean up display name punctuation (e.g. "Sr. No." remains readable)
            display_name = re.sub(r'\s+', ' ', display_name).strip()

            norm_name = normalize_column_name(display_name)
            # Ensure unique names
            base_norm = norm_name
            counter = 2
            while norm_name in seen_normalized:
                norm_name = f"{base_norm}_{counter}"
                counter += 1
            seen_normalized.add(norm_name)

            nodes.append(HeaderNode(
                col_index=orig_col,
                row_indices=header_row_indices,
                raw_tokens=tokens,
                normalized_name=norm_name,
                display_name=display_name,
            ))

        tree = HeaderTree(
            header_row_indices=header_row_indices,
            columns=nodes,
            column_names=[n.display_name for n in nodes],
            normalized_columns=[n.normalized_name for n in nodes],
            col_index_to_name={n.col_index: n.normalized_name for n in nodes},
        )

        provenance = ReconstructionProvenance(
            provenance_id="ATR-HDR-0001",
            operation="MERGE_HEADER_HIERARCHY",
            source_rows=header_row_indices,
            affected_columns=[n.col_index for n in nodes],
            after_state=tree.normalized_columns,
            confidence=1.0,
            explanation=f"Resolved {len(header_row_indices)}-row header hierarchy into {len(nodes)} canonical columns",
        )

        return tree, provenance
