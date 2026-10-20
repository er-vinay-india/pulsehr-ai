import React from "react";
import { formatDisplayLabel } from "../../utils/displayFormatters";

export default function ColumnVisibilityPicker({
  columns = [],
  visibleColumns = new Set(),
  colSearchQuery = "",
  setColSearchQuery = () => {},
  onToggleColumn = () => {},
  onSelectAll = () => {},
  onSelectFirstN = () => {},
  onDeselectAllExceptFirst = () => {},
}) {
  const getColKey = (c) => (typeof c === "string" ? c : c.key);
  const getColLabel = (c) => (typeof c === "string" ? formatDisplayLabel(c) : c.label || formatDisplayLabel(c.key));

  const filteredCols = columns.filter((c) => {
    const key = getColKey(c).toLowerCase();
    const label = getColLabel(c).toLowerCase();
    const q = colSearchQuery.toLowerCase();
    return key.includes(q) || label.includes(q);
  });

  return (
    <div
      className="col-picker-content"
      style={{
        width: "280px",
        maxHeight: "360px",
        display: "flex",
        flexDirection: "column",
        overflow: "hidden",
        background: "var(--color-bg-surface, #ffffff)",
        color: "var(--color-text-primary, #172B3A)",
      }}
    >
      {/* Popover Header */}
      <div style={{ padding: "0.65rem 0.85rem", borderBottom: "1px solid var(--color-border, #D4DDD6)", background: "var(--color-bg-subtle, #EEEFE9)" }}>
        <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: "6px" }}>
          <span style={{ fontSize: "0.8rem", fontWeight: 700, color: "var(--color-text-primary, #172B3A)" }}>
            Column Visibility
          </span>
          <span style={{ fontSize: "0.72rem", color: "var(--color-text-muted, #3C5059)" }}>
            {visibleColumns.size} of {columns.length} visible
          </span>
        </div>

        {/* Search inside column picker */}
        <input
          type="text"
          value={colSearchQuery}
          onChange={(e) => setColSearchQuery(e.target.value)}
          placeholder="Filter columns..."
          aria-label="Filter columns"
          style={{
            width: "100%",
            padding: "0.35rem 0.55rem",
            fontSize: "0.75rem",
            borderRadius: "6px",
            border: "1px solid var(--color-border, #D4DDD6)",
            background: "var(--color-bg-surface, #ffffff)",
            color: "var(--color-text-primary, #172B3A)",
            boxSizing: "border-box",
            outline: "none",
          }}
        />

        {/* Quick Action Buttons */}
        <div style={{ display: "flex", gap: "0.4rem", marginTop: "6px" }}>
          <button
            type="button"
            className="btn-secondary"
            onClick={onSelectAll}
            style={{ fontSize: "0.7rem", padding: "2px 6px", minHeight: "unset", lineHeight: 1.2 }}
          >
            All
          </button>
          {columns.length > 5 && (
            <button
              type="button"
              className="btn-secondary"
              onClick={() => onSelectFirstN(5)}
              style={{ fontSize: "0.7rem", padding: "2px 6px", minHeight: "unset", lineHeight: 1.2 }}
            >
              First 5
            </button>
          )}
          <button
            type="button"
            className="btn-secondary"
            onClick={onDeselectAllExceptFirst}
            style={{ fontSize: "0.7rem", padding: "2px 6px", minHeight: "unset", lineHeight: 1.2 }}
          >
            Min
          </button>
        </div>
      </div>

      {/* Column Checklist */}
      <div style={{ overflowY: "auto", padding: "0.5rem", flex: 1, maxHeight: "220px" }}>
        {filteredCols.map((c) => {
          const key = getColKey(c);
          const label = getColLabel(c);
          const isChecked = visibleColumns.has(key);
          return (
            <label
              key={key}
              style={{
                display: "flex",
                alignItems: "center",
                gap: "8px",
                padding: "5px 6px",
                borderRadius: "4px",
                cursor: "pointer",
                fontSize: "0.78rem",
                userSelect: "none",
                color: "var(--color-text-primary, #172B3A)",
              }}
            >
              <input
                type="checkbox"
                checked={isChecked}
                onChange={() => onToggleColumn(key)}
                style={{ cursor: "pointer" }}
              />
              <span>{label}</span>
            </label>
          );
        })}
      </div>
    </div>
  );
}
