import React from "react";
import { ArrowUpDown, ArrowUp, ArrowDown } from "lucide-react";
import { RefetchBadge } from "../loaders";
import {
  formatDisplayLabel,
  formatCuratedNumber,
  formatCompleteNumber,
} from "../../utils/displayFormatters";

export default function DataTableGrid({
  loading = false,
  displayedCols = [],
  processedRows = [],
  showRowIndex = false,
  sortCol = null,
  sortDir = null,
  onSort = () => {},
  onRowClick = null,
  selectedRowKey = null,
  rowKeyProp = null,
  localFilter = "",
  hasActiveFilters = false,
  onClearFilters = () => {},
  tableAriaLabel = "Data Explorer table",
}) {
  const getColDef = (col) =>
    typeof col === "string" ? { key: col, label: formatDisplayLabel(col), sortable: true } : col;

  const getRowVal = (row, colKey) => {
    if (!row) return undefined;
    if (row.values && row.values[colKey] !== undefined) return row.values[colKey];
    return row[colKey];
  };

  const getRowKey = (row, idx) => {
    if (typeof rowKeyProp === "function") return rowKeyProp(row, idx);
    if (typeof rowKeyProp === "string" && row[rowKeyProp] !== undefined) return row[rowKeyProp];
    return (
      row.id ||
      row.column_id ||
      row.relationship_id ||
      row.view_id ||
      row.fact_id ||
      row.__row_index ||
      row.number ||
      idx
    );
  };

  const isFiltered = Boolean(localFilter.trim() || hasActiveFilters);

  return (
    <div
      className="datatable-scroll-container"
      style={{
        overflowX: "auto",
        maxHeight: "560px",
        overflowY: "auto",
        borderRadius: "8px",
        border: "1px solid var(--color-border, #D4DDD6)",
        background: "var(--color-bg-surface, #ffffff)",
        position: "relative",
      }}
    >
      {loading && (
        <div
          role="status"
          aria-live="polite"
          style={{
            position: "absolute",
            inset: 0,
            background: "var(--color-bg-subtle, rgba(0, 0, 0, 0.04))",
            backdropFilter: "blur(1.5px)",
            WebkitBackdropFilter: "blur(1.5px)",
            display: "flex",
            alignItems: "center",
            justifyContent: "center",
            zIndex: 10,
            pointerEvents: "none",
          }}
        >
          <RefetchBadge active={true} label="Updating records…" />
        </div>
      )}

      <table
        aria-label={tableAriaLabel}
        style={{
          width: "100%",
          borderCollapse: "separate",
          borderSpacing: 0,
          fontSize: "0.8rem",
          textAlign: "left",
        }}
      >
        <thead>
          <tr>
            {/* Optional Sticky Source Row Index Header */}
            {showRowIndex && (
              <th
                scope="col"
                style={{
                  position: "sticky",
                  left: 0,
                  top: 0,
                  zIndex: 5,
                  background: "var(--color-bg-page, #F6F5F0)",
                  padding: "10px 12px",
                  textAlign: "center",
                  borderBottom: "2px solid var(--color-border, #D4DDD6)",
                  borderRight: "1px solid var(--color-border, #D4DDD6)",
                  color: "var(--color-text-primary, #172B3A)",
                  fontWeight: 700,
                  whiteSpace: "nowrap",
                  width: "60px",
                  minWidth: "60px",
                }}
              >
                #
              </th>
            )}

            {/* Data Column Headers */}
            {displayedCols.map((col) => {
              const colDef = getColDef(col);
              const colKey = colDef.key;
              const isSorted = sortCol === colKey;
              const isSortable = colDef.sortable !== false;
              const align = colDef.align || (colDef.type === "number" || colDef.type === "currency" || colDef.type === "percentage" ? "right" : "left");

              return (
                <th
                  key={colKey}
                  scope="col"
                  aria-sort={isSorted ? (sortDir === "asc" ? "ascending" : "descending") : "none"}
                  style={{
                    position: "sticky",
                    top: 0,
                    zIndex: 3,
                    background: "var(--color-bg-page, #F6F5F0)",
                    padding: "10px 12px",
                    textAlign: align,
                    borderBottom: "2px solid var(--color-border, #D4DDD6)",
                    borderRight: "1px solid var(--color-divider, #E5E9E3)",
                    color: isSorted ? "var(--color-brand-primary, #183B56)" : "var(--color-text-primary, #172B3A)",
                    fontWeight: 700,
                    whiteSpace: "nowrap",
                    userSelect: "none",
                    width: colDef.width || undefined,
                  }}
                >
                  {isSortable ? (
                    <button
                      type="button"
                      onClick={() => onSort(colKey)}
                      style={{
                        background: "none",
                        border: "none",
                        padding: 0,
                        font: "inherit",
                        color: "inherit",
                        cursor: "pointer",
                        display: "inline-flex",
                        alignItems: "center",
                        gap: "6px",
                        textAlign: align,
                        width: "100%",
                        justifyContent: align === "right" ? "flex-end" : align === "center" ? "center" : "flex-start",
                      }}
                      aria-label={`Sort by ${colDef.label}${
                        isSorted ? (sortDir === "asc" ? ", sorted ascending" : ", sorted descending") : ""
                      }`}
                      title={`Click to sort by ${colDef.label}`}
                    >
                      <span>{colDef.label}</span>
                      {isSorted ? (
                        sortDir === "asc" ? (
                          <ArrowUp size={13} color="var(--color-brand-primary, #183B56)" aria-hidden="true" />
                        ) : (
                          <ArrowDown size={13} color="var(--color-brand-primary, #183B56)" aria-hidden="true" />
                        )
                      ) : (
                        <ArrowUpDown
                          size={12}
                          color="var(--color-text-muted, #3C5059)"
                          style={{ opacity: 0.4 }}
                          aria-hidden="true"
                        />
                      )}
                    </button>
                  ) : (
                    <span>{colDef.label}</span>
                  )}
                </th>
              );
            })}
          </tr>
        </thead>

        <tbody>
          {processedRows.length === 0 ? (
            <tr>
              <td
                colSpan={displayedCols.length + (showRowIndex ? 1 : 0)}
                style={{
                  textAlign: "center",
                  padding: "2.5rem 1rem",
                  color: "var(--color-text-secondary, #334B57)",
                }}
              >
                <div style={{ display: "flex", flexDirection: "column", alignItems: "center", gap: "8px" }}>
                  <span>
                    {isFiltered
                      ? "No records match the current search or filters."
                      : "No records available for this table."}
                  </span>
                  {isFiltered && (
                    <button
                      type="button"
                      className="btn-secondary"
                      onClick={onClearFilters}
                      style={{
                        padding: "4px 12px",
                        fontSize: "0.78rem",
                        marginTop: "4px",
                      }}
                    >
                      Clear filters
                    </button>
                  )}
                </div>
              </td>
            </tr>
          ) : (
            processedRows.map((row, rIdx) => {
              const rKey = getRowKey(row, rIdx);
              const isSelected = selectedRowKey && String(selectedRowKey) === String(rKey);
              const isEven = rIdx % 2 === 0;
              const isClickable = Boolean(onRowClick);

              return (
                <tr
                  key={rKey}
                  onClick={isClickable ? () => onRowClick(row) : undefined}
                  className="datatable-row"
                  style={{
                    background: isSelected
                      ? "var(--color-bg-soft-blue, #EAF0F5)"
                      : isEven
                      ? "var(--color-bg-surface, #ffffff)"
                      : "var(--color-bg-subtle, #EEEFE9)",
                    cursor: isClickable ? "pointer" : "default",
                    transition: "background 0.12s ease",
                  }}
                >
                  {/* Optional Sticky Source Row Index Cell */}
                  {showRowIndex && (
                    <td
                      style={{
                        position: "sticky",
                        left: 0,
                        zIndex: 2,
                        background: isSelected
                          ? "var(--color-bg-soft-blue, #EAF0F5)"
                          : isEven
                          ? "var(--color-bg-surface, #ffffff)"
                          : "var(--color-bg-subtle, #EEEFE9)",
                        padding: "9px 12px",
                        textAlign: "center",
                        borderBottom: "1px solid var(--color-divider, #E5E9E3)",
                        borderRight: "1px solid var(--color-border, #D4DDD6)",
                        color: "var(--color-text-secondary, #334B57)",
                        fontFamily: "monospace",
                        fontSize: "0.75rem",
                        whiteSpace: "nowrap",
                      }}
                    >
                      {row.__row_index || row.number || rIdx + 1}
                    </td>
                  )}

                  {/* Data Cells */}
                  {displayedCols.map((col, cIdx) => {
                    const colDef = getColDef(col);
                    const colKey = colDef.key;
                    const val = getRowVal(row, colKey);
                    const align = colDef.align || (colDef.type === "number" || colDef.type === "currency" || colDef.type === "percentage" ? "right" : "left");

                    if (colDef.render) {
                      return (
                        <td
                          key={colKey || cIdx}
                          style={{
                            padding: "9px 12px",
                            borderBottom: "1px solid var(--color-divider, #E5E9E3)",
                            borderRight: "1px solid var(--color-divider, #E5E9E3)",
                            textAlign: align,
                            whiteSpace: "nowrap",
                          }}
                        >
                          {colDef.render(val, row, rIdx)}
                        </td>
                      );
                    }

                    const isNull = val === undefined || val === null || val === "";
                    let displayVal = "—";
                    let tooltipVal = "";

                    if (!isNull) {
                      const strVal = String(val).trim();
                      const isDate = /^\d{4}-\d{2}-\d{2}/.test(strVal);
                      const num = Number(val);
                      const isNumeric = !isDate && Number.isFinite(num);

                      if (colDef.type === "currency") {
                        displayVal = isNumeric
                          ? `$${num.toLocaleString("en-US", { minimumFractionDigits: 0, maximumFractionDigits: 2 })}`
                          : strVal;
                        tooltipVal = `Exact value: ${val}`;
                      } else if (colDef.type === "percentage") {
                        displayVal = isNumeric ? `${num}%` : strVal;
                        tooltipVal = `Exact: ${val}`;
                      } else if (isNumeric && !Number.isInteger(num)) {
                        displayVal = formatCuratedNumber(num, 2);
                        tooltipVal = `Complete: ${formatCompleteNumber(val)}`;
                      } else if (isNumeric && Number.isInteger(num)) {
                        displayVal = num.toLocaleString("en-US");
                        tooltipVal = String(val);
                      } else {
                        displayVal = strVal;
                        tooltipVal = strVal;
                      }
                    }

                    const isHoverable = tooltipVal && (tooltipVal.startsWith("Complete:") || tooltipVal.startsWith("Exact:"));

                    return (
                      <td
                        key={colKey || cIdx}
                        style={{
                          padding: "9px 12px",
                          borderBottom: "1px solid var(--color-divider, #E5E9E3)",
                          borderRight: "1px solid var(--color-divider, #E5E9E3)",
                          textAlign: align,
                          color: isNull ? "var(--color-text-muted, #3C5059)" : "var(--color-text-primary, #172B3A)",
                          fontStyle: isNull ? "italic" : "normal",
                          fontFamily:
                            colDef.type === "identifier" || colDef.type === "number" || colDef.type === "currency"
                              ? "monospace"
                              : "inherit",
                          whiteSpace: "nowrap",
                          maxWidth: "320px",
                          overflow: "hidden",
                          textOverflow: "ellipsis",
                          cursor: isHoverable ? "help" : undefined,
                        }}
                        title={tooltipVal}
                      >
                        {displayVal}
                      </td>
                    );
                  })}
                </tr>
              );
            })
          )}
        </tbody>
      </table>
    </div>
  );
}
