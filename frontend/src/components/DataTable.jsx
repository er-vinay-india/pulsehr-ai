import React, { useState, useMemo, useRef, useEffect } from "react";
import { X, FileSpreadsheet, SearchX } from "lucide-react";
import { formatDisplayLabel } from "../utils/displayFormatters";
import DataTableToolbar from "./datatable/DataTableToolbar";
import DataTableGrid from "./datatable/DataTableGrid";
import DataTablePagination from "./datatable/DataTablePagination";
import { compareValues } from "./datatable/datatableSorting";

/**
 * Enterprise-grade Interactive DataTable Component
 *
 * Capabilities:
 * - Multi-type column sorting (numeric, currency, percentage, date, identifier, text)
 * - Governed presentation status ranking (e.g., Safe -> Needs review -> Unsafe)
 * - Client-side & Server-side type-aware sorting and pagination
 * - Column visibility manager with search and presets
 * - Compact column filter dropdowns with active filter indicators and counts
 * - Reset controls (Clear filters, Reset sorting, Reset columns)
 * - Sticky table headers with ARIA sort semantics
 * - Keyboard navigation & visible focus
 * - 100% theme token integration (WCAG AAA compliant)
 */
export default function DataTable({
  columns = [],
  rows = [],
  rowKeyProp = null,
  onRowClick = null,
  selectedRowKey = null,
  showRowIndex = false,
  // Sorting props
  defaultSortCol = null,
  defaultSortDir = null,
  secondarySortCol = null,
  secondarySortDir = "asc",
  onSortChange = null,
  // Server-side props
  serverSide = false,
  totalRows = 0,
  serverPage = 1,
  serverTotalPages = 1,
  onPageChange = () => {},
  // Pagination & Page Size
  pageSize = 25,
  onPageSizeChange = null,
  pageSizeOptions = [15, 25, 50, 100],
  // Search & Filters
  searchQuery = "",
  onSearchChange = null,
  searchPlaceholder = "Search records...",
  searchFields = null,
  filters = [],
  activeFilters: controlledActiveFilters = null,
  onFilterChange: controlledOnFilterChange = null,
  // UI Customizations
  loading = false,
  sourceLabel = "",
  enableColumnVisibility = true,
  showExport = false,
  emptyMessage = "No records available.",
  tableAriaLabel = "Data table",
}) {
  // Normalize columns: array of column definition objects
  const colDefs = useMemo(() => {
    return columns.map((col) => {
      if (typeof col === "string") {
        return {
          key: col,
          label: formatDisplayLabel(col),
          sortable: true,
          defaultVisible: true,
        };
      }
      return {
        ...col,
        label: col.label || formatDisplayLabel(col.key),
        sortable: col.sortable !== false,
        defaultVisible: col.defaultVisible !== false,
      };
    });
  }, [columns]);

  // 1. Sorting State
  const [sortCol, setSortCol] = useState(() => defaultSortCol);
  const [sortDir, setSortDir] = useState(() => defaultSortDir);

  // Sync default sort if prop changes
  useEffect(() => {
    if (defaultSortCol && sortCol === null) {
      setSortCol(defaultSortCol);
      setSortDir(defaultSortDir || "asc");
    }
  }, [defaultSortCol, defaultSortDir]);

  // 2. Column Visibility State
  const [visibleColumns, setVisibleColumns] = useState(() => {
    const defaultVisibleKeys = colDefs
      .filter((c) => c.defaultVisible !== false)
      .map((c) => c.key);
    return new Set(defaultVisibleKeys.length > 0 ? defaultVisibleKeys : colDefs.map((c) => c.key));
  });
  const [colPickerOpen, setColPickerOpen] = useState(false);
  const [colSearchQuery, setColSearchQuery] = useState("");

  useEffect(() => {
    if (colDefs.length > 0) {
      setVisibleColumns((prev) => {
        if (prev.size === 0) {
          const defaults = colDefs
            .filter((c) => c.defaultVisible !== false)
            .map((c) => c.key);
          return new Set(defaults.length > 0 ? defaults : colDefs.map((c) => c.key));
        }
        const existing = new Set([...prev].filter((k) => colDefs.some((c) => c.key === k)));
        return existing.size > 0 ? existing : new Set(colDefs.map((c) => c.key));
      });
    }
  }, [colDefs]);

  // 3. Search & Filter State
  const [internalFilter, setInternalFilter] = useState(() => searchQuery || "");
  const [internalActiveFilters, setInternalActiveFilters] = useState({});
  const [filterPickerOpen, setFilterPickerOpen] = useState(false);

  const localFilter = searchQuery !== undefined && onSearchChange ? searchQuery : internalFilter;
  const setLocalFilter = (val) => {
    if (onSearchChange) {
      onSearchChange(val);
    } else {
      setInternalFilter(val);
    }
    setClientPage(1);
  };

  const activeFilters = controlledActiveFilters !== null ? controlledActiveFilters : internalActiveFilters;
  const handleFilterChange = (filterKey, filterVal) => {
    if (controlledOnFilterChange) {
      controlledOnFilterChange(filterKey, filterVal);
    } else {
      setInternalActiveFilters((prev) => ({
        ...prev,
        [filterKey]: filterVal,
      }));
    }
    setClientPage(1);
  };

  const handleClearFilters = () => {
    if (controlledOnFilterChange) {
      Object.keys(activeFilters).forEach((k) => controlledOnFilterChange(k, ""));
    } else {
      setInternalActiveFilters({});
    }
    setLocalFilter("");
    setClientPage(1);
  };

  // 4. Client Pagination State
  const [clientPage, setClientPage] = useState(1);
  const [clientPageSize, setClientPageSize] = useState(() => pageSize);

  const handlePageSizeChange = (newSize) => {
    setClientPageSize(newSize);
    setClientPage(1);
    if (onPageSizeChange) onPageSizeChange(newSize);
  };

  // Helper to extract row value
  const getVal = (row, key) => {
    if (!row) return undefined;
    if (row.values && row.values[key] !== undefined) return row.values[key];
    return row[key];
  };

  // Handle column header click (Toggle: asc -> desc -> reset/default)
  const handleSort = (colKey) => {
    let nextCol = colKey;
    let nextDir = "asc";

    if (sortCol === colKey) {
      if (sortDir === "asc") {
        nextDir = "desc";
      } else {
        nextCol = defaultSortCol || null;
        nextDir = defaultSortDir || null;
      }
    }

    setSortCol(nextCol);
    setSortDir(nextDir);
    setClientPage(1);

    if (onSortChange) {
      onSortChange(nextCol, nextDir);
    }
  };

  // Reset sorting to default
  const handleResetSort = () => {
    setSortCol(defaultSortCol || null);
    setSortDir(defaultSortDir || null);
    setClientPage(1);
    if (onSortChange) {
      onSortChange(defaultSortCol || null, defaultSortDir || null);
    }
  };

  // Column Visibility Handlers
  const toggleColumn = (colKey) => {
    const next = new Set(visibleColumns);
    if (next.has(colKey)) {
      if (next.size > 1) {
        next.delete(colKey);
      }
    } else {
      next.add(colKey);
    }
    setVisibleColumns(next);
  };

  const selectAllColumns = () => setVisibleColumns(new Set(colDefs.map((c) => c.key)));
  const selectFirstN = (n = 5) => setVisibleColumns(new Set(colDefs.slice(0, n).map((c) => c.key)));
  const deselectAllExceptFirst = () => setVisibleColumns(new Set([colDefs[0]?.key]));

  // Auto-extract filter options from data if not provided
  const enrichedFilters = useMemo(() => {
    if (!filters || filters.length === 0) return [];
    return filters.map((f) => {
      if (f.options && f.options.length > 0) return f;
      // Extract unique values from rows
      const uniqueVals = new Set();
      rows.forEach((r) => {
        const v = getVal(r, f.key);
        if (v !== undefined && v !== null && v !== "") {
          uniqueVals.add(String(v));
        }
      });
      return {
        ...f,
        options: Array.from(uniqueVals).sort(),
      };
    });
  }, [filters, rows]);

  // Client-side Filtering & Sorting
  const filteredAndSortedRows = useMemo(() => {
    if (serverSide) {
      return rows;
    }

    let result = [...rows];

    // 1. Text Search Filter
    const q = localFilter.trim().toLowerCase();
    if (q) {
      result = result.filter((row) => {
        if (row.number && String(row.number).includes(q)) return true;
        if (row.__row_index && String(row.__row_index).includes(q)) return true;

        if (searchFields && searchFields.length > 0) {
          return searchFields.some((f) => {
            const v = getVal(row, f);
            return v !== undefined && v !== null && String(v).toLowerCase().includes(q);
          });
        }

        // Default search across all visible columns
        return colDefs.some((c) => {
          if (!visibleColumns.has(c.key)) return false;
          const v = getVal(row, c.key);
          return v !== undefined && v !== null && String(v).toLowerCase().includes(q);
        });
      });
    }

    // 2. Column Filters
    const activeEntries = Object.entries(activeFilters).filter(([_, v]) => Boolean(v));
    if (activeEntries.length > 0) {
      result = result.filter((row) => {
        return activeEntries.every(([fKey, fVal]) => {
          const val = getVal(row, fKey);
          return val !== undefined && val !== null && String(val) === String(fVal);
        });
      });
    }

    // 3. Type-Aware Sorting with Secondary Tie-Breaker
    if (sortCol && sortDir) {
      const activeColDef = colDefs.find((c) => c.key === sortCol) || { key: sortCol };
      const secColDef = secondarySortCol
        ? colDefs.find((c) => c.key === secondarySortCol) || { key: secondarySortCol }
        : null;

      result.sort((a, b) => {
        const valA = activeColDef.sortKey ? activeColDef.sortKey(a) : getVal(a, sortCol);
        const valB = activeColDef.sortKey ? activeColDef.sortKey(b) : getVal(b, sortCol);

        let cmp = compareValues(valA, valB, activeColDef, sortDir);
        if (cmp === 0 && secColDef) {
          const secValA = secColDef.sortKey ? secColDef.sortKey(a) : getVal(a, secondarySortCol);
          const secValB = secColDef.sortKey ? secColDef.sortKey(b) : getVal(b, secondarySortCol);
          cmp = compareValues(secValA, secValB, secColDef, secondarySortDir || "asc");
        }
        return cmp;
      });
    }

    return result;
  }, [
    rows,
    serverSide,
    localFilter,
    activeFilters,
    sortCol,
    sortDir,
    secondarySortCol,
    secondarySortDir,
    colDefs,
    visibleColumns,
    searchFields,
  ]);

  // Client-side pagination slicing
  const displayedRows = useMemo(() => {
    if (serverSide) return rows;
    const start = (clientPage - 1) * clientPageSize;
    return filteredAndSortedRows.slice(start, start + clientPageSize);
  }, [serverSide, rows, filteredAndSortedRows, clientPage, clientPageSize]);

  const activeTotalRows = serverSide ? totalRows || rows.length : filteredAndSortedRows.length;
  const activeTotalPages = serverSide
    ? serverTotalPages
    : Math.max(1, Math.ceil(filteredAndSortedRows.length / clientPageSize));
  const activeCurrentPage = serverSide ? serverPage : clientPage;

  const handlePaginationChange = (newPage) => {
    if (serverSide) {
      onPageChange(newPage);
    } else {
      setClientPage(newPage);
    }
  };

  // Export visible data to CSV
  const handleExportCSV = () => {
    const activeCols = colDefs.filter((c) => visibleColumns.has(c.key));
    const headerRow = activeCols.map((c) => `"${c.label.replace(/"/g, '""')}"`).join(",");
    const bodyRows = (serverSide ? rows : filteredAndSortedRows).map((r) => {
      const vals = activeCols.map((c) => {
        const v = getVal(r, c.key);
        const clean = String(v ?? "").replace(/"/g, '""');
        return `"${clean}"`;
      });
      return vals.join(",");
    });

    const csvContent = "data:text/csv;charset=utf-8," + [headerRow, ...bodyRows].join("\n");
    const encodedUri = encodeURI(csvContent);
    const link = document.createElement("a");
    link.setAttribute("href", encodedUri);
    link.setAttribute("download", `${sourceLabel || "export"}_records.csv`);
    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);
  };

  const displayedCols = colDefs.filter((c) => visibleColumns.has(c.key));
  const hasActiveFilters = Object.values(activeFilters).some(Boolean);
  const isFiltered = Boolean(localFilter.trim() || hasActiveFilters);

  return (
    <div
      className="datatable-wrapper"
      style={{
        display: "flex",
        flexDirection: "column",
        width: "100%",
        gap: "6px",
      }}
    >
      {/* Top Toolbar */}
      <DataTableToolbar
        localFilter={localFilter}
        setLocalFilter={setLocalFilter}
        matchesCount={filteredAndSortedRows.length}
        totalRecords={rows.length}
        searchPlaceholder={searchPlaceholder}
        columns={colDefs}
        visibleColumns={visibleColumns}
        enableColumnVisibility={enableColumnVisibility}
        colPickerOpen={colPickerOpen}
        setColPickerOpen={setColPickerOpen}
        colSearchQuery={colSearchQuery}
        setColSearchQuery={setColSearchQuery}
        onToggleColumn={toggleColumn}
        onSelectAll={selectAllColumns}
        onSelectFirstN={selectFirstN}
        onDeselectAllExceptFirst={deselectAllExceptFirst}
        filters={enrichedFilters}
        activeFilters={activeFilters}
        onFilterChange={handleFilterChange}
        onClearFilters={handleClearFilters}
        filterPickerOpen={filterPickerOpen}
        setFilterPickerOpen={setFilterPickerOpen}
        showExport={showExport}
        onExportCSV={handleExportCSV}
      />

      {/* Stats and Row Counts Indicator */}
      <div
        style={{
          display: "flex",
          justifyContent: "space-between",
          alignItems: "center",
          fontSize: "0.78rem",
          color: "var(--color-text-secondary, #334B57)",
          padding: "0 2px",
        }}
      >
        <span>
          {isFiltered ? (
            <>
              Showing <strong>{filteredAndSortedRows.length}</strong> of {rows.length} records (filtered)
            </>
          ) : (
            <>
              Showing <strong>{activeTotalRows.toLocaleString()}</strong> {activeTotalRows === 1 ? "record" : "records"}
            </>
          )}
          {" · "}
          <strong>{displayedCols.length}</strong> of {colDefs.length} columns visible
        </span>

        {sortCol && (
          <span
            style={{
              color: "var(--color-brand-primary, #183B56)",
              display: "inline-flex",
              alignItems: "center",
              gap: "4px",
              fontWeight: 500,
            }}
          >
            Sorted by: <strong>{colDefs.find((c) => c.key === sortCol)?.label || sortCol}</strong> (
            {sortDir === "asc" ? "Ascending" : "Descending"})
            <button
              type="button"
              onClick={handleResetSort}
              style={{
                background: "none",
                border: "none",
                color: "var(--color-text-secondary, #334B57)",
                cursor: "pointer",
                padding: "2px",
                display: "inline-flex",
                alignItems: "center",
              }}
              aria-label="Reset sorting"
              title="Reset sorting"
            >
              <X size={12} />
            </button>
          </span>
        )}
      </div>

      {/* Main Table Grid */}
      <DataTableGrid
        loading={loading}
        displayedCols={displayedCols}
        processedRows={displayedRows}
        showRowIndex={showRowIndex}
        sortCol={sortCol}
        sortDir={sortDir}
        onSort={handleSort}
        onRowClick={onRowClick}
        selectedRowKey={selectedRowKey}
        rowKeyProp={rowKeyProp}
        localFilter={localFilter}
        hasActiveFilters={hasActiveFilters}
        onClearFilters={handleClearFilters}
        tableAriaLabel={tableAriaLabel}
      />

      {/* Pagination Controls */}
      <DataTablePagination
        currentPage={activeCurrentPage}
        totalPages={activeTotalPages}
        onPageChange={handlePaginationChange}
        pageSize={serverSide ? pageSize : clientPageSize}
        onPageSizeChange={serverSide ? onPageSizeChange : handlePageSizeChange}
        pageSizeOptions={pageSizeOptions}
        loading={loading}
        totalRows={activeTotalRows}
      />
    </div>
  );
}
