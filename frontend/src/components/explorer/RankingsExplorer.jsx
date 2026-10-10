import React from "react";
import GenericRankingExplorer from "../adaptive/GenericRankingExplorer";

export default function RankingsExplorer({
  datasetId,
  initialEntity = null,
  initialMeasure = null,
  initialMode = "TOP",
  themeTokens,
  isDark = false,
  onInspect,
}) {
  const rankingTopic = {
    title: "Entity Performance & Benchmarks",
    subtitle: "Complete interactive ranking with percentiles, scale expansion (5–500/Full), and baseline comparison.",
    analytical_intent: "RANKING",
    visual_spec: {
      chart_type: "ranked_bar",
      entity_column: initialEntity,
      measure_column: initialMeasure,
      is_ranking_story: true,
    },
    inspect_payload: {
      ranking_metadata: {
        entity_column: initialEntity,
        measure_column: initialMeasure,
      },
    },
  };

  return (
    <div
      className="rankings-explorer-panel"
      style={{
        display: "flex",
        flexDirection: "column",
        gap: "14px",
      }}
    >
      <div
        style={{
          padding: "16px 20px",
          borderRadius: "10px",
          backgroundColor: themeTokens?.colors?.surface,
          border: `1px solid ${themeTokens?.colors?.borderSubtle}`,
        }}
      >
        <div style={{ marginBottom: "12px" }}>
          <h2 style={{ margin: "0 0 4px 0", fontSize: "1.1rem", fontWeight: 700, color: themeTokens?.colors?.textPrimary }}>
            Entity Rankings & Benchmark Intelligence
          </h2>
          <p style={{ margin: 0, fontSize: "0.80rem", color: themeTokens?.colors?.textSecondary }}>
            Server-side group-by aggregation across entities. Toggle Top/Bottom/Both, expand from 5 to 500/Full, and search the complete population without UI clutter.
          </p>
        </div>

        <GenericRankingExplorer
          topic={rankingTopic}
          datasetId={datasetId}
          themeTokens={themeTokens}
          isDark={isDark}
          onInspect={onInspect}
        />
      </div>
    </div>
  );
}
