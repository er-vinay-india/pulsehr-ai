/**
 * HumanFacingCopyPolicy.js
 *
 * Strict UI presentation gate enforcing Human vs Machine metadata separation.
 *
 * GOVERNING PRINCIPLE:
 * "AI may need rich analytical metadata to reason.
 *  Humans do not need to see that metadata to understand the result."
 *
 * ALLOWED on Executive Surfaces:
 * - Business concepts, metrics, units, entities, findings, policies, comparisons, plain human language.
 *
 * FORBIDDEN on Executive Surfaces:
 * - Analytical intents, visual morphologies, pipeline stages, ranking algorithms,
 *   AI classifications, semantic families, internal governance taxonomy, implementation terminology.
 */

export const FORBIDDEN_MACHINE_METADATA_STRINGS = [
  // Analytical Intents & Families
  "DISTRIBUTIONS & VARIANCE",
  "DISTRIBUTIONS AND VARIANCE",
  "DISTRIBUTION_VARIANCE",
  "COMPARATIVE BENCHMARKS",
  "COMPARATIVE_BENCHMARKS",
  "LEADERSHIP FOCUS",
  "LEADERSHIP_FOCUS",
  "LEADERSHIP BRIEF",
  "LEADERSHIP_BRIEF",
  "DECISION SIMULATOR",
  "DECISION_SIMULATOR",
  "AI DECISION SIMULATOR",
  "COUNTERFACTUAL POLICY REPLAY",
  "COUNTERFACTUAL",
  "REPLAY ENGINE",
  "SCENARIO PROVENANCE",
  "TARGET VS ACTUAL",
  "TARGET_VS_ACTUAL",
  "METRIC CORRELATION",
  "METRIC_CORRELATION",
  "WORKFORCE DYNAMICS",
  "WORKFORCE_DYNAMICS",
  "RELATIONSHIP INTENT",
  "RELATIONSHIP_INTENT",
  "TEMPORAL TREND",
  "TEMPORAL_TREND",
  "PARETO CONCENTRATION",
  "PARETO_CONCENTRATION",
  "OUTLIER ISOLATION",
  "OUTLIER_ISOLATION",
  "CROSS SOURCE RELATIONSHIP",
  "CROSS_SOURCE_RELATIONSHIP",
  // Visual Morphologies
  "VISUAL MORPHOLOGY",
  "VISUAL_MORPHOLOGY",
  "MORPHOLOGY MATRIX",
  "MORPHOLOGY BAR",
  "MORPHOLOGY SCATTER",
  "MORPHOLOGY HEATMAP",
  "LAYOUT HINT",
  "LAYOUT_HINT",
  "SPATIAL PLACEMENT",
  "SPATIAL_PLACEMENT",
  // Internal Stages & Systems
  "DETERMINISTIC INTELLIGENCE",
  "DETERMINISTIC_INTELLIGENCE",
  "EVIDENCE GRAPH",
  "EVIDENCE_GRAPH",
  "MODEL GATEWAY",
  "MODEL_GATEWAY",
  "MCP CAPABILITY",
  "MCP_CAPABILITY",
  "LANGGRAPH ORCHESTRATOR",
  "CONTROL PLANE GATES",
  "SINGLE DOMAIN ANALYSIS",
  "SINGLE_DOMAIN_ANALYSIS",
];

// Normalized lookup set for O(1) checks
const FORBIDDEN_NORM_SET = new Set(
  FORBIDDEN_MACHINE_METADATA_STRINGS.map((s) => s.toUpperCase().trim())
);

/**
 * Checks whether a text string contains forbidden machine metadata.
 * @param {string} text - The visible string to inspect
 * @returns {{ isAllowed: boolean, matchedViolations: string[] }}
 */
export function checkHumanFacingCopy(text) {
  if (!text || typeof text !== "string") {
    return { isAllowed: true, matchedViolations: [] };
  }

  const upper = text.toUpperCase().trim();
  const matchedViolations = [];

  // Exact match check
  if (FORBIDDEN_NORM_SET.has(upper)) {
    matchedViolations.push(upper);
  }

  // Substring match check
  for (const forbidden of FORBIDDEN_MACHINE_METADATA_STRINGS) {
    if (upper.includes(forbidden)) {
      if (!matchedViolations.includes(forbidden)) {
        matchedViolations.push(forbidden);
      }
    }
  }

  return {
    isAllowed: matchedViolations.length === 0,
    matchedViolations,
  };
}

/**
 * Sanitizes or strips forbidden machine metadata from a human-facing string.
 * @param {string} text - Input string
 * @param {string} [fallback] - Fallback string if entire string is machine metadata
 * @returns {string} Sanitized string
 */
export function sanitizeHumanFacingCopy(text, fallback = "") {
  if (!text || typeof text !== "string") return fallback;
  const { isAllowed } = checkHumanFacingCopy(text);
  if (!isAllowed) {
    return fallback;
  }
  return text;
}

export default {
  FORBIDDEN_MACHINE_METADATA_STRINGS,
  checkHumanFacingCopy,
  sanitizeHumanFacingCopy,
};
