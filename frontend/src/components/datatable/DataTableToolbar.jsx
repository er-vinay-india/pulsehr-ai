import React from "react";
import { Search, X, Columns, Download } from "lucide-react";
import ColumnVisibilityPicker from "./ColumnVisibilityPicker";

export default function DataTableToolbar({
  localFilter,
  setLocalFilter,
  matchesCount,
  columns,
  visibleColumns,
  colPickerOpen,
  setColPickerOpen,
  colSearchQuery,
  setColSearchQuery,
  colPickerRef,
  onToggleColumn,
  onSelectAll,
  onSelectFirstN,
  onDeselectAllExceptFirst,
  onExportCSV,
}) {
  return (
    <div className="datatable-toolbar" style={{ display: "flex", flexWrap: "wrap", justifyContent: "space-between", alignItems: "center", gap: "0.85rem", marginBottom: "1rem" }}>
      {/* Left: Search & Filter */}
      <div style={{ display: "flex", alignItems: "center", gap: "0.75rem", flex: "1 1 320px" }}>
        <div className="datatable-search-input-wrap" style={{ position: "relative", width: "100%", maxWidth: "340px" }}>
          <Search size={14} style={{ position: "absolute", left: "10px", top: "50%", transform: "translateY(-50%)", color: "var(--fg-muted)" }} />
          <input
            type="text"
            value={localFilter}
            onChange={e => setLocalFilter(e.target.value)}
            placeholder="Quick search loaded rows & cells..."
            style={{
              width: "100%",
              padding: "0.45rem 0.65rem 0.45rem 2rem",
              fontSize: "0.8rem",
              borderRadius: "6px",
              border: "1px solid var(--border-subtle)",
              background: "rgba(0,0,0,0.3)",
              color: "var(--fg-primary)"
            }}
          />
          {localFilter && (
            <button
              onClick={() => setLocalFilter("")}
              style={{ position: "absolute", right: "8px", top: "50%", transform: "translateY(-50%)", background: "none", border: "none", color: "var(--fg-muted)", cursor: "pointer" }}
              title="Clear filter"
            >
              <X size={13} />
            </button>
          )}
        </div>

        {localFilter && (
          <span style={{ fontSize: "0.75rem", color: "var(--accent-500)", whiteSpace: "nowrap" }}>
            {matchesCount} matches
          </span>
        )}
      </div>

      {/* Right: Actions (Column Selector, Export CSV) */}
      <div style={{ display: "flex", alignItems: "center", gap: "0.6rem", flexWrap: "wrap" }}>
        <div style={{ position: "relative" }} ref={colPickerRef}>
          <button
            className="btn-secondary"
            onClick={() => setColPickerOpen(prev => !prev)}
            style={{
              display: "inline-flex",
              alignItems: "center",
              gap: "6px",
              fontSize: "0.78rem",
              padding: "0.4rem 0.75rem",
              background: colPickerOpen ? "rgba(224, 86, 36, 0.15)" : undefined,
              borderColor: colPickerOpen ? "var(--brand-400)" : undefined
            }}
            title="Select which columns to display"
          >
            <Columns size={14} color="var(--brand-400)" />
            <span>Columns ({visibleColumns.size}/{columns.length})</span>
          </button>

          <ColumnVisibilityPicker
            isOpen={colPickerOpen}
            columns={columns}
            visibleColumns={visibleColumns}
            colSearchQuery={colSearchQuery}
            setColSearchQuery={setColSearchQuery}
            onToggleColumn={onToggleColumn}
            onSelectAll={onSelectAll}
            onSelectFirstN={onSelectFirstN}
            onDeselectAllExceptFirst={onDeselectAllExceptFirst}
          />
        </div>

        <button
          className="btn-secondary"
          onClick={onExportCSV}
          style={{
            display: "inline-flex",
            alignItems: "center",
            gap: "6px",
            fontSize: "0.78rem",
            padding: "0.4rem 0.75rem",
            color: "var(--accent-500)",
            borderColor: "rgba(126, 231, 217, 0.3)"
          }}
          title="Download visible columns and rows as CSV"
        >
          <Download size={13} />
          <span>Export CSV</span>
        </button>
      </div>
    </div>
  );
}
