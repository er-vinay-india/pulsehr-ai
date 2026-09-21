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
        border: "1px solid var(--border-subtle)",
        background: "rgba(0,0,0,0.25)",
        position: "relative"
      }}
    >
      {loading && (
        <div style={{ position: "absolute", inset: 0, background: "rgba(15, 12, 10, 0.75)", display: "flex", alignItems: "center", justifyContent: "center", zIndex: 10 }}>
          <span style={{ fontSize: "0.85rem", color: "var(--brand-400)", fontWeight: 600 }}>Loading rows…</span>
        </div>
      )}

      <table style={{ width: "100%", borderCollapse: "separate", borderSpacing: 0, fontSize: "0.78rem" }}>
        <thead>
          <tr>
            {/* Sticky Source Row Index Header */}
            <th
              style={{
                position: "sticky",
                left: 0,
                top: 0,
                zIndex: 5,
                background: "#191412",
                padding: "9px 12px",
                textAlign: "center",
                borderBottom: "1px solid var(--border)",
                borderRight: "1px solid var(--border-subtle)",
                color: "var(--fg-muted)",
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
                  onClick={() => onSort(col)}
                  style={{
                    position: "sticky",
                    top: 0,
                    zIndex: 3,
                    background: "#191412",
                    padding: "9px 12px",
                    textAlign: "left",
                    borderBottom: "1px solid var(--border)",
                    borderRight: "1px solid rgba(255,255,255,0.03)",
                    color: isSorted ? "var(--brand-400)" : "var(--fg-secondary)",
                    fontWeight: 700,
                    whiteSpace: "nowrap",
                    cursor: "pointer",
                    userSelect: "none",
                    transition: "color 0.15s ease, background 0.15s ease"
                  }}
                  title={`Click to sort by ${col}. Original field: ${col}`}
                >
                  <div style={{ display: "inline-flex", alignItems: "center", gap: "6px" }}>
                    <span>{formatDisplayLabel(col)}</span>
                    {isSorted ? (
                      sortDir === "asc" ? <ArrowUp size={13} color="var(--brand-400)" /> : <ArrowDown size={13} color="var(--brand-400)" />
                    ) : (
                      <ArrowUpDown size={12} color="var(--fg-muted)" style={{ opacity: 0.4 }} />
                    )}
                  </div>
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
                style={{ textAlign: "center", padding: "2.5rem 1rem", color: "var(--fg-muted)" }}
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
                    background: isEven ? "rgba(255,255,255,0.015)" : "transparent",
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
                      background: isEven ? "#181412" : "#14110f",
                      padding: "8px 12px",
                      textAlign: "center",
                      borderBottom: "1px solid var(--border-subtle)",
                      borderRight: "1px solid var(--border-subtle)",
                      color: "var(--fg-muted)",
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
                          borderBottom: "1px solid var(--border-subtle)",
                          borderRight: "1px solid rgba(255,255,255,0.02)",
                          color: isNull ? "var(--fg-muted)" : "var(--fg-primary)",
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
