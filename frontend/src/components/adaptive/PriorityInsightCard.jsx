import React, { useMemo, useState } from "react";
import {
  ShieldCheck,
  TrendingUp,
  AlertTriangle,
  ArrowRight,
  ChevronDown,
  ChevronUp,
  Table,
  BarChart3,
  PieChart,
  ExternalLink,
  Volume2,
  SlidersHorizontal,
  UserCheck,
  Clock,
  ShieldAlert,
} from "lucide-react";
import SafeReactECharts from "../charts/SafeReactECharts";

function buildDonutOption(baseOption, heroValue, unitSuffix, title) {
  if (!baseOption) return null;
  const categories = baseOption?.xAxis?.data || [];
  const rawValues = baseOption?.series?.[0]?.data || [];
  const palette = ["#ff8a62", "#34d399", "#60a5fa", "#fbbb27", "#c084fc", "#fb7185", "#38bdf8"];

  const pieData = categories.map((cat, i) => ({
    name: String(cat),
    value: typeof rawValues[i] === "number" ? rawValues[i] : Number(rawValues[i]) || 0,
    itemStyle: {
      color: palette[i % palette.length],
      borderColor: "#171412",
      borderWidth: 2,
    },
  }));

  const numericVal = parseFloat(String(heroValue).replace(/[^0-9.-]/g, ""));
  if (pieData.length === 1 && !isNaN(numericVal) && numericVal <= 100 && numericVal > 0) {
    pieData.push({
      name: "Other / Remaining",
      value: Math.max(0, +(100 - numericVal).toFixed(1)),
      itemStyle: {
        color: "#524940",
        borderColor: "#171412",
        borderWidth: 2,
      },
    });
  }

  return {
    backgroundColor: "transparent",
    animation: false,
    tooltip: {
      trigger: "item",
      confine: true,
      backgroundColor: "#1c1815",
      borderColor: "#524940",
      borderWidth: 1,
      padding: [8, 12],
      textStyle: { color: "#fff9f2", fontSize: 12, fontFamily: "system-ui, sans-serif" },
      formatter: "{b}: <strong>{c}</strong> ({d}%)",
    },
    legend: {
      orient: "horizontal",
      bottom: 0,
      left: "center",
      textStyle: { color: "#ded5cb", fontSize: 11 },
      itemWidth: 10,
      itemHeight: 10,
      itemGap: 14,
    },
    series: [
      {
        name: title || "Workforce Capacity Split",
        type: "pie",
        radius: ["46%", "72%"],
        center: ["50%", "45%"],
        avoidLabelOverlap: false,
        itemStyle: {
          borderRadius: 4,
          borderColor: "#171412",
          borderWidth: 2,
        },
        label: {
          show: true,
          position: "center",
          formatter: () => `${heroValue}${unitSuffix}\n{sub|Split}`,
          rich: {
            sub: {
              fontSize: 11,
              color: "#ded5cb",
              lineHeight: 16,
              fontWeight: 500,
            },
          },
          fontSize: 18,
          fontWeight: 700,
          color: "#fff9f2",
        },
        emphasis: {
          scale: true,
          scaleSize: 4,
        },
        data: pieData,
      },
    ],
  };
}

/**
 * PriorityInsightCard — Adaptive Dashboard Lead HR Finding Component.
 *
 * Implements WP3 & WP4 executive guidelines:
 * - Prominent business headline and prominent hero number first
 * - No technical badge clutter in primary view
 * - Neutral department comparison on actual attendance
 * - Evidence-conditional next action with suggested owner role
 * - Multi-view visual mode switcher: Bar Ranking, Capacity Donut, Data Table
 * - Inline slide-out drawer trigger for supporting records
 * - Secondary controls: View records, Listen, Analysis details
 * - Expandable analysis details drawer housing engineering audit, limitations, and claim levels
 */
export default function PriorityInsightCard({
  priorityInsight,
  sheetId,
  snapshot,
  onInspect,
  onListen,
  onOpenRecords,
}) {
  const [visualMode, setVisualMode] = useState("bar"); // "bar" | "donut" | "table"
  const [showAudit, setShowAudit] = useState(false);
  const [isListening, setIsListening] = useState(false);

  if (!priorityInsight) {
    return null;
  }

  const {
    finding_id,
    strategy_code,
    strategy_name,
    short_business_title,
    prominent_number,
    unit,
    comparison_label,
    comparison_value,
    implication,
    next_check,
    evidence_details = {},
    visual_type,
    echarts_option,
    population_summary,
    allowed_claim_level = "descriptive_fact",
  } = priorityInsight;

  const hasChart = echarts_option && visual_type !== "none";
  const claimLevelLabel = allowed_claim_level.replace(/_/g, " ").toUpperCase();

  // Clean formatted value string to prevent duplicate unit suffix
  const displayVal = String(prominent_number || "");
  const unitSuffix = unit && !displayVal.toLowerCase().includes(unit.toLowerCase()) ? ` ${unit}` : "";

  const donutOption = useMemo(() => {
    return buildDonutOption(echarts_option, displayVal, unitSuffix, short_business_title);
  }, [echarts_option, displayVal, unitSuffix, short_business_title]);

  return (
    <section
      className="adaptive-priority-card"
      aria-label="Executive Priority Insight"
    >
      <div className="adaptive-priority-card__ambient-glow" />

      {/* Top Header: Business Headline & Action Controls */}
      <div className="adaptive-priority-card__header">
        <div className="adaptive-priority-card__heading-group">
          <span className="adaptive-priority-card__kicker">
            Workforce Priority Insight
          </span>
          <h2 className="adaptive-priority-card__title">
            {short_business_title}
          </h2>
          <p className="adaptive-priority-card__coverage">
            Population scope: <strong>{population_summary}</strong>
          </p>
        </div>

        {/* Secondary Controls Bar */}
        <div className="adaptive-priority-card__controls">
          {hasChart && (
            <div className="adaptive-priority-seg-control" role="group" aria-label="Visual view toggle">
              <button
                type="button"
                className={`adaptive-priority-seg-btn ${visualMode === "bar" ? "adaptive-priority-seg-btn--active" : ""}`}
                onClick={() => setVisualMode("bar")}
                aria-pressed={visualMode === "bar"}
                title="Ranked Comparison Chart"
              >
                <BarChart3 size={13} />
                <span>Bar</span>
              </button>
              <button
                type="button"
                className={`adaptive-priority-seg-btn ${visualMode === "donut" ? "adaptive-priority-seg-btn--active" : ""}`}
                onClick={() => setVisualMode("donut")}
                aria-pressed={visualMode === "donut"}
                title="Capacity Proportion Donut"
              >
                <PieChart size={13} />
                <span>Donut</span>
              </button>
              <button
                type="button"
                className={`adaptive-priority-seg-btn ${visualMode === "table" ? "adaptive-priority-seg-btn--active" : ""}`}
                onClick={() => setVisualMode("table")}
                aria-pressed={visualMode === "table"}
                title="Tabular Data Breakdown"
              >
                <Table size={13} />
                <span>Table</span>
              </button>
            </div>
          )}

          {onOpenRecords ? (
            <button
              type="button"
              onClick={onOpenRecords}
              className="adaptive-priority-btn"
              aria-label="Inspect supporting attendance records inline"
            >
              <ExternalLink size={14} />
              <span>View Records</span>
            </button>
          ) : sheetId ? (
            <a
              href={`#explorer?sheet_id=${sheetId}`}
              className="adaptive-priority-btn adaptive-priority-btn--link"
              aria-label="View raw employee records in Data Explorer"
            >
              <ExternalLink size={14} />
              <span>View Records</span>
            </a>
          ) : null}

          {onListen && (
            <button
              type="button"
              onClick={() => {
                setIsListening(true);
                onListen();
                setTimeout(() => setIsListening(false), 5000);
              }}
              className={`adaptive-priority-btn ${isListening ? "adaptive-priority-btn--active" : ""}`}
              aria-label="Listen to spoken executive briefing"
            >
              <Volume2 size={14} className={isListening ? "animate-pulse text-emerald-400" : ""} />
              <span>{isListening ? "Playing…" : "Listen"}</span>
            </button>
          )}

          <button
            type="button"
            onClick={() => setShowAudit(!showAudit)}
            className="adaptive-priority-btn"
            aria-expanded={showAudit}
            aria-label="Toggle analytical details and methodology audit"
          >
            <SlidersHorizontal size={14} />
            <span>{showAudit ? "Close Details" : "Analysis Details"}</span>
            {showAudit ? <ChevronUp size={14} /> : <ChevronDown size={14} />}
          </button>
        </div>
      </div>

      {/* Main Body: Metric Grid & Visual */}
      <div className="adaptive-priority-card__body">
        {/* Left Column: Metrics & Evidence-Bound Narrative */}
        <div className="adaptive-priority-card__content">
          {/* Prominent Number & Comparison Metrics */}
          <div className="adaptive-priority-metrics">
            <div className="adaptive-priority-metric adaptive-priority-metric--hero">
              <span className="adaptive-priority-metric__label">
                Disparity Spread
              </span>
              <div className="adaptive-priority-metric__value">
                {displayVal}{unitSuffix}
              </div>
              <span className="adaptive-priority-metric__hint">
                Difference between highest and lowest department average
              </span>
            </div>

            <div className="adaptive-priority-metric adaptive-priority-metric--comparison">
              <span className="adaptive-priority-metric__label">
                {comparison_label || "Observed Peer Baseline"}
              </span>
              <div className="adaptive-priority-metric__comparison-value">
                {comparison_value}
              </div>
              <span className="adaptive-priority-metric__hint">
                Neutral department attendance comparison
              </span>
            </div>
          </div>

          {/* Operational Implication */}
          <div className="adaptive-priority-callout adaptive-priority-callout--implication">
            <TrendingUp size={18} className="adaptive-priority-callout__icon adaptive-priority-callout__icon--brand" />
            <div className="adaptive-priority-callout__body">
              <h4 className="adaptive-priority-callout__label">
                Operational Implication
              </h4>
              <p className="adaptive-priority-callout__text">
                {implication}
              </p>
            </div>
          </div>

          {/* Next Recommended Action with HR Operational Ownership & Policy Guardrails (Merged from Report) */}
          <div className="adaptive-priority-callout adaptive-priority-callout--next-step">
            <ArrowRight size={18} className="adaptive-priority-callout__icon adaptive-priority-callout__icon--emerald" />
            <div className="adaptive-priority-callout__body">
              <div className="adaptive-priority-callout__header-row">
                <h4 className="adaptive-priority-callout__label adaptive-priority-callout__label--emerald">
                  Recommended Action & Accountability
                </h4>
                <span className="adaptive-priority-callout__role-badge">
                  <UserCheck size={12} aria-hidden="true" style={{ display: "inline-block", verticalAlign: "middle", marginRight: 4 }} />
                  <span>Suggested owner: {priorityInsight.owner || "Lead HRBP with Operations Head"}</span>
                </span>
              </div>
              <p className="adaptive-priority-callout__text">
                {next_check}
              </p>

              {/* HR Operational Window & Compliance Guardrail */}
              <div className="adaptive-priority-action-meta">
                <span className="adaptive-priority-action-meta__chip">
                  <Clock size={12} aria-hidden="true" />
                  <span>Target review: within 14 days (Q3 Workforce Cycle)</span>
                </span>
                <span className="adaptive-priority-action-meta__chip adaptive-priority-action-meta__chip--guardrail">
                  <ShieldAlert size={12} aria-hidden="true" />
                  <span>Policy guardrail: Verify flex arrangements & leave ledgers before review</span>
                </span>
              </div>

              {onOpenRecords ? (
                <div className="adaptive-priority-callout__link-wrap">
                  <button
                    type="button"
                    onClick={onOpenRecords}
                    className="adaptive-priority-evidence-link-btn"
                  >
                    Inspect supporting attendance records inline &rarr;
                  </button>
                </div>
              ) : sheetId ? (
                <div className="adaptive-priority-callout__link-wrap">
                  <a
                    href={`#explorer?sheet_id=${sheetId}`}
                    className="adaptive-priority-evidence-link"
                  >
                    Inspect supporting attendance records in Data Explorer &rarr;
                  </a>
                </div>
              ) : null}
            </div>
          </div>
        </div>

        {/* Right Column: Multi-View Visual (Bar Ranking | Capacity Donut | Data Table) */}
        <div className="adaptive-priority-card__visual">
          {hasChart ? (
            <div className="adaptive-priority-chart-wrapper">
              <div className="adaptive-priority-chart-wrapper__header">
                <span>
                  {visualMode === "bar"
                    ? `Department Comparison (${visual_type.replace(/_/g, " ")})`
                    : visualMode === "donut"
                    ? "Workforce Capacity Split"
                    : "Tabular Unit Breakdown"}
                </span>
                <span className="adaptive-priority-chart-wrapper__badge">
                  {visualMode === "donut" ? "Capacity Ratio" : "Recorded Attendance"}
                </span>
              </div>

              {visualMode === "table" ? (
                <div className="adaptive-priority-table-container">
                  <table className="adaptive-priority-table" aria-label="Department comparison table">
                    <thead>
                      <tr>
                        <th>Department</th>
                        <th className="adaptive-priority-table__th-right">Recorded Attendance</th>
                      </tr>
                    </thead>
                    <tbody>
                      {(echarts_option?.xAxis?.data || []).map((label, idx) => (
                        <tr key={label}>
                          <td>{label}</td>
                          <td className="adaptive-priority-table__td-right">
                            {echarts_option?.series?.[0]?.data?.[idx] != null
                              ? `${echarts_option.series[0].data[idx]} d`
                              : "—"}
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              ) : visualMode === "donut" && donutOption ? (
                <div className="adaptive-priority-chart-container">
                  <SafeReactECharts
                    option={donutOption}
                    opts={{ renderer: "svg" }}
                    style={{ height: "100%", width: "100%" }}
                  />
                </div>
              ) : (
                <div
                  className="adaptive-priority-chart-container"
                  style={{
                    height:
                      echarts_option?.yAxis?.type === "category"
                        ? Math.max(260, (echarts_option.yAxis.data?.length || 0) * 25 + 24)
                        : undefined,
                  }}
                >
                  <SafeReactECharts
                    option={echarts_option}
                    opts={{ renderer: "svg" }}
                    style={{
                      height:
                        echarts_option?.yAxis?.type === "category"
                          ? Math.max(260, (echarts_option.yAxis.data?.length || 0) * 25 + 24)
                          : "100%",
                      width: "100%",
                    }}
                  />
                </div>
              )}
            </div>
          ) : (
            <div className="adaptive-priority-visual-fallback">
              <p>Quantitative finding verified without secondary multi-point plot requirement.</p>
            </div>
          )}
        </div>
      </div>

      {/* Expandable Analysis Details & Methodology Drawer */}
      {showAudit && (
        <div className="adaptive-priority-audit" role="region" aria-label="Methodology and audit details">
          <div className="adaptive-priority-audit__title">
            <ShieldCheck size={16} />
            <span>Analysis Details & Methodology Audit</span>
          </div>

          {/* Strategy & Claim Badges Moved Here */}
          <div className="adaptive-priority-audit__badges-row">
            <span className="adaptive-priority-pill adaptive-priority-pill--primary">
              Strategy {strategy_code} · {strategy_name}
            </span>
            <span className="adaptive-priority-pill adaptive-priority-pill--claim">
              {claimLevelLabel}
            </span>
            <span className="adaptive-priority-pill adaptive-priority-pill--strategy">
              Deterministic Multi-Factor Scored
            </span>
          </div>

          <div className="adaptive-priority-audit__grid">
            <div className="adaptive-priority-audit__item">
              <span className="adaptive-priority-audit__item-label">Finding ID</span>
              <span className="adaptive-priority-audit__item-value">{finding_id}</span>
            </div>
            <div className="adaptive-priority-audit__item">
              <span className="adaptive-priority-audit__item-label">Calculation ID</span>
              <span className="adaptive-priority-audit__item-value">
                {evidence_details.calculation_id || "CALC-AUTONOMOUS"}
              </span>
            </div>
            <div className="adaptive-priority-audit__item">
              <span className="adaptive-priority-audit__item-label">Definition ID</span>
              <span className="adaptive-priority-audit__item-value">
                {evidence_details.definition_id || "DEF-AUTONOMOUS"}
              </span>
            </div>
            <div className="adaptive-priority-audit__item">
              <span className="adaptive-priority-audit__item-label">Snapshot Hash</span>
              <span className="adaptive-priority-audit__item-value">{snapshot || "SNAPSHOT-LIVE"}</span>
            </div>
          </div>

          {/* Explicit Limitations & Disclaimers */}
          {evidence_details.limitations && evidence_details.limitations.length > 0 && (
            <div className="adaptive-priority-audit__limitations">
              <div className="adaptive-priority-audit__limitations-header">
                <AlertTriangle size={14} />
                <span>Analytical Boundaries & Mandatory Disclaimers</span>
              </div>
              <ul>
                {evidence_details.limitations.map((lim, idx) => (
                  <li key={idx}>{lim}</li>
                ))}
              </ul>
            </div>
          )}

          {/* HR Governance & Legal Interpretation Guardrails (Merged from Leadership Report) */}
          <div className="adaptive-priority-audit__governance">
            <div className="adaptive-priority-audit__governance-header">
              <ShieldAlert size={15} color="var(--brand-400, #ffb089)" />
              <span>HR Policy Compliance & Interpretive Guardrails</span>
            </div>
            <p className="adaptive-priority-audit__governance-text">
              Observations describe recorded timecard logs and statistical variance. They do not establish individual performance, employee intent, or contractual breach. Mandatory HR protocol requires reconciling attendance against approved medical/annual leaves and core-hours agreements prior to taking administrative or supervisory action.
            </p>
          </div>
        </div>
      )}
    </section>
  );
}
