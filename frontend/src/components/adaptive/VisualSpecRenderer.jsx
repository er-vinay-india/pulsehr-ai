import React, { useMemo } from "react";
import SafeReactECharts from "../charts/SafeReactECharts";

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
  const chartOption = useMemo(() => {
    if (!visualSpec) return null;

    const textColor = isDark ? "#94a3b8" : "#475569";
    const splitLineColor = isDark ? "rgba(255, 255, 255, 0.08)" : "rgba(0, 0, 0, 0.06)";
    const chartType = (visualSpec.chart_type || "ranked_bar").toLowerCase();

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

    // 4. BULLET BAR / TARGET GAP
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

    // 5. DIVERGING BAR / BOTH EXTREMES COMPARISON
    if (chartType === "diverging_bar" || (chartType === "ranked_bar" && visualSpec.bottom_categories && visualSpec.bottom_categories.length > 0)) {
      const topCats = visualSpec.categories || [];
      const topVals = visualSpec.values || [];
      const botCats = visualSpec.bottom_categories || [];
      const botVals = visualSpec.bottom_values || [];

      // Combine both extremes for side-by-side or stacked extreme comparison
      const combinedCats = [...topCats.map((c) => `[Top] ${c}`), ...botCats.map((c) => `[Bottom] ${c}`)];
      const combinedVals = [...topVals, ...botVals];

      return {
        backgroundColor: "transparent",
        tooltip: {
          trigger: "axis",
          backgroundColor: isDark ? "#1e293b" : "#ffffff",
          borderColor: isDark ? "#334155" : "#e2e8f0",
          textStyle: { color: isDark ? "#f1f5f9" : "#0f172a", fontSize: 12 },
          formatter: (p) => `${p[0].name}: <strong>${p[0].value} ${unit}</strong>`,
        },
        grid: { top: 15, right: 30, bottom: 15, left: 140, containLabel: true },
        xAxis: {
          type: "value",
          splitLine: { lineStyle: { color: splitLineColor } },
          axisLabel: { color: textColor, fontSize: 11 },
        },
        yAxis: {
          type: "category",
          data: [...combinedCats].reverse(),
          axisLabel: { color: textColor, fontSize: 10 },
        },
        series: [
          {
            type: "bar",
            barMaxWidth: 18,
            data: [...combinedVals].reverse().map((v, idx) => {
              const isTop = idx >= botCats.length;
              return {
                value: v,
                itemStyle: {
                  color: isTop ? (isDark ? "#3b82f6" : "#2563eb") : (isDark ? "#f87171" : "#ef4444"),
                  borderRadius: [0, 4, 4, 0],
                },
              };
            }),
          },
        ],
      };
    }

    // 6. RANKED DOT PLOT (Compact Multi-Entity Archetype)
    if (chartType === "dot_plot" || chartType === "ranked_dot_plot") {
      return {
        backgroundColor: "transparent",
        tooltip: {
          trigger: "item",
          backgroundColor: isDark ? "#1e293b" : "#ffffff",
          borderColor: isDark ? "#334155" : "#e2e8f0",
          textStyle: { color: isDark ? "#f1f5f9" : "#0f172a", fontSize: 12 },
          formatter: (p) => `${p.name}: <strong>${p.value} ${unit}</strong>`,
        },
        grid: { top: 15, right: 25, bottom: 20, left: 130, containLabel: true },
        xAxis: {
          type: "value",
          splitLine: { lineStyle: { color: splitLineColor } },
          axisLabel: { color: textColor, fontSize: 11 },
        },
        yAxis: {
          type: "category",
          data: [...categories].reverse(),
          axisLabel: { color: textColor, fontSize: 10 },
        },
        series: [
          {
            type: "scatter",
            symbolSize: 12,
            itemStyle: { color: themeTokens?.colors?.brandBlue || "#2563eb" },
            data: [...values].reverse(),
          },
        ],
      };
    }

    // 6.5 SCATTER / CORRELATION (Relationship Archetype)
    if (chartType === "scatter" || chartType === "correlation_scatter") {
      const rawPoints = visualSpec.scatter_points || visualSpec.sample_points || visualSpec.points || [];
      const xLabel = visualSpec.x_label || "SO2";
      const yLabel = visualSpec.y_label || "NO2";
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

    // 7. DEFAULT: RANKED BAR / HORIZONTAL BAR (Ranking Archetype)
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
  }, [visualSpec, themeTokens, isDark]);

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
