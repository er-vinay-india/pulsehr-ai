import React, { useMemo, useState } from "react";
import { Info, ArrowRight, ShieldCheck, AlertCircle } from "lucide-react";
import SafeReactECharts from "../charts/SafeReactECharts";

/**
 * ExceptionWatchCard — Adaptive Dashboard Element 8 (Gate 8).
 * 
 * Presents one statistically defensible lead unusual period or segment from current-snapshot evidence,
 * displays observed value against typical observed range (robust MAD/IQR baseline),
 * renders an restrained ECharts dotplot or timeline band, and provides drill-through to Data Explorer.
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
        formattedValue: p.formatted_value,
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
          renderMode: "richText",
          formatter: (params) => {
            const pt = visual.points[params.dataIndex];
            if (!pt) return "";
            const statusText = pt.is_exception ? "Outside typical range" : "Within typical range";
            return `${pt.label}\nObserved: ${pt.formatted_value}\nTypical range: ${lead.formatted_expected_range}\nStatus: ${statusText}`;
          }
        },
        xAxis: {
          type: "value",
          scale: true,
          axisLine: { lineStyle: { color: "#3d362f" } },
          axisLabel: {
            color: "#ded5cb",
            fontSize: 11,
            formatter: (v) => `${v} ${lead.unit || ""}`.trim()
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
        name: p.label,
        formattedValue: p.formatted_value,
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
          bottom: 36,
          left: 48,
          containLabel: true
        },
        tooltip: {
          trigger: "axis",
          renderMode: "richText",
          formatter: (params) => {
            const first = params[0];
            if (!first) return "";
            const pt = visual.points[first.dataIndex];
            if (!pt) return "";
            const statusText = pt.is_exception ? "Outside typical range" : "Within typical range";
            const partialText = pt.is_partial ? " (Partial Period)" : "";
            return `${pt.label}${partialText}\nObserved: ${pt.formatted_value}\nTypical range: ${lead.formatted_expected_range}\nStatus: ${statusText}`;
          }
        },
        xAxis: {
          type: "category",
          data: labels,
          axisLine: { lineStyle: { color: "#3d362f" } },
          axisLabel: { color: "#ded5cb", fontSize: 11 }
        },
        yAxis: {
          type: "value",
          scale: true,
          axisLine: { lineStyle: { color: "#3d362f" } },
          axisLabel: { color: "#ded5cb", fontSize: 11 },
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
  }, [visual, lead]);

  return (
    <section className="adaptive-exception-card" aria-label="Exception watch">
      <div className="exception-header">
        <div className="exception-eyebrow-row">
          <span className="exception-kicker">Exception watch</span>
          {exception.caption && (
            <span className="exception-caption-tag">{exception.caption}</span>
          )}
        </div>
        <div className="exception-header-main">
          <h2 className="exception-title">{exception.title}</h2>
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
                <span className="stat-primary-value">{lead.formatted_observed_value}</span>
                <span className={`stat-direction-badge ${lead.direction}`}>
                  {lead.formatted_deviation}
                </span>
              </div>
            </div>

            <div className="exception-range-block">
              <span className="range-label">Typical observed range</span>
              <span className="range-value">{lead.formatted_expected_range}</span>
              <span className="range-footnote">Robust statistical baseline (MAD/IQR)</span>
            </div>

            <div className="exception-context-meta">
              <div className="meta-row">
                <span className="meta-key">Cohort:</span>
                <span className="meta-val">{lead.subject_label}</span>
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
            <p className="why-text">{exception.why_inspect}</p>
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
                        <td>{pt.label}</td>
                        <td>{pt.formatted_value}</td>
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
