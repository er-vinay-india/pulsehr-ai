import React, { useState, useEffect, useMemo, useCallback } from "react";
import {
  ArrowUpDown,
  Filter,
  BarChart2,
  Table as TableIcon,
  ChevronDown,
  Layers,
  Sparkles,
  Award,
  AlertCircle,
  TrendingDown,
  TrendingUp,
  Search,
} from "lucide-react";
import VisualSpecRenderer from "./VisualSpecRenderer";

/**
 * Generic Top/Bottom Ranking Explorer Component.
 *
 * Driven entirely by ingestion metadata & ranking intelligence contracts:
 * - Domain-independent (supports Department, Store, Product, Student, Employee, Customer, etc.)
 * - Semantic desirability direction: TOP != highest numeric value.
 * - Progressive scale presentation:
 *     5 / 15: Visual-first (ranked bar, bullet bar, lollipop, diverging bar)
 *     25 / 50: Scrollable ranked visual
 *     100 / 500 / Full: Statistical distribution / percentile summary + virtualized/searchable table
 * - Dynamic controls:
 *     [ Top ] [ Bottom ] [ Both ]
 *     Show: [ 5 | 15 | 25 | 50 | 100 | 500 | Full ]
 *     Entity selector (when multiple exist)
 *     Measure selector (when multiple exist)
 */
export default function GenericRankingExplorer({
  topic,
  datasetId,
  themeTokens,
  isDark = false,
  onInspect,
}) {
  const vSpec = topic?.visual_spec || {};
  const rankingMeta = topic?.inspect_payload?.ranking_metadata || {};

  // Available rank limits
  const SUPPORTED_LIMITS = [5, 15, 25, 50, 100, 500, "Full"];

  // Entity & Measure state
  const [selectedEntity, setSelectedEntity] = useState(
    rankingMeta.entity_column || vSpec.entity_column || "Department"
  );
  const [selectedMeasure, setSelectedMeasure] = useState(
    rankingMeta.measure_column || vSpec.measure_column || "Final Attendance"
  );
  const [mode, setMode] = useState("TOP"); // "TOP", "BOTTOM", "BOTH"
  const [limit, setLimit] = useState(5);
  const [searchFilter, setSearchFilter] = useState("");

  // Data state
  const [rankingData, setRankingData] = useState(null);
  const [loading, setLoading] = useState(false);
  const [availableSchema, setAvailableSchema] = useState(null);

  // Sync entity and measure if props change (e.g. from deep link navigation)
  useEffect(() => {
    const ent = rankingMeta.entity_column || vSpec.entity_column;
    if (ent) setSelectedEntity(ent);
    const meas = rankingMeta.measure_column || vSpec.measure_column;
    if (meas) setSelectedMeasure(meas);
  }, [vSpec.entity_column, vSpec.measure_column, rankingMeta.entity_column, rankingMeta.measure_column]);

  // 1. Fetch Ranking Schema on mount if datasetId is provided
  useEffect(() => {
    if (!datasetId) return;
    fetch(`/api/adaptive-dashboard/ranking/schema/${datasetId}`)
      .then((r) => (r.ok ? r.json() : null))
      .then((res) => {
        if (res) {
          setAvailableSchema(res);
          if (res.entities && res.entities.length > 0 && !rankingMeta.entity_column) {
            setSelectedEntity(res.entities[0].column);
          }
          if (res.measures && res.measures.length > 0 && !rankingMeta.measure_column) {
            setSelectedMeasure(res.measures[0].column);
          }
        }
      })
      .catch(() => {});
  }, [datasetId]);

  // 2. Fetch Ranking Data when entity, measure, mode, or limit changes
  const fetchRanking = useCallback(() => {
    if (!datasetId || !selectedEntity || !selectedMeasure) return;

    setLoading(true);
    fetch("/api/adaptive-dashboard/ranking", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        dataset_id: Number(datasetId),
        entity_column: selectedEntity,
        measure_column: selectedMeasure,
        direction: mode,
        limit: limit === "Full" ? "FULL" : limit,
      }),
    })
      .then((r) => (r.ok ? r.json() : null))
      .then((data) => {
        if (data) {
          setRankingData(data);
        }
      })
      .catch((err) => {
        console.error("Failed to query entity ranking:", err);
      })
      .finally(() => setLoading(false));
  }, [datasetId, selectedEntity, selectedMeasure, mode, limit]);

  useEffect(() => {
    fetchRanking();
  }, [fetchRanking]);

  // Determine Semantic Direction Labels:
  // If HIGHER_IS_BETTER: Top = Best, Bottom = Lowest
  // If LOWER_IS_BETTER:  Top = Lowest (Best, e.g. Defect), Bottom = Highest (Worst)
  // If NEUTRAL:          Highest / Lowest
  const rankingDir = rankingData?.ranking_direction || rankingMeta.ranking_direction || "HIGHER_IS_BETTER";
  const isNeutral = rankingDir === "NEUTRAL";
  const topLabel = isNeutral ? "Highest" : "Top";
  const bottomLabel = isNeutral ? "Lowest" : "Bottom";

  const rows = rankingData?.ranked_rows || [];
  const bottomRows = rankingData?.bottom_rows || [];
  const populationCount = rankingData?.population_count || vSpec.categories?.length || 0;
  const benchmark = rankingData?.benchmark ?? vSpec.benchmark;
  const unit = rankingData?.unit || vSpec.unit || "";

  // Filtered rows for 100+ table search
  const filteredRows = useMemo(() => {
    if (!searchFilter.trim()) return rows;
    const q = searchFilter.toLowerCase();
    return rows.filter((r) => String(r.entity).toLowerCase().includes(q));
  }, [rows, searchFilter]);

  // Determine Visual Archetype from Limit & Cardinality
  // 5 / 15 -> Normal Chart
  // 25 / 50 -> Scrollable Chart
  // 100 / 500 / Full -> Summary + Virtualized Table
  const isTableView = limit === 100 || limit === 500 || limit === "Full" || rows.length > 50;

  // Synthesize Visual Spec for 5–50 mode
  const dynamicVisualSpec = useMemo(() => {
    if (isTableView || rows.length === 0) return null;

    let chartType = vSpec.chart_type || "ranked_bar";
    if (mode === "BOTH" && bottomRows.length > 0) {
      chartType = "diverging_bar";
    } else if (limit === 25 || limit === 50) {
      chartType = "ranked_dot_plot";
    }

    return {
      chart_type: chartType,
      categories: rows.map((r) => r.entity),
      values: rows.map((r) => r.value),
      bottom_categories: bottomRows.map((r) => r.entity),
      bottom_values: bottomRows.map((r) => r.value),
      unit: unit,
      benchmark: benchmark,
      analytical_intent: "RANKING",
    };
  }, [isTableView, rows, bottomRows, mode, limit, unit, benchmark, vSpec.chart_type]);

  const availableEntities = availableSchema?.entities || [];
  const availableMeasures = availableSchema?.measures || [];

  return (
    <div
      className="generic-ranking-explorer"
      style={{
        display: "flex",
        flexDirection: "column",
        gap: "10px",
        width: "100%",
      }}
    >
      {/* 1. TOP INTERACTIVE TOOLBAR */}
      <div
        style={{
          display: "flex",
          flexWrap: "wrap",
          alignItems: "center",
          justifyContent: "space-between",
          gap: "8px",
          paddingBottom: "8px",
          borderBottom: `1px solid ${themeTokens?.colors?.borderSubtle || "#e2e8f0"}`,
        }}
      >
        {/* Left: Direction Segment Controls [ Top | Bottom | Both ] */}
        <div style={{ display: "inline-flex", borderRadius: "6px", overflow: "hidden", border: `1px solid ${themeTokens?.colors?.borderSubtle}` }}>
          <button
            type="button"
            onClick={() => setMode("TOP")}
            style={{
              padding: "4px 10px",
              fontSize: "0.74rem",
              fontWeight: 700,
              border: "none",
              cursor: "pointer",
              backgroundColor: mode === "TOP" ? (themeTokens?.colors?.brandBlue || "#2563eb") : "transparent",
              color: mode === "TOP" ? "#ffffff" : themeTokens?.colors?.textSecondary,
              transition: "all 0.15s ease",
            }}
          >
            {topLabel}
          </button>
          <button
            type="button"
            onClick={() => setMode("BOTTOM")}
            style={{
              padding: "4px 10px",
              fontSize: "0.74rem",
              fontWeight: 700,
              border: "none",
              cursor: "pointer",
              backgroundColor: mode === "BOTTOM" ? (themeTokens?.colors?.brandBlue || "#2563eb") : "transparent",
              color: mode === "BOTTOM" ? "#ffffff" : themeTokens?.colors?.textSecondary,
              borderLeft: `1px solid ${themeTokens?.colors?.borderSubtle}`,
              transition: "all 0.15s ease",
            }}
          >
            {bottomLabel}
          </button>
          <button
            type="button"
            onClick={() => setMode("BOTH")}
            style={{
              padding: "4px 10px",
              fontSize: "0.74rem",
              fontWeight: 700,
              border: "none",
              cursor: "pointer",
              backgroundColor: mode === "BOTH" ? (themeTokens?.colors?.brandBlue || "#2563eb") : "transparent",
              color: mode === "BOTH" ? "#ffffff" : themeTokens?.colors?.textSecondary,
              borderLeft: `1px solid ${themeTokens?.colors?.borderSubtle}`,
              transition: "all 0.15s ease",
            }}
          >
            Both
          </button>
        </div>

        {/* Middle: Scale Selector [ 5 | 15 | 25 | 50 | 100 | 500 | Full ] */}
        <div style={{ display: "flex", alignItems: "center", gap: "4px" }}>
          <span style={{ fontSize: "0.72rem", color: themeTokens?.colors?.textMuted, fontWeight: 600 }}>Show:</span>
          <div style={{ display: "inline-flex", gap: "2px" }}>
            {SUPPORTED_LIMITS.map((lim) => (
              <button
                key={lim}
                type="button"
                onClick={() => setLimit(lim)}
                style={{
                  padding: "2px 6px",
                  fontSize: "0.70rem",
                  fontWeight: limit === lim ? 700 : 500,
                  borderRadius: "4px",
                  border: `1px solid ${limit === lim ? (themeTokens?.colors?.brandBlue || "#2563eb") : "transparent"}`,
                  backgroundColor: limit === lim ? "rgba(37, 99, 235, 0.1)" : "transparent",
                  color: limit === lim ? (themeTokens?.colors?.brandBlue || "#2563eb") : themeTokens?.colors?.textSecondary,
                  cursor: "pointer",
                }}
              >
                {lim}
              </button>
            ))}
          </div>
        </div>

        {/* Right: Dynamic Entity & Measure Selectors */}
        <div style={{ display: "flex", alignItems: "center", gap: "8px" }}>
          {availableEntities.length > 1 && (
            <div style={{ display: "flex", alignItems: "center", gap: "4px" }}>
              <span style={{ fontSize: "0.70rem", color: themeTokens?.colors?.textMuted }}>Entity:</span>
              <select
                value={selectedEntity}
                onChange={(e) => setSelectedEntity(e.target.value)}
                style={{
                  fontSize: "0.72rem",
                  padding: "2px 4px",
                  borderRadius: "4px",
                  backgroundColor: themeTokens?.colors?.surface,
                  color: themeTokens?.colors?.textPrimary,
                  border: `1px solid ${themeTokens?.colors?.borderSubtle}`,
                }}
              >
                {availableEntities.map((ent) => (
                  <option key={ent.column} value={ent.column}>
                    {ent.display_name}
                  </option>
                ))}
              </select>
            </div>
          )}

          {availableMeasures.length > 1 && (
            <div style={{ display: "flex", alignItems: "center", gap: "4px" }}>
              <span style={{ fontSize: "0.70rem", color: themeTokens?.colors?.textMuted }}>Measure:</span>
              <select
                value={selectedMeasure}
                onChange={(e) => setSelectedMeasure(e.target.value)}
                style={{
                  fontSize: "0.72rem",
                  padding: "2px 4px",
                  borderRadius: "4px",
                  backgroundColor: themeTokens?.colors?.surface,
                  color: themeTokens?.colors?.textPrimary,
                  border: `1px solid ${themeTokens?.colors?.borderSubtle}`,
                }}
              >
                {availableMeasures.map((m) => (
                  <option key={m.column} value={m.column}>
                    {m.measure_label}
                  </option>
                ))}
              </select>
            </div>
          )}
        </div>
      </div>

      {/* 2. POPULATION BOUNDARY & DESIRABILITY BANNER */}
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", fontSize: "0.72rem", color: themeTokens?.colors?.textMuted }}>
        <span>
          {rankingData?.is_full_coverage
            ? `Showing all ${populationCount} ${rankingData?.entity_type || "entities"}`
            : `Showing ${rows.length} of ${populationCount} ${rankingData?.entity_type || "entities"}`}
        </span>
        {benchmark != null && (
          <span>
            Baseline Mean: <strong>{benchmark} {unit}</strong>
          </span>
        )}
      </div>

      {/* 3. PRESENTATION LAYER (Intelligently switches by scale) */}
      {loading ? (
        <div style={{ height: "220px", display: "flex", alignItems: "center", justifyContent: "center", color: themeTokens?.colors?.textMuted, fontSize: "0.80rem" }}>
          Aggregating entity rankings...
        </div>
      ) : isTableView ? (
        /* Large Population Presentation: Distribution Strip + Virtualized/Searchable Table */
        <div style={{ display: "flex", flexDirection: "column", gap: "8px", maxHeight: "280px" }}>
          {/* Distribution KPI Summary Pill */}
          {rankingData?.distribution_summary && (
            <div
              style={{
                display: "flex",
                justifyContent: "space-between",
                padding: "6px 12px",
                borderRadius: "6px",
                backgroundColor: isDark ? "rgba(255, 255, 255, 0.03)" : "rgba(0, 0, 0, 0.02)",
                border: `1px solid ${themeTokens?.colors?.borderSubtle}`,
                fontSize: "0.70rem",
              }}
            >
              <span>Min: <strong>{rankingData.distribution_summary.min}</strong></span>
              <span>P25: <strong>{rankingData.distribution_summary.p25}</strong></span>
              <span>Median: <strong>{rankingData.distribution_summary.median}</strong></span>
              <span>P75: <strong>{rankingData.distribution_summary.p75}</strong></span>
              <span>Max: <strong>{rankingData.distribution_summary.max}</strong></span>
            </div>
          )}

          {/* Table Search Filter */}
          <div style={{ display: "flex", alignItems: "center", gap: "6px" }}>
            <Search size={12} color={themeTokens?.colors?.textMuted} />
            <input
              type="text"
              placeholder={`Filter ${populationCount} entities...`}
              value={searchFilter}
              onChange={(e) => setSearchFilter(e.target.value)}
              style={{
                width: "100%",
                padding: "4px 8px",
                fontSize: "0.74rem",
                borderRadius: "4px",
                backgroundColor: "transparent",
                border: `1px solid ${themeTokens?.colors?.borderSubtle}`,
                color: themeTokens?.colors?.textPrimary,
              }}
            />
          </div>

          {/* Virtualized / Scrollable Ranked Table */}
          <div style={{ overflowY: "auto", maxHeight: "200px", border: `1px solid ${themeTokens?.colors?.borderSubtle}`, borderRadius: "6px" }}>
            <table style={{ width: "100%", borderCollapse: "collapse", fontSize: "0.74rem", textAlign: "left" }}>
              <thead>
                <tr style={{ backgroundColor: isDark ? "rgba(255, 255, 255, 0.05)" : "rgba(0, 0, 0, 0.03)", borderBottom: `1px solid ${themeTokens?.colors?.borderSubtle}` }}>
                  <th style={{ padding: "6px 8px", width: "45px" }}>Rank</th>
                  <th style={{ padding: "6px 8px" }}>Entity</th>
                  <th style={{ padding: "6px 8px", textAlign: "right" }}>Value</th>
                  <th style={{ padding: "6px 8px", textAlign: "right" }}>Percentile</th>
                  <th style={{ padding: "6px 8px", textAlign: "right" }}>Delta</th>
                </tr>
              </thead>
              <tbody>
                {filteredRows.map((r) => (
                  <tr key={r.rank + r.entity} style={{ borderBottom: `1px solid ${themeTokens?.colors?.borderSubtle}` }}>
                    <td style={{ padding: "4px 8px", fontWeight: 700, color: themeTokens?.colors?.textSecondary }}>#{r.rank}</td>
                    <td style={{ padding: "4px 8px", fontWeight: 600 }}>{r.entity}</td>
                    <td style={{ padding: "4px 8px", textAlign: "right", fontWeight: 700 }}>{r.formatted_value}</td>
                    <td style={{ padding: "4px 8px", textAlign: "right", color: themeTokens?.colors?.textMuted }}>{r.percentile_label}</td>
                    <td style={{ padding: "4px 8px", textAlign: "right", color: r.delta_benchmark >= 0 ? "#10b981" : "#ef4444" }}>
                      {r.delta_benchmark >= 0 ? `+${r.delta_benchmark}` : r.delta_benchmark}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      ) : dynamicVisualSpec ? (
        /* Visual-First Mode (5, 15, 25, 50 entities) */
        <div style={{ width: "100%", maxHeight: limit > 15 ? "280px" : "240px", overflowY: limit > 15 ? "auto" : "visible" }}>
          <VisualSpecRenderer
            visualSpec={dynamicVisualSpec}
            themeTokens={themeTokens}
            isDark={isDark}
            height={limit > 15 ? "320px" : "220px"}
          />
        </div>
      ) : (
        /* Fallback to default topic visual */
        <VisualSpecRenderer
          visualSpec={vSpec}
          themeTokens={themeTokens}
          isDark={isDark}
          height="220px"
        />
      )}
    </div>
  );
}
