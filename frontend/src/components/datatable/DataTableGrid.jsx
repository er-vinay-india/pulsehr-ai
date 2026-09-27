import React from "react";
import { ArrowUpDown, ArrowUp, ArrowDown } from "lucide-react";
import { formatDisplayLabel } from "../../utils/displayFormatters";

export default function DataTableGrid({
  loading,
  columns,
  displayedCols,
  processedRows,
  localFilter,
  sortCol,
  sortDir,
  onSort,
}) {
  return (
    <div
      className="datatable-scroll-container"
      style={{
        overflowX: "auto",
        maxHeight: "580px",
        overflowY: "auto",
        borderRadius: "8px",
        border: "1px solid var(--hv-border, #e2e8f0)",
        background: "var(--hv-bg-surface, #ffffff)",
        position: "relative"
      }}
    >
      {loading && (
        <div style={{ position: "absolute", inset: 0, background: "rgba(255, 255, 255, 0.85)", display: "flex", alignItems: "center", justifyContent: "center", zIndex: 10 }}>
          <span style={{ fontSize: "0.85rem", color: "var(--hv-brand-secondary, #005A6B)", fontWeight: 600 }}>Loading rows…</span>
        </div>
      )}

      <table aria-label="Dataset records table" style={{ width: "100%", borderCollapse: "separate", borderSpacing: 0, fontSize: "0.78rem" }}>
        <thead>
          <tr>
            {/* Sticky Source Row Index Header */}
            <th
              scope="col"
              style={{
                position: "sticky",
                left: 0,
                top: 0,
                zIndex: 5,
                background: "var(--hv-bg-page, #F8FAFC)",
                padding: "9px 12px",
                textAlign: "center",
                borderBottom: "2px solid var(--hv-border, #E2E8F0)",
                borderRight: "1px solid var(--hv-border, #E2E8F0)",
                color: "var(--hv-text-primary, #0B1F3A)",
                fontWeight: 700,
                whiteSpace: "nowrap",
                width: "80px",
                minWidth: "80px"
              }}
            >
              # Row
            </th>

            {/* Data Column Headers */}
            {displayedCols.map(col => {
              const isSorted = sortCol === col;
              return (
                <th
                  key={col}
                  scope="col"
                  aria-sort={isSorted ? (sortDir === "asc" ? "ascending" : "descending") : "none"}
                  style={{
                    position: "sticky",
                    top: 0,
                    zIndex: 3,
                    background: "var(--hv-bg-page, #F8FAFC)",
                    padding: "9px 12px",
                    textAlign: "left",
                    borderBottom: "2px solid var(--hv-border, #E2E8F0)",
                    borderRight: "1px solid var(--hv-border-subtle, #F1F5F9)",
                    color: isSorted ? "var(--hv-brand-secondary, #005A6B)" : "var(--hv-text-primary, #0B1F3A)",
                    fontWeight: 700,
                    whiteSpace: "nowrap",
                    userSelect: "none",
                    transition: "color 0.15s ease, background 0.15s ease"
                  }}
                >
                  <button
                    type="button"
                    onClick={() => onSort(col)}
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
                      textAlign: "left"
                    }}
                    aria-label={`Sort by ${formatDisplayLabel(col)}${isSorted ? (sortDir === "asc" ? ", sorted ascending" : ", sorted descending") : ""}`}
                    title={`Click to sort by ${col}. Original field: ${col}`}
                  >
                    <span>{formatDisplayLabel(col)}</span>
                    {isSorted ? (
                      sortDir === "asc" ? (
                        <ArrowUp size={13} color="var(--hv-brand-secondary, #005A6B)" aria-hidden="true" />
                      ) : (
                        <ArrowDown size={13} color="var(--hv-brand-secondary, #005A6B)" aria-hidden="true" />
                      )
                    ) : (
                      <ArrowUpDown size={12} color="var(--hv-text-muted, #64748B)" style={{ opacity: 0.5 }} aria-hidden="true" />
                    )}
                  </button>
                </th>
              );
            })}
          </tr>
        </thead>

        <tbody>
          {processedRows.length === 0 ? (
            <tr>
              <td
                colSpan={displayedCols.length + 1}
                style={{ textAlign: "center", padding: "2.5rem 1rem", color: "var(--hv-text-muted, #64748B)" }}
              >
                {localFilter ? "No matching records found for your filter." : "No records available."}
              </td>
            </tr>
          ) : (
            processedRows.map((row, rIdx) => {
              const isEven = rIdx % 2 === 0;
              return (
                <tr
                  key={rIdx}
                  style={{
                    background: isEven ? "var(--hv-bg-surface, #FFFFFF)" : "var(--hv-bg-page, #F8FAFC)",
                    transition: "background 0.12s ease"
                  }}
                  className="datatable-row"
                >
                  {/* Sticky Source Row Index Cell */}
                  <td
                    style={{
                      position: "sticky",
                      left: 0,
                      zIndex: 2,
                      background: isEven ? "var(--hv-bg-surface, #FFFFFF)" : "var(--hv-bg-page, #F8FAFC)",
                      padding: "8px 12px",
                      textAlign: "center",
                      borderBottom: "1px solid var(--hv-border-subtle, #F1F5F9)",
                      borderRight: "1px solid var(--hv-border, #E2E8F0)",
                      color: "var(--hv-text-secondary, #334155)",
                      fontFamily: "monospace",
                      fontSize: "0.75rem",
                      whiteSpace: "nowrap"
                    }}
                  >
                    {row.number}
                  </td>

                  {/* Data Cells */}
                  {displayedCols.map((col, cIdx) => {
                    const val = row.values ? row.values[col] : undefined;
                    const displayVal = val !== undefined && val !== null && val !== "" ? String(val) : "—";
                    const isNull = displayVal === "—";

                    return (
                      <td
                        key={cIdx}
                        style={{
                          padding: "8px 12px",
                          borderBottom: "1px solid var(--hv-border-subtle, #F1F5F9)",
                          borderRight: "1px solid var(--hv-border-subtle, #F1F5F9)",
                          color: isNull ? "var(--hv-text-muted, #64748B)" : "var(--hv-text-secondary, #334155)",
                          fontStyle: isNull ? "italic" : "normal",
                          whiteSpace: "nowrap",
                          maxWidth: "280px",
                          overflow: "hidden",
                          textOverflow: "ellipsis"
                        }}
                        title={!isNull ? displayVal : ""}
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
