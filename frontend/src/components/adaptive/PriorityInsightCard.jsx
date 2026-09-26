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
  Layers,
} from "lucide-react";
import SafeReactECharts from "../charts/SafeReactECharts";

/**
 * Intelligent number formatting with currency, SI prefixes (K, M, B) or standard rounding.
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
  if (abs >= 1e4) return `${prefix}${(num / 1e3).toFixed(1)}K${suffix}`;
  if (abs >= 100) return `${prefix}${num.toLocaleString(undefined, { maximumFractionDigits: 0 })}${suffix}`;
  return `${prefix}${num.toLocaleString(undefined, { maximumFractionDigits: 1 })}${suffix}`;
}

/**
 * Extracts categories and numeric values whether horizontal (yAxis.data) or vertical (xAxis.data).
 */
function getCategoriesAndValues(baseOption) {
  if (!baseOption) return { categories: [], values: [], isHoriz: false };
  const isHoriz = baseOption.yAxis?.type === "category";
  const categories = (isHoriz ? baseOption.yAxis?.data : baseOption.xAxis?.data) || [];
  const seriesData = baseOption.series?.[0]?.data || [];
  const values = seriesData.map((d) =>
    typeof d === "object" && d !== null ? (d.value != null ? Number(d.value) : 0) : Number(d) || 0
  );
  return { categories: [...categories], values: [...values], isHoriz };
}

/**
 * Builds an executive Donut Option.
 * If > 7 categories, consolidates into Top 5 + 'Other (N units)' to eliminate rainbow clutter.
 */
function buildDonutOption(baseOption, heroValue, unitSuffix, title, unit = "") {
  if (!baseOption) return null;
  const { categories, values } = getCategoriesAndValues(baseOption);
  if (!categories.length) return null;

  const palette = ["#ff8a62", "#34d399", "#60a5fa", "#fbbb27", "#c084fc", "#fb7185", "#38bdf8"];
  let pieData = [];

  if (categories.length > 7) {
    // Pair and sort descending
    const paired = categories.map((cat, i) => ({ name: String(cat), value: values[i] || 0 }));
    paired.sort((a, b) => b.value - a.value);

    const top5 = paired.slice(0, 5);
    const otherVal = paired.slice(5).reduce((sum, p) => sum + p.value, 0);

    pieData = top5.map((p, i) => ({
      name: p.name,
      value: p.value,
      itemStyle: { color: palette[i % palette.length], borderColor: "#171412", borderWidth: 2 },
    }));

    if (otherVal > 0) {
      pieData.push({
        name: `Other (${categories.length - 5} units)`,
        value: otherVal,
        itemStyle: { color: "#524940", borderColor: "#171412", borderWidth: 2 },
      });
    }
  } else {
    pieData = categories.map((cat, i) => ({
      name: String(cat),
      value: values[i] || 0,
      itemStyle: { color: palette[i % palette.length], borderColor: "#171412", borderWidth: 2 },
    }));
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
      formatter: (params) => {
        const valFmt = formatCompactNumber(params.value, unit);
        return `${params.name}: <strong>${valFmt}</strong> (${params.percent}%)`;
      },
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
        name: title || "Unit Split",
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
          fontSize: 16,
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
 * Builds a density-bounded ECharts Bar Option for executive display.
 */
function buildBoundedBarOption(baseOption, densityMode, unit = "") {
  if (!baseOption) return null;
  const { categories, values, isHoriz } = getCategoriesAndValues(baseOption);
  if (!categories.length) return baseOption;

  let filteredCats = categories;
  let filteredVals = values;

  if (densityMode === "top10" && categories.length > 10) {
    if (isHoriz) {
      // For horizontal bar (bottom-to-top rendering), the highest values are at the end of the array
      filteredCats = categories.slice(-10);
      filteredVals = values.slice(-10);
    } else {
      filteredCats = categories.slice(0, 10);
      filteredVals = values.slice(0, 10);
    }
  } else if (densityMode === "extremes" && categories.length > 10) {
    if (isHoriz) {
      const bottom5Cats = categories.slice(0, 5);
      const bottom5Vals = values.slice(0, 5);
      const top5Cats = categories.slice(-5);
      const top5Vals = values.slice(-5);
      filteredCats = [...bottom5Cats, ...top5Cats];
      filteredVals = [...bottom5Vals, ...top5Vals];
    } else {
      const top5Cats = categories.slice(0, 5);
      const top5Vals = values.slice(0, 5);
      const bottom5Cats = categories.slice(-5);
      const bottom5Vals = values.slice(-5);
      filteredCats = [...top5Cats, ...bottom5Cats];
      filteredVals = [...top5Vals, ...bottom5Vals];
    }
  }

  // Clone and override data with intelligent number formatting
  const opt = JSON.parse(JSON.stringify(baseOption));
  if (isHoriz) {
    if (opt.yAxis) opt.yAxis.data = filteredCats;
    if (opt.xAxis) {
      opt.xAxis.axisLabel = {
        ...opt.xAxis.axisLabel,
        formatter: (val) => formatCompactNumber(val, unit),
      };
    }
  } else {
    if (opt.xAxis) opt.xAxis.data = filteredCats;
    if (opt.yAxis) {
      opt.yAxis.axisLabel = {
        ...opt.yAxis.axisLabel,
        formatter: (val) => formatCompactNumber(val, unit),
      };
    }
  }

  if (opt.series && opt.series[0]) {
    opt.series[0].data = filteredVals;
    opt.series[0].label = {
      ...opt.series[0].label,
      show: true,
      formatter: (params) => formatCompactNumber(params.value, unit),
    };
  }

  opt.tooltip = {
    ...opt.tooltip,
    formatter: (params) => {
      const item = Array.isArray(params) ? params[0] : params;
      const valFmt = formatCompactNumber(item.value, unit);
      return `${item.name}: <strong>${valFmt}</strong>`;
    },
  };

  return opt;
}

export default function PriorityInsightCard({
  priorityInsight,
  sheetId,
  snapshot,
  onInspect,
  onListen,
  onOpenRecords,
}) {
  const [visualMode, setVisualMode] = useState("bar"); // "bar" | "donut" | "table"
  const [densityMode, setDensityMode] = useState("top10"); // "top10" | "extremes" | "all"
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
    unit = "",
    comparison_label,
    comparison_value,
    implication,
    next_check,
    evidence_details = {},
    visual_type,
    echarts_option,
    population_summary,
    allowed_claim_level = "descriptive_fact",
    dimension_name,
    metric_name,
    owner,
    guardrail,
    review_cycle,
  } = priorityInsight;

  const hasChart = echarts_option && visual_type !== "none";
  const claimLevelLabel = allowed_claim_level.replace(/_/g, " ").toUpperCase();

  // Extract categories and values for multi-view modes
  const { categories, values } = useMemo(
    () => getCategoriesAndValues(echarts_option),
    [echarts_option]
  );
  const hasManyCategories = categories.length > 10;

  // Domain-aware copy
  const isHr =
    (metric_name && metric_name.toLowerCase().includes("attendance")) ||
    (dimension_name && dimension_name.toLowerCase() === "department");

  const effectiveDimension = dimension_name || (isHr ? "Department" : "Unit");
  const effectiveMetric = metric_name || (isHr ? "Recorded Attendance" : "Observed Metric");
  const effectiveOwner = owner || (isHr ? "Lead HRBP with Operations Head" : "Operations & Performance Lead");
  const effectiveGuardrail =
    guardrail ||
    (isHr
      ? "Policy guardrail: Verify flex arrangements & leave ledgers before review"
      : "Data guardrail: Validate localized operational drivers before adjusting targets");
  const effectiveReviewCycle = review_cycle || (isHr ? "within 14 days (Q3 Workforce Cycle)" : "14-day operational review cycle");

  // Clean formatted hero value
  const displayVal = String(prominent_number || "");
  const unitSuffix = unit && !displayVal.toLowerCase().includes(unit.toLowerCase()) ? ` ${unit}` : "";

  // Dynamic Donut Option
  const donutOption = useMemo(() => {
    return buildDonutOption(echarts_option, displayVal, unitSuffix, short_business_title, unit);
  }, [echarts_option, displayVal, unitSuffix, short_business_title, unit]);

  // Dynamic Bounded Bar Option
  const boundedBarOption = useMemo(() => {
    return buildBoundedBarOption(echarts_option, densityMode, unit);
  }, [echarts_option, densityMode, unit]);

  // Dynamic Bar Height
  const barChartHeight = useMemo(() => {
    if (!boundedBarOption) return 320;
    const catCount =
      densityMode === "top10"
        ? Math.min(10, categories.length)
        : densityMode === "extremes"
        ? Math.min(10, categories.length)
        : categories.length;
    return Math.max(260, Math.min(680, catCount * 26 + 32));
  }, [boundedBarOption, densityMode, categories.length]);

  return (
    <section className="adaptive-priority-card" aria-label="Executive Priority Insight">
      <div className="adaptive-priority-card__ambient-glow" />

      {/* Top Header: Business Headline & Action Controls */}
      <div className="adaptive-priority-card__header">
        <div className="adaptive-priority-card__heading-group">
          <span className="adaptive-priority-card__kicker">
            {isHr ? "Workforce Priority Insight" : "Strategic Priority Insight"}
          </span>
          <h2 className="adaptive-priority-card__title">{short_business_title}</h2>
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
                title="Proportion Donut"
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
              aria-label={`Inspect supporting records for ${effectiveDimension}`}
            >
              <ExternalLink size={14} />
              <span>View Records</span>
            </button>
          ) : sheetId ? (
            <a
              href={`#explorer?sheet_id=${sheetId}`}
              className="adaptive-priority-btn adaptive-priority-btn--link"
              aria-label="View raw records in Data Explorer"
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
              <span className="adaptive-priority-metric__label">Disparity Spread</span>
              <div className="adaptive-priority-metric__value">
                {displayVal}
                {unitSuffix}
              </div>
              <span className="adaptive-priority-metric__hint">
                Difference between highest and lowest {effectiveDimension.toLowerCase()} average
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
                {isHr ? "Neutral department attendance comparison" : "Neutral comparative unit benchmark"}
              </span>
            </div>
          </div>

          {/* Operational Implication */}
          <div className="adaptive-priority-callout adaptive-priority-callout--implication">
            <TrendingUp size={18} className="adaptive-priority-callout__icon adaptive-priority-callout__icon--brand" />
            <div className="adaptive-priority-callout__body">
              <h4 className="adaptive-priority-callout__label">Operational Implication</h4>
              <p className="adaptive-priority-callout__text">{implication}</p>
            </div>
          </div>

          {/* Next Recommended Action with Operational Ownership & Policy Guardrails */}
          <div className="adaptive-priority-callout adaptive-priority-callout--next-step">
            <ArrowRight size={18} className="adaptive-priority-callout__icon adaptive-priority-callout__icon--emerald" />
            <div className="adaptive-priority-callout__body">
              <div className="adaptive-priority-callout__header-row">
                <h4 className="adaptive-priority-callout__label adaptive-priority-callout__label--emerald">
                  Recommended Action & Accountability
                </h4>
                <span className="adaptive-priority-callout__role-badge">
                  <UserCheck size={12} aria-hidden="true" style={{ display: "inline-block", verticalAlign: "middle", marginRight: 4 }} />
                  <span>Suggested owner: {effectiveOwner}</span>
                </span>
              </div>
              <p className="adaptive-priority-callout__text">{next_check}</p>

              {/* Operational Review Window & Compliance Guardrail */}
              <div className="adaptive-priority-action-meta">
                <span className="adaptive-priority-action-meta__chip">
                  <Clock size={12} aria-hidden="true" />
                  <span>Target review: {effectiveReviewCycle}</span>
                </span>
                <span className="adaptive-priority-action-meta__chip adaptive-priority-action-meta__chip--guardrail">
                  <ShieldAlert size={12} aria-hidden="true" />
                  <span>{effectiveGuardrail}</span>
                </span>
              </div>

              {onOpenRecords ? (
                <div className="adaptive-priority-callout__link-wrap">
                  <button
                    type="button"
                    onClick={onOpenRecords}
                    className="adaptive-priority-evidence-link-btn"
                  >
                    Inspect supporting {effectiveDimension.toLowerCase()} records inline &rarr;
                  </button>
                </div>
              ) : sheetId ? (
                <div className="adaptive-priority-callout__link-wrap">
                  <a
                    href={`#explorer?sheet_id=${sheetId}`}
                    className="adaptive-priority-evidence-link"
                  >
                    Inspect supporting records in Data Explorer &rarr;
                  </a>
                </div>
              ) : null}
            </div>
          </div>
        </div>

        {/* Right Column: Multi-View Visual (Bar Ranking | Proportion Donut | Data Table) */}
        <div className="adaptive-priority-card__visual">
          {hasChart ? (
            <div className="adaptive-priority-chart-wrapper">
              <div className="adaptive-priority-chart-wrapper__header">
                <div style={{ display: "flex", alignItems: "center", gap: 10 }}>
                  <span>
                    {visualMode === "bar"
                      ? `${effectiveDimension} Comparison (${visual_type.replace(/_/g, " ")})`
                      : visualMode === "donut"
                      ? `${effectiveDimension} Proportion Split`
                      : `Tabular ${effectiveDimension} Breakdown`}
                  </span>
                  {hasManyCategories && visualMode === "bar" && (
                    <div className="adaptive-priority-density-pills" role="group" aria-label="Category display density">
                      <button
                        type="button"
                        className={`density-pill-btn ${densityMode === "top10" ? "active" : ""}`}
                        onClick={() => setDensityMode("top10")}
                        title="Display top 10 ranked units"
                      >
                        Top 10
                      </button>
                      <button
                        type="button"
                        className={`density-pill-btn ${densityMode === "extremes" ? "active" : ""}`}
                        onClick={() => setDensityMode("extremes")}
                        title="Display top 5 and bottom 5 units"
                      >
                        Extremes
                      </button>
                      <button
                        type="button"
                        className={`density-pill-btn ${densityMode === "all" ? "active" : ""}`}
                        onClick={() => setDensityMode("all")}
                        title={`Display all ${categories.length} units`}
                      >
                        All ({categories.length})
                      </button>
                    </div>
                  )}
                </div>

                <span className="adaptive-priority-chart-wrapper__badge">
                  {visualMode === "donut" ? "Share Ratio" : effectiveMetric}
                </span>
              </div>

              {visualMode === "table" ? (
                <div className="adaptive-priority-table-container">
                  <table className="adaptive-priority-table" aria-label={`${effectiveDimension} comparison table`}>
                    <thead>
                      <tr>
                        <th>{effectiveDimension}</th>
                        <th className="adaptive-priority-table__th-right">{effectiveMetric}</th>
                      </tr>
                    </thead>
                    <tbody>
                      {categories.map((label, idx) => (
                        <tr key={label}>
                          <td>{label}</td>
                          <td className="adaptive-priority-table__td-right">
                            <strong>{formatCompactNumber(values[idx], unit)}</strong>
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              ) : visualMode === "donut" && donutOption ? (
                <div className="adaptive-priority-chart-container" style={{ minHeight: 320, height: 340 }}>
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
                    height: barChartHeight,
                    maxHeight: densityMode === "all" ? 680 : undefined,
                    overflowY: densityMode === "all" ? "auto" : "visible",
                  }}
                >
                  <SafeReactECharts
                    option={boundedBarOption}
                    opts={{ renderer: "svg" }}
                    style={{
                      height: barChartHeight,
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
              <span className="adaptive-priority-audit__item-label">Strategy</span>
              <span className="adaptive-priority-audit__item-value">
                {strategy_code} ({strategy_name})
              </span>
            </div>
            <div className="adaptive-priority-audit__item">
              <span className="adaptive-priority-audit__item-label">Evidence Claim Level</span>
              <span className="adaptive-priority-audit__item-value">{claimLevelLabel}</span>
            </div>
            <div className="adaptive-priority-audit__item">
              <span className="adaptive-priority-audit__item-label">Calculation ID</span>
              <span className="adaptive-priority-audit__item-value">
                {evidence_details.calculation_id || "calc_priority_01"}
              </span>
            </div>
            <div className="adaptive-priority-audit__item">
              <span className="adaptive-priority-audit__item-label">Definition ID</span>
              <span className="adaptive-priority-audit__item-value">
                {evidence_details.definition_id || "def_priority_v1"}
              </span>
            </div>
            <div className="adaptive-priority-audit__item">
              <span className="adaptive-priority-audit__item-label">Snapshot Provenance</span>
              <span className="adaptive-priority-audit__item-value">{snapshot || "live_source"}</span>
            </div>
          </div>

          {evidence_details.limitations && evidence_details.limitations.length > 0 && (
            <div className="adaptive-priority-audit__limitations">
              <h5 className="adaptive-priority-audit__limitations-title">
                <AlertTriangle size={14} />
                <span>Declared Limitations & Statistical Boundaries</span>
              </h5>
              <ul>
                {evidence_details.limitations.map((lim, i) => (
                  <li key={i}>{lim}</li>
                ))}
              </ul>
            </div>
          )}
        </div>
      )}
    </section>
  );
}
