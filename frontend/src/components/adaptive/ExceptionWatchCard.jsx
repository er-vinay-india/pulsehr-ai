import React, { useMemo, useState } from "react";
import { Info, ArrowRight, ShieldCheck, AlertCircle } from "lucide-react";
import SafeReactECharts from "../charts/SafeReactECharts";

/**
 * Intelligent compact number formatter for metrics, ticks, tooltips, and data tables.
 * Displays $1.80M, $903.3K, $646.5K, 12.5%, etc.
 */
function formatCompactNumber(val, unit = "") {
  if (val === null || val === undefined || isNaN(val)) return "—";
  const num = Number(val);
  const isCurr = unit === "$" || (typeof unit === "string" && unit.toLowerCase() === "usd");
  const prefix = isCurr ? "$" : "";
  const suffix = !isCurr && unit && unit !== "%" ? ` ${unit}` : (unit === "%" ? "%" : "");
  const abs = Math.abs(num);
  const sign = num < 0 ? "-" : "";
  if (abs >= 1e9) return `${sign}${prefix}${(abs / 1e9).toFixed(2)}B${suffix}`;
  if (abs >= 1e6) {
    const m = abs / 1e6;
    const formatted = m.toFixed(2).endsWith(".00") ? m.toFixed(0) : m.toFixed(2);
    return `${sign}${prefix}${formatted}M${suffix}`;
  }
  if (abs >= 1e3) {
    const k = abs / 1e3;
    const formatted = k.toFixed(1).endsWith(".0") ? k.toFixed(0) : k.toFixed(1);
    return `${sign}${prefix}${formatted}K${suffix}`;
  }
  if (abs >= 100) return `${sign}${prefix}${abs.toLocaleString(undefined, { maximumFractionDigits: 0 })}${suffix}`;
  if (isCurr) return `${sign}${prefix}${abs.toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`;
  if (abs >= 1) return `${sign}${prefix}${abs.toLocaleString(undefined, { maximumFractionDigits: 1 })}${suffix}`;
  return `${sign}${prefix}${abs.toLocaleString(undefined, { maximumFractionDigits: 2 })}${suffix}`;
}

/**
 * Converts date strings (ISO, week, standard) into human readable text (e.g. 2010-12-24 -> Dec 24, 2010).
 */
function formatHumanDate(dateStr) {
  if (!dateStr || typeof dateStr !== "string") return dateStr || "";
  const clean = dateStr.trim().split("T")[0].split(" ")[0];
  const months = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"];

  const wMatch = clean.match(/^(\d{4})-[Ww](\d{1,2})$/);
  if (wMatch) {
    return `Week ${parseInt(wMatch[2], 10)}, ${wMatch[1]}`;
  }

  const parts = clean.split(/[-/]/);
  if (parts.length === 3 && parts[0].length === 4 && !isNaN(parts[1]) && !isNaN(parts[2])) {
    const y = parts[0];
    const m = parseInt(parts[1], 10);
    const d = parseInt(parts[2], 10);
    if (m >= 1 && m <= 12 && d >= 1 && d <= 31) {
      return `${months[m - 1]} ${d}, ${y}`;
    }
  }
  if (parts.length === 2 && parts[0].length === 4 && !isNaN(parts[1])) {
    const y = parts[0];
    const m = parseInt(parts[1], 10);
    if (m >= 1 && m <= 12) {
      return `${months[m - 1]} ${y}`;
    }
  }
  return dateStr;
}

/**
 * Compact date formatter for chart axis tick labels (e.g. 2010-12-24 -> Dec 24 ’10 or Dec ’10).
 */
function formatTickDate(dateStr) {
  if (!dateStr || typeof dateStr !== "string") return dateStr || "";
  const clean = dateStr.trim();
  const months = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"];

  // Matches "Dec 24, 2010" or "Dec 2010"
  const humanMatch = clean.match(/^([A-Za-z]{3})\s*(?:\d{1,2},)?\s*(\d{4})$/);
  if (humanMatch) {
    const month = humanMatch[1];
    const yearShort = humanMatch[2].slice(2);
    return `${month} ’${yearShort}`;
  }

  const wMatch = clean.match(/^(\d{4})-[Ww](\d{1,2})$/);
  if (wMatch) {
    return `W${parseInt(wMatch[2], 10)} ’${wMatch[1].slice(2)}`;
  }

  const parts = clean.split(/[-/]/);
  if (parts.length === 3 && parts[0].length === 4 && !isNaN(parts[1]) && !isNaN(parts[2])) {
    const y = parts[0].slice(2);
    const m = parseInt(parts[1], 10);
    if (m >= 1 && m <= 12) {
      return `${months[m - 1]} ’${y}`;
    }
  }
  if (parts.length === 2 && parts[0].length === 4 && !isNaN(parts[1])) {
    const y = parts[0].slice(2);
    const m = parseInt(parts[1], 10);
    if (m >= 1 && m <= 12) {
      return `${months[m - 1]} ’${y}`;
    }
  }
  return formatHumanDate(dateStr);
}

/**
 * ExceptionWatchCard — Adaptive Dashboard Element 8 (Gate 8).
 * 
 * Presents one statistically defensible lead unusual period or segment from current-snapshot evidence,
 * displays observed value against typical observed range (robust MAD/IQR baseline),
 * renders a restrained ECharts dotplot or timeline band, and provides drill-through to Data Explorer.
 */
export default function ExceptionWatchCard({
  exception,
  sheetId,
  snapshot,
  onInspect,
  onNavigateTab
}) {
  const [showAccessibleTable, setShowAccessibleTable] = useState(false);

  if (!exception || exception.kind === "exception_unavailable" || !exception.lead_exception) {
    return null;
  }

  const lead = exception.lead_exception;
  const visual = exception.visual;
  const additionalCount = exception.additional_exceptions?.length || 0;

  const handleDrillThrough = (e) => {
    e.preventDefault();
    const targetUrl = `/?sheet_id=${encodeURIComponent(sheetId)}&view=eda#explorer`;
    window.history.pushState(null, "", targetUrl);
    window.location.hash = "explorer";
    if (onNavigateTab) {
      onNavigateTab("explorer");
    }
  };

  // Humanize title if it contains raw ISO period
  const displayTitle = useMemo(() => {
    if (!exception.title) return "Exception watch";
    if (exception.title.startsWith("Unusual period: ")) {
      const rawDate = exception.title.replace("Unusual period: ", "");
      return `Unusual period: ${formatHumanDate(rawDate)}`;
    }
    return exception.title;
  }, [exception.title]);

  // Ensure human-readable observed value and expected range
  const displayObservedValue = useMemo(() => {
    if (lead.formatted_observed_value && !lead.formatted_observed_value.match(/\b\d{4,}\b/)) {
      return lead.formatted_observed_value;
    }
    return formatCompactNumber(lead.observed_value, lead.unit);
  }, [lead.formatted_observed_value, lead.observed_value, lead.unit]);

  const displayExpectedRange = useMemo(() => {
    if (lead.formatted_expected_range && !lead.formatted_expected_range.match(/\b\d{4,}\b/)) {
      return lead.formatted_expected_range;
    }
    return `${formatCompactNumber(lead.expected_lower, lead.unit)}–${formatCompactNumber(lead.expected_upper, lead.unit)}`;
  }, [lead.formatted_expected_range, lead.expected_lower, lead.expected_upper, lead.unit]);

  // Ensure caption tag is compact and formatted
  const displayCaption = useMemo(() => {
    if (exception.caption && !exception.caption.match(/\b\d{4,}\b/)) {
      return exception.caption;
    }
    return `${displayObservedValue} · ${displayExpectedRange} typical · ${lead.formatted_deviation}`;
  }, [exception.caption, displayObservedValue, displayExpectedRange, lead.formatted_deviation]);

  // Humanize narrative dates
  const displayWhyInspect = useMemo(() => {
    if (!exception.why_inspect) return "";
    return exception.why_inspect.replace(/\b(\d{4}-\d{2}-\d{2})\b/g, (match) => formatHumanDate(match));
  }, [exception.why_inspect]);

  // Build ECharts option based on visual kind
  const chartOption = useMemo(() => {
    if (!visual || !visual.points || visual.points.length === 0) {
      return {};
    }

    if (visual.kind === "segment_dotplot") {
      const labels = visual.points.map((p) => p.label);
      const values = visual.points.map((p, idx) => ({
        value: [p.value != null ? p.value : 0, idx],
        name: p.label,
        formattedValue: formatCompactNumber(p.value, lead.unit),
        isException: p.is_exception,
        itemStyle: {
          color: p.is_exception ? "#d97706" : "#3b82f6",
          borderColor: p.is_exception ? "#b45309" : "#1d4ed8",
          borderWidth: p.is_exception ? 2 : 1
        },
        symbol: p.is_exception ? "diamond" : "circle",
        symbolSize: p.is_exception ? 12 : 8
      }));

      const expLower = lead.expected_lower;
      const expUpper = lead.expected_upper;

      return {
        grid: {
          top: 24,
          right: 32,
          bottom: 36,
          left: 140,
          containLabel: false
        },
        tooltip: {
          trigger: "item",
          backgroundColor: "#1c1815",
          borderColor: "#524940",
          textStyle: { color: "#fff9f2", fontSize: 12 },
          renderMode: "richText",
          formatter: (params) => {
            const pt = visual.points[params.dataIndex];
            if (!pt) return "";
            const statusText = pt.is_exception ? "Outside typical range" : "Within typical range";
            const valStr = formatCompactNumber(pt.value != null ? pt.value : pt.formatted_value, lead.unit);
            return `${pt.label}\nObserved: ${valStr}\nTypical range: ${displayExpectedRange}\nStatus: ${statusText}`;
          }
        },
        xAxis: {
          type: "value",
          scale: true,
          axisLine: { lineStyle: { color: "#3d362f" } },
          axisLabel: {
            color: "#ded5cb",
            fontSize: 11,
            formatter: (v) => formatCompactNumber(v, lead.unit)
          },
          splitLine: { lineStyle: { color: "#524940", type: "dashed" } }
        },
        yAxis: {
          type: "category",
          data: labels,
          inverse: true,
          axisLine: { lineStyle: { color: "#3d362f" } },
          axisTick: { show: false },
          axisLabel: {
            color: "#ded5cb",
            fontSize: 11,
            width: 125,
            overflow: "truncate",
            ellipsis: "..."
          }
        },
        series: [
          {
            name: "Cohort Value",
            type: "scatter",
            data: values,
            markArea: (expLower != null && expUpper != null) ? {
              silent: true,
              itemStyle: {
                color: "rgba(96, 165, 250, 0.12)",
                borderWidth: 1,
                borderColor: "#60a5fa",
                borderType: "dashed"
              },
              data: [
                [
                  { xAxis: expLower, name: "Typical observed range" },
                  { xAxis: expUpper }
                ]
              ]
            } : undefined
          }
        ]
      };
    }

    if (visual.kind === "timeline_band") {
      const labels = visual.points.map((p) => p.label);
      const obsValues = visual.points.map((p) => ({
        value: p.value,
        name: formatHumanDate(p.label),
        formattedValue: formatCompactNumber(p.value, lead.unit),
        isException: p.is_exception,
        isPartial: p.is_partial,
        itemStyle: {
          color: p.is_exception ? "#fbbb27" : "#60a5fa",
          borderColor: p.is_exception ? "#ff8a62" : "#93c5fd",
          borderWidth: p.is_exception ? 2 : 1
        },
        symbol: p.is_exception ? "diamond" : "circle",
        symbolSize: p.is_exception ? 10 : 6
      }));

      const expLower = lead.expected_lower;
      const expUpper = lead.expected_upper;

      return {
        grid: {
          top: 24,
          right: 24,
          bottom: visual.points.length > 8 ? 48 : 36,
          left: 48,
          containLabel: true
        },
        tooltip: {
          trigger: "axis",
          backgroundColor: "#1c1815",
          borderColor: "#524940",
          textStyle: { color: "#fff9f2", fontSize: 12 },
          renderMode: "richText",
          formatter: (params) => {
            const first = params[0];
            if (!first) return "";
            const pt = visual.points[first.dataIndex];
            if (!pt) return "";
            const statusText = pt.is_exception ? "Outside typical range" : "Within typical range";
            const partialText = pt.is_partial ? " (Partial Period)" : "";
            const dateLabel = formatHumanDate(pt.label);
            const valStr = formatCompactNumber(pt.value, lead.unit);
            return `${dateLabel}${partialText}\nObserved: ${valStr}\nTypical range: ${displayExpectedRange}\nStatus: ${statusText}`;
          }
        },
        xAxis: {
          type: "category",
          data: labels,
          axisLine: { lineStyle: { color: "#3d362f" } },
          axisLabel: {
            color: "#ded5cb",
            fontSize: 10,
            rotate: visual.points.length > 8 ? 30 : 0,
            margin: 8,
            formatter: (val) => formatTickDate(val),
            interval: (idx) => {
              if (visual.points.length <= 8) return true;
              const excIdx = visual.points.findIndex(p => p.is_exception);
              const step = Math.ceil(visual.points.length / 8);
              // Always show first and last
              if (idx === 0 || idx === visual.points.length - 1) return true;
              // Always show exception point
              if (idx === excIdx) return true;
              // Avoid crowding: suppress regular tick if within 65% of step distance from exception point
              if (excIdx >= 0 && Math.abs(idx - excIdx) < Math.floor(step * 0.65)) return false;
              return idx % step === 0;
            }
          }
        },
        yAxis: {
          type: "value",
          scale: true,
          axisLine: { lineStyle: { color: "#3d362f" } },
          axisLabel: {
            color: "#ded5cb",
            fontSize: 11,
            formatter: (v) => formatCompactNumber(v, lead.unit)
          },
          splitLine: { lineStyle: { color: "#524940", type: "dashed" } }
        },
        series: [
          {
            name: "Observed",
            type: "line",
            smooth: false,
            data: obsValues,
            lineStyle: { color: "#60a5fa", width: 2 },
            markArea: (expLower != null && expUpper != null) ? {
              silent: true,
              itemStyle: {
                color: "rgba(96, 165, 250, 0.12)",
                borderWidth: 1,
                borderColor: "#60a5fa",
                borderType: "dashed"
              },
              data: [
                [
                  { yAxis: expLower },
                  { yAxis: expUpper }
                ]
              ]
            } : undefined
          }
        ]
      };
    }

    return {};
  }, [visual, lead, displayExpectedRange]);

  return (
    <section className="adaptive-exception-card" aria-label="Exception watch">
      <div className="exception-header">
        <div className="exception-eyebrow-row">
          <span className="exception-kicker">Exception watch</span>
          {displayCaption && (
            <span className="exception-caption-tag">{displayCaption}</span>
          )}
        </div>
        <div className="exception-header-main">
          <h2 className="exception-title">{displayTitle}</h2>
          {onInspect && (
            <button
              type="button"
              className="exception-inspect-btn"
              onClick={() => onInspect("exception", exception.inspect)}
              aria-label="Inspect exception watch methodology, sample and calculations"
              title="Inspect exception methodology and evidence"
            >
              <Info size={16} aria-hidden="true" />
            </button>
          )}
        </div>
      </div>

      <div className="exception-body-grid">
        {/* Metric / Lead Exception Stats & Narrative */}
        <div className="exception-narrative-col">
          <div className="exception-stat-group">
            <div className="exception-observed-block">
              <span className="stat-label">Observed value</span>
              <div className="stat-value-row">
                <span className="stat-primary-value">{displayObservedValue}</span>
                <span className={`stat-direction-badge ${lead.direction}`}>
                  {lead.formatted_deviation}
                </span>
              </div>
            </div>

            <div className="exception-range-block">
              <span className="range-label">Typical observed range</span>
              <span className="range-value">{displayExpectedRange}</span>
              <span className="range-footnote">Robust statistical baseline (MAD/IQR)</span>
            </div>

            <div className="exception-context-meta">
              <div className="meta-row">
                <span className="meta-key">Cohort:</span>
                <span className="meta-val">
                  {lead.exception_type === "temporal" ? formatHumanDate(lead.subject_label) : lead.subject_label}
                </span>
              </div>
              <div className="meta-row">
                <span className="meta-key">Sample:</span>
                <span className="meta-val">{lead.sample_label}</span>
              </div>
              {lead.context_flags && lead.context_flags.length > 0 && (
                <div className="meta-row flags-row">
                  {lead.context_flags.map((flag, idx) => (
                    <span key={idx} className="context-flag-pill">
                      {flag}
                    </span>
                  ))}
                </div>
              )}
            </div>
          </div>

          {/* Why Inspect */}
          <div className="exception-why-box">
            <h3 className="why-label">Why inspect</h3>
            <p className="why-text">{displayWhyInspect}</p>
          </div>

          {/* Action Drill-Through */}
          <div className="exception-actions-row">
            <a
              href={`/?sheet_id=${encodeURIComponent(sheetId)}&view=eda#explorer`}
              onClick={handleDrillThrough}
              className="btn-inspect-data"
              aria-label={`Inspect supporting data for sheet ${sheetId} in Data Explorer`}
            >
              <span>Inspect supporting data</span>
              <ArrowRight size={15} aria-hidden="true" />
            </a>

            {additionalCount > 0 && (
              <span className="additional-exceptions-note">
                +{additionalCount} other eligible {additionalCount === 1 ? "exception" : "exceptions"} screened
              </span>
            )}
          </div>
        </div>

        {/* Visual Column */}
        {visual && visual.kind !== "none" && visual.points && visual.points.length > 0 && (
          <div className="exception-visual-col">
            <div className="visual-header-row">
              <span className="visual-label">
                {visual.kind === "timeline_band"
                  ? "Observed timeline vs typical range"
                  : "Segment comparison dot plot"}
              </span>
              <button
                type="button"
                className="btn-toggle-table"
                onClick={() => setShowAccessibleTable(!showAccessibleTable)}
                aria-expanded={showAccessibleTable}
              >
                {showAccessibleTable ? "Hide data table" : "Show data table"}
              </button>
            </div>

            {!showAccessibleTable ? (
              <div className="exception-chart-wrapper" aria-hidden="true">
                <SafeReactECharts
                  option={chartOption}
                  opts={{ renderer: "svg" }}
                  style={{
                    height:
                      visual.kind === "segment_dotplot"
                        ? Math.max(220, visual.points.length * 30 + 50)
                        : 260,
                    width: "100%",
                    maxWidth: "100%"
                  }}
                />
              </div>
            ) : (
              <div className="exception-accessible-table-wrap">
                <table className="exception-table">
                  <thead>
                    <tr>
                      <th>{visual.kind === "timeline_band" ? "Period" : "Segment"}</th>
                      <th>Observed</th>
                      <th>Status</th>
                    </tr>
                  </thead>
                  <tbody>
                    {visual.points.map((pt, idx) => (
                      <tr key={idx} className={pt.is_exception ? "row-exception" : ""}>
                        <td>{visual.kind === "timeline_band" ? formatHumanDate(pt.label) : pt.label}</td>
                        <td>{formatCompactNumber(pt.value, lead.unit)}</td>
                        <td>
                          {pt.is_exception ? (
                            <span className="badge-exception">Outside typical range</span>
                          ) : (
                            <span className="badge-typical">Typical</span>
                          )}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          </div>
        )}
      </div>
    </section>
  );
}
