import React, { useState, useEffect } from "react";
import { getExplorerSourceRows } from "../../../api/client";
import { ShieldCheck, Database, AlertCircle } from "lucide-react";
import StatusBadge from "../common/StatusBadge";
import DataTable from "../../DataTable";

/**
 * HighView Data Explorer — Data (Source Records)
 * Displays authentic source records without derived columns.
 * Upgraded to use full-featured enterprise DataTable with full-dataset server-side sorting,
 * server pagination, column visibility manager, and exact unrounded tooltips.
 */
export default function SourceMode({
  datasetId,
  sheets = [],
  selectedSheetId,
  onSelectSheet,
  themeTokens,
  isDark = false,
}) {
  const [activeSheet, setActiveSheet] = useState(
    () => selectedSheetId || (sheets[0]?.sheet_id || sheets[0]?.name || "")
  );
  const [rowsData, setRowsData] = useState(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);
  const [page, setPage] = useState(1);
  const [pageSize, setPageSize] = useState(25);
  const [searchTerm, setSearchTerm] = useState("");
  const [sortCol, setSortCol] = useState(null);
  const [sortDir, setSortDir] = useState(null);

  const bgSurface = themeTokens?.colors?.surface || "var(--color-bg-surface)";
  const borderCol = themeTokens?.colors?.borderSubtle || "var(--color-divider)";
  const textPrimary = themeTokens?.colors?.textPrimary || "var(--color-text-primary)";
  const textSecondary = themeTokens?.colors?.textSecondary || "var(--color-text-secondary)";
  const brandPrimary = themeTokens?.colors?.brandPrimary || "var(--color-brand-primary)";
  const brandSoftBg = themeTokens?.colors?.softBlue || "var(--color-bg-soft-blue)";

  useEffect(() => {
    if (selectedSheetId && sheets.some((s) => (s.sheet_id || s.name) === selectedSheetId)) {
      setActiveSheet(selectedSheetId);
      setPage(1);
    } else if (sheets.length > 0 && !sheets.some((s) => (s.sheet_id || s.name) === activeSheet)) {
      setActiveSheet(sheets[0].sheet_id || sheets[0].name);
      setPage(1);
    }
  }, [selectedSheetId, sheets, activeSheet]);

  useEffect(() => {
    if (!datasetId || !activeSheet) return;
    let isCancelled = false;

    async function loadRows() {
      setLoading(true);
      setError(null);
      try {
        const res = await getExplorerSourceRows(
          datasetId,
          activeSheet,
          page,
          pageSize,
          searchTerm,
          sortCol,
          sortDir
        );
        if (!isCancelled) {
          setRowsData(res);
        }
      } catch (err) {
        if (!isCancelled) {
          setError(err.message || "Failed to load source records");
        }
      } finally {
        if (!isCancelled) {
          setLoading(false);
        }
      }
    }

    loadRows();
    return () => {
      isCancelled = true;
    };
  }, [datasetId, activeSheet, page, pageSize, searchTerm, sortCol, sortDir]);

  const handleSheetChange = (sheetId) => {
    setActiveSheet(sheetId);
    setPage(1);
    setSearchTerm("");
    setSortCol(null);
    setSortDir(null);
    if (onSelectSheet) onSelectSheet(sheetId);
  };

  const handleSortChange = (newSortCol, newSortDir) => {
    setSortCol(newSortCol);
    setSortDir(newSortDir);
    setPage(1);
  };

  const handleSearchChange = (query) => {
    setSearchTerm(query);
    setPage(1);
  };

  const totalPages = rowsData ? Math.max(1, Math.ceil(rowsData.total_rows / pageSize)) : 1;

  return (
    <div className="sdr-source-mode-container" style={{ display: "flex", flexDirection: "column", gap: "16px" }}>
      {/* Header & Exactness Guarantee */}
      <div
        style={{
          background: bgSurface,
          border: `1px solid ${borderCol}`,
          borderRadius: "10px",
          padding: "16px",
          display: "flex",
          flexDirection: "column",
          gap: "12px",
        }}
      >
        <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", flexWrap: "wrap", gap: "10px" }}>
          <div style={{ display: "flex", alignItems: "center", gap: "8px" }}>
            <Database size={18} color={brandPrimary} aria-hidden="true" />
            <h2 style={{ margin: 0, fontSize: "1.1rem", fontWeight: 700, color: textPrimary }}>
              Source Data
            </h2>
          </div>
          <div style={{ display: "flex", alignItems: "center", gap: "8px", flexWrap: "wrap" }}>
            <StatusBadge status="Exact raw values" variant="success" icon={ShieldCheck} />
            <StatusBadge status="0 derived columns" variant="neutral" />
          </div>
        </div>
        <p style={{ margin: 0, fontSize: "0.82rem", color: textSecondary }}>
          Authentic uploaded records with intact identifiers and preserved precision.
        </p>

        {/* Sheet Selector Pills */}
        <div style={{ display: "flex", alignItems: "center", gap: "6px", overflowX: "auto", paddingTop: "4px" }}>
          {sheets.map((s) => {
            const sid = s.sheet_id || s.name;
            const isSelected = sid === activeSheet;
            return (
              <button
                key={sid}
                type="button"
                onClick={() => handleSheetChange(sid)}
                style={{
                  padding: "6px 12px",
                  fontSize: "0.8rem",
                  fontWeight: isSelected ? 700 : 500,
                  borderRadius: "8px",
                  border: isSelected ? `1px solid ${brandPrimary}` : `1px solid ${borderCol}`,
                  background: isSelected ? brandSoftBg : "transparent",
                  color: isSelected ? brandPrimary : textSecondary,
                  cursor: "pointer",
                  whiteSpace: "nowrap",
                  transition: "all 0.15s ease",
                }}
              >
                {s.display_name || s.name} ({s.row_count || 0})
              </button>
            );
          })}
        </div>
      </div>

      {/* Error state if API call failed */}
      {error && (
        <div
          style={{
            padding: "16px",
            background: "var(--color-bg-soft-error, #FAEAEE)",
            border: "1px solid var(--color-error, #8E1938)",
            borderRadius: "8px",
            color: "var(--color-error, #8E1938)",
            display: "flex",
            alignItems: "center",
            gap: "8px",
            fontSize: "0.85rem",
          }}
        >
          <AlertCircle size={16} />
          <span>{error}</span>
        </div>
      )}

      {/* Full-featured Enterprise DataTable */}
      <DataTable
        columns={rowsData ? rowsData.columns : []}
        rows={rowsData ? rowsData.rows : []}
        rowKeyProp="__row_index"
        showRowIndex={true}
        serverSide={true}
        totalRows={rowsData ? rowsData.total_rows : 0}
        serverPage={page}
        serverTotalPages={totalPages}
        onPageChange={setPage}
        pageSize={pageSize}
        onPageSizeChange={(newSize) => {
          setPageSize(newSize);
          setPage(1);
        }}
        searchQuery={searchTerm}
        onSearchChange={handleSearchChange}
        searchPlaceholder="Search raw values across sheet..."
        onSortChange={handleSortChange}
        enableColumnVisibility={true}
        showExport={true}
        sourceLabel={activeSheet}
        loading={loading}
        tableAriaLabel={`${activeSheet} source records table`}
        emptyMessage="No source records matched your query."
      />
    </div>
  );
}
