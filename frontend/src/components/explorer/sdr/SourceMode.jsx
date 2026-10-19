import React, { useState, useEffect } from "react";
import { getExplorerSourceRows } from "../../../api/client";
import { Table, Search, ChevronLeft, ChevronRight, ShieldCheck, Database, AlertCircle } from "lucide-react";

export default function SourceMode({
  datasetId,
  sheets = [],
  selectedSheetId,
  onSelectSheet,
  themeTokens,
  isDark = false,
}) {
  const [activeSheet, setActiveSheet] = useState(() => selectedSheetId || (sheets[0]?.sheet_id || sheets[0]?.name || ""));
  const [rowsData, setRowsData] = useState(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);
  const [page, setPage] = useState(1);
  const [pageSize] = useState(25);
  const [searchTerm, setSearchTerm] = useState("");
  const [searchInput, setSearchInput] = useState("");
  useEffect(() => {
    if (selectedSheetId && sheets.some(s => (s.sheet_id || s.name) === selectedSheetId)) {
      setActiveSheet(selectedSheetId);
      setPage(1);
    } else if (sheets.length > 0 && !sheets.some(s => (s.sheet_id || s.name) === activeSheet)) {
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
        const res = await getExplorerSourceRows(datasetId, activeSheet, page, pageSize, searchTerm);
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
  }, [datasetId, activeSheet, page, pageSize, searchTerm]);

  const handleSearchSubmit = (e) => {
    e.preventDefault();
    setSearchTerm(searchInput.trim());
    setPage(1);
  };

  const handleSheetChange = (sheetId) => {
    setActiveSheet(sheetId);
    setPage(1);
    setSearchInput("");
    setSearchTerm("");
    if (onSelectSheet) onSelectSheet(sheetId);
  };

  const totalPages = rowsData ? Math.max(1, Math.ceil(rowsData.total_rows / pageSize)) : 1;

  const bgCard = isDark ? "#1e293b" : "#ffffff";
  const borderCol = isDark ? "#334155" : "#e2e8f0";
  const textPrimary = isDark ? "#f8fafc" : "#0f172a";
  const textSecondary = isDark ? "#94a3b8" : "#64748b";

  return (
    <div className="sdr-source-mode-container" style={{ display: "flex", flexDirection: "column", gap: "16px" }}>
      {/* Header & Exactness Guarantee Banner */}
      <div
        style={{
          background: isDark ? "rgba(30, 41, 59, 0.7)" : "#ffffff",
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
            <Database size={18} color="#2563eb" />
            <h2 style={{ margin: 0, fontSize: "1.1rem", fontWeight: 700, color: textPrimary }}>
              Source Data (Raw Observed Evidence)
            </h2>
          </div>
          <div style={{ display: "flex", alignItems: "center", gap: "8px", flexWrap: "wrap" }}>
            <span
              style={{
                display: "inline-flex",
                alignItems: "center",
                gap: "5px",
                fontSize: "0.75rem",
                fontWeight: 600,
                padding: "3px 8px",
                borderRadius: "6px",
                background: "rgba(16, 185, 129, 0.12)",
                color: "#10b981",
                border: "1px solid rgba(16, 185, 129, 0.3)",
              }}
            >
              <ShieldCheck size={13} />
              Exactness-First · Raw Values
            </span>
            <span
              style={{
                display: "inline-flex",
                alignItems: "center",
                gap: "5px",
                fontSize: "0.75rem",
                fontWeight: 600,
                padding: "3px 8px",
                borderRadius: "6px",
                background: "rgba(99, 102, 241, 0.12)",
                color: "#6366f1",
                border: "1px solid rgba(99, 102, 241, 0.3)",
              }}
            >
              0 Derived Columns Masquerading
            </span>
          </div>
        </div>
        <p style={{ margin: 0, fontSize: "0.82rem", color: textSecondary }}>
          Displays authentic uploaded records with zero synthetic derivations, intact leading zeros, and uncompacted identifiers.
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
                  border: isSelected ? "1px solid #2563eb" : `1px solid ${borderCol}`,
                  background: isSelected ? (isDark ? "rgba(37, 99, 235, 0.2)" : "rgba(37, 99, 235, 0.08)") : "transparent",
                  color: isSelected ? "#2563eb" : textSecondary,
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

      {/* Search & Pagination Bar */}
      <div
        style={{
          display: "flex",
          justifyContent: "space-between",
          alignItems: "center",
          flexWrap: "wrap",
          gap: "10px",
        }}
      >
        <form onSubmit={handleSearchSubmit} style={{ display: "flex", alignItems: "center", gap: "6px" }}>
          <div
            style={{
              display: "flex",
              alignItems: "center",
              gap: "6px",
              background: bgCard,
              border: `1px solid ${borderCol}`,
              borderRadius: "8px",
              padding: "5px 10px",
            }}
          >
            <Search size={14} color={textSecondary} />
            <input
              type="text"
              placeholder="Search raw values..."
              value={searchInput}
              onChange={(e) => setSearchInput(e.target.value)}
              style={{
                border: "none",
                background: "transparent",
                color: textPrimary,
                fontSize: "0.82rem",
                outline: "none",
                width: "180px",
              }}
            />
          </div>
          <button
            type="submit"
            style={{
              padding: "6px 12px",
              fontSize: "0.8rem",
              fontWeight: 600,
              background: "#2563eb",
              color: "#ffffff",
              border: "none",
              borderRadius: "8px",
              cursor: "pointer",
            }}
          >
            Filter
          </button>
          {searchTerm && (
            <button
              type="button"
              onClick={() => {
                setSearchInput("");
                setSearchTerm("");
                setPage(1);
              }}
              style={{
                padding: "6px 10px",
                fontSize: "0.78rem",
                background: "transparent",
                color: textSecondary,
                border: `1px solid ${borderCol}`,
                borderRadius: "8px",
                cursor: "pointer",
              }}
            >
              Clear
            </button>
          )}
        </form>

        {rowsData && (
          <div style={{ display: "flex", alignItems: "center", gap: "10px", fontSize: "0.8rem", color: textSecondary }}>
            <span>
              Showing {rowsData.rows.length} of {rowsData.total_rows} records
            </span>
            <div style={{ display: "flex", alignItems: "center", gap: "4px" }}>
              <button
                type="button"
                disabled={page <= 1 || loading}
                onClick={() => setPage((p) => Math.max(1, p - 1))}
                style={{
                  padding: "4px 8px",
                  borderRadius: "6px",
                  border: `1px solid ${borderCol}`,
                  background: bgCard,
                  color: page <= 1 ? (isDark ? "#475569" : "#cbd5e1") : textPrimary,
                  cursor: page <= 1 ? "not-allowed" : "pointer",
                  display: "flex",
                  alignItems: "center",
                }}
              >
                <ChevronLeft size={14} />
              </button>
              <span style={{ fontWeight: 600 }}>
                {page} / {totalPages}
              </span>
              <button
                type="button"
                disabled={page >= totalPages || loading}
                onClick={() => setPage((p) => Math.min(totalPages, p + 1))}
                style={{
                  padding: "4px 8px",
                  borderRadius: "6px",
                  border: `1px solid ${borderCol}`,
                  background: bgCard,
                  color: page >= totalPages ? (isDark ? "#475569" : "#cbd5e1") : textPrimary,
                  cursor: page >= totalPages ? "not-allowed" : "pointer",
                  display: "flex",
                  alignItems: "center",
                }}
              >
                <ChevronRight size={14} />
              </button>
            </div>
          </div>
        )}
      </div>

      {/* Main Table Content */}
      {loading ? (
        <div style={{ padding: "40px", textAlign: "center", color: textSecondary, fontSize: "0.9rem" }}>
          Loading exact source records…
        </div>
      ) : error ? (
        <div
          style={{
            padding: "16px",
            background: "rgba(239, 68, 68, 0.1)",
            border: "1px solid rgba(239, 68, 68, 0.3)",
            borderRadius: "8px",
            color: "#ef4444",
            display: "flex",
            alignItems: "center",
            gap: "8px",
            fontSize: "0.85rem",
          }}
        >
          <AlertCircle size={16} />
          <span>{error}</span>
        </div>
      ) : rowsData && rowsData.rows.length > 0 ? (
        <div
          style={{
            overflowX: "auto",
            background: bgCard,
            border: `1px solid ${borderCol}`,
            borderRadius: "10px",
          }}
        >
          <table
            style={{
              width: "100%",
              borderCollapse: "collapse",
              fontSize: "0.82rem",
              textAlign: "left",
            }}
          >
            <thead>
              <tr style={{ background: isDark ? "#0f172a" : "#f8fafc", borderBottom: `2px solid ${borderCol}` }}>
                <th style={{ padding: "10px 12px", width: "50px", color: textSecondary, fontWeight: 700 }}>
                  #
                </th>
                {rowsData.columns.map((col) => (
                  <th key={col} style={{ padding: "10px 12px", color: textPrimary, fontWeight: 700 }}>
                    {col}
                  </th>
                ))}
              </tr>
            </thead>
            <tbody>
              {rowsData.rows.map((row, idx) => (
                <tr
                  key={row.__row_index || idx}
                  style={{
                    borderBottom: `1px solid ${borderCol}`,
                    background: idx % 2 === 1 ? (isDark ? "rgba(255,255,255,0.02)" : "rgba(0,0,0,0.015)") : "transparent",
                  }}
                >
                  <td style={{ padding: "10px 12px", color: textSecondary, fontWeight: 600 }}>
                    {row.__row_index}
                  </td>
                  {rowsData.columns.map((col) => {
                    const val = row[col];
                    const isNull = val === null || val === undefined;
                    return (
                      <td
                        key={col}
                        style={{
                          padding: "10px 12px",
                          color: isNull ? (isDark ? "#64748b" : "#94a3b8") : textPrimary,
                          fontFamily: typeof val === "number" || (typeof val === "string" && /^\d+$/.test(val)) ? "monospace" : "inherit",
                          fontStyle: isNull ? "italic" : "normal",
                          whiteSpace: "nowrap",
                        }}
                      >
                        {isNull ? "null" : String(val)}
                      </td>
                    );
                  })}
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      ) : (
        <div style={{ padding: "40px", textAlign: "center", color: textSecondary, fontSize: "0.9rem" }}>
          No source records matched your query.
        </div>
      )}
    </div>
  );
}
