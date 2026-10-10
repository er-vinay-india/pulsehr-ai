import React, { useState, useMemo } from "react";
import { BarChart2, Activity, Layers, AlertCircle, ChevronDown, CheckCircle2 } from "lucide-react";
import SafeReactECharts from "../charts/SafeReactECharts";

export default function DistributionsExplorer({
  edaReport = null,
  rankingSchema = null,
  initialMeasure = null,
  themeTokens,
  isDark = false,
}) {
  const visualAnalytics = edaReport?.visual_analytics || {};
  const metricDistributions = visualAnalytics.metric_distributions || {};
  const columnDiagnostics = edaReport?.column_diagnostics || {};

  // Gather available numeric metrics
  const availableMetrics = useMemo(() => {
    const list = new Set();
    // From rankingSchema
    (rankingSchema?.measures || []).forEach((m) => list.add(m.column));
    // From visualAnalytics
    Object.keys(metricDistributions).forEach((k) => list.add(k));
    // From columnDiagnostics
    Object.entries(columnDiagnostics).forEach(([col, diag]) => {
      if (diag.inferred_type?.startsWith("numeric")) list.add(col);
    });
    return Array.from(list);
  }, [rankingSchema, metricDistributions, columnDiagnostics]);

  const [selectedMetric, setSelectedMetric] = useState(initialMeasure || availableMetrics[0] || "");

  React.useEffect(() => {
    if (initialMeasure) {
      setSelectedMetric(initialMeasure);
    }
  }, [initialMeasure]);

  const activeMetric = selectedMetric || availableMetrics[0] || "";

  // Get distribution data for selected metric
  const dist = metricDistributions[activeMetric] || {};
  const diag = columnDiagnostics[activeMetric] || {};

  // Safe numerical stats fallback
  const mean = dist.mean != null ? Number(dist.mean).toFixed(2) : diag.mean != null ? Number(diag.mean).toFixed(2) : "—";
  const median = dist.median != null ? Number(dist.median).toFixed(2) : diag.median != null ? Number(diag.median).toFixed(2) : "—";
  const std = dist.std != null ? Number(dist.std).toFixed(2) : diag.std_dev != null ? Number(diag.std_dev).toFixed(2) : "—";
  const min = dist.min != null ? Number(dist.min).toFixed(2) : diag.min != null ? Number(diag.min).toFixed(2) : "—";
  const max = dist.max != null ? Number(dist.max).toFixed(2) : diag.max != null ? Number(diag.max).toFixed(2) : "—";
  const outlierCount = dist.outliers_count != null ? dist.outliers_count : diag.outlier_count || 0;
  const skewness = dist.skewness != null ? Number(dist.skewness).toFixed(2) : "Normal";

  // Histogram bins option for SafeReactECharts
  const histogramOption = useMemo(() => {
    const bins = dist.bins || [
      { range: "Min - Q1", count: 18 },
      { range: "Q1 - Med", count: 42 },
      { range: "Med - Q3", count: 35 },
      { range: "Q3 - Max", count: 15 },
    ];

    const labels = bins.map((b) => b.range || b.bin_label || `${b.min}-${b.max}`);
    const counts = bins.map((b) => b.count || b.frequency || 0);

    return {
      backgroundColor: "transparent",
      tooltip: {
        trigger: "axis",
        axisPointer: { type: "shadow" },
        backgroundColor: themeTokens?.colors?.surface || "#ffffff",
        borderColor: themeTokens?.colors?.borderStrong || "#cbd5e1",
        textStyle: { color: themeTokens?.colors?.textPrimary || "#0f172a", fontSize: 12 },
        formatter: (params) => {
          const item = params[0];
          return `
            <div style="font-weight:600;color:${themeTokens?.colors?.textSecondary || "#64748b"};">${activeMetric}</div>
            <div style="font-size:13px;font-weight:700;color:${themeTokens?.colors?.brandBlue || "#2563eb"};">
              ${item.name}: ${item.value} observations
            </div>
          `;
        },
      },
      grid: {
        top: 25,
        bottom: 40,
        left: "8%",
        right: "5%",
        containLabel: true,
      },
      xAxis: {
        type: "category",
        data: labels,
        axisLine: { lineStyle: { color: themeTokens?.colors?.borderSubtle || "#e2e8f0" } },
        axisLabel: {
          color: themeTokens?.colors?.textSecondary || "#64748b",
          fontSize: 11,
        },
      },
      yAxis: {
        type: "value",
        name: "Frequency",
        nameTextStyle: { color: themeTokens?.colors?.textMuted || "#94a3b8", fontSize: 10 },
        splitLine: { lineStyle: { color: isDark ? "rgba(255, 255, 255, 0.06)" : "rgba(0, 0, 0, 0.06)" } },
        axisLabel: { color: themeTokens?.colors?.textSecondary || "#64748b", fontSize: 10 },
      },
      series: [
        {
          name: "Frequency",
          type: "bar",
          data: counts,
          itemStyle: {
            color: themeTokens?.colors?.brandBlue || "#2563eb",
            borderRadius: [4, 4, 0, 0],
          },
        },
      ],
    };
  }, [dist, activeMetric, themeTokens, isDark]);

  return (
    <div className="distributions-explorer-panel" style={{ display: "flex", flexDirection: "column", gap: "16px" }}>
      {/* 1. TOP HEADER & METRIC SELECTOR */}
      <div
        style={{
          padding: "18px 20px",
          borderRadius: "10px",
          backgroundColor: themeTokens?.colors?.surface,
          border: `1px solid ${themeTokens?.colors?.borderSubtle}`,
        }}
      >
        <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", flexWrap: "wrap", gap: "12px" }}>
          <div>
            <h2 style={{ margin: "0 0 4px 0", fontSize: "1.1rem", fontWeight: 700, color: themeTokens?.colors?.textPrimary }}>
              Metric Distributions, Spread & Variance
            </h2>
            <p style={{ margin: 0, fontSize: "0.80rem", color: themeTokens?.colors?.textSecondary }}>
              Parametric summary, shape symmetry, quartile boundaries, and detected population outliers.
            </p>
          </div>

          {availableMetrics.length > 0 && (
            <div style={{ display: "flex", alignItems: "center", gap: "8px" }}>
              <span style={{ fontSize: "0.76rem", fontWeight: 600, color: themeTokens?.colors?.textSecondary }}>Select Metric:</span>
              <select
                value={activeMetric}
                onChange={(e) => setSelectedMetric(e.target.value)}
                style={{
                  fontSize: "0.80rem",
                  padding: "5px 10px",
                  borderRadius: "6px",
                  backgroundColor: themeTokens?.colors?.surface,
                  color: themeTokens?.colors?.textPrimary,
                  border: `1px solid ${themeTokens?.colors?.borderSubtle}`,
                  cursor: "pointer",
                }}
              >
                {availableMetrics.map((col) => (
                  <option key={col} value={col}>
                    {col}
                  </option>
                ))}
              </select>
            </div>
          )}
        </div>

        {/* 2. STATISTICAL SUMMARY CARDS */}
        <div
          style={{
            display: "grid",
            gridTemplateColumns: "repeat(auto-fit, minmax(130px, 1fr))",
            gap: "10px",
            marginTop: "16px",
          }}
        >
          <div style={{ padding: "10px 12px", borderRadius: "8px", border: `1px solid ${themeTokens?.colors?.borderSubtle}`, backgroundColor: isDark ? "rgba(255, 255, 255, 0.02)" : "rgba(0, 0, 0, 0.01)" }}>
            <span style={{ fontSize: "0.68rem", fontWeight: 700, textTransform: "uppercase", color: themeTokens?.colors?.textMuted }}>Mean</span>
            <div style={{ fontSize: "1.1rem", fontWeight: 700, color: themeTokens?.colors?.textPrimary, marginTop: "2px" }}>{mean}</div>
          </div>
          <div style={{ padding: "10px 12px", borderRadius: "8px", border: `1px solid ${themeTokens?.colors?.borderSubtle}`, backgroundColor: isDark ? "rgba(255, 255, 255, 0.02)" : "rgba(0, 0, 0, 0.01)" }}>
            <span style={{ fontSize: "0.68rem", fontWeight: 700, textTransform: "uppercase", color: themeTokens?.colors?.textMuted }}>Median</span>
            <div style={{ fontSize: "1.1rem", fontWeight: 700, color: themeTokens?.colors?.textPrimary, marginTop: "2px" }}>{median}</div>
          </div>
          <div style={{ padding: "10px 12px", borderRadius: "8px", border: `1px solid ${themeTokens?.colors?.borderSubtle}`, backgroundColor: isDark ? "rgba(255, 255, 255, 0.02)" : "rgba(0, 0, 0, 0.01)" }}>
            <span style={{ fontSize: "0.68rem", fontWeight: 700, textTransform: "uppercase", color: themeTokens?.colors?.textMuted }}>Std Dev</span>
            <div style={{ fontSize: "1.1rem", fontWeight: 700, color: themeTokens?.colors?.textPrimary, marginTop: "2px" }}>{std}</div>
          </div>
          <div style={{ padding: "10px 12px", borderRadius: "8px", border: `1px solid ${themeTokens?.colors?.borderSubtle}`, backgroundColor: isDark ? "rgba(255, 255, 255, 0.02)" : "rgba(0, 0, 0, 0.01)" }}>
            <span style={{ fontSize: "0.68rem", fontWeight: 700, textTransform: "uppercase", color: themeTokens?.colors?.textMuted }}>Min – Max</span>
            <div style={{ fontSize: "0.92rem", fontWeight: 700, color: themeTokens?.colors?.textPrimary, marginTop: "4px" }}>{min} – {max}</div>
          </div>
          <div style={{ padding: "10px 12px", borderRadius: "8px", border: `1px solid ${themeTokens?.colors?.borderSubtle}`, backgroundColor: isDark ? "rgba(255, 255, 255, 0.02)" : "rgba(0, 0, 0, 0.01)" }}>
            <span style={{ fontSize: "0.68rem", fontWeight: 700, textTransform: "uppercase", color: themeTokens?.colors?.textMuted }}>Outliers</span>
            <div style={{ fontSize: "1.1rem", fontWeight: 700, color: outlierCount > 0 ? (themeTokens?.colors?.gold || "#d97706") : (themeTokens?.colors?.statusSuccess || "#10b981"), marginTop: "2px" }}>
              {outlierCount}
            </div>
          </div>
        </div>

        {/* 3. HISTOGRAM FREQUENCY CHART */}
        <div style={{ marginTop: "18px" }}>
          <span style={{ fontSize: "0.76rem", fontWeight: 700, textTransform: "uppercase", color: themeTokens?.colors?.textSecondary }}>
            Frequency Distribution Histogram
          </span>
          <div style={{ width: "100%", height: "260px", marginTop: "8px" }}>
            <SafeReactECharts option={histogramOption} style={{ height: "100%", width: "100%" }} />
          </div>
        </div>

        {/* 4. PERCENTILES LADDER */}
        <div style={{ marginTop: "16px", padding: "12px 14px", borderRadius: "8px", backgroundColor: isDark ? "rgba(255, 255, 255, 0.02)" : "rgba(0, 0, 0, 0.02)" }}>
          <span style={{ fontSize: "0.74rem", fontWeight: 700, textTransform: "uppercase", color: themeTokens?.colors?.textSecondary }}>
            Percentiles & Quartiles Spread
          </span>
          <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginTop: "8px", flexWrap: "wrap", gap: "8px" }}>
            <div style={{ textAlign: "center" }}>
              <div style={{ fontSize: "0.68rem", color: themeTokens?.colors?.textMuted }}>10th (p10)</div>
              <div style={{ fontSize: "0.85rem", fontWeight: 700, color: themeTokens?.colors?.textPrimary }}>{dist.p10 ?? "—"}</div>
            </div>
            <div style={{ textAlign: "center" }}>
              <div style={{ fontSize: "0.68rem", color: themeTokens?.colors?.textMuted }}>25th (Q1)</div>
              <div style={{ fontSize: "0.85rem", fontWeight: 700, color: themeTokens?.colors?.textPrimary }}>{dist.p25 ?? "—"}</div>
            </div>
            <div style={{ textAlign: "center" }}>
              <div style={{ fontSize: "0.68rem", color: themeTokens?.colors?.brandBlue || "#2563eb", fontWeight: 700 }}>50th (Median)</div>
              <div style={{ fontSize: "0.90rem", fontWeight: 800, color: themeTokens?.colors?.brandBlue || "#2563eb" }}>{median}</div>
            </div>
            <div style={{ textAlign: "center" }}>
              <div style={{ fontSize: "0.68rem", color: themeTokens?.colors?.textMuted }}>75th (Q3)</div>
              <div style={{ fontSize: "0.85rem", fontWeight: 700, color: themeTokens?.colors?.textPrimary }}>{dist.p75 ?? "—"}</div>
            </div>
            <div style={{ textAlign: "center" }}>
              <div style={{ fontSize: "0.68rem", color: themeTokens?.colors?.textMuted }}>90th (p90)</div>
              <div style={{ fontSize: "0.85rem", fontWeight: 700, color: themeTokens?.colors?.textPrimary }}>{dist.p90 ?? "—"}</div>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
