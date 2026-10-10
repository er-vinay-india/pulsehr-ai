/**
 * Unified Data Explorer Navigation & Deep-Link Helper.
 *
 * Implements a standardized ExplorerDeepLink contract across all dashboard surfaces:
 * - ExecutiveVisualStory
 * - ScenarioSummaryCard
 * - KPI cards
 * - Quick Inspect drawer
 * - Evidence & Ranking handoff buttons
 */

export function buildExplorerUrl({
  datasetId = null,
  tab = "overview",
  topicId = null,
  evidenceId = null,
  entity = null,
  measure = null,
  relationshipId = null,
  temporalFamily = null,
  filters = null,
} = {}) {
  const params = new URLSearchParams();

  if (datasetId) params.set("dataset_id", datasetId);
  if (tab) params.set("tab", tab);
  if (topicId) params.set("topic_id", topicId);
  if (evidenceId) params.set("evidence_id", evidenceId);
  if (entity) params.set("entity", entity);
  if (measure) params.set("measure", measure);
  if (relationshipId) params.set("relationship_id", relationshipId);
  if (temporalFamily) params.set("temporal_family", temporalFamily);

  if (filters && typeof filters === "object") {
    Object.entries(filters).forEach(([k, v]) => {
      if (v != null) params.set(k, v);
    });
  }

  return `${window.location.pathname}?${params.toString()}#explorer`;
}

export function navigateToExplorer(options = {}) {
  const targetUrl = buildExplorerUrl(options);
  window.location.href = targetUrl;
}

/**
 * Derives contextual Data Explorer target and action label from an ExecutiveTopic.
 */
export function getContextualExplorerTarget(topic, datasetId = null) {
  if (!topic) {
    return {
      tab: "overview",
      label: "Explore analysis",
      url: buildExplorerUrl({ datasetId, tab: "overview" }),
    };
  }

  const intent = (topic.analytical_intent || "").toUpperCase();
  const spec = topic.visual_spec || {};
  const meta = topic.inspect_payload?.ranking_metadata || {};
  const entity = spec.entity_column || meta.entity_column || topic.dimension_name;
  const measure = spec.measure_column || meta.measure_column || topic.primary_measure || topic.metric_name;
  const topicId = topic.topic_id || topic.inspect_payload?.topic_id;
  const evidenceId = (topic.evidence_ids && topic.evidence_ids[0]) || topic.evidence_ref;

  // 1. RANKING -> Data Explorer / Rankings
  if (intent === "RANKING" || spec.is_ranking_story) {
    return {
      tab: "rankings",
      label: "Explore full ranking",
      url: buildExplorerUrl({ datasetId, tab: "rankings", entity, measure, topicId, evidenceId }),
    };
  }

  // 2. TREND -> Data Explorer / Trends
  if (intent === "TREND" || spec.chart_type === "line" || spec.chart_type === "trend_line") {
    return {
      tab: "trends",
      label: "Explore trend analysis",
      url: buildExplorerUrl({
        datasetId,
        tab: "trends",
        measure,
        temporalFamily: topic.metric_family || "reporting_cycles",
        topicId,
        evidenceId,
      }),
    };
  }

  // 3. RELATIONSHIP -> Data Explorer / Relationships
  if (intent === "RELATIONSHIP" || topic.is_cross_sheet || topic.relationship_id) {
    return {
      tab: "relationships",
      label: topic.is_cross_sheet ? "Explore cross-source relationships" : "Explore relationship",
      url: buildExplorerUrl({
        datasetId,
        tab: "relationships",
        relationshipId: topic.relationship_id,
        topicId,
        evidenceId,
      }),
    };
  }

  // 4. ANOMALY / VARIANCE -> Data Explorer / Distributions
  if (intent === "ANOMALY" || spec.chart_type === "variance_bar") {
    return {
      tab: "distributions",
      label: "Explore distribution & anomalies",
      url: buildExplorerUrl({ datasetId, tab: "distributions", entity, measure, topicId, evidenceId }),
    };
  }

  // 5. COMPOSITION -> Data Explorer / Relationships or Distributions
  if (intent === "COMPOSITION" || spec.chart_type === "100_percent_stacked_bar") {
    return {
      tab: "relationships",
      label: "Explore composition breakdown",
      url: buildExplorerUrl({ datasetId, tab: "relationships", topicId, evidenceId }),
    };
  }

  // 6. Fallback -> Data Explorer / Evidence
  return {
    tab: "evidence",
    label: "Explore evidence ledger",
    url: buildExplorerUrl({ datasetId, tab: "evidence", topicId, evidenceId }),
  };
}
