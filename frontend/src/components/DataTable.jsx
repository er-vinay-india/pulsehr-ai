import React, { useState, useMemo, useRef, useEffect } from "react";
import { X } from "lucide-react";
import { formatDisplayLabel } from "../utils/displayFormatters";
import DataTableToolbar from "./datatable/DataTableToolbar";
import DataTableGrid from "./datatable/DataTableGrid";
import DataTablePagination from "./datatable/DataTablePagination";

/**
 * Enterprise-grade Interactive DataTable Component
 * Features:
 * - Multi-type column sorting (numeric, date, string) with 3-state toggle
 * - Column visibility manager with column search & quick selection (vital for 100+ column sheets)
 * - Real-time client-side row filtering with match highlight
 * - Sticky frozen headers and pinned row-index column
 * - Page size selector (15, 25, 50, 100) and server/client pagination
 * - One-click visible data export to CSV
 */
export default function DataTable({
  columns = [],
  rows = [],
  totalRows = 0,
  serverPage = 1,
  serverTotalPages = 1,
  onPageChange = () => {},
  pageSize = 25,
  onPageSizeChange = null,
  searchQuery = "",
  onSearchChange = null,
  loading = false,
  sourceLabel = ""
}) {
  // 1. Sorting State
  const [sortCol, setSortCol] = useState(null);
  const [sortDir, setSortDir] = useState(null); // 'asc' | 'desc' | null

  // 2. Column Visibility State
  const [visibleColumns, setVisibleColumns] = useState(new Set());
  const [colPickerOpen, setColPickerOpen] = useState(false);
  const [colSearchQuery, setColSearchQuery] = useState("");
  const colPickerRef = useRef(null);

  // 3. Local Row Filter State
  const [localFilter, setLocalFilter] = useState("");

  // Initialize visible columns when columns prop updates
  useEffect(() => {
    if (columns && columns.length > 0) {
      if (columns.length > 15 && visibleColumns.size === 0) {
        setVisibleColumns(new Set(columns.slice(0, 12)));
      } else if (visibleColumns.size === 0) {
        setVisibleColumns(new Set(columns));
      } else {
        const existing = new Set([...visibleColumns].filter(c => columns.includes(c)));
        if (existing.size === 0) {
          setVisibleColumns(new Set(columns.length > 15 ? columns.slice(0, 12) : columns));
        } else {
          setVisibleColumns(existing);
        }
      }
    }
  }, [columns]);

  // Close column picker when clicking outside
  useEffect(() => {
    function handleClickOutside(event) {
      if (colPickerRef.current && !colPickerRef.current.contains(event.target)) {
        setColPickerOpen(false);
      }
    }
    document.addEventListener("mousedown", handleClickOutside);
    return () => document.removeEventListener("mousedown", handleClickOutside);
  }, []);

  // Handle column header click (Toggle: asc -> desc -> reset)
  const handleSort = (col) => {
    if (sortCol !== col) {
      setSortCol(col);
      setSortDir("asc");
    } else if (sortDir === "asc") {
      setSortDir("desc");
    } else {
      setSortCol(null);
      setSortDir(null);
    }
  };

  // Toggle single column visibility
  const toggleColumn = (col) => {
    const next = new Set(visibleColumns);
    if (next.has(col)) {
      if (next.size > 1) {
        next.delete(col);
      }
    } else {
      next.add(col);
    }
    setVisibleColumns(next);
  };

  const selectAllColumns = () => setVisibleColumns(new Set(columns));
  const selectFirstN = (n = 10) => setVisibleColumns(new Set(columns.slice(0, n)));
  const deselectAllExceptFirst = () => setVisibleColumns(new Set(columns.slice(0, 1)));

  // Filtered & Sorted Rows
  const processedRows = useMemo(() => {
    let result = [...rows];

    // Client-side row filter
    if (localFilter.trim()) {
      const q = localFilter.trim().toLowerCase();
      result = result.filter(r => {
        if (String(r.number).includes(q)) return true;
        return Object.values(r.values || {}).some(val =>
          String(val ?? "").toLowerCase().includes(q)
        );
      });
    }

    // Client-side sorting
    if (sortCol && sortDir) {
      result.sort((a, b) => {
        const valA = a.values ? a.values[sortCol] : undefined;
        const valB = b.values ? b.values[sortCol] : undefined;

        if (valA === undefined || valA === null || valA === "") return 1;
        if (valB === undefined || valB === null || valB === "") return -1;

        // Numeric comparison
        const numA = Number(valA);
        const numB = Number(valB);
        if (!isNaN(numA) && !isNaN(numB)) {
          return sortDir === "asc" ? numA - numB : numB - numA;
        }

        // Date comparison
        const dateA = Date.parse(valA);
        const dateB = Date.parse(valB);
        if (!isNaN(dateA) && !isNaN(dateB) && String(valA).length >= 8 && String(valB).length >= 8) {
          return sortDir === "asc" ? dateA - dateB : dateB - dateA;
        }

        // String comparison
        const strA = String(valA).toLowerCase();
        const strB = String(valB).toLowerCase();
        return sortDir === "asc" ? strA.localeCompare(strB) : strB.localeCompare(strA);
      });
    }

    return result;
  }, [rows, localFilter, sortCol, sortDir]);

  // Export visible data to CSV
  const handleExportCSV = () => {
    const activeCols = columns.filter(c => visibleColumns.has(c));
    const headerRow = ["Source Row", ...activeCols.map(c => `"${formatDisplayLabel(c).replace(/"/g, '""')}"`)].join(",");
    const bodyRows = processedRows.map(r => {
      const vals = activeCols.map(c => {
        const v = r.values ? r.values[c] : "";
        const clean = String(v ?? "").replace(/"/g, '""');
        return `"${clean}"`;
      });
      return [`"${r.number}"`, ...vals].join(",");
    });

    const csvContent = "data:text/csv;charset=utf-8," + [headerRow, ...bodyRows].join("\n");
    const encodedUri = encodeURI(csvContent);
    const link = document.createElement("a");
    link.setAttribute("href", encodedUri);
    link.setAttribute("download", `data_extract_${sourceLabel || "table"}_page_${serverPage}.csv`);
    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);
  };

  const displayedCols = columns.filter(c => visibleColumns.has(c));

  return (
    <div className="datatable-wrapper card-panel" style={{ marginTop: "1rem", padding: "1.25rem", width: "100%" }}>
      {/* Top Toolbar */}
      <DataTableToolbar
        localFilter={localFilter}
        setLocalFilter={setLocalFilter}
        matchesCount={processedRows.length}
        columns={columns}
        visibleColumns={visibleColumns}
        colPickerOpen={colPickerOpen}
        setColPickerOpen={setColPickerOpen}
        colSearchQuery={colSearchQuery}
        setColSearchQuery={setColSearchQuery}
        colPickerRef={colPickerRef}
        onToggleColumn={toggleColumn}
        onSelectAll={selectAllColumns}
        onSelectFirstN={selectFirstN}
        onDeselectAllExceptFirst={deselectAllExceptFirst}
        onExportCSV={handleExportCSV}
      />

      {/* Stats and Row Counts Indicator */}
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", fontSize: "0.78rem", color: "var(--fg-muted)", marginBottom: "0.5rem" }}>
        <span>
          Showing <strong>{processedRows.length}</strong> loaded {processedRows.length === 1 ? "record" : "records"}
          {totalRows > 0 && ` (Total ${totalRows.toLocaleString()} across dataset)`} · <strong>{displayedCols.length}</strong> of {columns.length} columns active
        </span>
        {sortCol && (
          <span style={{ color: "var(--brand-400)", display: "inline-flex", alignItems: "center", gap: "4px" }}>
            Sorted by: <strong>{formatDisplayLabel(sortCol)}</strong> ({sortDir === "asc" ? "Ascending" : "Descending"})
            <button
              onClick={() => { setSortCol(null); setSortDir(null); }}
              style={{ background: "none", border: "none", color: "var(--fg-muted)", cursor: "pointer", marginLeft: "4px" }}
              title="Reset sorting"
            >
              <X size={12} />
            </button>
          </span>
        )}
      </div>

      {/* Main Table Grid with Sticky Header & Frozen Row Index Column */}
      <DataTableGrid
        loading={loading}
        columns={columns}
        displayedCols={displayedCols}
        processedRows={processedRows}
        localFilter={localFilter}
        sortCol={sortCol}
        sortDir={sortDir}
        onSort={handleSort}
      />

      {/* Pagination & Server Navigation Controls */}
      <DataTablePagination
        serverPage={serverPage}
        serverTotalPages={serverTotalPages}
        onPageChange={onPageChange}
        loading={loading}
      />
    </div>
  );
}
