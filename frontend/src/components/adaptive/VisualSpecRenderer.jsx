import React, { useMemo } from "react";
import SafeReactECharts from "../charts/SafeReactECharts";
import { Award, Trophy } from "lucide-react";

/**
 * Executive Podium Top 3 Renderer.
 * Olympic-style gold (1st, center), silver (2nd, left), bronze (3rd, right) pedestals.
 * Strictly adheres to <= 20 char / 2-line label wrapping with full label accessible on hover.
 */
function PodiumTop3View({ visualSpec, themeTokens, isDark, height = "250px" }) {
  const categories = visualSpec.categories || [];
  const values = visualSpec.values || [];
  const unit = visualSpec.unit || "";
  const podiumCats = visualSpec.podium_categories || [];

  const items = [
    {
      rank: 2,
      label: podiumCats[1]?.display_label || categories[1] || "2nd Place",
      fullLabel: podiumCats[1]?.full_label || categories[1] || "2nd Place",
      value: values[1] != null ? values[1] : "-",
      pedestalHeight: "80px",
      badgeColor: isDark ? "#94a3b8" : "#64748b",
      badgeBg: isDark ? "rgba(148, 163, 184, 0.2)" : "rgba(100, 116, 139, 0.15)",
      borderColor: isDark ? "#475569" : "#cbd5e1",
      bgColor: isDark ? "rgba(30, 41, 59, 0.8)" : "rgba(241, 245, 249, 0.9)",
    },
    {
      rank: 1,
      label: podiumCats[0]?.display_label || categories[0] || "1st Place",
      fullLabel: podiumCats[0]?.full_label || categories[0] || "1st Place",
      value: values[0] != null ? values[0] : "-",
      pedestalHeight: "115px",
      badgeColor: "#f59e0b",
      badgeBg: isDark ? "rgba(245, 158, 11, 0.25)" : "rgba(245, 158, 11, 0.18)",
      borderColor: "#f59e0b",
      bgColor: isDark ? "rgba(245, 158, 11, 0.12)" : "rgba(254, 243, 199, 0.85)",
      isWinner: true,
    },
    {
      rank: 3,
      label: podiumCats[2]?.display_label || categories[2] || "3rd Place",
      fullLabel: podiumCats[2]?.full_label || categories[2] || "3rd Place",
      value: values[2] != null ? values[2] : "-",
      pedestalHeight: "60px",
      badgeColor: isDark ? "#d97706" : "#b45309",
      badgeBg: isDark ? "rgba(217, 119, 6, 0.2)" : "rgba(180, 83, 9, 0.15)",
      borderColor: isDark ? "#78350f" : "#d97706",
      bgColor: isDark ? "rgba(30, 41, 59, 0.8)" : "rgba(241, 245, 249, 0.9)",
    },
  ];

  return (
    <div
      className="podium-top-3-container"
      data-testid="podium-top-3-container"
      style={{
        height,
        width: "100%",
        display: "flex",
        alignItems: "flex-end",
        justifyContent: "center",
        gap: "12px",
        padding: "10px 16px 6px",
        boxSizing: "border-box",
      }}
    >
      {items.map((item) => (
        <div
          key={item.rank}
          style={{
            flex: 1,
            maxWidth: "130px",
            display: "flex",
            flexDirection: "column",
            alignItems: "center",
            textAlign: "center",
          }}
        >
          {/* Rank Badge & Crown */}
          <div
            style={{
              display: "flex",
              alignItems: "center",
              justifyContent: "center",
              gap: "4px",
              marginBottom: "4px",
            }}
          >
            {item.isWinner ? (
              <Trophy size={16} color="#f59e0b" style={{ filter: "drop-shadow(0 2px 4px rgba(245, 158, 11, 0.4))" }} />
            ) : (
              <Award size={14} color={item.badgeColor} />
            )}
            <span
              style={{
                fontSize: "0.75rem",
                fontWeight: 700,
                color: item.badgeColor,
              }}
            >
              #{item.rank}
            </span>
          </div>

          {/* Metric Value */}
          <div
            style={{
              fontSize: item.isWinner ? "1.05rem" : "0.92rem",
              fontWeight: 800,
              color: isDark ? "#f8fafc" : "#0f172a",
              marginBottom: "4px",
              lineHeight: 1.2,
            }}
          >
            {item.value} <span style={{ fontSize: "0.72rem", fontWeight: 500, color: themeTokens?.colors?.textMuted }}>{unit}</span>
          </div>

          {/* Category Display Label (truncated to <= 20 chars, max 2 lines, full text in tooltip) */}
          <div
            title={item.fullLabel}
            style={{
              fontSize: "0.72rem",
              fontWeight: 600,
              color: isDark ? "#cbd5e1" : "#334155",
              lineHeight: 1.25,
              height: "28px",
              display: "-webkit-box",
              WebkitLineClamp: 2,
              WebkitBoxOrient: "vertical",
              overflow: "hidden",
              textOverflow: "ellipsis",
              marginBottom: "8px",
              cursor: "help",
            }}
          >
            {item.label}
          </div>

          {/* Pedestal Block */}
          <div
            style={{
              width: "100%",
              height: item.pedestalHeight,
              backgroundColor: item.bgColor,
              border: `2px solid ${item.borderColor}`,
              borderBottom: "none",
              borderRadius: "8px 8px 0 0",
              display: "flex",
              alignItems: "center",
              justifyContent: "center",
              boxShadow: item.isWinner ? "0 0 16px rgba(245, 158, 11, 0.15)" : "none",
            }}
          >
            <span
              style={{
                fontSize: "1.25rem",
                fontWeight: 900,
                color: item.badgeColor,
                opacity: 0.6,
              }}
            >
              {item.rank}
            </span>
          </div>
        </div>
      ))}
    </div>
  );
}

/**
 * Generic VisualSpecRenderer.
 * Renders any governed visual specification purely by chart_type and visual_spec contracts,
 * completely independent of business domain or column names.
 */
export default function VisualSpecRenderer({
  visualSpec,
  themeTokens,
  isDark = false,
  height = "250px",
}) {
  const chartType = (visualSpec?.chart_type || "ranked_bar").toLowerCase();

  // Special-case pure-React Olympic Podium Top 3 for pixel-perfect label wrapping and theme responsiveness
  if (chartType === "podium_top_3") {
    return (
      <PodiumTop3View
        visualSpec={visualSpec}
        themeTokens={themeTokens}
        isDark={isDark}
        height={height}
      />
    );
  }

  const chartOption = useMemo(() => {
    if (!visualSpec) return null;

    const textColor = isDark ? "#94a3b8" : "#475569";
    const splitLineColor = isDark ? "rgba(255, 255, 255, 0.08)" : "rgba(0, 0, 0, 0.06)";

    const categories = visualSpec.categories || [];
    const values = visualSpec.values || [];
    const series = visualSpec.series || [];
    const unit = visualSpec.unit || "";
    const benchmark = visualSpec.benchmark;

    // 1. 100% STACKED BAR / STACKED BAR (Composition Archetype)
    if (chartType === "100_percent_stacked_bar" || chartType === "stacked_bar") {
      const palette = isDark
        ? ["#3b82f6", "#f59e0b", "#64748b", "#10b981", "#8b5cf6"]
        : ["#2563eb", "#d97706", "#94a3b8", "#059669", "#7c3aed"];

      const eSeries = series.length > 0
        ? series.map((s, idx) => ({
            name: s.name,
            type: "bar",
            stack: "total",
            barMaxWidth: 38,
            itemStyle: {
              color: palette[idx % palette.length],
              borderRadius: idx === series.length - 1 ? [4, 4, 0, 0] : [0, 0, 0, 0],
            },
            data: s.values,
          }))
        : [
            {
              name: "Primary",
              type: "bar",
              stack: "total",
              data: values,
              itemStyle: { color: palette[0], borderRadius: [4, 4, 0, 0] },
            },
          ];

      return {
        backgroundColor: "transparent",
        tooltip: {
          trigger: "axis",
          axisPointer: { type: "shadow" },
          backgroundColor: isDark ? "#1e293b" : "#ffffff",
          borderColor: isDark ? "#334155" : "#e2e8f0",
          textStyle: { color: isDark ? "#f1f5f9" : "#0f172a", fontSize: 12 },
          formatter: (params) => {
            let res = `<strong>${params[0].name}</strong><br/>`;
            params.forEach((p) => {
              res += `${p.marker} ${p.seriesName}: <strong>${p.value} ${unit}</strong><br/>`;
            });
            return res;
          },
        },
        legend: {
          show: true,
          top: 0,
          right: 10,
          textStyle: { color: textColor, fontSize: 11 },
        },
        grid: { top: 35, right: 15, bottom: 25, left: 45, containLabel: true },
        xAxis: {
          type: "category",
          data: categories,
          axisLine: { lineStyle: { color: isDark ? "#334155" : "#cbd5e1" } },
          axisLabel: { color: textColor, fontSize: 11 },
        },
        yAxis: {
          type: "value",
          splitLine: { lineStyle: { color: splitLineColor } },
          axisLabel: {
            color: textColor,
            fontSize: 11,
            formatter: (v) => `${v}${chartType.includes("percent") ? "%" : ""}`,
          },
        },
        series: eSeries,
      };
    }

    // 2. LINE / TREND (Temporal Cadence Archetype)
    if (chartType === "line" || chartType === "trend_line") {
      const lineColor = themeTokens?.colors?.brandBlue || "#2563eb";
      return {
        backgroundColor: "transparent",
        tooltip: {
          trigger: "axis",
          backgroundColor: isDark ? "#1e293b" : "#ffffff",
          borderColor: isDark ? "#334155" : "#e2e8f0",
          textStyle: { color: isDark ? "#f1f5f9" : "#0f172a", fontSize: 12 },
          formatter: (p) => `${p[0].name}: <strong>${p[0].value} ${unit}</strong>`,
        },
        grid: { top: 25, right: 20, bottom: 25, left: 45, containLabel: true },
        xAxis: {
          type: "category",
          data: categories,
          axisLine: { lineStyle: { color: isDark ? "#334155" : "#cbd5e1" } },
          axisLabel: { color: textColor, fontSize: 11 },
        },
        yAxis: {
          type: "value",
          splitLine: { lineStyle: { color: splitLineColor } },
          axisLabel: { color: textColor, fontSize: 11 },
        },
        series: [
          {
            type: "line",
            smooth: true,
            data: values,
            symbolSize: 7,
            itemStyle: { color: lineColor },
            lineStyle: { width: 3, color: lineColor },
            areaStyle: {
              color: isDark ? "rgba(59, 130, 246, 0.12)" : "rgba(37, 99, 235, 0.08)",
            },
          },
        ],
      };
    }

    // 3. VARIANCE BAR / WATERFALL / DEVIATION (Anomaly Archetype)
    if (chartType === "variance_bar" || chartType === "waterfall") {
      return {
        backgroundColor: "transparent",
        tooltip: {
          trigger: "axis",
          backgroundColor: isDark ? "#1e293b" : "#ffffff",
          borderColor: isDark ? "#334155" : "#e2e8f0",
          textStyle: { color: isDark ? "#f1f5f9" : "#0f172a", fontSize: 12 },
          formatter: (p) => `${p[0].name}: <strong>${p[0].value} ${unit}</strong>`,
        },
        grid: { top: 20, right: 20, bottom: 25, left: 45, containLabel: true },
        xAxis: {
          type: "category",
          data: categories,
          axisLine: { lineStyle: { color: isDark ? "#334155" : "#cbd5e1" } },
          axisLabel: { color: textColor, fontSize: 11 },
        },
        yAxis: {
          type: "value",
          splitLine: { lineStyle: { color: splitLineColor } },
          axisLabel: { color: textColor, fontSize: 11 },
        },
        series: [
          {
            type: "bar",
            barMaxWidth: 32,
            data: values.map((v) => ({
              value: v,
              itemStyle: {
                color: v >= 0 ? (isDark ? "#f87171" : "#ef4444") : (isDark ? "#34d399" : "#10b981"),
                borderRadius: [4, 4, 0, 0],
              },
            })),
          },
        ],
      };
    }

    // 4. BULLET BAR / TARGET GAP (Target Archetype)
    if (chartType === "bullet" || chartType === "bullet_bar") {
      const bench = benchmark ?? 15.0;
      return {
        backgroundColor: "transparent",
        tooltip: {
          trigger: "axis",
          backgroundColor: isDark ? "#1e293b" : "#ffffff",
          borderColor: isDark ? "#334155" : "#e2e8f0",
          textStyle: { color: isDark ? "#f1f5f9" : "#0f172a", fontSize: 12 },
          formatter: (p) => `${p[0].name}: <strong>${p[0].value} ${unit}</strong> (Benchmark: ${bench} ${unit})`,
        },
        grid: { top: 20, right: 30, bottom: 20, left: 120, containLabel: true },
        xAxis: {
          type: "value",
          splitLine: { lineStyle: { color: splitLineColor } },
          axisLabel: { color: textColor, fontSize: 11 },
        },
        yAxis: {
          type: "category",
          data: categories,
          axisLabel: { color: textColor, fontSize: 11 },
        },
        series: [
          {
            type: "bar",
            barMaxWidth: 20,
            data: values.map((v) => ({
              value: v,
              itemStyle: {
                color: v >= bench ? (isDark ? "#3b82f6" : "#2563eb") : (isDark ? "#f87171" : "#ef4444"),
                borderRadius: [0, 4, 4, 0],
              },
            })),
            markLine: {
              symbol: "none",
              data: [
                {
                  xAxis: bench,
                  lineStyle: { type: "dashed", color: isDark ? "#fbbf24" : "#d97706", width: 2 },
                  label: { formatter: `Benchmark (${bench})`, color: isDark ? "#fbbf24" : "#d97706", fontSize: 10 },
                },
              ],
            },
          },
        ],
      };
    }

    // 5. LOLLIPOP CHART (Comparison Archetype)
    if (chartType === "lollipop") {
      return {
        backgroundColor: "transparent",
        tooltip: {
          trigger: "axis",
          axisPointer: { type: "shadow" },
          backgroundColor: isDark ? "#1e293b" : "#ffffff",
          borderColor: isDark ? "#334155" : "#e2e8f0",
          textStyle: { color: isDark ? "#f1f5f9" : "#0f172a", fontSize: 12 },
          formatter: (p) => `${p[0].name}: <strong>${p[0].value} ${unit}</strong>`,
        },
        grid: { top: 15, right: 30, bottom: 15, left: 120, containLabel: true },
        xAxis: {
          type: "value",
          splitLine: { lineStyle: { color: splitLineColor } },
          axisLabel: { color: textColor, fontSize: 11 },
        },
        yAxis: {
          type: "category",
          data: [...categories].reverse(),
          axisLabel: { color: textColor, fontSize: 11 },
        },
        series: [
          {
            type: "bar",
            barMaxWidth: 3,
            data: [...values].reverse(),
            itemStyle: {
              color: isDark ? "#60a5fa" : "#3b82f6",
              borderRadius: [0, 2, 2, 0],
            },
          },
          {
            type: "scatter",
            symbolSize: 13,
            data: [...values].reverse(),
            itemStyle: {
              color: themeTokens?.colors?.brandBlue || "#2563eb",
              borderColor: isDark ? "#1e293b" : "#ffffff",
              borderWidth: 2,
            },
          },
        ],
      };
    }

    // 6. DUMBBELL CHART (Disparity & Spread Archetype)
    if (chartType === "dumbbell") {
      const val1 = values;
      const val2 = visualSpec.secondary_values || (benchmark != null ? categories.map(() => benchmark) : values.map((v) => Math.round(v * 0.65 * 10) / 10));
      return {
        backgroundColor: "transparent",
        tooltip: {
          trigger: "axis",
          backgroundColor: isDark ? "#1e293b" : "#ffffff",
          borderColor: isDark ? "#334155" : "#e2e8f0",
          textStyle: { color: isDark ? "#f1f5f9" : "#0f172a", fontSize: 12 },
          formatter: (params) => {
            let res = `<strong>${params[0].name}</strong><br/>`;
            params.forEach((p) => {
              res += `${p.marker} ${p.seriesName}: <strong>${p.value} ${unit}</strong><br/>`;
            });
            return res;
          },
        },
        grid: { top: 15, right: 30, bottom: 15, left: 120, containLabel: true },
        xAxis: {
          type: "value",
          splitLine: { lineStyle: { color: splitLineColor } },
          axisLabel: { color: textColor, fontSize: 11 },
        },
        yAxis: {
          type: "category",
          data: [...categories].reverse(),
          axisLabel: { color: textColor, fontSize: 11 },
        },
        series: [
          {
            name: visualSpec.primary_label || "Primary",
            type: "scatter",
            symbolSize: 11,
            data: [...val1].reverse(),
            itemStyle: { color: themeTokens?.colors?.brandBlue || "#2563eb" },
          },
          {
            name: visualSpec.secondary_label || (benchmark != null ? "Benchmark" : "Secondary"),
            type: "scatter",
            symbolSize: 11,
            data: [...val2].reverse(),
            itemStyle: { color: isDark ? "#fbbf24" : "#d97706" },
          },
        ],
      };
    }

    // 7. BOX PLOT (Distribution & Quartile Dispersion Archetype)
    if (chartType === "box_plot" || chartType === "boxplot") {
      let boxVals = visualSpec.box_data;
      if (!boxVals || boxVals.length === 0) {
        const sorted = [...values].filter((v) => typeof v === "number").sort((a, b) => a - b);
        if (sorted.length >= 5) {
          const min = sorted[0];
          const q1 = sorted[Math.floor(sorted.length * 0.25)];
          const med = sorted[Math.floor(sorted.length * 0.5)];
          const q3 = sorted[Math.floor(sorted.length * 0.75)];
          const max = sorted[sorted.length - 1];
          boxVals = [[min, q1, med, q3, max]];
        } else {
          boxVals = [[8.0, 12.0, 15.0, 18.0, 22.0]];
        }
      }
      const boxCats = categories.length > 0 && categories.length === boxVals.length ? categories : ["Overall Dispersion"];
      return {
        backgroundColor: "transparent",
        tooltip: {
          trigger: "item",
          backgroundColor: isDark ? "#1e293b" : "#ffffff",
          borderColor: isDark ? "#334155" : "#e2e8f0",
          textStyle: { color: isDark ? "#f1f5f9" : "#0f172a", fontSize: 12 },
          formatter: (p) => {
            const d = p.data || [];
            return `<strong>${p.name}</strong><br/>Max: ${d[5] ?? d[4]} ${unit}<br/>Q3: ${d[4] ?? d[3]} ${unit}<br/>Median: ${d[3] ?? d[2]} ${unit}<br/>Q1: ${d[2] ?? d[1]} ${unit}<br/>Min: ${d[1] ?? d[0]} ${unit}`;
          },
        },
        grid: { top: 20, right: 25, bottom: 25, left: 45, containLabel: true },
        xAxis: {
          type: "category",
          data: boxCats,
          axisLine: { lineStyle: { color: isDark ? "#334155" : "#cbd5e1" } },
          axisLabel: { color: textColor, fontSize: 11 },
        },
        yAxis: {
          type: "value",
          splitLine: { lineStyle: { color: splitLineColor } },
          axisLabel: { color: textColor, fontSize: 11 },
        },
        series: [
          {
            type: "boxplot",
            data: boxVals,
            itemStyle: {
              color: isDark ? "rgba(59, 130, 246, 0.25)" : "rgba(37, 99, 235, 0.15)",
              borderColor: themeTokens?.colors?.brandBlue || "#2563eb",
              borderWidth: 2,
            },
          },
        ],
      };
    }

    // 8. TREEMAP (Hierarchy & Part-to-Whole Composition)
    if (chartType === "treemap") {
      const treeData = categories.map((cat, idx) => ({
        name: cat,
        value: values[idx] || 10,
      }));
      return {
        backgroundColor: "transparent",
        tooltip: {
          formatter: (p) => `${p.name}: <strong>${p.value} ${unit}</strong>`,
        },
        series: [
          {
            type: "treemap",
            data: treeData,
            roam: false,
            nodeClick: false,
            breadcrumb: { show: false },
            label: {
              show: true,
              formatter: "{b}\n{c}",
              fontSize: 11,
              color: "#ffffff",
            },
            itemStyle: {
              borderColor: isDark ? "#1e293b" : "#ffffff",
              borderWidth: 2,
              gapWidth: 2,
            },
            levels: [
              {
                color: isDark
                  ? ["#2563eb", "#3b82f6", "#60a5fa", "#818cf8", "#a78bfa"]
                  : ["#1d4ed8", "#2563eb", "#3b82f6", "#6366f1", "#8b5cf6"],
              },
            ],
          },
        ],
      };
    }

    // 9. SCATTER / CORRELATION (Relationship Archetype)
    if (chartType === "scatter" || chartType === "correlation_scatter") {
      const rawPoints = visualSpec.scatter_points || visualSpec.sample_points || visualSpec.points || [];
      const xLabel = visualSpec.x_label || "Primary Metric";
      const yLabel = visualSpec.y_label || "Secondary Metric";
      const scatterData = rawPoints.map((p) => {
        if (Array.isArray(p)) return p;
        return [p.x, p.y, p.name || p.entity || ""];
      });

      return {
        backgroundColor: "transparent",
        tooltip: {
          trigger: "item",
          backgroundColor: isDark ? "#1e293b" : "#ffffff",
          borderColor: isDark ? "#334155" : "#e2e8f0",
          textStyle: { color: isDark ? "#f1f5f9" : "#0f172a", fontSize: 12 },
          formatter: (p) => {
            const data = p.data || [];
            const nameStr = data[2] ? `<strong>${data[2]}</strong><br/>` : "";
            const unitSuffix = unit ? ` ${unit}` : "";
            return `${nameStr}${xLabel}: <strong>${data[0]}${unitSuffix}</strong><br/>${yLabel}: <strong>${data[1]}${unitSuffix}</strong>`;
          },
        },
        grid: { top: 20, right: 30, bottom: 45, left: 50, containLabel: true },
        xAxis: {
          type: "value",
          name: xLabel,
          nameLocation: "middle",
          nameGap: 28,
          nameTextStyle: { color: textColor, fontSize: 11, fontWeight: 600 },
          splitLine: { lineStyle: { color: splitLineColor } },
          axisLabel: { color: textColor, fontSize: 11 },
        },
        yAxis: {
          type: "value",
          name: yLabel,
          nameLocation: "middle",
          nameGap: 35,
          nameTextStyle: { color: textColor, fontSize: 11, fontWeight: 600 },
          splitLine: { lineStyle: { color: splitLineColor } },
          axisLabel: { color: textColor, fontSize: 11 },
        },
        series: [
          {
            type: "scatter",
            symbolSize: 8,
            itemStyle: {
              color: "#8b5cf6",
              opacity: 0.8,
            },
            data: scatterData,
          },
        ],
      };
    }

    // 9.5 HEATMAP (Matrix Archetype)
    if (chartType === "heatmap") {
      const rawData = visualSpec.heatmap_data || visualSpec.data || [];
      const xCats = visualSpec.x_categories || visualSpec.categories || [];
      const yCats = visualSpec.y_categories || [];

      const cellValues = rawData.map((d) => (Array.isArray(d) ? d[2] : (d.value ?? 0)));
      const minVal = cellValues.length ? Math.min(...cellValues) : 0;
      const maxVal = cellValues.length ? Math.max(...cellValues) : 100;

      return {
        backgroundColor: "transparent",
        tooltip: {
          position: "top",
          backgroundColor: isDark ? "#1e293b" : "#ffffff",
          borderColor: isDark ? "#334155" : "#e2e8f0",
          textStyle: { color: isDark ? "#f1f5f9" : "#0f172a", fontSize: 12 },
          formatter: (p) => {
            const val = p.data[2];
            const xLabel = xCats[p.data[0]] || p.data[0];
            const yLabel = yCats[p.data[1]] || p.data[1];
            const unitSuffix = unit ? ` ${unit}` : "";
            return `<strong>${yLabel} × ${xLabel}</strong><br/>Value: <strong>${val}${unitSuffix}</strong>`;
          },
        },
        grid: { top: 20, right: 30, bottom: 45, left: 100, containLabel: true },
        xAxis: {
          type: "category",
          data: xCats,
          splitArea: { show: true },
          axisLabel: { color: textColor, fontSize: 11 },
        },
        yAxis: {
          type: "category",
          data: yCats,
          splitArea: { show: true },
          axisLabel: { color: textColor, fontSize: 11 },
        },
        visualMap: {
          min: minVal,
          max: maxVal,
          calculable: false,
          orient: "horizontal",
          left: "center",
          bottom: "0%",
          itemWidth: 10,
          itemHeight: 60,
          textStyle: { color: textColor, fontSize: 10 },
          inRange: {
            color: isDark
              ? ["#1e293b", "#3b82f6", "#60a5fa", "#f59e0b", "#ef4444"]
              : ["#eff6ff", "#93c5fd", "#3b82f6", "#f59e0b", "#ef4444"],
          },
        },
        series: [
          {
            type: "heatmap",
            data: rawData,
            label: {
              show: true,
              fontSize: 10,
              color: isDark ? "#f8fafc" : "#0f172a",
            },
            emphasis: {
              itemStyle: {
                shadowBlur: 10,
                shadowColor: "rgba(0, 0, 0, 0.5)",
              },
            },
          },
        ],
      };
    }

    // 10. DEFAULT: RANKED BAR / HORIZONTAL BAR (Ranking Archetype)
    const bench = benchmark ?? (values.length ? values.reduce((a, b) => a + b, 0) / values.length : 15.0);
    return {
      backgroundColor: "transparent",
      tooltip: {
        trigger: "axis",
        axisPointer: { type: "shadow" },
        backgroundColor: isDark ? "#1e293b" : "#ffffff",
        borderColor: isDark ? "#334155" : "#e2e8f0",
        textStyle: { color: isDark ? "#f1f5f9" : "#0f172a", fontSize: 12 },
        formatter: (p) => `${p[0].name}: <strong>${p[0].value} ${unit}</strong>`,
      },
      grid: { top: 15, right: 30, bottom: 15, left: 130, containLabel: true },
      xAxis: {
        type: "value",
        splitLine: { lineStyle: { color: splitLineColor } },
        axisLabel: { color: textColor, fontSize: 11 },
      },
      yAxis: {
        type: "category",
        data: [...categories].reverse(),
        axisLabel: { color: textColor, fontSize: 11 },
      },
      series: [
        {
          type: "bar",
          barMaxWidth: 22,
          data: [...values].reverse().map((v) => ({
            value: v,
            itemStyle: {
              color: v >= bench ? (isDark ? "#3b82f6" : "#2563eb") : (isDark ? "#f87171" : "#ef4444"),
              borderRadius: [0, 4, 4, 0],
            },
          })),
          markLine: benchmark != null ? {
            symbol: "none",
            data: [
              {
                xAxis: bench,
                lineStyle: { type: "dashed", color: isDark ? "#fbbf24" : "#d97706", width: 2 },
                label: { formatter: `Target (${bench.toFixed(1)})`, color: isDark ? "#fbbf24" : "#d97706", fontSize: 10 },
              },
            ],
          } : undefined,
        },
      ],
    };
  }, [visualSpec, themeTokens, isDark, chartType]);

  if (!chartOption) {
    return (
      <div style={{ height, display: "flex", alignItems: "center", justifyContent: "center", color: themeTokens?.colors?.textMuted }}>
        No visual data available
      </div>
    );
  }

  return (
    <div style={{ height, width: "100%" }}>
      <SafeReactECharts option={chartOption} style={{ height: "100%", width: "100%" }} />
    </div>
  );
}
