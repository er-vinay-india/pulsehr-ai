import React, { useMemo } from "react";
import { ArrowRight } from "lucide-react";
import VisualSpecRenderer from "./VisualSpecRenderer";
import SemanticIcon from "./SemanticIcon";
import { getContextualExplorerTarget } from "../../utils/explorerNavigation";

export default function ExecutiveVisualStory({
  topic,
  isHero = false,
  datasetId = null,
  themeTokens,
  isDark = false,
  onInspect,
}) {
  if (!topic) return null;

  const intentColor = {
    RANKING: themeTokens?.colors?.brandBlue || "#2563eb",
    TREND: themeTokens?.colors?.gold || "#d97706",
    COMPOSITION: themeTokens?.colors?.statusSuccess || "#10b981",
    RELATIONSHIP: "#8b5cf6",
    ANOMALY: themeTokens?.colors?.statusError || "#ef4444",
    DISTRIBUTION: "#06b6d4",
    TARGET_VS_ACTUAL: themeTokens?.colors?.statusSuccess || "#10b981",
    COMPARISON: themeTokens?.colors?.brandBlue || "#2563eb",
    PART_TO_WHOLE: "#8b5cf6",
    GAP_EXPLANATION: themeTokens?.colors?.gold || "#d97706",
    MATRIX: "#6366f1",
  }[topic.analytical_intent] || (themeTokens?.colors?.brandBlue || "#2563eb");

  const intentBg = isDark
    ? "rgba(255, 255, 255, 0.06)"
    : "rgba(0, 0, 0, 0.04)";

  const isRankingStory = topic.analytical_intent === "RANKING" || topic.visual_spec?.is_ranking_story;

  // Contextual Data Explorer Target (Rankings, Trends, Relationships, Distributions, Evidence)
  const contextualTarget = useMemo(() => getContextualExplorerTarget(topic, datasetId), [topic, datasetId]);

  // Executive Dashboard Ranking Constraint: Exactly Top 3 + Bottom 3 only (never more than 6 unique entities)
  const compactVisualSpec = useMemo(() => {
    if (!topic.visual_spec) return null;
    if (topic.visual_spec.chart_type === "podium_top_3") return topic.visual_spec;
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

  // Layout hint class for grid density
  const layoutHint = (topic.layout_hint || topic.visual_spec?.layout_hint || (isHero ? "HERO" : "MEDIUM")).toLowerCase();
  const layoutClass = `layout-hint-${layoutHint}`;

  return (
    <article
      className={`executive-insight-card ${isHero ? "hero-card" : "supporting-card"} ${layoutClass}`}
      data-testid={isHero ? "hero-card" : `supporting-card-${topic.topic_id}`}
      style={{
        backgroundColor: themeTokens?.colors?.surface,
        border: `1px solid ${isHero ? (themeTokens?.colors?.brandBlue || "#2563eb") : themeTokens?.colors?.borderSubtle}`,
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
        {/* Compressed Header: Semantic Icon + Short Title (<= 7 words) + Inspect CTA */}
        <div className="card-header-compressed" style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: "4px" }}>
          <div className="card-title-group" style={{ display: "flex", alignItems: "center", gap: "8px", minWidth: 0 }}>
            <span
              className="semantic-icon-wrapper"
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
            <h3
              className="card-compressed-title"
              title={topic.title}
              style={{
                margin: 0,
                fontSize: isHero ? "1.15rem" : "0.95rem",
                fontWeight: 700,
                color: themeTokens?.colors?.textPrimary,
                lineHeight: 1.25,
                whiteSpace: "nowrap",
                overflow: "hidden",
                textOverflow: "ellipsis",
              }}
            >
              {microcopy.short_title}
            </h3>
          </div>

          <div className="card-actions-group" style={{ display: "flex", alignItems: "center", gap: "6px", flexShrink: 0 }}>
            {contextualTarget && (
              <a
                href={contextualTarget.url}
                onClick={(e) => {
                  e.preventDefault();
                  window.location.href = contextualTarget.url;
                }}
                style={{
                  textDecoration: "none",
                  border: `1px solid ${themeTokens?.colors?.brandBlue || "#2563eb"}`,
                  borderRadius: "6px",
                  color: themeTokens?.colors?.brandBlue || "#2563eb",
                  fontSize: "0.70rem",
                  fontWeight: 600,
                  padding: "2px 7px",
                  display: "inline-flex",
                  alignItems: "center",
                  gap: "3px",
                  backgroundColor: isDark ? "rgba(37, 99, 235, 0.12)" : "rgba(37, 99, 235, 0.06)",
                  cursor: "pointer",
                }}
                aria-label={`${contextualTarget.label} in Data Explorer`}
              >
                <span>{contextualTarget.label}</span>
                <ArrowRight size={10} />
              </a>
            )}

            {onInspect && (
              <button
                type="button"
                className="card-btn-inspect"
                onClick={() => onInspect(topic)}
                style={{
                  background: "transparent",
                  border: `1px solid ${themeTokens?.colors?.borderSubtle || "rgba(0, 0, 0, 0.12)"}`,
                  borderRadius: "6px",
                  color: themeTokens?.colors?.textSecondary || "#64748b",
                  fontSize: "0.70rem",
                  fontWeight: 600,
                  padding: "2px 8px",
                  cursor: "pointer",
                  display: "inline-flex",
                  alignItems: "center",
                  gap: "3px",
                }}
                aria-label={`Inspect ${topic.title}`}
              >
                <span>{microcopy.cta || "Inspect →"}</span>
              </button>
            )}
          </div>
        </div>

        {/* Sub-strip: Primary metric number + Short context sentence (<= 8 words) */}
        {(microcopy.primary_number || microcopy.short_context) && (
          <div
            className="card-metric-context"
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
                className="card-primary-number"
                style={{
                  fontWeight: 800,
                  fontSize: "0.88rem",
                  color: intentColor,
                }}
              >
                {microcopy.primary_number}
              </span>
            )}
            {microcopy.short_context && (
              <span
                className="card-short-context"
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

        {/* Visual Spec Chart View */}
        <div style={{ marginTop: "4px", width: "100%" }}>
          <VisualSpecRenderer
            visualSpec={compactVisualSpec}
            themeTokens={themeTokens}
            isDark={isDark}
            height={isHero ? "290px" : "220px"}
          />
        </div>
      </div>

      {/* Compressed Footer: Single short insight sentence (<= 12 words) without permanent action block */}
      <div
        className="card-short-insight"
        style={{
          display: "flex",
          justifyContent: "space-between",
          alignItems: "center",
          gap: "8px",
          paddingTop: "8px",
          marginTop: "4px",
          borderTop: `1px solid ${themeTokens?.colors?.borderSubtle || "#e2e8f0"}`,
        }}
      >
        <p
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
        {contextualTarget && (
          <a
            href={contextualTarget.url}
            onClick={(e) => {
              e.preventDefault();
              window.location.href = contextualTarget.url;
            }}
            style={{
              fontSize: "0.72rem",
              color: themeTokens?.colors?.brandBlue || "#2563eb",
              textDecoration: "none",
              fontWeight: 600,
              whiteSpace: "nowrap",
              flexShrink: 0,
            }}
          >
            Deep Dive →
          </a>
        )}
      </div>
    </article>
  );
}
