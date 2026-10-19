import React from "react";
import {
  FileSpreadsheet,
  Layers,
  Award,
  TrendingUp,
  GitMerge,
  BarChart2,
  AlertTriangle,
  ArrowRight,
  Database,
  Calendar,
  Sparkles,
} from "lucide-react";

export default function OverviewExplorer({
  activeDataset,
  selectedSheet,
  catalog,
  dataHealth,
  rankingSchema,
  onNavigateTab,
  themeTokens,
  isDark = false,
}) {
  const sheets = (catalog?.sheets || []).filter((sheet) => String(sheet.dataset_id) === String(selectedSheet?.dataset_id));
  const entities = rankingSchema?.entities || [];
  const measures = rankingSchema?.measures || [];
  const totalRows = selectedSheet?.row_count || activeDataset?.row_count || 0;
  const colCount = selectedSheet?.columns?.length || 0;

  return (
    <div
      className="overview-explorer-panel"
      style={{
        display: "flex",
        flexDirection: "column",
        gap: "16px",
      }}
    >
      {/* 1. DATASET / WORKBOOK IDENTITY STRIP */}
      <section
        style={{
          display: "grid",
          gridTemplateColumns: "repeat(auto-fit, minmax(220px, 1fr))",
          gap: "12px",
        }}
      >
        <div
          style={{
            padding: "14px 16px",
            borderRadius: "10px",
            backgroundColor: themeTokens?.colors?.surface,
            border: `1px solid ${themeTokens?.colors?.borderSubtle}`,
          }}
        >
          <span style={{ fontSize: "0.72rem", fontWeight: 700, textTransform: "uppercase", color: themeTokens?.colors?.textSecondary }}>
            Workbook
          </span>
          <div style={{ marginTop: "4px", fontSize: "1.1rem", fontWeight: 700, color: themeTokens?.colors?.textPrimary }}>
            {activeDataset?.original_name || activeDataset?.display_name || selectedSheet?.display_name || "Active Workbook"}
          </div>
          <div style={{ fontSize: "0.76rem", color: themeTokens?.colors?.textMuted, marginTop: "2px" }}>
            {sheets.length} sheet{sheets.length !== 1 ? "s" : ""} · {totalRows.toLocaleString()} rows
          </div>
        </div>

        <div
          style={{
            padding: "14px 16px",
            borderRadius: "10px",
            backgroundColor: themeTokens?.colors?.surface,
            border: `1px solid ${themeTokens?.colors?.borderSubtle}`,
          }}
        >
          <span style={{ fontSize: "0.72rem", fontWeight: 700, textTransform: "uppercase", color: themeTokens?.colors?.textSecondary }}>
            Active Sheet
          </span>
          <div style={{ marginTop: "4px", fontSize: "1.1rem", fontWeight: 700, color: themeTokens?.colors?.textPrimary }}>
            {selectedSheet?.display_name || selectedSheet?.name || "Single Sheet"}
          </div>
          <div style={{ fontSize: "0.76rem", color: themeTokens?.colors?.textMuted, marginTop: "2px" }}>
            {colCount} columns · {selectedSheet?.row_count?.toLocaleString() || 0} rows
          </div>
        </div>

        <div
          style={{
            padding: "14px 16px",
            borderRadius: "10px",
            backgroundColor: themeTokens?.colors?.surface,
            border: `1px solid ${themeTokens?.colors?.borderSubtle}`,
          }}
        >
          <span style={{ fontSize: "0.72rem", fontWeight: 700, textTransform: "uppercase", color: themeTokens?.colors?.textSecondary }}>
            Data completeness
          </span>
          <div style={{ marginTop: "4px", fontSize: "1.1rem", fontWeight: 700, color: dataHealth?.completenessPct >= 95 ? "#10b981" : "#f59e0b" }}>
            {dataHealth?.completenessPct != null ? `${dataHealth.completenessPct}% Complete` : "Not available"}
          </div>
          <div style={{ fontSize: "0.76rem", color: themeTokens?.colors?.textMuted, marginTop: "2px" }}>
            {dataHealth?.totalNullCells || 0} missing cells
          </div>
        </div>
      </section>

      {/* 2. ANALYTICAL MAP (Entities, Measures, Temporal Fields) */}
      <section
        style={{
          display: "grid",
          gridTemplateColumns: "repeat(auto-fit, minmax(300px, 1fr))",
          gap: "14px",
        }}
      >
        {/* Detected Meaningful Entities */}
        <div
          style={{
            padding: "16px",
            borderRadius: "10px",
            backgroundColor: themeTokens?.colors?.surface,
            border: `1px solid ${themeTokens?.colors?.borderSubtle}`,
            display: "flex",
            flexDirection: "column",
            justifyContent: "space-between",
          }}
        >
          <div>
            <div style={{ display: "flex", alignItems: "center", gap: "6px", marginBottom: "8px" }}>
              <Database size={15} color={themeTokens?.colors?.brandBlue || "#2563eb"} />
              <h3 style={{ margin: 0, fontSize: "0.92rem", fontWeight: 700, color: themeTokens?.colors?.textPrimary }}>
                Categories to compare ({entities.length})
              </h3>
            </div>
            <div style={{ display: "flex", flexWrap: "wrap", gap: "6px", marginTop: "6px" }}>
              {entities.map((e) => (
                <span
                  key={e.column}
                  style={{
                    padding: "3px 8px",
                    borderRadius: "6px",
                    fontSize: "0.74rem",
                    fontWeight: 600,
                    backgroundColor: isDark ? "rgba(37, 99, 235, 0.15)" : "rgba(37, 99, 235, 0.08)",
                    color: themeTokens?.colors?.brandBlue || "#2563eb",
                    border: `1px solid ${isDark ? "rgba(37, 99, 235, 0.3)" : "rgba(37, 99, 235, 0.2)"}`,
                  }}
                >
                  {e.display_name} ({e.cardinality} groups)
                </span>
              ))}
              {entities.length === 0 && (
                <span style={{ fontSize: "0.78rem", color: themeTokens?.colors?.textMuted }}>
                  No comparison categories found yet.
                </span>
              )}
            </div>
          </div>
          <button
            type="button"
            onClick={() => onNavigateTab("rankings")}
            style={{
              marginTop: "12px",
              background: "transparent",
              border: "none",
              color: themeTokens?.colors?.brandBlue || "#2563eb",
              fontSize: "0.76rem",
              fontWeight: 600,
              cursor: "pointer",
              display: "inline-flex",
              alignItems: "center",
              gap: "4px",
              padding: 0,
            }}
          >
            <span>View rankings</span>
            <ArrowRight size={12} />
          </button>
        </div>

        {/* Detected Numbers to explore */}
        <div
          style={{
            padding: "16px",
            borderRadius: "10px",
            backgroundColor: themeTokens?.colors?.surface,
            border: `1px solid ${themeTokens?.colors?.borderSubtle}`,
            display: "flex",
            flexDirection: "column",
            justifyContent: "space-between",
          }}
        >
          <div>
            <div style={{ display: "flex", alignItems: "center", gap: "6px", marginBottom: "8px" }}>
              <Award size={15} color="#d97706" />
              <h3 style={{ margin: 0, fontSize: "0.92rem", fontWeight: 700, color: themeTokens?.colors?.textPrimary }}>
                Numbers to explore ({measures.length})
              </h3>
            </div>
            <div style={{ display: "flex", flexWrap: "wrap", gap: "6px", marginTop: "6px" }}>
              {measures.slice(0, 6).map((m) => (
                <span
                  key={m.column}
                  style={{
                    padding: "3px 8px",
                    borderRadius: "6px",
                    fontSize: "0.74rem",
                    fontWeight: 600,
                    backgroundColor: isDark ? "rgba(217, 119, 6, 0.15)" : "rgba(217, 119, 6, 0.08)",
                    color: "#d97706",
                    border: `1px solid ${isDark ? "rgba(217, 119, 6, 0.3)" : "rgba(217, 119, 6, 0.2)"}`,
                  }}
                >
                  {m.measure_label} {m.unit ? `(${m.unit})` : ""}
                </span>
              ))}
              {measures.length > 6 && (
                <span style={{ fontSize: "0.72rem", color: themeTokens?.colors?.textMuted, alignSelf: "center" }}>
                  +{measures.length - 6} more
                </span>
              )}
            </div>
          </div>
          <button
            type="button"
            onClick={() => onNavigateTab("distributions")}
            style={{
              marginTop: "12px",
              background: "transparent",
              border: "none",
              color: "#d97706",
              fontSize: "0.76rem",
              fontWeight: 600,
              cursor: "pointer",
              display: "inline-flex",
              alignItems: "center",
              gap: "4px",
              padding: 0,
            }}
          >
            <span>View value ranges</span>
            <ArrowRight size={12} />
          </button>
        </div>

        {/* Trends & connections */}
        <div
          style={{
            padding: "16px",
            borderRadius: "10px",
            backgroundColor: themeTokens?.colors?.surface,
            border: `1px solid ${themeTokens?.colors?.borderSubtle}`,
            display: "flex",
            flexDirection: "column",
            justifyContent: "space-between",
          }}
        >
          <div>
            <div style={{ display: "flex", alignItems: "center", gap: "6px", marginBottom: "8px" }}>
              <Calendar size={15} color="#10b981" />
              <h3 style={{ margin: 0, fontSize: "0.92rem", fontWeight: 700, color: themeTokens?.colors?.textPrimary }}>
                Trends & connections
              </h3>
            </div>
            <p style={{ margin: "4px 0", fontSize: "0.78rem", color: themeTokens?.colors?.textSecondary, lineHeight: 1.4 }}>
              Explore changes over time and connections between sheets.
            </p>
          </div>
          <div style={{ display: "flex", gap: "12px", marginTop: "12px" }}>
            <button
              type="button"
              onClick={() => onNavigateTab("trends")}
              style={{
                background: "transparent",
                border: "none",
                color: "#10b981",
                fontSize: "0.76rem",
                fontWeight: 600,
                cursor: "pointer",
                display: "inline-flex",
                alignItems: "center",
                gap: "4px",
                padding: 0,
              }}
            >
              <span>View trends</span>
              <ArrowRight size={12} />
            </button>
            <button
              type="button"
              onClick={() => onNavigateTab("relationships")}
              style={{
                background: "transparent",
                border: "none",
                color: "#8b5cf6",
                fontSize: "0.76rem",
                fontWeight: 600,
                cursor: "pointer",
                display: "inline-flex",
                alignItems: "center",
                gap: "4px",
                padding: 0,
              }}
            >
              <span>View connections</span>
              <ArrowRight size={12} />
            </button>
          </div>
        </div>
      </section>


    </div>
  );
}
