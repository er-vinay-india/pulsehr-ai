import React, { useState, useMemo } from "react";
import { GitMerge, Link2, Share2, ArrowRight, Layers, HelpCircle, CheckCircle2 } from "lucide-react";
import SafeReactECharts from "../charts/SafeReactECharts";

export default function RelationshipsExplorer({
  catalog,
  derivedTables = [],
  crossCorrelations = [],
  edaReport = null,
  initialRelationshipId = null,
  themeTokens,
  isDark = false,
  onExploreDerivedTable = () => {},
}) {
  const relationships = catalog?.relationships || [];
  const visualAnalytics = edaReport?.visual_analytics || {};
  const correlationMatrix = visualAnalytics.correlation_matrix || { metrics: [], pairs: [], matrix: [] };
  const metrics = correlationMatrix.metrics || [];
  const pairs = correlationMatrix.pairs || [];

  const [selectedPairIndex, setSelectedPairIndex] = useState(0);

  // Correlation heatmap ECharts options
  const heatmapOption = useMemo(() => {
    if (!metrics.length || !correlationMatrix.matrix?.length) return null;

    const data = [];
    metrics.forEach((m1, i) => {
      metrics.forEach((m2, j) => {
        const val = correlationMatrix.matrix[i]?.[j];
        data.push([j, i, val != null ? Number(val.toFixed(2)) : null]);
      });
    });

    return {
      backgroundColor: "transparent",
      tooltip: {
        position: "top",
        backgroundColor: themeTokens?.colors?.surface || "#ffffff",
        borderColor: themeTokens?.colors?.borderStrong || "#cbd5e1",
        textStyle: { color: themeTokens?.colors?.textPrimary || "#0f172a", fontSize: 12 },
        formatter: (params) => {
          const [colIdx, rowIdx, val] = params.data;
          const xName = metrics[colIdx];
          const yName = metrics[rowIdx];
          if (xName === yName) return `<b>${xName}</b> (Self Identity: 1.0)`;
          if (val == null) return `<b>${xName} × ${yName}</b><br/>Insufficient variance`;
          const dir = val > 0 ? "Positive" : "Negative";
          const strength = Math.abs(val) >= 0.7 ? "Strong" : Math.abs(val) >= 0.35 ? "Moderate" : "Mild";
          const color = val >= 0 ? (themeTokens?.colors?.statusSuccess || "#10b981") : (themeTokens?.colors?.statusError || "#ef4444");
          return `
            <div style="font-weight:600;margin-bottom:4px;color:${themeTokens?.colors?.textSecondary || "#64748b"};">${xName} ↔ ${yName}</div>
            <div style="font-size:13px;font-weight:700;color:${color};">
              ${strength} ${dir} Correlation: ${val > 0 ? "+" : ""}${val}
            </div>
          `;
        },
      },
      grid: {
        top: 20,
        bottom: 70,
        left: "15%",
        right: "5%",
        containLabel: true,
      },
      xAxis: {
        type: "category",
        data: metrics,
        splitArea: { show: true },
        axisLabel: {
          color: themeTokens?.colors?.textSecondary || "#64748b",
          rotate: 35,
          fontSize: 10,
        },
      },
      yAxis: {
        type: "category",
        data: metrics,
        splitArea: { show: true },
        axisLabel: {
          color: themeTokens?.colors?.textSecondary || "#64748b",
          fontSize: 10,
        },
      },
      visualMap: {
        min: -1,
        max: 1,
        calculable: true,
        orient: "horizontal",
        left: "center",
        bottom: 5,
        inRange: {
          color: [
            themeTokens?.colors?.statusError || "#ef4444",
            isDark ? "#1e293b" : "#f1f5f9",
            themeTokens?.colors?.brandBlue || "#2563eb",
          ],
        },
        textStyle: { color: themeTokens?.colors?.textSecondary || "#64748b", fontSize: 10 },
      },
      series: [
        {
          name: "Correlation",
          type: "heatmap",
          data: data,
          label: {
            show: metrics.length <= 8,
            fontSize: 10,
            color: isDark ? "#ffffff" : "#0f172a",
          },
          emphasis: {
            itemStyle: {
              shadowBlur: 10,
              shadowColor: "rgba(0, 0, 0, 0.4)",
            },
          },
        },
      ],
    };
  }, [metrics, correlationMatrix, themeTokens, isDark]);

  const sheetsMap = useMemo(() => {
    const map = {};
    (catalog?.sheets || []).forEach((s) => {
      map[s.id] = s.display_name || s.name || `Sheet ${s.id}`;
    });
    return map;
  }, [catalog]);

  return (
    <div className="relationships-explorer-panel" style={{ display: "flex", flexDirection: "column", gap: "16px" }}>
      {/* 1. RELATIONAL STRUCTURE SUMMARY CARD */}
      <div
        style={{
          padding: "18px 20px",
          borderRadius: "10px",
          backgroundColor: themeTokens?.colors?.surface,
          border: `1px solid ${themeTokens?.colors?.borderSubtle}`,
        }}
      >
        <div style={{ marginBottom: "12px" }}>
          <h2 style={{ margin: "0 0 4px 0", fontSize: "1.1rem", fontWeight: 700, color: themeTokens?.colors?.textPrimary }}>
            Relational Architecture & Cross-Sheet Joins
          </h2>
          <p style={{ margin: 0, fontSize: "0.80rem", color: themeTokens?.colors?.textSecondary }}>
            Reconciled relational joins, synthesized multi-sheet rollups, and empirical correlation dependencies.
          </p>
        </div>

        {relationships.length > 0 ? (
          <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(280px, 1fr))", gap: "10px", marginTop: "12px" }}>
            {relationships.map((rel, idx) => {
              const sourceName = rel.source_sheet_name || rel.source_sheet || sheetsMap[rel.left_sheet] || `Sheet ${rel.left_sheet || 1}`;
              const targetName = rel.target_sheet_name || rel.target_sheet || sheetsMap[rel.right_sheet] || `Sheet ${rel.right_sheet || 2}`;
              const keyCol = rel.source_column || rel.left_column || rel.key_column || "id";
              return (
                <div
                  key={idx}
                  style={{
                    padding: "12px 14px",
                    borderRadius: "8px",
                    border: `1px solid ${themeTokens?.colors?.borderSubtle}`,
                    backgroundColor: isDark ? "rgba(255, 255, 255, 0.02)" : "rgba(0, 0, 0, 0.02)",
                    display: "flex",
                    flexDirection: "column",
                    gap: "6px",
                  }}
                >
                  <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between" }}>
                    <div style={{ display: "flex", alignItems: "center", gap: "6px" }}>
                      <Link2 size={13} color={themeTokens?.colors?.brandBlue || "#2563eb"} />
                      <span style={{ fontSize: "0.82rem", fontWeight: 700, color: themeTokens?.colors?.textPrimary }}>
                        {sourceName} ↔ {targetName}
                      </span>
                    </div>
                    <span
                      style={{
                        fontSize: "0.68rem",
                        fontWeight: 600,
                        padding: "2px 6px",
                        borderRadius: "4px",
                        backgroundColor: "rgba(16, 185, 129, 0.12)",
                        color: themeTokens?.colors?.statusSuccess || "#10b981",
                      }}
                    >
                      {rel.confidence ? `${Math.round(rel.confidence * 100)}% Match` : "Verified Join"}
                    </span>
                  </div>
                  <div style={{ fontSize: "0.76rem", color: themeTokens?.colors?.textSecondary }}>
                    Key column: <code>{keyCol}</code>
                  </div>
                </div>
              );
            })}
          </div>
        ) : (
          <div
            style={{
              padding: "14px 16px",
              borderRadius: "8px",
              backgroundColor: isDark ? "rgba(255, 255, 255, 0.02)" : "rgba(0, 0, 0, 0.02)",
              fontSize: "0.80rem",
              color: themeTokens?.colors?.textSecondary,
              display: "flex",
              alignItems: "center",
              gap: "8px",
            }}
          >
            <GitMerge size={16} color={themeTokens?.colors?.textMuted} />
            <span>Single consolidated entity sheet detected. Cross-sheet join links activate when uploading multi-sheet workbooks.</span>
          </div>
        )}
      </div>

      {/* 2. SYNTHESIZED DERIVED TABLES */}
      {derivedTables.length > 0 && (
        <div
          style={{
            padding: "18px 20px",
            borderRadius: "10px",
            backgroundColor: themeTokens?.colors?.surface,
            border: `1px solid ${themeTokens?.colors?.borderSubtle}`,
          }}
        >
          <h3 style={{ margin: "0 0 4px 0", fontSize: "0.98rem", fontWeight: 700, color: themeTokens?.colors?.textPrimary }}>
            Synthesized Analytical Views & Derived Rollups
          </h3>
          <p style={{ margin: "0 0 12px 0", fontSize: "0.78rem", color: themeTokens?.colors?.textSecondary }}>
            Automated joins computed to enable higher-order cross-domain analysis.
          </p>

          <div style={{ display: "flex", flexDirection: "column", gap: "8px" }}>
            {derivedTables.map((dt) => (
              <div
                key={dt.id}
                style={{
                  display: "flex",
                  alignItems: "center",
                  justifyContent: "space-between",
                  padding: "10px 14px",
                  borderRadius: "8px",
                  border: `1px solid ${themeTokens?.colors?.borderSubtle}`,
                  backgroundColor: isDark ? "rgba(255, 255, 255, 0.02)" : "rgba(0, 0, 0, 0.01)",
                }}
              >
                <div>
                  <div style={{ fontSize: "0.84rem", fontWeight: 600, color: themeTokens?.colors?.textPrimary }}>
                    {dt.display_name || dt.name}
                  </div>
                  <div style={{ fontSize: "0.74rem", color: themeTokens?.colors?.textMuted }}>
                    {dt.description || `${dt.row_count || 0} synthesized records`}
                  </div>
                </div>
                <button
                  type="button"
                  onClick={() => onExploreDerivedTable(dt.id)}
                  style={{
                    padding: "4px 10px",
                    borderRadius: "6px",
                    border: `1px solid ${themeTokens?.colors?.borderSubtle}`,
                    background: "transparent",
                    color: themeTokens?.colors?.brandBlue || "#2563eb",
                    fontSize: "0.74rem",
                    fontWeight: 600,
                    cursor: "pointer",
                    display: "inline-flex",
                    alignItems: "center",
                    gap: "4px",
                  }}
                >
                  <span>Explore Rows</span>
                  <ArrowRight size={12} />
                </button>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* 3. CORRELATION MATRIX & PAIRWISE RELATIONSHIPS */}
      <div
        style={{
          padding: "18px 20px",
          borderRadius: "10px",
          backgroundColor: themeTokens?.colors?.surface,
          border: `1px solid ${themeTokens?.colors?.borderSubtle}`,
        }}
      >
        <div style={{ display: "flex", justifyContent: "space-between", alignItems: "baseline", marginBottom: "12px" }}>
          <div>
            <h3 style={{ margin: "0 0 4px 0", fontSize: "0.98rem", fontWeight: 700, color: themeTokens?.colors?.textPrimary }}>
              Empirical Metric Correlations & Dependencies
            </h3>
            <p style={{ margin: 0, fontSize: "0.78rem", color: themeTokens?.colors?.textSecondary }}>
              Bivariate Pearson correlation coefficients calculated across observed continuous measures.
            </p>
          </div>
          {metrics.length > 0 && (
            <span style={{ fontSize: "0.72rem", color: themeTokens?.colors?.textMuted }}>
              {metrics.length} metric dimensions
            </span>
          )}
        </div>

        {heatmapOption ? (
          <div style={{ width: "100%", height: "320px", marginBottom: "16px" }}>
            <SafeReactECharts option={heatmapOption} style={{ height: "100%", width: "100%" }} />
          </div>
        ) : (
          <div
            style={{
              padding: "16px",
              borderRadius: "8px",
              backgroundColor: isDark ? "rgba(255, 255, 255, 0.02)" : "rgba(0, 0, 0, 0.02)",
              fontSize: "0.80rem",
              color: themeTokens?.colors?.textSecondary,
              marginBottom: "12px",
            }}
          >
            Correlation matrix requires at least 2 numeric metric columns with variance.
          </div>
        )}

        {/* Top Correlated Pairs Grid */}
        {pairs.length > 0 && (
          <div>
            <span style={{ fontSize: "0.74rem", fontWeight: 700, textTransform: "uppercase", color: themeTokens?.colors?.textSecondary }}>
              Strongest Detected Co-Movements
            </span>
            <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(240px, 1fr))", gap: "8px", marginTop: "8px" }}>
              {pairs.slice(0, 6).map((pair, idx) => {
                const rawR = pair.correlation != null ? pair.correlation : (pair.pearson_r != null ? pair.pearson_r : pair.r);
                const numR = Number(rawR);
                const r = !isNaN(numR) ? numR : 0.0;
                const isPos = r >= 0;
                return (
                  <div
                    key={idx}
                    style={{
                      padding: "10px 12px",
                      borderRadius: "8px",
                      border: `1px solid ${themeTokens?.colors?.borderSubtle}`,
                      backgroundColor: isDark ? "rgba(255, 255, 255, 0.02)" : "rgba(0, 0, 0, 0.01)",
                      display: "flex",
                      alignItems: "center",
                      justifyContent: "space-between",
                    }}
                  >
                    <div>
                      <div style={{ fontSize: "0.80rem", fontWeight: 600, color: themeTokens?.colors?.textPrimary }}>
                        {pair.x || pair.metric1} ↔ {pair.y || pair.metric2}
                      </div>
                      <div style={{ fontSize: "0.70rem", color: themeTokens?.colors?.textMuted }}>
                        {Math.abs(r) >= 0.7 ? "Strong" : "Moderate"} {isPos ? "Positive" : "Negative"}
                      </div>
                    </div>
                    <span
                      style={{
                        fontSize: "0.84rem",
                        fontWeight: 700,
                        color: isPos ? (themeTokens?.colors?.statusSuccess || "#10b981") : (themeTokens?.colors?.statusError || "#ef4444"),
                      }}
                    >
                      {r > 0 ? "+" : ""}{Number(r).toFixed(2)}
                    </span>
                  </div>
                );
              })}
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
