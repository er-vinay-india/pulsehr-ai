/**
 * DashboardStateContract.js
 *
 * Formal Executive Dashboard state machine and surface contract.
 * Enforces first-class lifecycle states and prevents unauthorized
 * component rendering or data leakage when datasets are missing or stale.
 */

export const DASHBOARD_STATES = Object.freeze({
  LOADING: "LOADING",
  CATALOG_EMPTY: "CATALOG_EMPTY",
  DATASET_RESOLVING: "DATASET_RESOLVING",
  DATASET_READY: "DATASET_READY",
  DATASET_DELETED_OR_STALE: "DATASET_DELETED_OR_STALE",
  DATASET_ERROR: "DATASET_ERROR",
});

export const DASHBOARD_SURFACES = Object.freeze({
  DASHBOARD_READY: "DASHBOARD_READY",
  DASHBOARD_EMPTY: "DASHBOARD_EMPTY",
  DASHBOARD_LOADING: "DASHBOARD_LOADING",
  DASHBOARD_ERROR: "DASHBOARD_ERROR",
  DASHBOARD_STALE_DATASET: "DASHBOARD_STALE_DATASET",
  UPLOAD_MODAL: "UPLOAD_MODAL",
  QUICK_INSPECT: "QUICK_INSPECT",
  DEEP_DIVE_ENTRY: "DEEP_DIVE_ENTRY",
});

/**
 * Surface requirement declarations.
 * Declares allowed primitives, routing rules, and truth boundaries per surface.
 */
export const SURFACE_REQUIREMENTS = Object.freeze({
  [DASHBOARD_SURFACES.DASHBOARD_EMPTY]: {
    allowedPrimitives: ["Button", "IconButton", "ActionIconButton", "IconWrap"],
    forbiddenComponents: [
      "ExecutiveSummary",
      "ExecutiveKPIGrid",
      "EvidenceStrip",
      "GenericRankingExplorer",
      "ExecutiveVisualCard",
      "ExecutiveScenarioExplorer",
      "UnifiedExecutiveInsightsGrid",
    ],
    requiresGovernedData: false,
    disallowSyntheticFacts: true,
  },
  [DASHBOARD_SURFACES.DASHBOARD_READY]: {
    allowedPrimitives: ["Button", "IconButton", "ActionIconButton", "Card", "Grid", "Dialog"],
    requiresGovernedData: true,
    disallowSyntheticFacts: true,
  },
  [DASHBOARD_SURFACES.DASHBOARD_LOADING]: {
    allowedPrimitives: ["Loader", "Waveform", "StatusNotice"],
    requiresGovernedData: false,
    disallowSyntheticFacts: true,
  },
  [DASHBOARD_SURFACES.DASHBOARD_ERROR]: {
    allowedPrimitives: ["Button", "StatusNotice", "AlertTriangle"],
    requiresGovernedData: false,
    disallowSyntheticFacts: true,
  },
});

/**
 * Resolve current dashboard state deterministically from runtime context.
 */
export function resolveDashboardState({
  sourcesLoading = false,
  sources = [],
  selectedDatasetId = null,
  data = null,
  calculating = false,
  calcError = null,
  sourcesError = null,
}) {
  if (sourcesLoading) {
    return DASHBOARD_STATES.LOADING;
  }

  if (sourcesError) {
    return DASHBOARD_STATES.DATASET_ERROR;
  }

  if (!sources || sources.length === 0) {
    return DASHBOARD_STATES.CATALOG_EMPTY;
  }

  if (selectedDatasetId) {
    const exists = sources.some((s) => String(s.id) === String(selectedDatasetId));
    if (!exists) {
      return DASHBOARD_STATES.DATASET_DELETED_OR_STALE;
    }
  } else {
    return DASHBOARD_STATES.DATASET_RESOLVING;
  }

  if (calculating) {
    return DASHBOARD_STATES.LOADING;
  }

  if (calcError) {
    return DASHBOARD_STATES.DATASET_ERROR;
  }

  if (data) {
    return DASHBOARD_STATES.DATASET_READY;
  }

  return DASHBOARD_STATES.LOADING;
}
