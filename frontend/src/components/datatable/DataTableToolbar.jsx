import React from "react";
import { Search, X, Columns, Download } from "lucide-react";
import ColumnVisibilityPicker from "./ColumnVisibilityPicker";
import DataTableFilterPopover from "./DataTableFilterPopover";
import Popover from "../common/Popover";

export default function DataTableToolbar({
  localFilter = "",
  setLocalFilter = () => {},
  matchesCount = 0,
  totalRecords = 0,
  searchPlaceholder = "Search records...",
  columns = [],
  visibleColumns = new Set(),
  enableColumnVisibility = true,
  colPickerOpen = false,
  setColPickerOpen = () => {},
  colSearchQuery = "",
  setColSearchQuery = () => {},
  onToggleColumn = () => {},
  onSelectAll = () => {},
  onSelectFirstN = () => {},
  onDeselectAllExceptFirst = () => {},
  // Column filters
  filters = [],
  activeFilters = {},
  onFilterChange = () => {},
  onClearFilters = () => {},
  filterPickerOpen = false,
  setFilterPickerOpen = () => {},
  // Export
  showExport = false,
  onExportCSV = null,
}) {
  const activeFilterEntries = Object.entries(activeFilters).filter(([_, v]) => Boolean(v));
  const hasActiveFilters = activeFilterEntries.length > 0;
  const isFiltered = Boolean(localFilter.trim() || hasActiveFilters);

  return (
    <div className="datatable-toolbar" style={{ display: "flex", flexDirection: "column", gap: "8px", marginBottom: "0.75rem" }}>
      <div style={{ display: "flex", flexWrap: "wrap", justifyContent: "space-between", alignItems: "center", gap: "0.75rem" }}>
        {/* Left: Search Bar */}
        <div style={{ display: "flex", alignItems: "center", gap: "0.75rem", flex: "1 1 280px" }}>
          <div className="datatable-search-input-wrap" style={{ position: "relative", width: "100%", maxWidth: "320px" }}>
            <Search
              size={14}
              style={{
                position: "absolute",
                left: "10px",
                top: "50%",
                transform: "translateY(-50%)",
                color: "var(--color-text-secondary, #334B57)",
              }}
              aria-hidden="true"
            />
            <input
              type="text"
              aria-label={searchPlaceholder}
              value={localFilter}
              onChange={(e) => setLocalFilter(e.target.value)}
              placeholder={searchPlaceholder}
              style={{
                width: "100%",
                padding: "0.45rem 2rem 0.45rem 2rem",
                fontSize: "0.8rem",
                borderRadius: "8px",
                border: "1px solid var(--color-border, #D4DDD6)",
                background: "var(--color-bg-surface, #ffffff)",
                color: "var(--color-text-primary, #172B3A)",
                boxSizing: "border-box",
                outline: "none",
              }}
            />
            {localFilter && (
              <button
                type="button"
                onClick={() => setLocalFilter("")}
                aria-label="Clear search"
                style={{
                  position: "absolute",
                  right: "8px",
                  top: "50%",
                  transform: "translateY(-50%)",
                  background: "none",
                  border: "none",
                  color: "var(--color-text-secondary, #334B57)",
                  cursor: "pointer",
                  display: "flex",
                  alignItems: "center",
                }}
                title="Clear search"
              >
                <X size={13} />
              </button>
            )}
          </div>
        </div>

        {/* Right: Actions (Filter, Column Visibility, Export CSV) */}
        <div style={{ display: "flex", alignItems: "center", gap: "0.5rem", flexWrap: "wrap" }}>
          {/* Filter Popover */}
          {filters && filters.length > 0 && (
            <DataTableFilterPopover
              filters={filters}
              activeFilters={activeFilters}
              onFilterChange={onFilterChange}
              onClearFilters={onClearFilters}
              isOpen={filterPickerOpen}
              onOpenChange={setFilterPickerOpen}
            />
          )}

          {/* Column Visibility Selector */}
          {enableColumnVisibility && columns && columns.length > 1 && (
            <Popover
              open={colPickerOpen}
              onOpenChange={setColPickerOpen}
              trigger={
                <button
                  type="button"
                  className="btn-secondary"
                  aria-label={`Column visibility (${visibleColumns.size}/${columns.length})`}
                  style={{
                    display: "inline-flex",
                    alignItems: "center",
                    gap: "6px",
                    fontSize: "0.78rem",
                    padding: "0.4rem 0.75rem",
                    background: colPickerOpen ? "var(--color-bg-soft-blue, rgba(35, 78, 112, 0.1))" : undefined,
                    borderColor: colPickerOpen ? "var(--color-brand-primary, #183B56)" : undefined,
                  }}
                  title="Select which columns to display"
                >
                  <Columns size={13} />
                  <span>Columns ({visibleColumns.size}/{columns.length})</span>
                </button>
              }
            >
              <ColumnVisibilityPicker
                columns={columns}
                visibleColumns={visibleColumns}
                colSearchQuery={colSearchQuery}
                setColSearchQuery={setColSearchQuery}
                onToggleColumn={onToggleColumn}
                onSelectAll={onSelectAll}
                onSelectFirstN={onSelectFirstN}
                onDeselectAllExceptFirst={onDeselectAllExceptFirst}
              />
            </Popover>
          )}

          {/* CSV Export (optional) */}
          {showExport && onExportCSV && (
            <button
              type="button"
              className="btn-secondary"
              onClick={onExportCSV}
              style={{
                display: "inline-flex",
                alignItems: "center",
                gap: "6px",
                fontSize: "0.78rem",
                padding: "0.4rem 0.75rem",
              }}
              title="Download visible columns and rows as CSV"
            >
              <Download size={13} />
              <span>Export CSV</span>
            </button>
          )}
        </div>
      </div>

      {/* Active Filter Chips Bar */}
      {hasActiveFilters && (
        <div
          className="datatable-active-filters-bar"
          style={{
            display: "flex",
            alignItems: "center",
            gap: "6px",
            flexWrap: "wrap",
            padding: "4px 8px",
            background: "var(--color-bg-subtle, #EEEFE9)",
            borderRadius: "6px",
            fontSize: "0.75rem",
          }}
        >
          <span style={{ fontWeight: 600, color: "var(--color-text-secondary, #334B57)" }}>Filters:</span>
          {activeFilterEntries.map(([fKey, fVal]) => {
            const fDef = filters.find((f) => f.key === fKey);
            const fLabel = fDef?.label || fKey;
            return (
              <span
                key={fKey}
                style={{
                  display: "inline-flex",
                  alignItems: "center",
                  gap: "4px",
                  background: "var(--color-bg-surface, #ffffff)",
                  border: "1px solid var(--color-border, #D4DDD6)",
                  borderRadius: "4px",
                  padding: "2px 6px",
                  color: "var(--color-text-primary, #172B3A)",
                  fontWeight: 500,
                }}
              >
                <strong>{fLabel}:</strong> {fVal}
                <button
                  type="button"
                  onClick={() => onFilterChange(fKey, "")}
                  aria-label={`Remove filter ${fLabel}`}
                  style={{
                    background: "none",
                    border: "none",
                    padding: 0,
                    cursor: "pointer",
                    display: "flex",
                    alignItems: "center",
                    color: "var(--color-text-secondary, #334B57)",
                  }}
                >
                  <X size={11} />
                </button>
              </span>
            );
          })}
          <button
            type="button"
            className="btn-secondary"
            onClick={onClearFilters}
            style={{
              padding: "2px 8px",
              fontSize: "0.72rem",
              minHeight: "unset",
              lineHeight: 1.2,
              marginLeft: "auto",
            }}
          >
            Clear filters
          </button>
        </div>
      )}
    </div>
  );
}
