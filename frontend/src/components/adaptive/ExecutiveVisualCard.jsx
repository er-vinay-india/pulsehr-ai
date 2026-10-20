import React, { useMemo, useState, useEffect } from "react";
import VisualSpecRenderer from "./VisualSpecRenderer";
import SemanticIcon from "./SemanticIcon";
import ActionIconButton from "../../design-system/components/ActionIconButton";
import DataTable from "../DataTable";
import { resolvePresentationLabel } from "../../design-system/registries/PresentationLabelResolver";
import { getContextualExplorerTarget } from "../../utils/explorerNavigation";

/**
 * ExecutiveVisualCard: Semantic `<article>` container for individual executive decision visuals.
 * Enforces Header ("What is this?"), Visual Figure ("What is happening?"), and Figcaption/Footer ("What can I do next?").
 */
export default function ExecutiveVisualCard({
  topic,
  isHero = false,
  datasetId = null,
  themeTokens,
  isDark = false,
  onInspect,
}) {
  if (!topic) return null;

  const [selectedMetricId, setSelectedMetricId] = useState(null);
  const [isRankingDrawerOpen, setIsRankingDrawerOpen] = useState(false);

  useEffect(() => {
    if (!isRankingDrawerOpen) return;
    const handleKeyDown = (e) => {
      if (e.key === "Escape") {
        setIsRankingDrawerOpen(false);
      }
    };
    window.addEventListener("keydown", handleKeyDown);
    return () => window.removeEventListener("keydown", handleKeyDown);
  }, [isRankingDrawerOpen]);

  const intentColor = {
    RANKING: themeTokens?.colors?.brandBlue || "var(--color-brand-blue, var(--action-primary-bg))",
    TREND: themeTokens?.colors?.gold || "var(--color-gold, var(--color-warning))",
    COMPOSITION: themeTokens?.colors?.statusSuccess || "var(--color-success)",
    RELATIONSHIP: "var(--color-indigo, var(--action-primary-bg))",
    ANOMALY: themeTokens?.colors?.statusError || "var(--color-danger)",
    DISTRIBUTION: "var(--color-cyan, var(--color-brand-secondary))",
    TARGET_VS_ACTUAL: themeTokens?.colors?.statusSuccess || "var(--color-success)",
    COMPARISON: themeTokens?.colors?.brandBlue || "var(--color-brand-blue, var(--action-primary-bg))",
    PART_TO_WHOLE: "var(--color-indigo, var(--action-primary-bg))",
    GAP_EXPLANATION: themeTokens?.colors?.gold || "var(--color-gold, var(--color-warning))",
    MATRIX: "var(--color-violet, var(--action-primary-bg))",
  }[topic.analytical_intent] || (themeTokens?.colors?.brandBlue || "var(--color-brand-blue, var(--action-primary-bg))");

  const intentBg = isDark
    ? "rgba(255, 255, 255, 0.06)"
    : "rgba(0, 0, 0, 0.04)";

  const isGeospatial =
    topic.visual_spec?.chart_type === "map" ||
    topic.visual_spec?.chart_type === "choropleth" ||
    topic.visual_spec?.chart_type === "bubble_map" ||
    topic.visual_spec?.chart_type === "point_map" ||
    topic.analytical_intent === "GEOSPATIAL";

  const isRankingStory = (topic.analytical_intent === "RANKING" || topic.visual_spec?.is_ranking_story) && !isGeospatial;

  // Contextual Data Explorer Target
  const contextualTarget = useMemo(() => getContextualExplorerTarget(topic, datasetId), [topic, datasetId]);

  // Executive Dashboard Ranking Constraint: Exactly Top 3 + Bottom 3 only (never more than 6 unique entities)
  const compactVisualSpec = useMemo(() => {
    if (!topic.visual_spec) return null;
    if (isGeospatial || topic.visual_spec.chart_type === "podium_top_3") return topic.visual_spec;
    if (!isRankingStory) return topic.visual_spec;

    const spec = { ...topic.visual_spec };
    const rawCategories = spec.categories || [];
    const rawValues = spec.values || [];

    if (spec.bottom_categories && spec.bottom_categories.length > 0) {
      const topCats = rawCategories.slice(0, 3);
      const topVals = rawValues.slice(0, 3);
      const botCats = [];
      const botVals = [];
      (spec.bottom_categories || []).forEach((cat, idx) => {
        if (!topCats.includes(cat) && (topCats.length + botCats.length) < 6) {
          botCats.push(cat);
          botVals.push(spec.bottom_values ? spec.bottom_values[idx] : 0);
        }
      });
      return {
        ...spec,
        chart_type: botCats.length > 0 ? "diverging_bar" : "ranked_bar",
        categories: topCats,
        values: topVals,
        bottom_categories: botCats,
        bottom_values: botVals,
      };
    }

    if (rawCategories.length <= 6) {
      return {
        ...spec,
        chart_type: "ranked_bar",
        categories: rawCategories,
        values: rawValues,
        bottom_categories: [],
        bottom_values: [],
      };
    }

    const topCats = rawCategories.slice(0, 3);
    const topVals = rawValues.slice(0, 3);
    const candBotCats = rawCategories.slice(-3);
    const candBotVals = rawValues.slice(-3);

    const botCats = [];
    const botVals = [];
    candBotCats.forEach((cat, idx) => {
      if (!topCats.includes(cat) && (topCats.length + botCats.length) < 6) {
        botCats.push(cat);
        botVals.push(candBotVals[idx]);
      }
    });

    return {
      ...spec,
      chart_type: botCats.length > 0 ? "diverging_bar" : "ranked_bar",
      categories: topCats,
      values: topVals,
      bottom_categories: botCats,
      bottom_values: botVals,
    };
  }, [topic.visual_spec, isRankingStory]);

  // Compressed Level-1 Microcopy (<= 7 word title, <= 8 word context, <= 12 word finding)
  const microcopy = useMemo(() => {
    if (topic.visual_microcopy) {
      return topic.visual_microcopy;
    }
    const words = (str) => (str || "").trim().split(/\s+/).filter(Boolean);
    const shortTitle = words(topic.title).slice(0, 7).join(" ");
    const shortContext = words(topic.subtitle || "").slice(0, 8).join(" ");
    const shortTakeaway = words(topic.primary_takeaway || topic.takeaway || topic.title || "").slice(0, 12).join(" ");
    return {
      icon: topic.analytical_intent === "TARGET_VS_ACTUAL" ? "target" : "activity",
      short_title: shortTitle || topic.title,
      primary_number: topic.key_metric || "",
      short_context: shortContext,
      short_finding: shortTakeaway || "Analyzed metric distributions across reporting population.",
      cta: "Inspect →",
    };
  }, [topic]);

  // Client-side Axis Narrative Integrity Guard: Prevents cross-domain title corruption
  const displayTitle = useMemo(() => {
    let rawTitle = microcopy.short_title || topic.title || "";
    const vSpec = topic.visual_spec;
    if (vSpec) {
      // Check relationship / scatter cards
      if (topic.analytical_intent === "RELATIONSHIP" || vSpec.chart_type === "scatter") {
        const xLabel = vSpec.x_label;
        const yLabel = vSpec.y_label;
        if (xLabel && yLabel) {
          const titleLower = rawTitle.toLowerCase();
          const axesLower = `${xLabel} ${yLabel}`.toLowerCase();
          const isNonWorkforceAxes = /temperature|fuel|traffic|revenue|sales|store|cpi|unemployment|pm10|so2|no2/i.test(axesLower);
          const hasWorkforceTokens = /\b(attendance|leave|leaves|employee|wfo)\b/i.test(titleLower);
          if (isNonWorkforceAxes && hasWorkforceTokens) {
            rawTitle = `${xLabel} vs ${yLabel}`;
          }
        }
      }
    }
    return resolvePresentationLabel(rawTitle);
  }, [microcopy.short_title, topic.title, topic.visual_spec, topic.analytical_intent]);

  // Server-driven Spatial Placement (SpatialCompositionOptimizer)
  const colSpan = topic.spatial_placement?.column_span || (isHero ? 12 : isGeospatial ? 12 : topic.layout_hint === "LARGE" ? 8 : topic.layout_hint === "COMPACT" ? 4 : 6);
  const heightClass = topic.spatial_placement?.height_class || (isHero ? "standard" : "standard");
  const layoutHint = (topic.layout_hint || topic.visual_spec?.layout_hint || (isHero ? "HERO" : isGeospatial ? "LARGE" : "MEDIUM")).toLowerCase();
  const layoutClass = `span-${colSpan} height-${heightClass} layout-hint-${layoutHint} visual-card--${layoutHint}`;

  // Synchronized chart height based on row height class
  const chartHeight = useMemo(() => {
    if (isGeospatial) return "440px";
    if (isHero) return "320px";
    if (heightClass === "tall") return "320px";
    if (heightClass === "short") return "190px";
    return "230px";
  }, [heightClass, isHero, isGeospatial]);

  const availableMetrics = useMemo(() => {
    if (!isGeospatial) return [];
    return compactVisualSpec?.available_metrics || [];
  }, [isGeospatial, compactVisualSpec]);

  const activeMetric = useMemo(() => {
    if (!availableMetrics || availableMetrics.length === 0) return null;
    if (selectedMetricId) {
      return availableMetrics.find((m) => m.metric_id === selectedMetricId) || availableMetrics[0];
    }
    return availableMetrics[0];
  }, [availableMetrics, selectedMetricId]);

  const activeVisualSpec = useMemo(() => {
    if (!isGeospatial || !activeMetric) return compactVisualSpec;
    return {
      ...compactVisualSpec,
      chart_type: activeMetric.map_type || compactVisualSpec.chart_type,
      map_type: activeMetric.map_type || compactVisualSpec.map_type,
      measure_label: activeMetric.label,
      primary_measure: activeMetric.label,
      unit: activeMetric.unit,
      categories: activeMetric.categories || compactVisualSpec.categories,
      values: activeMetric.values || compactVisualSpec.values,
      map_data: activeMetric.map_data || compactVisualSpec.map_data,
      table_data: activeMetric.table_data || compactVisualSpec.table_data,
      key_metric: activeMetric.key_metric || compactVisualSpec.key_metric,
    };
  }, [isGeospatial, activeMetric, compactVisualSpec]);

  const geoTableColumns = useMemo(() => {
    const tblData = activeVisualSpec?.table_data || [];
    const hasDensity = tblData.some((r) => r.density != null);
    const hasGrowth = tblData.some((r) => r.growth != null);
    const hasPop = tblData.some((r) => r.population != null);
    const primaryLabel = activeVisualSpec?.measure_label || activeVisualSpec?.primary_measure || "Metric Value";

    const cols = [
      { key: "rank", label: "Rank", sortable: true, align: "center", width: "70px" },
      { key: "location", label: activeVisualSpec?.geo_dimension || "Territory", sortable: true, filterable: true },
      { key: "value", label: primaryLabel, sortable: true, align: "right" },
    ];

    if (hasGrowth && !primaryLabel.toLowerCase().includes("growth")) {
      cols.push({ key: "growth", label: "Growth (2001-2011)", sortable: true, align: "right", width: "150px" });
    }
    if (hasPop && !primaryLabel.toLowerCase().includes("pop")) {
      cols.push({ key: "population", label: "Population 2011", sortable: true, align: "right", width: "150px" });
    }
    if (hasDensity && !primaryLabel.toLowerCase().includes("density")) {
      cols.push({ key: "density", label: "Population Density", sortable: true, align: "right", width: "160px" });
    }

    cols.push({
      key: "lineage",
      label: "Lineage",
      sortable: true,
      align: "center",
      width: "110px",
      render: (val) => (
        <span
          style={{
            fontSize: "0.68rem",
            padding: "2px 6px",
            borderRadius: "4px",
            backgroundColor: isDark ? "rgba(59, 130, 246, 0.2)" : "rgba(219, 234, 254, 0.8)",
            color: isDark ? "#93c5fd" : "#1d4ed8",
            fontWeight: 600,
          }}
        >
          {val || "OBSERVED"}
        </span>
      ),
    });

    return cols;
  }, [activeVisualSpec, isDark]);

  const geoTableRows = useMemo(() => {
    if (!activeVisualSpec || !isGeospatial) return [];
    if (activeVisualSpec.table_data && activeVisualSpec.table_data.length > 0) {
      return activeVisualSpec.table_data.map((r, i) => ({
        id: `geo-row-${i}`,
        rank: r.rank != null ? r.rank : i + 1,
        location: r.location || "-",
        value: r.formatted_value || `${r.value ?? "-"}`,
        raw_value: r.value != null ? r.value : 0,
        growth: r.growth || "-",
        population: r.population || "-",
        density: r.density || "-",
        lineage: r.lineage || activeVisualSpec.geo_source || "OBSERVED",
      }));
    }
    const cats = activeVisualSpec.categories || [];
    const vals = activeVisualSpec.values || [];
    const unit = activeVisualSpec.unit || "";
    return cats.map((cat, idx) => ({
      id: `geo-row-${idx}`,
      rank: idx + 1,
      location: cat,
      value: vals[idx] != null ? `${vals[idx]} ${unit}`.trim() : "-",
      raw_value: vals[idx] != null ? vals[idx] : 0,
      growth: "-",
      population: "-",
      density: "-",
      lineage: activeVisualSpec.geo_source || "OBSERVED",
    }));
  }, [activeVisualSpec, isGeospatial]);

  const accessibleChartDescription = topic.primary_takeaway || topic.takeaway || topic.title || "Visual analytics chart.";

  const activePrimaryNumber = isGeospatial && activeMetric?.key_metric
    ? activeMetric.key_metric
    : microcopy.primary_number;

  const activeTakeaway = isGeospatial && activeMetric?.takeaway
    ? activeMetric.takeaway
    : (topic.primary_takeaway || topic.takeaway || microcopy.short_finding);

  const activeAccessibleSummary = isGeospatial && (activeMetric?.accessible_summary || activeVisualSpec?.accessible_summary)
    ? (activeMetric?.accessible_summary || activeVisualSpec?.accessible_summary)
    : accessibleChartDescription;

  return (
    <article
      className={`executive-visual-card executive-insight-card ${isHero ? "hero-card visual-card--hero hero-chart-container" : "supporting-card"} ${layoutClass}`}
      data-testid={isHero ? "hero-card" : "supporting-chart-container"}
      data-topic-id={topic.topic_id}
      data-column-span={colSpan}
      data-height-class={heightClass}
      aria-labelledby={`topic-title-${topic.topic_id}`}
      style={{
        gridColumn: `span ${colSpan}`,
        backgroundColor: themeTokens?.colors?.surface,
        border: `1px solid ${isHero ? (themeTokens?.colors?.brandBlue || "var(--action-primary-bg)") : (themeTokens?.colors?.borderSubtle || "var(--color-border)")}`,
        borderRadius: "12px",
        padding: isHero ? "18px 22px" : "14px 16px",
        display: "flex",
        flexDirection: "column",
        justifyContent: "space-between",
        gap: "10px",
        boxShadow: isHero ? "0 4px 20px -2px rgba(37, 99, 235, 0.08)" : "none",
        minWidth: 0,
        overflow: "hidden",
      }}
    >
      <div>
        {/* 1. HEADER ("What is this?"): Semantic Icon + H3 Title (Protected) + ActionIconButton */}
        <header className="visual-card__header visual-card__header-grid">
          <span
            className="visual-card__icon semantic-icon-wrapper"
            aria-hidden="true"
            style={{
              display: "inline-flex",
              alignItems: "center",
              justifyContent: "center",
              width: "26px",
              height: "26px",
              borderRadius: "6px",
              backgroundColor: intentBg,
              color: intentColor,
              flexShrink: 0,
            }}
          >
            <SemanticIcon name={microcopy.icon} size={15} />
          </span>

          <div className="visual-card__title-cell">
            <h3
              id={`topic-title-${topic.topic_id}`}
              className="visual-card__title card-compressed-title"
              title={topic.technical_title || topic.title}
              aria-label={displayTitle}
              style={{
                margin: 0,
                fontSize: isHero ? "1.15rem" : "0.98rem",
                fontWeight: 700,
                color: themeTokens?.colors?.textPrimary,
                lineHeight: 1.25,
              }}
            >
              {displayTitle}
            </h3>
          </div>

          <div className="visual-card__actions-cell">
            <ActionIconButton
              action="details"
              title={topic.technical_title || topic.title}
              tooltip={`Explain ${topic.technical_title || topic.title}`}
              ariaLabel={`Explain ${topic.technical_title || topic.title}`}
              onClick={() => onInspect && onInspect(topic)}
              size={14}
            />
            {contextualTarget && (
              <ActionIconButton
                action="deep_dive"
                title={topic.technical_title || topic.title}
                tooltip={`${contextualTarget.label} in Data Explorer`}
                ariaLabel={`${contextualTarget.label} in Data Explorer`}
                href={contextualTarget.url}
                size={14}
              />
            )}
          </div>
        </header>

        {/* Metric / Context sub-strip: Primary metric number + Short context sentence */}
        {(activePrimaryNumber || microcopy.short_context) && (
          <div
            className="visual-card__metric-context card-metric-context"
            style={{
              display: "flex",
              alignItems: "baseline",
              gap: "8px",
              marginBottom: "6px",
              fontSize: "0.78rem",
            }}
          >
            {activePrimaryNumber && (
              <span
                className="visual-card__metric card-primary-number"
                style={{
                  fontWeight: 800,
                  fontSize: isHero ? "1.05rem" : "0.88rem",
                  color: intentColor,
                }}
              >
                {activePrimaryNumber}
              </span>
            )}
            {microcopy.short_context && (
              <span
                className="visual-card__context card-short-context"
                style={{
                  color: themeTokens?.colors?.textSecondary,
                  fontSize: "0.75rem",
                  whiteSpace: "nowrap",
                  overflow: "hidden",
                  textOverflow: "ellipsis",
                }}
              >
                {microcopy.short_context}
              </span>
            )}
          </div>
        )}

        {/* Governed Compact Metric Selector above Map */}
        {isGeospatial && availableMetrics.length > 1 && (
          <div
            className="geo-metric-selector"
            role="tablist"
            aria-label="Select geographic metric to visualize on map"
            style={{
              display: "flex",
              alignItems: "center",
              gap: "6px",
              margin: "6px 0 10px 0",
              flexWrap: "wrap",
            }}
          >
            {availableMetrics.map((m) => {
              const isSelected = m.metric_id === (activeMetric?.metric_id || availableMetrics[0].metric_id);
              return (
                <button
                  key={m.metric_id}
                  type="button"
                  role="tab"
                  aria-selected={isSelected}
                  onClick={() => setSelectedMetricId(m.metric_id)}
                  style={{
                    padding: "4px 10px",
                    fontSize: "0.74rem",
                    fontWeight: isSelected ? 700 : 500,
                    borderRadius: "6px",
                    border: isSelected
                      ? `1px solid ${isDark ? "#38bdf8" : "#2563eb"}`
                      : `1px solid ${isDark ? "#334155" : "#e2e8f0"}`,
                    backgroundColor: isSelected
                      ? isDark
                        ? "rgba(56, 189, 248, 0.15)"
                        : "rgba(37, 99, 235, 0.08)"
                      : isDark
                      ? "#1e293b"
                      : "#f8fafc",
                    color: isSelected
                      ? isDark
                        ? "#38bdf8"
                        : "#1d4ed8"
                      : isDark
                      ? "#94a3b8"
                      : "#475569",
                    cursor: "pointer",
                    transition: "all 0.15s ease",
                  }}
                >
                  {m.label}
                </button>
              );
            })}
          </div>
        )}

        {/* 2. FIGURE ("What is happening?"): ECharts Visual Spec Renderer with accessible fallback */}
        <figure
          className="visual-card__figure"
          style={{
            margin: "4px 0 0 0",
            padding: 0,
            width: "100%",
            display: "flex",
            flexDirection: "column",
          }}
        >
          <p className="sr-only">
            {activeAccessibleSummary}
          </p>
          <VisualSpecRenderer
            visualSpec={activeVisualSpec}
            themeTokens={themeTokens}
            isDark={isDark}
            height={isGeospatial ? "440px" : chartHeight}
          />
          {/* Note: Full DataTable permanently removed from default figure; accessible on-demand via "View ranking →" drawer */}
          <figcaption
            className="visual-card__figcaption card-short-insight"
            style={{
              paddingTop: "10px",
              marginTop: "6px",
              borderTop: `1px solid ${themeTokens?.colors?.borderSubtle || "var(--color-border)"}`,
              display: "flex",
              alignItems: "center",
              justifyContent: "space-between",
              gap: "12px",
              flexWrap: "wrap",
            }}
          >
            <p
              className="visual-card__finding"
              style={{
                margin: 0,
                fontSize: "0.80rem",
                fontWeight: 500,
                color: themeTokens?.colors?.textPrimary,
                lineHeight: 1.4,
                flex: "1 1 300px",
              }}
            >
              {activeTakeaway}
            </p>
            {isGeospatial && (
              <button
                type="button"
                onClick={() => setIsRankingDrawerOpen(true)}
                className="geo-view-ranking-btn"
                aria-haspopup="dialog"
                aria-expanded={isRankingDrawerOpen}
                style={{
                  display: "inline-flex",
                  alignItems: "center",
                  gap: "5px",
                  background: isDark ? "rgba(56, 189, 248, 0.1)" : "rgba(37, 99, 235, 0.06)",
                  border: `1px solid ${isDark ? "rgba(56, 189, 248, 0.25)" : "rgba(37, 99, 235, 0.18)"}`,
                  borderRadius: "6px",
                  padding: "5px 10px",
                  color: isDark ? "#38bdf8" : "#2563eb",
                  fontSize: "0.75rem",
                  fontWeight: 600,
                  cursor: "pointer",
                  whiteSpace: "nowrap",
                  transition: "all 0.15s ease",
                }}
              >
                View ranking →
              </button>
            )}
          </figcaption>
        </figure>
      </div>

      {/* Ranking Drawer for Detailed Tabular Exploration */}
      {isRankingDrawerOpen && (
        <div
          className="drawer-overlay"
          onClick={() => setIsRankingDrawerOpen(false)}
          role="presentation"
          style={{ zIndex: 1200 }}
        >
          <div
            className="drawer-panel"
            role="dialog"
            aria-modal="true"
            aria-labelledby={`geo-drawer-title-${topic.topic_id}`}
            style={{
              width: "min(100%, 720px)",
              backgroundColor: isDark ? "#0f172a" : "#ffffff",
              color: isDark ? "#f8fafc" : "#0f172a",
            }}
            onClick={(e) => e.stopPropagation()}
          >
            <div
              className="drawer-header"
              style={{
                padding: "16px 20px",
                borderBottom: `1px solid ${isDark ? "#334155" : "#e2e8f0"}`,
                display: "flex",
                justifyContent: "space-between",
                alignItems: "flex-start",
                backgroundColor: isDark ? "#1e293b" : "#f8fafc",
              }}
            >
              <div>
                <h2
                  id={`geo-drawer-title-${topic.topic_id}`}
                  style={{
                    margin: 0,
                    fontSize: "1.15rem",
                    fontWeight: 700,
                    color: isDark ? "#f8fafc" : "#0f172a",
                  }}
                >
                  {activeMetric?.label || "Territory"} Ranking
                </h2>
                <div
                  style={{
                    fontSize: "0.78rem",
                    color: isDark ? "#94a3b8" : "#64748b",
                    marginTop: "3px",
                  }}
                >
                  {geoTableRows.length} observed territories across {activeVisualSpec.geo_scope || "India"}
                </div>
              </div>
              <div style={{ display: "flex", alignItems: "center", gap: "8px" }}>
                {contextualTarget && (
                  <a
                    href={contextualTarget.url}
                    className="drawer-explorer-link"
                    style={{
                      display: "inline-flex",
                      alignItems: "center",
                      gap: "4px",
                      fontSize: "0.75rem",
                      fontWeight: 600,
                      color: isDark ? "#38bdf8" : "#2563eb",
                      textDecoration: "none",
                      padding: "4px 8px",
                      borderRadius: "4px",
                      border: `1px solid ${isDark ? "rgba(56, 189, 248, 0.3)" : "rgba(37, 99, 235, 0.2)"}`,
                    }}
                  >
                    <span>Explore in Data Explorer</span>
                    <span>→</span>
                  </a>
                )}
                <button
                  type="button"
                  onClick={() => setIsRankingDrawerOpen(false)}
                  aria-label="Close ranking drawer"
                  style={{
                    background: "none",
                    border: "none",
                    color: isDark ? "#94a3b8" : "#64748b",
                    fontSize: "1.2rem",
                    cursor: "pointer",
                    padding: "4px 8px",
                    borderRadius: "4px",
                    lineHeight: 1,
                  }}
                >
                  ✕
                </button>
              </div>
            </div>

            <div
              className="drawer-body"
              style={{
                padding: "20px",
                overflowY: "auto",
                flex: 1,
                display: "flex",
                flexDirection: "column",
                gap: "16px",
              }}
            >
              {availableMetrics.length > 1 && (
                <div
                  style={{
                    display: "flex",
                    alignItems: "center",
                    gap: "6px",
                    flexWrap: "wrap",
                  }}
                >
                  <span style={{ fontSize: "0.75rem", fontWeight: 600, color: isDark ? "#94a3b8" : "#64748b", marginRight: "4px" }}>
                    Metric:
                  </span>
                  {availableMetrics.map((m) => {
                    const isSelected = m.metric_id === (activeMetric?.metric_id || availableMetrics[0].metric_id);
                    return (
                      <button
                        key={`drawer-m-${m.metric_id}`}
                        type="button"
                        onClick={() => setSelectedMetricId(m.metric_id)}
                        style={{
                          padding: "3px 8px",
                          fontSize: "0.72rem",
                          fontWeight: isSelected ? 700 : 500,
                          borderRadius: "5px",
                          border: isSelected
                            ? `1px solid ${isDark ? "#38bdf8" : "#2563eb"}`
                            : `1px solid ${isDark ? "#334155" : "#e2e8f0"}`,
                          backgroundColor: isSelected
                            ? isDark
                              ? "rgba(56, 189, 248, 0.15)"
                              : "rgba(37, 99, 235, 0.08)"
                            : isDark
                            ? "#1e293b"
                            : "#f8fafc",
                          color: isSelected
                            ? isDark
                              ? "#38bdf8"
                              : "#1d4ed8"
                            : isDark
                            ? "#94a3b8"
                            : "#475569",
                          cursor: "pointer",
                        }}
                      >
                        {m.label}
                      </button>
                    );
                  })}
                </div>
              )}

              <DataTable
                columns={geoTableColumns}
                rows={geoTableRows}
                pageSize={10}
                pageSizeOptions={[10, 20, 36]}
                defaultSortCol="rank"
                defaultSortDir="asc"
                searchPlaceholder="Search territories..."
                emptyMessage="No territories match search."
                tableAriaLabel={`${activeMetric?.label || "Territory"} ranking table`}
              />
            </div>
          </div>
        </div>
      )}
    </article>
  );
}
