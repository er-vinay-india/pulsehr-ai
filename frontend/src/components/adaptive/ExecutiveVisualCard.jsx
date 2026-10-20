import React, { useMemo } from "react";
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
    if (isGeospatial) return "380px";
    if (isHero) return "320px";
    if (heightClass === "tall") return "320px";
    if (heightClass === "short") return "190px";
    return "230px";
  }, [heightClass, isHero, isGeospatial]);

  const geoTableColumns = useMemo(() => {
    const hasDensity = compactVisualSpec?.table_data?.some((r) => r.density != null);
    const hasGrowth = compactVisualSpec?.table_data?.some((r) => r.growth != null);
    const hasPop = compactVisualSpec?.table_data?.some((r) => r.population != null);
    const primaryLabel = compactVisualSpec?.measure_label || compactVisualSpec?.primary_measure || compactVisualSpec?.primary_label || "Metric Value";

    const cols = [
      { key: "rank", label: "Rank", sortable: true, align: "center", width: "65px" },
      { key: "location", label: compactVisualSpec?.geo_dimension || "Territory", sortable: true, filterable: true },
      { key: "value", label: primaryLabel, sortable: true, align: "right" },
    ];

    if (hasGrowth) {
      cols.push({ key: "growth", label: "Growth (2001-2011)", sortable: true, align: "right", width: "140px" });
    }
    if (hasPop) {
      cols.push({ key: "population", label: "Population 2011", sortable: true, align: "right", width: "140px" });
    }

    cols.push({
      key: "lineage",
      label: "Lineage",
      sortable: true,
      align: "center",
      width: "100px",
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
  }, [compactVisualSpec, isDark]);

  const geoTableRows = useMemo(() => {
    if (!compactVisualSpec || !isGeospatial) return [];
    if (compactVisualSpec.table_data && compactVisualSpec.table_data.length > 0) {
      return compactVisualSpec.table_data.map((r, i) => ({
        id: `geo-row-${i}`,
        rank: r.rank != null ? r.rank : i + 1,
        location: r.location || "-",
        value: r.formatted_value || `${r.value ?? "-"}`,
        raw_value: r.value != null ? r.value : 0,
        growth: r.growth || "-",
        population: r.population || "-",
        density: r.density || "-",
        lineage: r.lineage || compactVisualSpec.geo_source || "OBSERVED",
      }));
    }
    const cats = compactVisualSpec.categories || [];
    const vals = compactVisualSpec.values || [];
    const unit = compactVisualSpec.unit || "";
    return cats.map((cat, idx) => ({
      id: `geo-row-${idx}`,
      rank: idx + 1,
      location: cat,
      value: vals[idx] != null ? `${vals[idx]} ${unit}`.trim() : "-",
      raw_value: vals[idx] != null ? vals[idx] : 0,
      growth: "-",
      population: "-",
      density: "-",
      lineage: compactVisualSpec.geo_source || "OBSERVED",
    }));
  }, [compactVisualSpec, isGeospatial]);

  const accessibleChartDescription = topic.primary_takeaway || topic.takeaway || topic.title || "Visual analytics chart.";

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
        {(microcopy.primary_number || microcopy.short_context) && (
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
            {microcopy.primary_number && (
              <span
                className="visual-card__metric card-primary-number"
                style={{
                  fontWeight: 800,
                  fontSize: isHero ? "1.05rem" : "0.88rem",
                  color: intentColor,
                }}
              >
                {microcopy.primary_number}
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
            {accessibleChartDescription}
          </p>
          <VisualSpecRenderer
            visualSpec={compactVisualSpec}
            themeTokens={themeTokens}
            isDark={isDark}
            height={isGeospatial ? "380px" : chartHeight}
          />
          {/* Map + Ranked Geographic DataTable */}
          {isGeospatial && geoTableRows.length > 0 && (
            <div style={{ marginTop: "14px", width: "100%" }}>
              <div
                style={{
                  display: "flex",
                  alignItems: "center",
                  justifyContent: "space-between",
                  marginBottom: "8px",
                  padding: "0 2px",
                }}
              >
                <span
                  style={{
                    fontSize: "0.74rem",
                    fontWeight: 700,
                    color: themeTokens?.colors?.textSecondary,
                    textTransform: "uppercase",
                    letterSpacing: "0.04em",
                  }}
                >
                  Ranked Geographic DataTable ({geoTableRows.length} territories)
                </span>
                <span style={{ fontSize: "0.72rem", color: themeTokens?.colors?.textMuted }}>
                  Lineage: <strong>{compactVisualSpec.geo_source || "OBSERVED"}</strong>
                </span>
              </div>
              <DataTable
                columns={geoTableColumns}
                rows={geoTableRows}
                pageSize={6}
                pageSizeOptions={[6, 12, 25]}
                defaultSortCol="rank"
                defaultSortDir="asc"
                searchPlaceholder="Search locations..."
                emptyMessage="No geographic records match."
                tableAriaLabel={`${displayTitle} ranked geographic comparison table`}
              />
            </div>
          )}
          {/* 3. FIGCAPTION ("What can I do next?"): Compressed finding + Deep dive link */}
          <figcaption
            className="visual-card__figcaption card-short-insight"
            style={{
              paddingTop: "8px",
              marginTop: "4px",
              borderTop: `1px solid ${themeTokens?.colors?.borderSubtle || "var(--color-border)"}`,
            }}
          >
            <p
              className="visual-card__finding"
              style={{
                margin: 0,
                fontSize: "0.78rem",
                fontWeight: 500,
                color: themeTokens?.colors?.textPrimary,
                lineHeight: 1.35,
              }}
            >
              {microcopy.short_finding}
            </p>
          </figcaption>
        </figure>
      </div>
    </article>
  );
}
