/**
 * DatasetReferenceIntegrity.js
 *
 * Governs dataset identification, catalog validation, and URL self-healing.
 * Pointers in URL, sessionStorage, or state are treated as untrusted candidates
 * until validated against the authoritative workspace catalog.
 */

export function extractDatasetIdFromUrl() {
  try {
    const searchP = new URLSearchParams(window.location.search);
    const searchVal = searchP.get("dataset_id") || searchP.get("sheet_id");
    if (searchVal) return searchVal;

    const hash = window.location.hash || "";
    if (hash.includes("?")) {
      const hashP = new URLSearchParams(hash.substring(hash.indexOf("?")));
      const hashVal = hashP.get("dataset_id") || hashP.get("sheet_id");
      if (hashVal) return hashVal;
    }
  } catch {}
  return "";
}

/**
 * Validate requested dataset ID against loaded catalog.
 * Self-heals stale URLs by removing deleted/missing parameters via replaceState.
 */
export function validateAndResolveDataset(catalog = [], requestedId = "") {
  const list = Array.isArray(catalog) ? catalog : catalog?.datasets || [];

  // Case 1: Catalog is completely empty (zero datasets in workspace)
  if (list.length === 0) {
    selfHealUrl(null);
    return {
      resolvedId: "",
      status: "CATALOG_EMPTY",
      staleDetected: Boolean(requestedId),
      activeDataset: null,
    };
  }

  // Case 2: Requested ID is present and valid
  if (requestedId) {
    const match = list.find((d) => String(d.id) === String(requestedId));
    if (match) {
      return {
        resolvedId: String(match.id),
        status: "VALID",
        staleDetected: false,
        activeDataset: match,
      };
    }
  }

  // Case 3: Requested ID was stale or missing, fallback to first valid dataset
  const fallback = list[0];
  const targetId = String(fallback.id);
  selfHealUrl(targetId);

  return {
    resolvedId: targetId,
    status: requestedId ? "STALE_HEALED" : "DEFAULT_SELECTED",
    staleDetected: Boolean(requestedId),
    activeDataset: fallback,
  };
}

/**
 * Cleanly synchronize browser URL with resolved dataset state without reloading.
 */
export function selfHealUrl(datasetId) {
  try {
    const url = new URL(window.location);
    if (datasetId) {
      url.searchParams.set("dataset_id", datasetId);
    } else {
      url.searchParams.delete("dataset_id");
    }
    url.searchParams.delete("sheet_id");
    window.history.replaceState({}, "", url);
  } catch {}
}
