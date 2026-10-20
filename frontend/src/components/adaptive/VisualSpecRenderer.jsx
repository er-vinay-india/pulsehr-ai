import React, { useMemo } from "react";
import * as echarts from "echarts";
import SafeReactECharts from "../charts/SafeReactECharts";
import { Award, Trophy, MapPin, AlertCircle } from "lucide-react";
import { resolvePresentationLabel } from "../../design-system/registries/PresentationLabelResolver";
import worldMap from "../../assets/maps/world.json";
import indiaMap from "../../assets/maps/india.json";
import usaMap from "../../assets/maps/usa.json";

// Register offline local maps once
if (typeof window !== "undefined") {
  try {
    if (!echarts.getMap("world")) echarts.registerMap("world", worldMap);
    if (!echarts.getMap("india")) echarts.registerMap("india", indiaMap);
    if (!echarts.getMap("usa")) echarts.registerMap("usa", usaMap);
  } catch (err) {
    console.warn("Failed to register offline ECharts maps:", err);
  }
}

const CITY_STATE_CENTROIDS = {
  "bengaluru": [77.5946, 12.9716],
  "bangalore": [77.5946, 12.9716],
  "mumbai": [72.8777, 19.0760],
  "bombay": [72.8777, 19.0760],
  "delhi": [77.1025, 28.7041],
  "new delhi": [77.1025, 28.7041],
  "kolkata": [88.3639, 22.5726],
  "calcutta": [88.3639, 22.5726],
  "chennai": [80.2707, 13.0827],
  "hyderabad": [78.4867, 17.3850],
  "pune": [73.8567, 18.5204],
  "ahmedabad": [72.5714, 23.0225],
  "karnataka": [75.7139, 15.3173],
  "maharashtra": [75.7139, 19.7515],
  "west bengal": [87.8550, 22.9868],
  "tamil nadu": [78.6569, 11.1271],
  "telangana": [79.0193, 18.1124],
  "andhra pradesh": [79.7400, 15.9129],
  "uttar pradesh": [80.9462, 26.8467],
  "bihar": [85.3131, 25.0961],
  "rajasthan": [74.2179, 27.0238],
  "madhya pradesh": [78.6569, 22.9734],
  "gujarat": [71.1924, 22.2587],
  "kerala": [76.2711, 10.8505],
  "odisha": [85.0985, 20.9517],
  "punjab": [75.3412, 31.1471],
  "haryana": [76.0856, 29.0588],
  "austin": [-97.7431, 30.2672],
  "chicago": [-87.6298, 41.8781],
  "san francisco": [-122.4194, 37.7749],
  "new york": [-74.0060, 40.7128],
  "london": [-0.1278, 51.5074],
  "paris": [2.3522, 48.8566],
  "singapore": [103.8198, 1.3521],
  "tokyo": [139.6503, 35.6762],
  "sydney": [151.2093, -33.8688]
};

const INDIA_STATE_ALIASES = {
  "orissa": "Odisha",
  "uttaranchal": "Uttarakhand",
  "pondicherry": "Puducherry",
  "andaman & nicobar islands": "Andaman and Nicobar Islands",
  "andaman & nicobar island": "Andaman and Nicobar Islands",
  "andaman and nicobar": "Andaman and Nicobar Islands",
  "andaman and nicobar islands": "Andaman and Nicobar Islands",
  "andaman and nicobar island": "Andaman and Nicobar Islands",
  "dadra & nagar haveli": "Dadra and Nagar Haveli",
  "daman & diu": "Daman and Diu",
  "nct of delhi": "Delhi",
  "jammu & kashmir": "Jammu and Kashmir",
  "jammu and kashmir": "Jammu and Kashmir",
};

/**
 * Computes polygon/multipolygon centroids dynamically from GeoJSON features.
 * Guarantees every single state and union territory has an exact geometric pin coordinate.
 */
function extractGeoCentroids(geoJson) {
  if (!geoJson || !geoJson.features) return {};
  const centroids = {};
  geoJson.features.forEach((feature) => {
    let minX = Infinity, maxX = -Infinity, minY = Infinity, maxY = -Infinity;
    function walk(coords) {
      if (typeof coords[0] === "number") {
        const [x, y] = coords;
        if (x < minX) minX = x;
        if (x > maxX) maxX = x;
        if (y < minY) minY = y;
        if (y > maxY) maxY = y;
      } else if (Array.isArray(coords)) {
        coords.forEach(walk);
      }
    }
    if (feature.geometry && feature.geometry.coordinates) {
      walk(feature.geometry.coordinates);
    }
    if (minX !== Infinity) {
      const name = (feature.properties?.name || feature.properties?.state_name || "").toLowerCase().trim();
      if (name) {
        centroids[name] = [
          Number(((minX + maxX) / 2).toFixed(4)),
          Number(((minY + maxY) / 2).toFixed(4)),
        ];
      }
    }
  });
  return centroids;
}

const INDIA_GEO_CENTROIDS = extractGeoCentroids(indiaMap);

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
  const secondaryIds = visualSpec.secondary_ids || [];

  const items = [
    {
      rank: 2,
      label: resolvePresentationLabel(podiumCats[1]?.display_label || categories[1] || "2nd Place"),
      fullLabel: resolvePresentationLabel(podiumCats[1]?.full_label || categories[1] || "2nd Place"),
      secondaryId: secondaryIds[1],
      value: values[1] != null ? values[1] : "-",
      pedestalHeight: "80px",
      badgeColor: isDark ? "#94a3b8" : "#64748b",
      badgeBg: isDark ? "rgba(148, 163, 184, 0.2)" : "rgba(100, 116, 139, 0.15)",
      borderColor: isDark ? "#475569" : "#cbd5e1",
      bgColor: isDark ? "rgba(30, 41, 59, 0.8)" : "rgba(241, 245, 249, 0.9)",
    },
    {
      rank: 1,
      label: resolvePresentationLabel(podiumCats[0]?.display_label || categories[0] || "1st Place"),
      fullLabel: resolvePresentationLabel(podiumCats[0]?.full_label || categories[0] || "1st Place"),
      secondaryId: secondaryIds[0],
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
      label: resolvePresentationLabel(podiumCats[2]?.display_label || categories[2] || "3rd Place"),
      fullLabel: resolvePresentationLabel(podiumCats[2]?.full_label || categories[2] || "3rd Place"),
      secondaryId: secondaryIds[2],
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
        gap: "8px",
        padding: "10px 8px 6px",
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

          {/* Category Display Label (with optional secondary identifier) */}
          <div
            title={item.fullLabel + (item.secondaryId ? ` (ID: ${item.secondaryId})` : "")}
            style={{
              fontSize: "0.72rem",
              fontWeight: 600,
              color: isDark ? "#cbd5e1" : "#334155",
              lineHeight: 1.25,
              height: item.secondaryId ? "36px" : "28px",
              display: "flex",
              flexDirection: "column",
              alignItems: "center",
              justifyContent: "center",
              marginBottom: "8px",
              cursor: "help",
              textAlign: "center",
              maxWidth: "100%",
            }}
          >
            <span
              style={{
                overflow: "hidden",
                textOverflow: "ellipsis",
                whiteSpace: "nowrap",
                maxWidth: "100%",
                display: "block",
              }}
            >
              {item.label}
            </span>
            {item.secondaryId && (
              <span
                style={{
                  fontSize: "0.64rem",
                  color: themeTokens?.colors?.textMuted || "#64748b",
                  fontWeight: 500,
                  display: "block",
                }}
              >
                ID: {item.secondaryId}
              </span>
            )}
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

    const formatAxisValue = (v) => {
      if (typeof v !== "number") return v;
      const abs = Math.abs(v);
      if (abs >= 1000000) {
        return `${(v / 1000000).toFixed(abs % 1000000 === 0 ? 0 : 1)}M`;
      }
      if (abs >= 1000) {
        return `${(v / 1000).toFixed(abs % 1000 === 0 ? 0 : 1)}K`;
      }
      return Number.isInteger(v) ? v : v.toFixed(1);
    };

    const formatCategoryLabel = (val, maxLen = 18) => {
      if (typeof val !== "string") return val;
      return val.length > maxLen ? `${val.slice(0, maxLen - 2)}…` : val;
    };

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
          confine: true,
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
        grid: { top: 35, right: 15, bottom: 25, left: 15, containLabel: true },
        xAxis: {
          type: "category",
          data: categories,
          axisLine: { lineStyle: { color: isDark ? "#334155" : "#cbd5e1" } },
          axisLabel: { color: textColor, fontSize: 11, formatter: (v) => formatCategoryLabel(v, 16) },
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
          confine: true,
          backgroundColor: isDark ? "#1e293b" : "#ffffff",
          borderColor: isDark ? "#334155" : "#e2e8f0",
          textStyle: { color: isDark ? "#f1f5f9" : "#0f172a", fontSize: 12 },
          formatter: (p) => `${p[0].name}: <strong>${p[0].value} ${unit}</strong>`,
        },
        grid: { top: 25, right: 20, bottom: 25, left: 15, containLabel: true },
        xAxis: {
          type: "category",
          data: categories,
          axisLine: { lineStyle: { color: isDark ? "#334155" : "#cbd5e1" } },
          axisLabel: { color: textColor, fontSize: 11, formatter: (v) => formatCategoryLabel(v, 16) },
        },
        yAxis: {
          type: "value",
          splitLine: { lineStyle: { color: splitLineColor } },
          axisLabel: { color: textColor, fontSize: 11, formatter: formatAxisValue },
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
          confine: true,
          backgroundColor: isDark ? "#1e293b" : "#ffffff",
          borderColor: isDark ? "#334155" : "#e2e8f0",
          textStyle: { color: isDark ? "#f1f5f9" : "#0f172a", fontSize: 12 },
          formatter: (p) => `${p[0].name}: <strong>${p[0].value} ${unit}</strong>`,
        },
        grid: { top: 20, right: 20, bottom: 25, left: 15, containLabel: true },
        xAxis: {
          type: "category",
          data: categories,
          axisLine: { lineStyle: { color: isDark ? "#334155" : "#cbd5e1" } },
          axisLabel: { color: textColor, fontSize: 11, formatter: (v) => formatCategoryLabel(v, 16) },
        },
        yAxis: {
          type: "value",
          splitLine: { lineStyle: { color: splitLineColor } },
          axisLabel: { color: textColor, fontSize: 11, formatter: formatAxisValue },
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
      const hasBench = benchmark != null;
      const bench = hasBench ? benchmark : null;
      return {
        backgroundColor: "transparent",
        tooltip: {
          trigger: "axis",
          confine: true,
          backgroundColor: isDark ? "#1e293b" : "#ffffff",
          borderColor: isDark ? "#334155" : "#e2e8f0",
          textStyle: { color: isDark ? "#f1f5f9" : "#0f172a", fontSize: 12 },
          formatter: (p) => hasBench ? `${p[0].name}: <strong>${p[0].value} ${unit}</strong> (Benchmark: ${bench} ${unit})` : `${p[0].name}: <strong>${p[0].value} ${unit}</strong>`,
        },
        grid: { top: 20, right: 25, bottom: 20, left: 10, containLabel: true },
        xAxis: {
          type: "value",
          splitLine: { lineStyle: { color: splitLineColor } },
          axisLabel: { color: textColor, fontSize: 11, formatter: formatAxisValue },
        },
        yAxis: {
          type: "category",
          data: categories,
          axisLabel: { color: textColor, fontSize: 11, formatter: (v) => formatCategoryLabel(v, 18) },
        },
        series: [
          {
            type: "bar",
            barMaxWidth: 20,
            data: values.map((v) => ({
              value: v,
              itemStyle: {
                color: hasBench ? (v >= bench ? (isDark ? "#3b82f6" : "#2563eb") : (isDark ? "#f87171" : "#ef4444")) : (themeTokens?.colors?.brandBlue || "#2563eb"),
                borderRadius: [0, 4, 4, 0],
              },
            })),
            markLine: hasBench ? {
              symbol: "none",
              data: [
                {
                  xAxis: bench,
                  lineStyle: { type: "dashed", color: isDark ? "#fbbf24" : "#d97706", width: 2 },
                  label: { formatter: `Benchmark (${bench})`, color: isDark ? "#fbbf24" : "#d97706", fontSize: 10 },
                },
              ],
            } : undefined,
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
          confine: true,
          backgroundColor: isDark ? "#1e293b" : "#ffffff",
          borderColor: isDark ? "#334155" : "#e2e8f0",
          textStyle: { color: isDark ? "#f1f5f9" : "#0f172a", fontSize: 12 },
          formatter: (p) => `${p[0].name}: <strong>${p[0].value} ${unit}</strong>`,
        },
        grid: { top: 15, right: 25, bottom: 20, left: 10, containLabel: true },
        xAxis: {
          type: "value",
          splitLine: { lineStyle: { color: splitLineColor } },
          axisLabel: { color: textColor, fontSize: 11, formatter: formatAxisValue },
        },
        yAxis: {
          type: "category",
          data: [...categories].reverse(),
          axisLabel: { color: textColor, fontSize: 11, formatter: (v) => formatCategoryLabel(v, 18) },
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
          confine: true,
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
          top: 4,
          right: 15,
          textStyle: { color: textColor, fontSize: 11 },
          itemWidth: 10,
          itemHeight: 10,
        },
        grid: { top: 34, right: 25, bottom: 20, left: 10, containLabel: true },
        xAxis: {
          type: "value",
          splitLine: { lineStyle: { color: splitLineColor } },
          axisLabel: { color: textColor, fontSize: 11, formatter: formatAxisValue },
        },
        yAxis: {
          type: "category",
          data: [...categories].reverse(),
          axisLabel: { color: textColor, fontSize: 11, formatter: (v) => formatCategoryLabel(v, 18) },
        },
        series: [
          {
            name: resolvePresentationLabel(visualSpec.primary_label || "Primary"),
            type: "scatter",
            symbolSize: 11,
            data: [...val1].reverse(),
            itemStyle: { color: themeTokens?.colors?.brandBlue || "#2563eb" },
          },
          {
            name: resolvePresentationLabel(visualSpec.secondary_label || (benchmark != null ? "Benchmark" : "Secondary")),
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
          confine: true,
          backgroundColor: isDark ? "#1e293b" : "#ffffff",
          borderColor: isDark ? "#334155" : "#e2e8f0",
          textStyle: { color: isDark ? "#f1f5f9" : "#0f172a", fontSize: 12 },
          formatter: (p) => {
            const d = p.data || [];
            return `<strong>${p.name}</strong><br/>Max: ${d[5] ?? d[4]} ${unit}<br/>Q3: ${d[4] ?? d[3]} ${unit}<br/>Median: ${d[3] ?? d[2]} ${unit}<br/>Q1: ${d[2] ?? d[1]} ${unit}<br/>Min: ${d[1] ?? d[0]} ${unit}`;
          },
        },
        grid: { top: 20, right: 25, bottom: 25, left: 15, containLabel: true },
        xAxis: {
          type: "category",
          data: boxCats,
          axisLine: { lineStyle: { color: isDark ? "#334155" : "#cbd5e1" } },
          axisLabel: { color: textColor, fontSize: 11, formatter: (v) => formatCategoryLabel(v, 16) },
        },
        yAxis: {
          type: "value",
          splitLine: { lineStyle: { color: splitLineColor } },
          axisLabel: { color: textColor, fontSize: 11, formatter: formatAxisValue },
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
        value: values[idx] != null ? values[idx] : 0,
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
      const xLabel = resolvePresentationLabel(visualSpec.x_label, "Primary Metric");
      const yLabel = resolvePresentationLabel(visualSpec.y_label, "Secondary Metric");
      const scatterData = rawPoints.map((p) => {
        if (Array.isArray(p)) return p;
        return [p.x, p.y, p.name || p.entity || ""];
      });

      return {
        backgroundColor: "transparent",
        tooltip: {
          trigger: "item",
          confine: true,
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
        grid: { top: 20, right: 25, bottom: 42, left: 15, containLabel: true },
        xAxis: {
          type: "value",
          name: xLabel,
          nameLocation: "middle",
          nameGap: 24,
          nameTextStyle: { color: textColor, fontSize: 11, fontWeight: 600 },
          splitLine: { lineStyle: { color: splitLineColor } },
          axisLabel: { color: textColor, fontSize: 11, formatter: formatAxisValue },
        },
        yAxis: {
          type: "value",
          name: yLabel,
          nameLocation: "middle",
          nameGap: 30,
          nameTextStyle: { color: textColor, fontSize: 11, fontWeight: 600 },
          splitLine: { lineStyle: { color: splitLineColor } },
          axisLabel: { color: textColor, fontSize: 11, formatter: formatAxisValue },
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
          confine: true,
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
        grid: { top: 20, right: 25, bottom: 45, left: 15, containLabel: true },
        xAxis: {
          type: "category",
          data: xCats,
          splitArea: { show: true },
          axisLabel: {
            color: textColor,
            fontSize: 10,
            interval: 0,
            rotate: xCats.length > 5 ? 25 : 0,
            formatter: (v) => formatCategoryLabel(v, 14),
          },
        },
        yAxis: {
          type: "category",
          data: yCats,
          splitArea: { show: true },
          axisLabel: { color: textColor, fontSize: 11, formatter: (v) => formatCategoryLabel(v, 18) },
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

    // 9.8 GEOSPATIAL MAP (Choropleth, Bubble Map, Point Map Archetype)
    if (chartType === "map" || chartType === "choropleth" || chartType === "bubble_map" || chartType === "point_map") {
      const scope = visualSpec.geo_scope || "india";
      const isBubble = visualSpec.map_type === "bubble" || chartType === "bubble_map";
      const rawCategories = visualSpec.categories || [];
      const rawValues = visualSpec.values || [];

      // Prefer rich map_data if provided, fallback to raw categories & values
      let mapData = [];
      if (visualSpec.map_data && Array.isArray(visualSpec.map_data) && visualSpec.map_data.length > 0) {
        mapData = visualSpec.map_data.map((item) => {
          let cleanName = String(item.name || "").trim();
          const low = cleanName.toLowerCase();
          if (scope === "india" && INDIA_STATE_ALIASES[low]) {
            cleanName = INDIA_STATE_ALIASES[low];
          }
          return {
            ...item,
            name: cleanName,
            value: item.value != null ? item.value : 0,
          };
        });
      } else {
        mapData = rawCategories.map((cat, idx) => {
          let cleanName = String(cat).trim();
          const low = cleanName.toLowerCase();
          if (scope === "india" && INDIA_STATE_ALIASES[low]) {
            cleanName = INDIA_STATE_ALIASES[low];
          }
          const val = rawValues[idx] != null ? rawValues[idx] : 0;
          return { name: cleanName, value: val };
        });
      }

      const numericVals = mapData.map((d) => d.value).filter((v) => v != null && !isNaN(v));
      const minVal = numericVals.length ? Math.min(...numericVals) : 0;
      const maxVal = numericVals.length ? Math.max(...numericVals) : 100;

      if (isBubble) {
        // City / Location Point Map (Proportional Symbol Bubble Map)
        const bubblePoints = mapData.map((item) => {
          const cat = item.name;
          const low = String(cat).toLowerCase().trim();
          const aliased = INDIA_STATE_ALIASES[low] ? INDIA_STATE_ALIASES[low].toLowerCase() : low;
          const coords =
            CITY_STATE_CENTROIDS[low] ||
            CITY_STATE_CENTROIDS[aliased] ||
            INDIA_GEO_CENTROIDS[low] ||
            INDIA_GEO_CENTROIDS[aliased] ||
            [78.9629, 20.5937];
          const val = item.value != null ? item.value : 0;
          return {
            name: cat,
            value: [coords[0], coords[1], val],
            formatted_value: item.formatted_value,
            population: item.population,
            growth: item.growth,
            density: item.density,
          };
        });

        return {
          backgroundColor: "transparent",
          tooltip: {
            trigger: "item",
            confine: true,
            backgroundColor: isDark ? "#1e293b" : "#ffffff",
            borderColor: isDark ? "#334155" : "#e2e8f0",
            textStyle: { color: isDark ? "#f1f5f9" : "#0f172a", fontSize: 12 },
            formatter: (p) => {
              const d = p.data || {};
              const territoryName = p.name || d.name || "Territory";
              const val = Array.isArray(p.value) ? p.value[2] : p.value;
              const valFormatted = d.formatted_value || (val != null ? `${val}${unit ? ' ' + unit : ''}` : "N/A");
              const measLabel = visualSpec.measure_label || visualSpec.primary_label || "Metric";
              
              let html = `<div style="padding: 2px 4px; font-family: sans-serif; font-size: 12px; line-height: 1.45;">`;
              html += `<div style="font-weight: 700; font-size: 13px; margin-bottom: 5px; border-bottom: 1px solid ${isDark ? '#334155' : '#e2e8f0'}; padding-bottom: 3px;">${territoryName}</div>`;
              html += `<div style="display: flex; justify-content: space-between; gap: 12px; margin-bottom: 2px;"><span style="color: ${isDark ? '#94a3b8' : '#64748b'};">${measLabel}:</span><span style="font-weight: 700;">${valFormatted}</span></div>`;
              if (d.density && !measLabel.toLowerCase().includes("density")) {
                html += `<div style="display: flex; justify-content: space-between; gap: 12px; margin-bottom: 2px;"><span style="color: ${isDark ? '#94a3b8' : '#64748b'};">Density:</span><span style="font-weight: 600;">${d.density}</span></div>`;
              }
              if (d.growth && !measLabel.toLowerCase().includes("growth")) {
                html += `<div style="display: flex; justify-content: space-between; gap: 12px; margin-bottom: 2px;"><span style="color: ${isDark ? '#94a3b8' : '#64748b'};">Decadal Growth:</span><span style="font-weight: 600;">${d.growth}</span></div>`;
              }
              if (d.population && !measLabel.toLowerCase().includes("pop")) {
                html += `<div style="display: flex; justify-content: space-between; gap: 12px;"><span style="color: ${isDark ? '#94a3b8' : '#64748b'};">Population:</span><span style="font-weight: 600;">${d.population}</span></div>`;
              }
              html += `</div>`;
              return html;
            },
          },
          geo: {
            map: scope,
            roam: true,
            layoutCenter: ['50%', '46%'],
            layoutSize: '88%',
            scaleLimit: { min: 0.8, max: 4 },
            itemStyle: {
              areaColor: isDark ? "#1e293b" : "#f1f5f9",
              borderColor: isDark ? "#334155" : "#cbd5e1",
              borderWidth: 0.8,
            },
            emphasis: {
              itemStyle: { areaColor: isDark ? "#334155" : "#e2e8f0" },
            },
          },
          series: [
            {
              name: visualSpec.primary_label || "Locations",
              type: "scatter",
              coordinateSystem: "geo",
              data: bubblePoints,
              symbolSize: (val) => {
                const spread = Math.max(1, maxVal - minVal);
                const ratio = ((val[2] || 0) - minVal) / spread;
                return Math.max(10, Math.min(36, 10 + ratio * 26));
              },
              itemStyle: {
                color: isDark ? "#38bdf8" : "#2563eb",
                opacity: 0.85,
                shadowBlur: 4,
                shadowColor: "rgba(0,0,0,0.25)",
              },
            },
          ],
        };
      }

      // Choropleth Map (State or Country)
      return {
        backgroundColor: "transparent",
        tooltip: {
          trigger: "item",
          confine: true,
          backgroundColor: isDark ? "#1e293b" : "#ffffff",
          borderColor: isDark ? "#334155" : "#e2e8f0",
          textStyle: { color: isDark ? "#f1f5f9" : "#0f172a", fontSize: 12 },
          formatter: (p) => {
            const d = p.data || {};
            const territoryName = p.name || d.name || "Territory";
            const val = p.value != null && !isNaN(p.value) ? p.value : null;
            const valFormatted = d.formatted_value || (val != null ? `${val}${unit ? ' ' + unit : ''}` : "N/A");
            const measLabel = visualSpec.measure_label || visualSpec.primary_label || "Metric";
            
            let html = `<div style="padding: 2px 4px; font-family: sans-serif; font-size: 12px; line-height: 1.45;">`;
            html += `<div style="font-weight: 700; font-size: 13px; margin-bottom: 5px; border-bottom: 1px solid ${isDark ? '#334155' : '#e2e8f0'}; padding-bottom: 3px;">${territoryName}</div>`;
            html += `<div style="display: flex; justify-content: space-between; gap: 12px; margin-bottom: 2px;"><span style="color: ${isDark ? '#94a3b8' : '#64748b'};">${measLabel}:</span><span style="font-weight: 700;">${valFormatted}</span></div>`;
            if (d.density && !measLabel.toLowerCase().includes("density")) {
              html += `<div style="display: flex; justify-content: space-between; gap: 12px; margin-bottom: 2px;"><span style="color: ${isDark ? '#94a3b8' : '#64748b'};">Density:</span><span style="font-weight: 600;">${d.density}</span></div>`;
            }
            if (d.growth) {
              html += `<div style="display: flex; justify-content: space-between; gap: 12px; margin-bottom: 2px;"><span style="color: ${isDark ? '#94a3b8' : '#64748b'};">Decadal Growth:</span><span style="font-weight: 600;">${d.growth}</span></div>`;
            }
            if (d.population) {
              html += `<div style="display: flex; justify-content: space-between; gap: 12px;"><span style="color: ${isDark ? '#94a3b8' : '#64748b'};">Population:</span><span style="font-weight: 600;">${d.population}</span></div>`;
            }
            html += `</div>`;
            return html;
          },
        },
        visualMap: {
          min: minVal,
          max: maxVal,
          orient: "horizontal",
          left: "center",
          bottom: 0,
          calculable: true,
          itemWidth: 12,
          itemHeight: 75,
          textStyle: { color: textColor, fontSize: 10 },
          inRange: {
            color: isDark
              ? ["#1e293b", "#1e40af", "#2563eb", "#38bdf8", "#93c5fd"]
              : ["#eff6ff", "#bfdbfe", "#60a5fa", "#2563eb", "#1e40af"],
          },
        },
        series: [
          {
            name: visualSpec.primary_label || "Territory",
            type: "map",
            map: scope,
            roam: true,
            layoutCenter: ['50%', '46%'],
            layoutSize: '88%',
            scaleLimit: { min: 0.8, max: 4 },
            label: {
              show: false,
              fontSize: 9,
              color: isDark ? "#f1f5f9" : "#0f172a",
            },
            emphasis: {
              label: {
                show: true,
                fontSize: 10,
                color: isDark ? "#ffffff" : "#0f172a",
                fontWeight: "bold",
              },
              itemStyle: {
                areaColor: isDark ? "#38bdf8" : "#93c5fd",
                borderColor: isDark ? "#ffffff" : "#1e40af",
                borderWidth: 1.5,
              },
            },
            itemStyle: {
              areaColor: isDark ? "#0f172a" : "#f8fafc",
              borderColor: isDark ? "#334155" : "#cbd5e1",
              borderWidth: 0.8,
            },
            data: mapData,
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
        confine: true,
        backgroundColor: isDark ? "#1e293b" : "#ffffff",
        borderColor: isDark ? "#334155" : "#e2e8f0",
        textStyle: { color: isDark ? "#f1f5f9" : "#0f172a", fontSize: 12 },
        formatter: (p) => `${p[0].name}: <strong>${p[0].value} ${unit}</strong>`,
      },
      grid: { top: 15, right: 25, bottom: 20, left: 10, containLabel: true },
      xAxis: {
        type: "value",
        splitLine: { lineStyle: { color: splitLineColor } },
        axisLabel: { color: textColor, fontSize: 11, formatter: formatAxisValue },
      },
      yAxis: {
        type: "category",
        data: [...categories].reverse(),
        axisLabel: { color: textColor, fontSize: 11, formatter: (v) => formatCategoryLabel(v, 18) },
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
