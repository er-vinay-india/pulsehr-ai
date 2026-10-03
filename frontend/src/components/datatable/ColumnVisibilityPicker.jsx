import React from "react";
import { formatDisplayLabel } from "../../utils/displayFormatters";

export default function ColumnVisibilityPicker({
  columns,
  visibleColumns,
  colSearchQuery,
  setColSearchQuery,
  onToggleColumn,
  onSelectAll,
  onSelectFirstN,
  onDeselectAllExceptFirst,
}) {
  const filteredCols = columns.filter(c =>
    c.toLowerCase().includes(colSearchQuery.toLowerCase()) ||
    formatDisplayLabel(c).toLowerCase().includes(colSearchQuery.toLowerCase())
  );

  return (
    <div
      className="col-picker-content"
      style={{
        width: "300px",
        maxHeight: "380px",
        display: "flex",
        flexDirection: "column",
        overflow: "hidden"
      }}
    >
      {/* Popover Header */}
      <div style={{ padding: "0.65rem 0.85rem", borderBottom: "1px solid var(--color-border)", background: "var(--color-bg-subtle)" }}>
        <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: "6px" }}>
          <span style={{ fontSize: "0.8rem", fontWeight: 700, color: "var(--color-text-primary)" }}>
            Column Visibility
          </span>
          <span style={{ fontSize: "0.72rem", color: "var(--color-text-muted)" }}>
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
            borderRadius: "6px",
            border: "1px solid var(--color-border)",
            background: "var(--color-bg-surface)",
            color: "var(--color-text-primary)",
            boxSizing: "border-box"
          }}
        />

        {/* Quick Action Buttons */}
        <div style={{ display: "flex", gap: "0.4rem", marginTop: "6px" }}>
          <button
            type="button"
            onClick={onSelectAll}
            style={{ fontSize: "0.7rem", padding: "2px 6px", borderRadius: "4px", border: "1px solid var(--color-border)", background: "var(--color-bg-surface)", color: "var(--color-text-secondary)", cursor: "pointer" }}
          >
            All
          </button>
          {columns.length > 10 && (
            <button
              type="button"
              onClick={() => onSelectFirstN(10)}
              style={{ fontSize: "0.7rem", padding: "2px 6px", borderRadius: "4px", border: "1px solid var(--color-border)", background: "var(--color-bg-surface)", color: "var(--color-text-secondary)", cursor: "pointer" }}
            >
              First 10
            </button>
          )}
          <button
            type="button"
            onClick={onDeselectAllExceptFirst}
            style={{ fontSize: "0.7rem", padding: "2px 6px", borderRadius: "4px", border: "1px solid var(--color-border)", background: "var(--color-bg-surface)", color: "var(--color-text-secondary)", cursor: "pointer" }}
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
                padding: "5px 6px",
                borderRadius: "4px",
                cursor: "pointer",
                fontSize: "0.76rem",
                color: isChecked ? "var(--color-text-primary)" : "var(--color-text-muted)",
                background: isChecked ? "var(--color-bg-soft-teal)" : "transparent"
              }}
            >
              <input
                type="checkbox"
                checked={isChecked}
                onChange={() => onToggleColumn(col)}
                style={{ accentColor: "var(--color-brand-secondary)" }}
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
