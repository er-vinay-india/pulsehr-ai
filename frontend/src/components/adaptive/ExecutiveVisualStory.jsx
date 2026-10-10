import React, { useState, useMemo } from "react";
import { Sparkles, ArrowRight, ExternalLink, ShieldCheck, TrendingUp, BarChart3, AlertCircle, SlidersHorizontal, HelpCircle } from "lucide-react";
import VisualSpecRenderer from "./VisualSpecRenderer";
import GenericRankingExplorer from "./GenericRankingExplorer";
import { getContextualExplorerTarget } from "../../utils/explorerNavigation";

function sanitizeTemplateText(text, fallback = "") {
  if (!text || typeof text !== "string") return fallback;
  const tokenRegex = /\{[a-zA-Z0-9_]+\}/g;
  if (tokenRegex.test(text)) {
    return text.replace(tokenRegex, "").replace(/\s{2,}/g, " ").trim() || fallback;
  }
  return text;
}

export default function ExecutiveVisualStory({
  topic,
  isHero = false,
  datasetId = null,
  themeTokens,
  isDark = false,
  onInspect,
}) {
  if (!topic) return null;

  const [explorerOpen, setExplorerOpen] = useState(false);

  const intentColor = {
    RANKING: themeTokens?.colors?.brandBlue || "#2563eb",
    TREND: themeTokens?.colors?.gold || "#d97706",
    COMPOSITION: themeTokens?.colors?.statusSuccess || "#10b981",
    RELATIONSHIP: "#8b5cf6",
    ANOMALY: themeTokens?.colors?.statusError || "#ef4444",
  }[topic.analytical_intent] || (themeTokens?.colors?.brandBlue || "#2563eb");

  const isRankingStory = topic.analytical_intent === "RANKING" || topic.visual_spec?.is_ranking_story;

  // Contextual Data Explorer Target (Rankings, Trends, Relationships, Distributions, Evidence)
  const contextualTarget = useMemo(() => getContextualExplorerTarget(topic, datasetId), [topic, datasetId]);

  // Executive Dashboard Ranking Constraint: Exactly Top 3 + Bottom 3 only (never more than 6 unique entities)
  const compactVisualSpec = useMemo(() => {
    if (!topic.visual_spec) return null;
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

    // Single category list:
    // If population <= 6 unique entities, show all as clean ranked_bar without duplicating
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

    // Population > 6: Take Top 3 + Bottom 3 unique entities
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

  return (
    <article
      className={`executive-insight-card ${isHero ? "hero-card" : "supporting-card"}`}
      data-testid={isHero ? "hero-card" : `supporting-card-${topic.topic_id}`}
      style={{
        backgroundColor: themeTokens?.colors?.surface,
        border: `1px solid ${isHero ? (themeTokens?.colors?.brandBlue || "#2563eb") : themeTokens?.colors?.borderSubtle}`,
        borderRadius: "12px",
        padding: isHero ? "20px 24px" : "18px 20px",
        display: "flex",
        flexDirection: "column",
        justifyContent: "space-between",
        gap: "12px",
        boxShadow: isHero ? "0 4px 20px -2px rgba(37, 99, 235, 0.08)" : "none",
      }}
    >
      <div>
        {/* Header Badges */}
        <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: "4px" }}>
          <div style={{ display: "flex", alignItems: "center", gap: "8px" }}>
            <span
              style={{
                padding: "2px 8px",
                borderRadius: "6px",
                fontSize: "0.70rem",
                fontWeight: 700,
                textTransform: "uppercase",
                backgroundColor: isHero ? "rgba(37, 99, 235, 0.12)" : "var(--color-bg-subtle, rgba(0, 0, 0, 0.04))",
                color: intentColor,
                display: "inline-flex",
                alignItems: "center",
                gap: "4px",
              }}
            >
              {isHero ? <Sparkles size={11} /> : <BarChart3 size={11} />}
              {topic.analytical_intent || "ANALYSIS"}
            </span>
            {topic.key_metric && (
              <span
                style={{
                  fontSize: "0.72rem",
                  fontWeight: 600,
                  color: themeTokens?.colors?.textPrimary,
                  backgroundColor: isDark ? "rgba(255, 255, 255, 0.06)" : "rgba(0, 0, 0, 0.05)",
                  padding: "2px 7px",
                  borderRadius: "4px",
                }}
              >
                {topic.key_metric}
              </span>
            )}
          </div>

          <div style={{ display: "flex", alignItems: "center", gap: "8px" }}>
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
                  fontSize: "0.72rem",
                  fontWeight: 600,
                  padding: "3px 9px",
                  display: "inline-flex",
                  alignItems: "center",
                  gap: "4px",
                  backgroundColor: isDark ? "rgba(37, 99, 235, 0.12)" : "rgba(37, 99, 235, 0.06)",
                  cursor: "pointer",
                }}
                aria-label={`${contextualTarget.label} in Data Explorer`}
              >
                <span>{contextualTarget.label}</span>
                <ArrowRight size={12} />
              </a>
            )}

            {onInspect && (
              <button
                type="button"
                className="btn-inspect-subtle"
                onClick={() => onInspect(topic)}
                style={{
                  background: "transparent",
                  border: `1px solid ${themeTokens?.colors?.borderSubtle || "rgba(0, 0, 0, 0.12)"}`,
                  borderRadius: "6px",
                  color: themeTokens?.colors?.textSecondary || "#64748b",
                  fontSize: "0.72rem",
                  fontWeight: 500,
                  padding: "3px 8px",
                  cursor: "pointer",
                  display: "inline-flex",
                  alignItems: "center",
                  gap: "4px",
                }}
                aria-label={`Why this matters: ${topic.title}`}
              >
                <HelpCircle size={12} />
                <span>Why this matters</span>
              </button>
            )}
          </div>
        </div>

        {/* Title & Subtitle */}
        <h3
          style={{
            margin: "4px 0 2px 0",
            fontSize: isHero ? "1.22rem" : "1.02rem",
            fontWeight: 700,
            color: themeTokens?.colors?.textPrimary,
            lineHeight: 1.3,
          }}
        >
          {topic.title}
        </h3>
        {topic.subtitle && (
          <p style={{ margin: "0 0 8px 0", fontSize: "0.78rem", color: themeTokens?.colors?.textSecondary }}>
            {topic.subtitle}
          </p>
        )}

        {/* Visual Chart */}
        <div style={{ marginTop: "6px", width: "100%" }}>
          <VisualSpecRenderer
            visualSpec={compactVisualSpec}
            themeTokens={themeTokens}
            isDark={isDark}
            height={isHero ? "290px" : "230px"}
          />
        </div>
      </div>

      {/* Takeaway & Action Footer */}
      <div
        style={{
          display: "grid",
          gridTemplateColumns: isHero ? "repeat(auto-fit, minmax(260px, 1fr))" : "1fr",
          gap: "10px",
          paddingTop: "10px",
          borderTop: `1px solid ${themeTokens?.colors?.borderSubtle || "#e2e8f0"}`,
        }}
      >
        <div>
          <span
            style={{
              fontSize: "0.68rem",
              fontWeight: 700,
              textTransform: "uppercase",
              color: intentColor,
            }}
          >
            Key Finding
          </span>
          <p
            style={{
              margin: "2px 0 0 0",
              fontSize: isHero ? "0.88rem" : "0.82rem",
              fontWeight: 600,
              color: themeTokens?.colors?.textPrimary,
              lineHeight: 1.38,
            }}
          >
            {sanitizeTemplateText(topic.primary_takeaway || topic.takeaway, "Analyzed metric distributions across reporting population.")}
          </p>
        </div>

        {topic.recommended_action && (
          <div
            style={{
              backgroundColor: isDark ? "rgba(255, 255, 255, 0.03)" : "rgba(0, 0, 0, 0.02)",
              border: `1px solid ${themeTokens?.colors?.borderSubtle}`,
              borderRadius: "6px",
              padding: "6px 10px",
            }}
          >
            <div style={{ display: "flex", alignItems: "center", gap: "4px", marginBottom: "2px" }}>
              <ArrowRight size={11} color={intentColor} />
              <span
                style={{
                  fontSize: "0.68rem",
                  fontWeight: 700,
                  textTransform: "uppercase",
                  color: themeTokens?.colors?.textSecondary,
                }}
              >
                Recommended Action
              </span>
            </div>
            <p style={{ margin: 0, fontSize: "0.78rem", color: themeTokens?.colors?.textSecondary, lineHeight: 1.3 }}>
              {sanitizeTemplateText(topic.recommended_action)}
            </p>
          </div>
        )}
      </div>
    </article>
  );
}
