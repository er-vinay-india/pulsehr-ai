import React, { useState, useEffect, useMemo } from "react";
import { getExplorerProfiling } from "../../../api/client";
import ProfileDetailDrawer from "./ProfileDetailDrawer";
import StatusBadge from "../common/StatusBadge";
import DataTable from "../../DataTable";
import { SkeletonBlock } from "../../loaders";
import {
  Activity,
  Layers,
  AlertTriangle,
  Eye,
  CheckCircle2,
  Table,
  Hash,
  Percent,
  Search,
  Filter,
} from "lucide-react";

/**
 * HighView Data Explorer — Data Profile
 * "Understand data quality, distributions, ranges, and unusual values."
 * Deterministic structural profiling: completeness, types, distributions,
 * Tukey IQR 1.5 outliers, and quality status.
 */
export default function DataProfileMode({
  datasetId,
  sheets = [],
  selectedSheetId,
  onSelectSheet,
  themeTokens,
  isDark = false,
}) {
  const [activeSheet, setActiveSheet] = useState(() => selectedSheetId || "");
  const [profileData, setProfileData] = useState(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);
  const [selectedColumn, setSelectedColumn] = useState(null);
  const [quickFilter, setQuickFilter] = useState("all"); // 'all' | 'attention' | 'outliers' | 'missing' | 'numeric' | 'categorical'

  const bgSurface = themeTokens?.colors?.surface || "var(--color-bg-surface)";
  const bgSubtle = themeTokens?.colors?.surfaceHover || "var(--color-bg-subtle)";
  const borderCol = themeTokens?.colors?.borderSubtle || "var(--color-divider)";
  const borderStrong = themeTokens?.colors?.border || "var(--color-border)";
  const textPrimary = themeTokens?.colors?.textPrimary || "var(--color-text-primary)";
  const textSecondary = themeTokens?.colors?.textSecondary || "var(--color-text-secondary)";
  const textMuted = themeTokens?.colors?.textMuted || "var(--color-text-muted)";
  const brandPrimary = themeTokens?.colors?.brandPrimary || "var(--color-brand-primary)";
  const brandSoftBg = themeTokens?.colors?.softBlue || "var(--color-bg-soft-blue)";

  useEffect(() => {
    if (selectedSheetId !== undefined && selectedSheetId !== activeSheet) {
      setActiveSheet(selectedSheetId);
    }
  }, [selectedSheetId]);

  useEffect(() => {
    if (!datasetId) return;
    let isCancelled = false;

    async function loadProfile() {
      setLoading(true);
      setError(null);
      try {
        const res = await getExplorerProfiling(datasetId, activeSheet || null);
        if (!isCancelled) {
          setProfileData(res);
        }
      } catch (err) {
        if (!isCancelled) {
          setError(err.message || "Failed to load data profile");
        }
      } finally {
        if (!isCancelled) {
          setLoading(false);
        }
      }
    }

    loadProfile();
    return () => {
      isCancelled = true;
    };
  }, [datasetId, activeSheet]);

  const handleSheetFilter = (sheetId) => {
    setActiveSheet(sheetId);
    if (onSelectSheet) onSelectSheet(sheetId);
  };

  const rawColumns = profileData?.columns || [];
  const summary = profileData?.summary || {
    total_rows: 0,
    total_columns: rawColumns.length,
    completeness_pct: 100,
    numeric_columns: rawColumns.filter((c) => c.is_numeric).length,
    categorical_columns: rawColumns.filter((c) => !c.is_numeric).length,
    columns_with_outliers: rawColumns.filter((c) => (c.outlier_count || 0) > 0).length,
    columns_needing_attention: rawColumns.filter((c) => c.status === "Needs Attention" || c.status === "Missing Values").length,
  };

  // Filter columns based on quickFilter
  const filteredColumns = useMemo(() => {
    if (quickFilter === "attention") {
      return rawColumns.filter((c) => c.status === "Needs Attention" || c.status === "Missing Values");
    }
    if (quickFilter === "outliers") {
      return rawColumns.filter((c) => (c.outlier_count || 0) > 0);
    }
    if (quickFilter === "missing") {
      return rawColumns.filter((c) => (c.null_count || 0) > 0);
    }
    if (quickFilter === "numeric") {
      return rawColumns.filter((c) => c.is_numeric);
    }
    if (quickFilter === "categorical") {
      return rawColumns.filter((c) => !c.is_numeric);
    }
    return rawColumns;
  }, [rawColumns, quickFilter]);

  // Available sheets from profileData or fallback to sheets prop
  const effectiveSheets = useMemo(() => {
    if (profileData?.sheets && profileData.sheets.length > 0) {
      return profileData.sheets;
    }
    return sheets;
  }, [profileData?.sheets, sheets]);

  // DataTable column definitions
  const tableColumns = useMemo(
    () => [
      {
        key: "column",
        label: "Column",
        type: "text",
        sortable: true,
        defaultVisible: true,
        render: (val, row) => (
          <div style={{ display: "flex", flexDirection: "column", gap: "2px" }}>
            <span style={{ fontWeight: 600, color: textPrimary, fontSize: "0.82rem" }}>
              {val}
            </span>
          </div>
        ),
      },
      {
        key: "sheet_name",
        label: "Sheet",
        type: "text",
        sortable: true,
        defaultVisible: true,
        render: (val) => (
          <span style={{ fontSize: "0.78rem", color: textSecondary }}>
            {val || "—"}
          </span>
        ),
      },
      {
        key: "data_type",
        label: "Type",
        type: "text",
        sortable: true,
        defaultVisible: true,
        render: (val, row) => (
          <span
            style={{
              display: "inline-block",
              padding: "2px 8px",
              borderRadius: "4px",
              fontSize: "0.74rem",
              fontWeight: 600,
              background: bgSubtle,
              border: `1px solid ${borderCol}`,
              color: textPrimary,
            }}
          >
            {val || "Categorical"}
          </span>
        ),
      },
      {
        key: "completeness",
        label: "Non-null %",
        type: "percentage",
        sortable: true,
        defaultVisible: true,
        sortVal: (row) => row.populated_pct ?? 100,
        render: (_, row) => {
          const pop = row.populated_pct ?? 100;
          const nullCnt = row.null_count ?? 0;
          return (
            <div style={{ display: "flex", alignItems: "center", gap: "8px", minWidth: "115px" }}>
              <div
                style={{
                  flex: 1,
                  height: "6px",
                  borderRadius: "3px",
                  backgroundColor: nullCnt > 0 ? "var(--color-bg-soft-warning, #FEF3C7)" : "var(--color-bg-soft-teal, #E7F3ED)",
                  overflow: "hidden",
                  display: "flex",
                }}
                title={`${pop}% populated, ${nullCnt} missing`}
              >
                <div
                  style={{
                    width: `${pop}%`,
                    height: "100%",
                    backgroundColor: brandPrimary,
                  }}
                />
              </div>
              <span style={{ fontSize: "0.75rem", fontWeight: 600, color: textPrimary, width: "36px", textAlign: "right" }}>
                {pop}%
              </span>
            </div>
          );
        },
      },
      {
        key: "distinct_count",
        label: "Distinct %",
        type: "numeric",
        sortable: true,
        defaultVisible: true,
        sortVal: (row) => row.distinct_pct ?? 0,
        render: (val, row) => (
          <span style={{ fontSize: "0.78rem", color: textSecondary }}>
            <strong style={{ color: textPrimary }}>{row.distinct_pct != null ? `${row.distinct_pct}%` : "—"}</strong>
            {row.distinct_count != null ? ` (${row.distinct_count.toLocaleString()})` : ""}
          </span>
        ),
      },
      {
        key: "min",
        label: "Min",
        type: "numeric",
        sortable: true,
        defaultVisible: true,
        sortVal: (row) => (row.min != null ? Number(row.min) : -Infinity),
        render: (val, row) => (
          <span style={{ fontSize: "0.78rem", color: textSecondary }}>
            {row.is_numeric && val != null ? Number(val).toLocaleString() : "—"}
          </span>
        ),
      },
      {
        key: "max",
        label: "Max",
        type: "numeric",
        sortable: true,
        defaultVisible: true,
        sortVal: (row) => (row.max != null ? Number(row.max) : -Infinity),
        render: (val, row) => (
          <span style={{ fontSize: "0.78rem", color: textSecondary }}>
            {row.is_numeric && val != null ? Number(val).toLocaleString() : "—"}
          </span>
        ),
      },
      {
        key: "mean_median",
        label: "Mean / Median",
        type: "text",
        sortable: true,
        defaultVisible: true,
        sortVal: (row) => (row.mean != null ? Number(row.mean) : -Infinity),
        render: (_, row) => {
          if (!row.is_numeric || (row.mean == null && row.median == null)) {
            return <span style={{ color: textMuted }}>—</span>;
          }
          return (
            <span style={{ fontSize: "0.76rem", color: textSecondary }}>
              <span title="Mean">{row.mean != null ? row.mean.toLocaleString() : "—"}</span>
              <span style={{ color: textMuted, margin: "0 4px" }}>/</span>
              <span title="Median" style={{ color: textPrimary, fontWeight: 600 }}>{row.median != null ? row.median.toLocaleString() : "—"}</span>
            </span>
          );
        },
      },
      {
        key: "outliers",
        label: "Outliers",
        type: "numeric",
        sortable: true,
        defaultVisible: true,
        sortVal: (row) => row.outlier_count ?? 0,
        render: (val, row) => {
          if (!row.is_numeric) return <span style={{ color: textMuted }}>—</span>;
          const count = row.outlier_count || 0;
          if (count > 0) {
            return (
              <span
                style={{
                  display: "inline-flex",
                  alignItems: "center",
                  gap: "4px",
                  padding: "2px 8px",
                  borderRadius: "4px",
                  fontSize: "0.74rem",
                  fontWeight: 600,
                  backgroundColor: "var(--color-bg-soft-warning, #FEF3C7)",
                  color: "var(--color-warning, #D97706)",
                }}
              >
                <AlertTriangle size={11} />
                {count} potential
              </span>
            );
          }
          return <span style={{ fontSize: "0.76rem", color: textMuted }}>0</span>;
        },
      },
      {
        key: "status",
        label: "Status",
        type: "status",
        sortable: true,
        defaultVisible: true,
        sortVal: (row) => {
          if (row.status === "Needs Attention") return 4;
          if (row.status === "Potential Outliers") return 3;
          if (row.status === "Missing Values") return 2;
          return 1;
        },
        render: (val) => <StatusBadge status={val} />,
      },
      {
        key: "actions",
        label: "",
        sortable: false,
        filterable: false,
        defaultVisible: true,
        width: "50px",
        render: (_, row) => (
          <button
            type="button"
            onClick={(e) => {
              e.stopPropagation();
              setSelectedColumn(row);
            }}
            aria-label={`Inspect ${row.column}`}
            style={{
              padding: "4px 8px",
              fontSize: "0.72rem",
              fontWeight: 600,
              borderRadius: "4px",
              border: `1px solid ${borderCol}`,
              background: bgSurface,
              color: brandPrimary,
              cursor: "pointer",
              display: "inline-flex",
              alignItems: "center",
              gap: "4px",
            }}
          >
            <Eye size={12} />
            Inspect
          </button>
        ),
      },
    ],
    [bgSurface, bgSubtle, borderCol, brandPrimary, textPrimary, textSecondary, textMuted]
  );

  return (
    <div
      className="data-profile-mode"
      style={{
        display: "flex",
        flexDirection: "column",
        gap: "16px",
      }}
    >
      {/* 1. Header & Sheet Selector */}
      <div
        style={{
          background: bgSurface,
          border: `1px solid ${borderCol}`,
          borderRadius: "10px",
          padding: "16px 20px",
          display: "flex",
          flexDirection: "column",
          gap: "12px",
        }}
      >
        <div style={{ display: "flex", alignItems: "center", gap: "8px" }}>
          <Activity size={18} color={brandPrimary} />
          <h2 style={{ margin: 0, fontSize: "1.05rem", fontWeight: 700, color: textPrimary }}>
            Data Profile
          </h2>
        </div>
        <p style={{ margin: 0, fontSize: "0.82rem", color: textSecondary }}>
          Understand data quality, distributions, ranges, and unusual values.
        </p>

        {/* Sheet Selector Pills (if multiple sheets exist) */}
        {effectiveSheets && effectiveSheets.length > 0 && (
          <div style={{ display: "flex", alignItems: "center", gap: "6px", overflowX: "auto", paddingTop: "4px" }}>
            <button
              type="button"
              onClick={() => handleSheetFilter("")}
              style={{
                padding: "6px 12px",
                fontSize: "0.8rem",
                fontWeight: activeSheet === "" ? 700 : 500,
                borderRadius: "8px",
                border: activeSheet === "" ? `1px solid ${brandPrimary}` : `1px solid ${borderCol}`,
                background: activeSheet === "" ? brandSoftBg : "transparent",
                color: activeSheet === "" ? brandPrimary : textSecondary,
                cursor: "pointer",
                whiteSpace: "nowrap",
                transition: "all 0.15s ease",
              }}
            >
              All Sheets
            </button>
            {effectiveSheets.map((s) => {
              const sid = s.sheet_id || s.name || s.id;
              const isSelected = String(sid) === String(activeSheet);
              return (
                <button
                  key={sid}
                  type="button"
                  onClick={() => handleSheetFilter(sid)}
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
                  {s.display_name || s.name}
                </button>
              );
            })}
          </div>
        )}
      </div>

      {/* 2. Compact Summary Strip */}
      <div
        style={{
          display: "grid",
          gridTemplateColumns: "repeat(auto-fit, minmax(130px, 1fr))",
          gap: "10px",
        }}
      >
        <div
          style={{
            background: bgSurface,
            border: `1px solid ${borderCol}`,
            borderRadius: "8px",
            padding: "12px 14px",
          }}
        >
          <div style={{ fontSize: "0.72rem", color: textMuted }}>Total Rows</div>
          <div style={{ fontSize: "1.05rem", fontWeight: 700, color: textPrimary, marginTop: "2px" }}>
            {summary.total_rows ? summary.total_rows.toLocaleString() : "—"}
          </div>
        </div>

        <div
          style={{
            background: bgSurface,
            border: `1px solid ${borderCol}`,
            borderRadius: "8px",
            padding: "12px 14px",
          }}
        >
          <div style={{ fontSize: "0.72rem", color: textMuted }}>Total Columns</div>
          <div style={{ fontSize: "1.05rem", fontWeight: 700, color: textPrimary, marginTop: "2px" }}>
            {summary.total_columns ? summary.total_columns.toLocaleString() : "0"}
          </div>
        </div>

        <div
          style={{
            background: bgSurface,
            border: `1px solid ${borderCol}`,
            borderRadius: "8px",
            padding: "12px 14px",
          }}
        >
          <div style={{ fontSize: "0.72rem", color: textMuted }}>Completeness</div>
          <div style={{ fontSize: "1.05rem", fontWeight: 700, color: summary.completeness_pct >= 95 ? "var(--color-success, #075443)" : "var(--color-warning, #D97706)", marginTop: "2px" }}>
            {summary.completeness_pct != null ? `${summary.completeness_pct}%` : "100%"}
          </div>
        </div>

        <div
          style={{
            background: bgSurface,
            border: `1px solid ${borderCol}`,
            borderRadius: "8px",
            padding: "12px 14px",
          }}
        >
          <div style={{ fontSize: "0.72rem", color: textMuted }}>Numeric</div>
          <div style={{ fontSize: "1.05rem", fontWeight: 700, color: textPrimary, marginTop: "2px" }}>
            {summary.numeric_columns ?? 0}
          </div>
        </div>

        <div
          style={{
            background: bgSurface,
            border: `1px solid ${borderCol}`,
            borderRadius: "8px",
            padding: "12px 14px",
          }}
        >
          <div style={{ fontSize: "0.72rem", color: textMuted }}>Categorical</div>
          <div style={{ fontSize: "1.05rem", fontWeight: 700, color: textPrimary, marginTop: "2px" }}>
            {summary.categorical_columns ?? 0}
          </div>
        </div>

        <div
          style={{
            background: bgSurface,
            border: `1px solid ${borderCol}`,
            borderRadius: "8px",
            padding: "12px 14px",
          }}
        >
          <div style={{ fontSize: "0.72rem", color: textMuted }}>With Outliers</div>
          <div style={{ fontSize: "1.05rem", fontWeight: 700, color: summary.columns_with_outliers > 0 ? "var(--color-warning, #D97706)" : textPrimary, marginTop: "2px" }}>
            {summary.columns_with_outliers ?? 0}
          </div>
        </div>

        <div
          style={{
            background: bgSurface,
            border: `1px solid ${borderCol}`,
            borderRadius: "8px",
            padding: "12px 14px",
          }}
        >
          <div style={{ fontSize: "0.72rem", color: textMuted }}>Needs Attention</div>
          <div style={{ fontSize: "1.05rem", fontWeight: 700, color: summary.columns_needing_attention > 0 ? "var(--color-error, #8E1938)" : "var(--color-success, #075443)", marginTop: "2px" }}>
            {summary.columns_needing_attention ?? 0}
          </div>
        </div>
      </div>

      {/* 3. Quick Filter Tabs */}
      <div style={{ display: "flex", alignItems: "center", gap: "6px", overflowX: "auto" }}>
        {[
          { id: "all", label: `All Columns (${rawColumns.length})` },
          { id: "attention", label: `Needs Attention (${rawColumns.filter((c) => c.status === "Needs Attention" || c.status === "Missing Values").length})` },
          { id: "outliers", label: `Has Outliers (${rawColumns.filter((c) => (c.outlier_count || 0) > 0).length})` },
          { id: "missing", label: `Has Missing Values (${rawColumns.filter((c) => (c.null_count || 0) > 0).length})` },
          { id: "numeric", label: `Numeric (${rawColumns.filter((c) => c.is_numeric).length})` },
          { id: "categorical", label: `Categorical (${rawColumns.filter((c) => !c.is_numeric).length})` },
        ].map((f) => {
          const isActive = quickFilter === f.id;
          return (
            <button
              key={f.id}
              type="button"
              onClick={() => setQuickFilter(f.id)}
              style={{
                padding: "6px 12px",
                fontSize: "0.8rem",
                fontWeight: isActive ? 700 : 500,
                borderRadius: "8px",
                border: isActive ? `1px solid ${brandPrimary}` : `1px solid ${borderCol}`,
                background: isActive ? brandSoftBg : "transparent",
                color: isActive ? brandPrimary : textSecondary,
                cursor: "pointer",
                whiteSpace: "nowrap",
                transition: "all 0.15s ease",
              }}
            >
              {f.label}
            </button>
          );
        })}
      </div>

      {/* 4. Table Surface */}
      {loading ? (
        <div
          role="status"
          aria-label="Loading data profile"
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
          <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
            <span style={{ fontSize: "0.82rem", fontWeight: 600, color: textSecondary }}>
              Profiling columns, distributions, and missingness…
            </span>
          </div>
          <SkeletonBlock variant="table-row" count={8} columns={8} />
        </div>
      ) : error ? (
        <div
          style={{
            padding: "16px",
            background: "var(--color-bg-soft-error, #FAEAEE)",
            border: "1px solid var(--color-error, #8E1938)",
            borderRadius: "8px",
            color: "var(--color-error, #8E1938)",
            fontSize: "0.82rem",
          }}
        >
          {error}
        </div>
      ) : filteredColumns.length === 0 ? (
        <div
          style={{
            background: bgSurface,
            border: `1px solid ${borderCol}`,
            borderRadius: "10px",
            padding: "36px 20px",
            textAlign: "center",
          }}
        >
          <p style={{ margin: 0, fontSize: "0.88rem", color: textSecondary }}>
            No profiling information is available for this dataset.
          </p>
        </div>
      ) : (
        <div
          style={{
            background: bgSurface,
            border: `1px solid ${borderCol}`,
            borderRadius: "10px",
            padding: "16px",
          }}
        >
          <DataTable
            columns={tableColumns}
            rows={filteredColumns}
            totalRows={filteredColumns.length}
            pageSize={25}
            searchable={true}
            searchPlaceholder="Search columns or sheets…"
            columnVisibilityEnabled={true}
            onRowClick={(row) => setSelectedColumn(row)}
            emptyMessage="No matching columns found."
          />
        </div>
      )}

      {/* 5. Column Detail Drawer */}
      {selectedColumn && (
        <ProfileDetailDrawer
          column={selectedColumn}
          onClose={() => setSelectedColumn(null)}
          themeTokens={themeTokens}
          isDark={isDark}
        />
      )}
    </div>
  );
}
