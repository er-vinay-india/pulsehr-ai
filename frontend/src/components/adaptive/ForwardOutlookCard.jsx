import React, { useMemo, useState } from "react";
import { Info, ShieldCheck, Target, TrendingUp, AlertCircle, Table } from "lucide-react";
import SafeReactECharts from "../charts/SafeReactECharts";

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

  // Build ECharts option for statistical forecast
  const chartOption = useMemo(() => {
    if (kind !== "statistical_forecast" || !points || points.length === 0) {
      return {};
    }

    const periods = points.map((p) => p.period_label || p.period);
    
    // Historical actuals: values for historical points, null for forecast point
    const actualSeries = points.map((p) => (p.actual_value != null ? p.actual_value : null));
    
    // Forecast series: starts from the last actual point to connect lines, then goes to forecast value
    const lastActualIdx = points.findIndex((p) => p.forecast_value != null) - 1;
    const forecastSeries = points.map((p, idx) => {
      if (idx === lastActualIdx && p.actual_value != null) {
        return p.actual_value;
      }
      return p.forecast_value != null ? p.forecast_value : null;
    });

    // Lower & Upper range series for forecast points
    const lowerSeries = points.map((p) => (p.lower_bound != null ? p.lower_bound : null));
    const upperSeries = points.map((p) => (p.upper_bound != null ? p.upper_bound : null));

    // Calculate Y-axis bounds with padding
    const validVals = points.flatMap((p) => [p.actual_value, p.forecast_value, p.lower_bound, p.upper_bound]).filter((v) => v != null && isFinite(v));
    const minVal = validVals.length > 0 ? Math.min(...validVals) : 0;
    const maxVal = validVals.length > 0 ? Math.max(...validVals) : 100;
    const yPad = (maxVal - minVal) * 0.15 || 5;
    const yMin = Math.max(0, Math.floor(minVal - yPad));
    const yMax = Math.ceil(maxVal + yPad);

    return {
      backgroundColor: "transparent",
      tooltip: {
        trigger: "axis",
        backgroundColor: "#1c1917",
        borderColor: "#44403c",
        textStyle: { color: "#f5f5f4", fontSize: 12 },
        formatter: (params) => {
          if (!params || params.length === 0) return "";
          const pIdx = params[0].dataIndex;
          const pt = points[pIdx];
          if (!pt) return "";
          const isForecast = pt.forecast_value != null;
          let html = `<div style="font-weight:600;margin-bottom:4px;">${pt.period_label || pt.period}</div>`;
          if (isForecast) {
            html += `<div style="color:#f59e0b;">Forecast: <strong>${pt.forecast_value} ${unit}</strong></div>`;
            if (pt.lower_bound != null && pt.upper_bound != null) {
              html += `<div style="color:#a8a29e;font-size:11px;">Empirical range: ${pt.lower_bound}–${pt.upper_bound} ${unit}</div>`;
            }
            html += `<div style="color:#78716c;font-size:11px;margin-top:2px;">Model: ${validation?.model_label || "Validated Model"}</div>`;
          } else if (pt.actual_value != null) {
            html += `<div style="color:#38bdf8;">Observed actual: <strong>${pt.actual_value} ${unit}</strong></div>`;
            if (pt.is_partial) {
              html += `<div style="color:#fbbf24;font-size:11px;">Partial period (excluded from training)</div>`;
            }
          }
          return html;
        },
      },
      legend: {
        show: true,
        bottom: 0,
        textStyle: { color: "#a8a29e", fontSize: 11 },
        data: ["Historical actuals", "Statistical forecast", "Forecast range"],
      },
      grid: {
        top: 24,
        left: 54,
        right: 28,
        bottom: 40,
        containLabel: false,
      },
      xAxis: {
        type: "category",
        data: periods,
        axisLine: { lineStyle: { color: "#44403c" } },
        axisLabel: { color: "#a8a29e", fontSize: 11, rotate: periods.length > 10 ? 30 : 0 },
        splitLine: { show: false },
      },
      yAxis: {
        type: "value",
        min: yMin,
        max: yMax,
        name: unit,
        nameTextStyle: { color: "#a8a29e", fontSize: 11, align: "left" },
        axisLine: { show: false },
        axisLabel: { color: "#a8a29e", fontSize: 11 },
        splitLine: { lineStyle: { color: "#292524", type: "dashed" } },
      },
      series: [
        {
          name: "Historical actuals",
          type: "line",
          data: actualSeries,
          smooth: false,
          showSymbol: true,
          symbolSize: 6,
          itemStyle: { color: "#38bdf8" },
          lineStyle: { width: 2.5, color: "#38bdf8" },
          areaStyle: {
            color: {
              type: "linear",
              x: 0,
              y: 0,
              x2: 0,
              y2: 1,
              colorStops: [
                { offset: 0, color: "rgba(56, 189, 248, 0.2)" },
                { offset: 1, color: "rgba(56, 189, 248, 0.0)" },
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
          itemStyle: { color: "#f59e0b" },
          lineStyle: { width: 2.5, color: "#f59e0b", type: "dashed" },
        },
        {
          name: "Forecast range",
          type: "line",
          data: upperSeries,
          lineStyle: { opacity: 0 },
          stack: "confidence-band",
          symbol: "none",
        },
        {
          name: "Forecast range",
          type: "line",
          data: lowerSeries.map((low, i) => (upperSeries[i] != null && low != null ? upperSeries[i] - low : null)),
          lineStyle: { opacity: 0 },
          areaStyle: { color: "rgba(245, 158, 11, 0.18)" },
          stack: "confidence-band",
          symbol: "none",
        },
      ],
    };
  }, [kind, points, unit, validation]);

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
              <span className="box-val">{actual_value} {unit}</span>
            </div>
            <div className="target-metric-box">
              <span className="box-label">Recorded Target Plan</span>
              <span className="box-val">{target_value} {unit}</span>
            </div>
            <div className="target-metric-box">
              <span className="box-label">Net Variance Gap</span>
              <span className={`box-val ${gap_value >= 0 ? "positive" : "negative"}`}>
                {gap_value > 0 ? "+" : ""}{gap_value} {unit}
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
              <span className="lead-forecast-value">{glance?.formatted_value}</span>
              <span className="range-badge">
                Range: {lower_bound}–{upper_bound} {unit}
              </span>
            </div>
            <p className="forecast-subtitle">
              Next {temporal_grain || "period"} projection for {metric_name} ({validation?.model_label || "Validated Model"})
            </p>
          </div>

          <div className="forecast-chart-container" style={{ height: 260, position: "relative" }}>
            <SafeReactECharts
              option={chartOption}
              style={{ height: "100%", width: "100%" }}
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
                      <td>{p.actual_value != null ? `${p.actual_value} ${unit}` : "—"}</td>
                      <td>{p.forecast_value != null ? `${p.forecast_value} ${unit}` : "—"}</td>
                      <td>{p.lower_bound != null ? `${p.lower_bound} ${unit}` : "—"}</td>
                      <td>{p.upper_bound != null ? `${p.upper_bound} ${unit}` : "—"}</td>
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
