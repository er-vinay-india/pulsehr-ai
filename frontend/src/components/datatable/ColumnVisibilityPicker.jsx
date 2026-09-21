import React from "react";
import { formatDisplayLabel } from "../../utils/displayFormatters";

export default function ColumnVisibilityPicker({
  isOpen,
  columns,
  visibleColumns,
  colSearchQuery,
  setColSearchQuery,
  onToggleColumn,
  onSelectAll,
  onSelectFirstN,
  onDeselectAllExceptFirst,
}) {
  if (!isOpen) return null;

  const filteredCols = columns.filter(c =>
    c.toLowerCase().includes(colSearchQuery.toLowerCase()) ||
    formatDisplayLabel(c).toLowerCase().includes(colSearchQuery.toLowerCase())
  );

  return (
    <div
      className="col-picker-popover"
      style={{
        position: "absolute",
        right: 0,
        top: "calc(100% + 6px)",
        zIndex: 100,
        width: "300px",
        maxHeight: "380px",
        background: "#181311",
        border: "1px solid var(--border)",
        borderRadius: "8px",
        boxShadow: "0 12px 32px rgba(0, 0, 0, 0.6)",
        display: "flex",
        flexDirection: "column",
        overflow: "hidden"
      }}
    >
      {/* Popover Header */}
      <div style={{ padding: "0.65rem 0.85rem", borderBottom: "1px solid var(--border-subtle)", background: "rgba(255,255,255,0.02)" }}>
        <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: "6px" }}>
          <span style={{ fontSize: "0.8rem", fontWeight: 700, color: "var(--fg-primary)" }}>
            Column Visibility
          </span>
          <span style={{ fontSize: "0.72rem", color: "var(--fg-muted)" }}>
            {visibleColumns.size} of {columns.length} visible
          </span>
        </div>

        {/* Search inside column picker */}
        <input
          type="text"
          value={colSearchQuery}
          onChange={e => setColSearchQuery(e.target.value)}
          placeholder="Filter column names..."
          style={{
            width: "100%",
            padding: "0.35rem 0.55rem",
            fontSize: "0.75rem",
            borderRadius: "4px",
            border: "1px solid var(--border-subtle)",
            background: "rgba(0,0,0,0.4)",
            color: "var(--fg-primary)"
          }}
        />

        {/* Quick Action Buttons */}
        <div style={{ display: "flex", gap: "0.4rem", marginTop: "6px" }}>
          <button
            type="button"
            onClick={onSelectAll}
            style={{ fontSize: "0.7rem", padding: "2px 6px", borderRadius: "3px", border: "1px solid var(--border-subtle)", background: "rgba(255,255,255,0.05)", color: "var(--fg-secondary)", cursor: "pointer" }}
          >
            All
          </button>
          {columns.length > 10 && (
            <button
              type="button"
              onClick={() => onSelectFirstN(10)}
              style={{ fontSize: "0.7rem", padding: "2px 6px", borderRadius: "3px", border: "1px solid var(--border-subtle)", background: "rgba(255,255,255,0.05)", color: "var(--fg-secondary)", cursor: "pointer" }}
            >
              First 10
            </button>
          )}
          <button
            type="button"
            onClick={onDeselectAllExceptFirst}
            style={{ fontSize: "0.7rem", padding: "2px 6px", borderRadius: "3px", border: "1px solid var(--border-subtle)", background: "rgba(255,255,255,0.05)", color: "var(--fg-secondary)", cursor: "pointer" }}
          >
            Min
          </button>
        </div>
      </div>

      {/* Column Checklist */}
      <div style={{ overflowY: "auto", padding: "0.5rem", flex: 1, maxHeight: "240px" }}>
        {filteredCols.map(col => {
          const isChecked = visibleColumns.has(col);
          return (
            <label
              key={col}
              style={{
                display: "flex",
                alignItems: "center",
                gap: "8px",
                padding: "4px 6px",
                borderRadius: "4px",
                cursor: "pointer",
                fontSize: "0.76rem",
                color: isChecked ? "var(--fg-primary)" : "var(--fg-muted)",
                background: isChecked ? "rgba(255,255,255,0.03)" : "transparent"
              }}
            >
              <input
                type="checkbox"
                checked={isChecked}
                onChange={() => onToggleColumn(col)}
                style={{ accentColor: "var(--brand-400)" }}
              />
              <span style={{ overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }} title={col}>
                {formatDisplayLabel(col)}
              </span>
            </label>
          );
        })}
      </div>
    </div>
  );
}
