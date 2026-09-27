import React, { useMemo, useState } from "react";
import { Info, ShieldCheck, Target, TrendingUp, AlertCircle, Table } from "lucide-react";
import SafeReactECharts from "../charts/SafeReactECharts";
import { useTheme } from "../../context/ThemeContext";

/**
 * Intelligent compact number formatter for metrics, ticks, tooltips, and data tables.
 */
function formatCompactNumber(val, unit = "") {
  if (val === null || val === undefined || isNaN(val)) return "—";
  const num = Number(val);
  const isCurr = unit === "$" || unit.toLowerCase() === "usd";
  const prefix = isCurr ? "$" : "";
  const suffix = !isCurr && unit ? ` ${unit}` : "";
  const abs = Math.abs(num);
  if (abs >= 1e9) return `${prefix}${(num / 1e9).toFixed(2)}B${suffix}`;
  if (abs >= 1e6) return `${prefix}${(num / 1e6).toFixed(2)}M${suffix}`;
  if (abs >= 1e3) return `${prefix}${(num / 1e3).toFixed(1)}K${suffix}`;
  if (abs >= 100) return `${prefix}${num.toLocaleString(undefined, { maximumFractionDigits: 0 })}${suffix}`;
  return `${prefix}${num.toLocaleString(undefined, { maximumFractionDigits: 1 })}${suffix}`;
}

/**
 * ForwardOutlookCard — Adaptive Dashboard Element 9 (Gate 9).
 * 
 * Renders one of three strictly verified forward-looking modes:
 * 1. Target-gap: Explicit recorded target variance without synthetic forecasting.
 * 2. Statistical forecast: Rolling-origin validated short-horizon forecast with empirical range.
 * 3. Outlook unavailable: Honest, constructive explanation when criteria or governance forbid forecasting.
 */
export default function ForwardOutlookCard({
  outlook,
  sheetId,
  snapshot,
  onInspect,
}) {
  const [showAccessibleTable, setShowAccessibleTable] = useState(false);
  const { isDark } = useTheme();

  if (!outlook) {
    return null;
  }

  const {
    kind,
    business_concept,
    metric_name,
    unit,
    temporal_grain,
    actual_value,
    target_value,
    gap_value,
    forecast_value,
    lower_bound,
    upper_bound,
    model_id,
    validation,
    points = [],
    next_review_period,
    why_available_or_unavailable,
    glance,
    explain,
    caption,
  } = outlook;

  // Accessible theme-aware foreground/background colors
  const actualLineColor = isDark ? "#38BDF8" : "#005A6B"; // Teal on light (7.4:1 AAA), Cyan on dark (6.8:1)
  const actualAreaStart = isDark ? "rgba(56, 189, 248, 0.2)" : "rgba(0, 90, 107, 0.14)";
  const forecastLineColor = isDark ? "#FBBF24" : "#B45309"; // Amber on light (5.5:1 AA), Gold on dark (7.2:1)
  const forecastRangeArea = isDark ? "rgba(251, 191, 36, 0.22)" : "rgba(180, 83, 9, 0.16)";

  const labelColor = isDark ? "#CBD5E1" : "#334155";
  const headingColor = isDark ? "#F8FAFC" : "#0B1F3A";
  const axisLineColor = isDark ? "#26384D" : "#CBD5E1";
  const splitLineColor = isDark ? "rgba(248, 250, 252, 0.08)" : "rgba(11, 31, 58, 0.08)";
  const tooltipBg = isDark ? "#172A40" : "#FFFFFF";
  const tooltipBorder = isDark ? "#26384D" : "#CBD5E1";
  const tooltipText = isDark ? "#F8FAFC" : "#0B1F3A";

  // Build ECharts option for statistical forecast
  const chartOption = useMemo(() => {
    if (kind !== "statistical_forecast" || !points || points.length === 0) {
      return {};
    }

    // For visual clarity and preventing label collisions, window chart to recent 16 periods + forecast.
    const displayPoints = points.length > 20 ? points.slice(-16) : points;
    const periods = displayPoints.map((p) => p.period_label || p.period);
    
    // Historical actuals: values for historical points, null for forecast point
    const actualSeries = displayPoints.map((p) => (p.actual_value != null ? p.actual_value : null));
    
    // Forecast series: starts from the last actual point to connect lines, then goes to forecast value
    const lastActualIdx = displayPoints.findIndex((p) => p.forecast_value != null) - 1;
    const forecastSeries = displayPoints.map((p, idx) => {
      if (idx === lastActualIdx && p.actual_value != null) {
        return p.actual_value;
      }
      return p.forecast_value != null ? p.forecast_value : null;
    });

    // Lower & Upper range series for forecast points
    const lowerSeries = displayPoints.map((p) => (p.lower_bound != null ? p.lower_bound : null));
    const upperSeries = displayPoints.map((p) => (p.upper_bound != null ? p.upper_bound : null));

    // Calculate Y-axis bounds with padding based on visible window
    const validVals = displayPoints.flatMap((p) => [p.actual_value, p.forecast_value, p.lower_bound, p.upper_bound]).filter((v) => v != null && isFinite(v));
    const minVal = validVals.length > 0 ? Math.min(...validVals) : 0;
    const maxVal = validVals.length > 0 ? Math.max(...validVals) : 100;
    const yPad = (maxVal - minVal) * 0.18 || 5;
    const yMin = Math.max(0, Math.floor(minVal - yPad));
    const yMax = Math.ceil(maxVal + yPad);

    return {
      backgroundColor: "transparent",
      tooltip: {
        trigger: "axis",
        backgroundColor: tooltipBg,
        borderColor: tooltipBorder,
        textStyle: { color: tooltipText, fontSize: 12 },
        extraCssText: "box-shadow: 0 4px 14px rgba(11, 31, 58, 0.12); border-radius: 6px;",
        formatter: (params) => {
          if (!params || params.length === 0) return "";
          const pIdx = params[0].dataIndex;
          const pt = displayPoints[pIdx];
          if (!pt) return "";
          const isForecast = pt.forecast_value != null;
          let html = `<div style="font-weight:700;margin-bottom:4px;color:${headingColor};">${pt.period_label || pt.period}</div>`;
          if (isForecast) {
            html += `<div style="color:${forecastLineColor};">Forecast: <strong>${formatCompactNumber(pt.forecast_value, unit)}</strong></div>`;
            if (pt.lower_bound != null && pt.upper_bound != null) {
              html += `<div style="color:${labelColor};font-size:11px;">Empirical range: ${formatCompactNumber(pt.lower_bound, unit)}–${formatCompactNumber(pt.upper_bound, unit)}</div>`;
            }
            html += `<div style="color:${labelColor};font-size:11px;margin-top:2px;">Model: ${validation?.model_label || "Validated Model"}</div>`;
          } else if (pt.actual_value != null) {
            html += `<div style="color:${actualLineColor};">Observed actual: <strong>${formatCompactNumber(pt.actual_value, unit)}</strong></div>`;
            if (pt.is_partial) {
              html += `<div style="color:${forecastLineColor};font-size:11px;">Partial period (excluded from training)</div>`;
            }
          }
          return html;
        },
      },
      legend: {
        show: true,
        bottom: 2,
        textStyle: { color: labelColor, fontSize: 11, fontWeight: 600 },
        data: ["Historical actuals", "Statistical forecast", "Forecast range"],
      },
      grid: {
        top: 28,
        left: 14,
        right: 20,
        bottom: 52,
        containLabel: true,
      },
      xAxis: {
        type: "category",
        data: periods,
        axisLine: { lineStyle: { color: axisLineColor } },
        axisLabel: {
          color: labelColor,
          fontSize: 10,
          fontWeight: 500,
          rotate: periods.length > 8 ? 30 : 0,
          margin: 8,
          interval: (idx) => {
            if (periods.length <= 8) return true;
            return idx % 2 === 0 || idx === periods.length - 1;
          },
        },
        splitLine: { show: false },
      },
      yAxis: {
        type: "value",
        min: yMin,
        max: yMax,
        splitNumber: 4,
        axisLine: { show: false },
        axisLabel: {
          color: labelColor,
          fontSize: 10,
          fontWeight: 500,
          formatter: (val) => formatCompactNumber(val, unit),
        },
        splitLine: { lineStyle: { color: splitLineColor, type: "dashed" } },
      },
      series: [
        {
          name: "Historical actuals",
          type: "line",
          data: actualSeries,
          smooth: false,
          showSymbol: true,
          symbolSize: 6,
          itemStyle: { color: actualLineColor },
          lineStyle: { width: 2.5, color: actualLineColor },
          areaStyle: {
            color: {
              type: "linear",
              x: 0,
              y: 0,
              x2: 0,
              y2: 1,
              colorStops: [
                { offset: 0, color: actualAreaStart },
                { offset: 1, color: "rgba(0, 0, 0, 0.0)" },
              ],
            },
          },
        },
        {
          name: "Statistical forecast",
          type: "line",
          data: forecastSeries,
          smooth: false,
          showSymbol: true,
          symbol: "diamond",
          symbolSize: 8,
          itemStyle: { color: forecastLineColor },
          lineStyle: { width: 2.5, color: forecastLineColor, type: "dashed" },
        },
        {
          name: "Forecast range",
          type: "line",
          data: lowerSeries,
          lineStyle: { opacity: 0 },
          stack: "confidence-band",
          symbol: "none",
        },
        {
          name: "Forecast range",
          type: "line",
          data: lowerSeries.map((low, i) => (upperSeries[i] != null && low != null ? upperSeries[i] - low : null)),
          lineStyle: { opacity: 0 },
          areaStyle: { color: forecastRangeArea },
          stack: "confidence-band",
          symbol: "none",
        },
      ],
    };
  }, [
    kind,
    points,
    unit,
    validation,
    actualLineColor,
    actualAreaStart,
    forecastLineColor,
    forecastRangeArea,
    labelColor,
    headingColor,
    axisLineColor,
    splitLineColor,
    tooltipBg,
    tooltipBorder,
    tooltipText,
  ]);

  return (
    <section
      className="adaptive-element-card adaptive-outlook-card"
      aria-labelledby="forward-outlook-heading"
      data-testid="forward-outlook-card"
    >
      <header className="adaptive-card-header">
        <div className="card-header-left">
          <span className="card-eyebrow" id="forward-outlook-heading">
            Forward outlook
          </span>
          <span className={`outlook-mode-pill mode-${kind}`}>
            {kind === "target_gap" && (
              <>
                <Target size={12} className="pill-icon" aria-hidden="true" />
                Target Comparison
              </>
            )}
            {kind === "statistical_forecast" && (
              <>
                <TrendingUp size={12} className="pill-icon" aria-hidden="true" />
                Backtested Forecast
              </>
            )}
            {kind === "outlook_unavailable" && (
              <>
                <ShieldCheck size={12} className="pill-icon" aria-hidden="true" />
                Evidence Withheld
              </>
            )}
          </span>
        </div>
        <button
          type="button"
          className="glance-info-btn"
          aria-label="Inspect forward outlook methodology and evidence"
          onClick={() => onInspect && onInspect("outlook")}
        >
          <Info size={16} aria-hidden="true" />
        </button>
      </header>

      {/* MODE 1: OUTLOOK UNAVAILABLE */}
      {kind === "outlook_unavailable" && (
        <div className="outlook-unavailable-body">
          <div className="unavailable-callout">
            <div className="callout-icon-col">
              <ShieldCheck size={20} className="shield-icon" aria-hidden="true" />
            </div>
            <div className="callout-text-col">
              <h4 className="unavailable-title">Forward Outlook Withheld</h4>
              <p className="unavailable-reason">{why_available_or_unavailable}</p>
            </div>
          </div>
          <div className="unavailable-footer-hint">
            <span>Governance Rule:</span> Outlook requires either an explicit documented target or $\ge 12$ periods with backtested performance beating a naïve baseline.
          </div>
        </div>
      )}

      {/* MODE 2: TARGET GAP */}
      {kind === "target_gap" && (
        <div className="outlook-target-body">
          <div className="target-headline-block">
            <div className="lead-value-row">
              <span className="lead-gap-value">{glance?.formatted_value}</span>
              <span className="lead-gap-badge">{actual_value >= target_value ? "Above Target" : "Below Target"}</span>
            </div>
            <p className="target-concept-label">
              Observed {metric_name} vs. Recorded Target Baseline
            </p>
          </div>

          <div className="target-metrics-grid">
            <div className="target-metric-box">
              <span className="box-label">Current Observed Actual</span>
              <span className="box-val">{formatCompactNumber(actual_value, unit)}</span>
            </div>
            <div className="target-metric-box">
              <span className="box-label">Recorded Target Plan</span>
              <span className="box-val">{formatCompactNumber(target_value, unit)}</span>
            </div>
            <div className="target-metric-box">
              <span className="box-label">Net Variance Gap</span>
              <span className={`box-val ${gap_value >= 0 ? "positive" : "negative"}`}>
                {gap_value > 0 ? "+" : ""}{formatCompactNumber(gap_value, unit)}
              </span>
            </div>
          </div>

          <div className="outlook-narrative-box">
            <p className="narrative-text">{why_available_or_unavailable}</p>
            {next_review_period && (
              <p className="review-text">
                <strong>Next review:</strong> {next_review_period}
              </p>
            )}
          </div>
        </div>
      )}

      {/* MODE 3: STATISTICAL FORECAST */}
      {kind === "statistical_forecast" && (
        <div className="outlook-forecast-body">
          <div className="forecast-headline-block">
            <div className="lead-value-row">
              <span className="lead-forecast-value">{glance?.formatted_value || formatCompactNumber(forecast_value, unit)}</span>
              <span className="range-badge">
                Range: {formatCompactNumber(lower_bound, unit)}–{formatCompactNumber(upper_bound, unit)}
              </span>
            </div>
            <p className="forecast-subtitle">
              Next {temporal_grain || "period"} projection for {metric_name} ({validation?.model_label || "Validated Model"})
            </p>
          </div>

          <div className="forecast-chart-container" style={{ minHeight: 250, position: "relative" }}>
            <SafeReactECharts
              option={chartOption}
              style={{ height: 240, width: "100%" }}
            />
          </div>

          <div className="forecast-footer-bar">
            <div className="validation-note">
              <span className="model-chip">{validation?.model_label}</span>
              <span className="wape-text">
                Backtested across {validation?.fold_count} folds (WAPE {(validation?.wape * 100).toFixed(1)}% vs. Baseline {(validation?.baseline_wape * 100).toFixed(1)}%)
              </span>
            </div>
            <button
              type="button"
              className="accessible-table-toggle-btn"
              onClick={() => setShowAccessibleTable(!showAccessibleTable)}
              aria-expanded={showAccessibleTable}
            >
              <Table size={14} aria-hidden="true" />
              <span>{showAccessibleTable ? "Hide data table" : "Show data table"}</span>
            </button>
          </div>

          {showAccessibleTable && (
            <div className="accessible-data-table-container">
              <table className="outlook-data-table" aria-label="Forecast points and empirical bounds">
                <thead>
                  <tr>
                    <th scope="col">Period</th>
                    <th scope="col">Actual</th>
                    <th scope="col">Forecast</th>
                    <th scope="col">Lower Bound</th>
                    <th scope="col">Upper Bound</th>
                  </tr>
                </thead>
                <tbody>
                  {points.map((p, idx) => (
                    <tr key={p.period || idx}>
                      <td>{p.period_label || p.period}</td>
                      <td>{p.actual_value != null ? formatCompactNumber(p.actual_value, unit) : "—"}</td>
                      <td>{p.forecast_value != null ? formatCompactNumber(p.forecast_value, unit) : "—"}</td>
                      <td>{p.lower_bound != null ? formatCompactNumber(p.lower_bound, unit) : "—"}</td>
                      <td>{p.upper_bound != null ? formatCompactNumber(p.upper_bound, unit) : "—"}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}

          <div className="outlook-narrative-box">
            <p className="narrative-text">{why_available_or_unavailable}</p>
          </div>
        </div>
      )}
    </section>
  );
}
