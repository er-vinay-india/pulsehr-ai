import React, { useMemo, useState } from "react";
import { Info, Network, ExternalLink, AlertCircle, Table } from "lucide-react";
import SafeReactECharts from "../charts/SafeReactECharts";

/**
 * EnterpriseSynthesisCard — Adaptive Dashboard Element 10 (Gate 10).
 *
 * Renders verified cross-source enterprise synthesis:
 * - Scope: Sibling sheets belonging to the same dataset upload.
 * - Multi-source manifest and combined deterministic content hash.
 * - Supports:
 *     1. Matched cohort comparison (privacy-safe aggregation by cohort)
 *     2. Cross-source association (N >= 30, non-causal, outlier checked)
 *     3. Reconciled lifecycle metric (e.g. orders <-> returns, leads <-> wins)
 *     4. Coverage-only synthesis (transparent disclosure when no safe key passes)
 * - Safe Explorer drill-through links.
 * - ECharts visual presentation only.
 */
export default function EnterpriseSynthesisCard({
  enterprise,
  sheetId,
  snapshot,
  onInspect,
  infoButtonRef,
}) {
  const [showAccessibleTable, setShowAccessibleTable] = useState(false);

  if (!enterprise) {
    return null;
  }

  const {
    kind,
    business_concept,
    title,
    sources = [],
    source_count = 0,
    lead_finding,
    visual,
    what_it_establishes,
    what_it_does_not_establish,
    next_check,
    drilldown_targets = [],
    glance,
    explain,
    caption,
  } = enterprise;

  const isCoverageOnly = kind === "coverage_only" || !visual || visual.kind === "none";
  const points = visual?.points || [];

  // Build ECharts option based on visual kind
  const chartOption = useMemo(() => {
    if (isCoverageOnly || points.length === 0) {
      return {};
    }

    if (visual.kind === "paired_dot") {
      // Matched Cohort Comparison: Paired dots for two metrics across cohorts
      const categories = points.map((p) => p.label);
      const xVals = points.map((p) => p.x);
      const yVals = points.map((p) => p.y);
      const metricNames = lead_finding?.metric_names || ["Primary metric", "Secondary metric"];

      return {
        backgroundColor: "transparent",
        tooltip: {
          trigger: "axis",
          axisPointer: { type: "shadow" },
          backgroundColor: "#1c1815",
          borderColor: "#524940",
          textStyle: { color: "#fff9f2", fontSize: 12 },
          formatter: (params) => {
            if (!params || params.length === 0) return "";
            const idx = params[0].dataIndex;
            const pt = points[idx];
            if (!pt) return "";
            return `
              <div style="font-weight:600;margin-bottom:4px;color:#fff9f2;">${pt.label}</div>
              <div style="color:#38bdf8;">${metricNames[0]}: <strong>${pt.formatted_x || pt.x}</strong></div>
              <div style="color:#c084fc;">${metricNames[1] || "Metric 2"}: <strong>${pt.formatted_y || pt.y}</strong></div>
              ${pt.sample_size ? `<div style="color:#ded5cb;font-size:11px;margin-top:2px;">Matched sample: ${pt.sample_size} entities</div>` : ""}
            `;
          },
        },
        legend: {
          data: [metricNames[0] || "Primary Metric", metricNames[1] || "Secondary Metric"],
          textStyle: { color: "#ded5cb", fontSize: 11 },
          top: 0,
          right: 12,
        },
        grid: {
          left: "3%",
          right: "4%",
          bottom: "3%",
          top: 36,
          containLabel: true,
        },
        xAxis: {
          type: "value",
          splitLine: { lineStyle: { color: "#524940", type: "dashed" } },
          axisLabel: { color: "#ded5cb", fontSize: 11 },
        },
        yAxis: {
          type: "category",
          data: categories,
          axisLine: { lineStyle: { color: "#3d362f" } },
          axisLabel: {
            color: "#ded5cb",
            fontSize: 11,
            formatter: (val) => (val.length > 22 ? `${val.substring(0, 20)}…` : val),
          },
        },
        series: [
          {
            name: metricNames[0] || "Primary Metric",
            type: "scatter",
            symbolSize: 12,
            data: xVals.map((value, index) => [value, index]),
            itemStyle: { color: "#38bdf8" },
          },
          {
            name: metricNames[1] || "Secondary Metric",
            type: "scatter",
            symbolSize: 12,
            data: yVals.map((value, index) => [value, index]),
            itemStyle: { color: "#c084fc" },
          },
        ],
      };
    }

    if (visual.kind === "scatter") {
      // Cross-Source Association: Binned scatter plot with non-causal trend line
      const scatterData = points.map((p) => [p.x, p.y, p.label, p.sample_size]);
      const xVals = points.map((p) => p.x);
      const minX = Math.min(...xVals);
      const maxX = Math.max(...xVals);

      return {
        backgroundColor: "transparent",
        tooltip: {
          trigger: "item",
          backgroundColor: "#1c1815",
          borderColor: "#524940",
          textStyle: { color: "#fff9f2", fontSize: 12 },
          formatter: (param) => {
            const [x, y, label, n] = param.value || [];
            return `
              <div style="font-weight:600;margin-bottom:4px;color:#fff9f2;">${label || "Aggregated Bin"}</div>
              <div style="color:#38bdf8;">${visual.x_axis_title || "X"}: <strong>${x}</strong></div>
              <div style="color:#c084fc;">${visual.y_axis_title || "Y"}: <strong>${y}</strong></div>
              ${n ? `<div style="color:#ded5cb;font-size:11px;margin-top:2px;">Sample size: ${n} records</div>` : ""}
            `;
          },
        },
        grid: {
          left: "4%",
          right: "4%",
          bottom: "10%",
          top: "8%",
          containLabel: true,
        },
        xAxis: {
          type: "value",
          name: visual.x_axis_title || "Measure X",
          nameLocation: "middle",
          nameGap: 24,
          nameTextStyle: { color: "#ded5cb", fontSize: 11 },
          splitLine: { lineStyle: { color: "#524940", type: "dashed" } },
          axisLabel: { color: "#ded5cb", fontSize: 11 },
        },
        yAxis: {
          type: "value",
          name: visual.y_axis_title || "Measure Y",
          nameTextStyle: { color: "#ded5cb", fontSize: 11 },
          splitLine: { lineStyle: { color: "#524940", type: "dashed" } },
          axisLabel: { color: "#ded5cb", fontSize: 11 },
        },
        series: [
          {
            type: "scatter",
            symbolSize: 14,
            data: scatterData,
            itemStyle: { color: "#38bdf8", opacity: 0.85 },
          },
        ],
      };
    }

    if (visual.kind === "lifecycle_flow") {
      // Reconciled Lifecycle Metric: Stage bar
      const stages = points.map((p) => p.label);
      const counts = points.map((p) => p.y);

      return {
        backgroundColor: "transparent",
        tooltip: {
          trigger: "axis",
          axisPointer: { type: "shadow" },
          backgroundColor: "#1c1815",
          borderColor: "#524940",
          textStyle: { color: "#fff9f2", fontSize: 12 },
        },
        grid: {
          left: "4%",
          right: "4%",
          bottom: "5%",
          top: "10%",
          containLabel: true,
        },
        xAxis: {
          type: "category",
          data: stages,
          axisLine: { lineStyle: { color: "#3d362f" } },
          axisLabel: { color: "#ded5cb", fontSize: 11 },
        },
        yAxis: {
          type: "value",
          splitLine: { lineStyle: { color: "#524940", type: "dashed" } },
          axisLabel: { color: "#ded5cb", fontSize: 11 },
        },
        series: [
          {
            type: "bar",
            data: counts,
            barWidth: "40%",
            itemStyle: {
              color: (params) => (params.dataIndex === 0 ? "#38bdf8" : "#34d399"),
              borderRadius: [4, 4, 0, 0],
            },
          },
        ],
      };
    }

    return {};
  }, [isCoverageOnly, points, visual, lead_finding]);

  return (
    <div
      className="enterprise-synthesis-card"
      data-testid="enterprise-synthesis-card"
      data-kind={kind}
    >
      {/* Header with Title and Scope Pill */}
      <div className="card-header">
        <div className="header-eyebrow">
          <div className="eyebrow-left">
            <Network className="header-icon" size={14} aria-hidden="true" />
            <span className="eyebrow-text">Element 10 · Enterprise synthesis</span>
          </div>
          <span className="scope-badge" title="Source reconciliation scope">
            {caption || `${source_count} evaluated sources`}
          </span>
        </div>

        <div className="header-main">
          <div>
            <h3 className="card-title">
              {lead_finding?.title || business_concept || title}
            </h3>
            {lead_finding?.observation && (
              <p className="card-subtitle">{lead_finding.observation}</p>
            )}
          </div>
          {glance?.has_info_control && (
            <button
              ref={infoButtonRef}
              type="button"
              className="info-btn"
              onClick={() => onInspect && onInspect("enterprise")}
              aria-label="Inspect enterprise synthesis methodology and audit details"
              title="Inspect enterprise synthesis methodology and audit details"
            >
              <Info size={16} />
            </button>
          )}
        </div>
      </div>

      {/* Glance Metric Highlight Bar */}
      {glance && (
        <div className="glance-summary-bar">
          <div className="glance-item">
            <span className="glance-label">{glance.label}</span>
            <span className="glance-value">{glance.formatted_value || glance.value}</span>
            {glance.context_qualifier && (
              <span className="glance-qualifier">{glance.context_qualifier}</span>
            )}
          </div>
          {lead_finding && (
            <div className="glance-item">
              <span className="glance-label">Match Coverage</span>
              <span className="glance-value">
                {Math.round((lead_finding.coverage_ratio || 0) * 100)}%
              </span>
              <span className="glance-qualifier">
                {lead_finding.matched_count?.toLocaleString()} matched entities
              </span>
            </div>
          )}
          {lead_finding?.join_description && (
            <div className="glance-item join-rule">
              <span className="glance-label">Reconciliation Key</span>
              <span className="glance-rule-text">{lead_finding.join_description}</span>
            </div>
          )}
        </div>
      )}

      {/* Visual Chart Section (if applicable) */}
      {!isCoverageOnly && points.length > 0 && (
        <div className="chart-wrapper">
          <div className="chart-header">
            <span className="chart-caption">
              {visual.kind === "paired_dot" && "Matched cohort aggregates (privacy-safe group grain)"}
              {visual.kind === "scatter" && "Bivariate cross-source association (non-causal)"}
              {visual.kind === "lifecycle_flow" && "Reconciled lifecycle milestone progression"}
            </span>
            <button
              type="button"
              className="table-toggle-btn"
              onClick={() => setShowAccessibleTable((prev) => !prev)}
              aria-expanded={showAccessibleTable}
              aria-label="Toggle accessible tabular data"
            >
              <Table size={13} />
              <span>{showAccessibleTable ? "Hide data table" : "Show data table"}</span>
            </button>
          </div>

          <div className="echarts-container" style={{ height: "260px", width: "100%" }}>
            <SafeReactECharts
              option={chartOption}
              style={{ height: "100%", width: "100%" }}
              opts={{ renderer: "canvas" }}
            />
          </div>

          {/* Accessible Table for Screen Readers / Keyboard Users */}
          {showAccessibleTable && (
            <div className="accessible-table-container">
              <table className="accessible-data-table">
                <thead>
                  <tr>
                    <th>Cohort / Entity</th>
                    <th>{lead_finding?.metric_names?.[0] || "Measure 1"}</th>
                    <th>{lead_finding?.metric_names?.[1] || "Measure 2"}</th>
                    <th>Sample size</th>
                  </tr>
                </thead>
                <tbody>
                  {points.map((pt, idx) => (
                    <tr key={idx}>
                      <td>{pt.label}</td>
                      <td>{pt.formatted_x || pt.x}</td>
                      <td>{pt.formatted_y || pt.y}</td>
                      <td>{pt.sample_size || "—"}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </div>
      )}

      {/* Coverage Only Message Block */}
      {isCoverageOnly && (
        <div className="coverage-only-block">
          <AlertCircle className="coverage-icon" size={18} aria-hidden="true" />
          <div className="coverage-text">
            <strong>Cross-Source Scope Notice:</strong> {what_it_does_not_establish}
          </div>
        </div>
      )}

      {/* Analytical Interpretation Sections */}
      <div className="interpretation-grid">
        <div className="interpretation-card establishes">
          <div className="section-label">What this establishes</div>
          <p className="section-content">{what_it_establishes}</p>
        </div>

        <div className="interpretation-card does-not-establish">
          <div className="section-label">What this does not establish</div>
          <p className="section-content">{what_it_does_not_establish}</p>
        </div>

        <div className="interpretation-card next-check">
          <div className="section-label">Recommended next check</div>
          <p className="section-content">{next_check}</p>
        </div>
      </div>

      {/* Drill-through Links to Data Explorer */}
      {drilldown_targets.length > 0 && (
        <div className="drilldown-bar">
          <span className="drilldown-title">Inspect supporting sources:</span>
          <div className="drilldown-links">
            {drilldown_targets.map((target, idx) => (
              <a
                key={idx}
                href={target.route}
                className="drilldown-link-btn"
                title={`Open ${target.label} in Data Explorer`}
              >
                <span>{target.label}</span>
                <ExternalLink size={12} aria-hidden="true" />
              </a>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}
