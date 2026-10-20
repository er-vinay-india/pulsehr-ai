/**
 * Enterprise DataTable Type-Aware Sorting and Governed Status Rankings
 *
 * Implements presentation-level semantic orderings without altering backend truth:
 * - Relationship safety (Safe to join -> Safe after aggregation -> Needs review -> Unsafe to join)
 * - Freshness (Current -> Needs review -> Stale / Refresh needed)
 * - Confidence (High -> Medium -> Low)
 * - Numeric / Currency / Percentage numeric sorting
 * - Chronological date sorting
 * - Leading-zero preserving identifier natural sorting
 */

export const GOVERNED_STATUS_RANKS = {
  // Relationships safety (presentation ordering)
  "safe to join": 1,
  "safe after aggregation": 2,
  "needs review": 3,
  "unsafe to join": 4,
  "safe": 1,
  "unsafe": 4,

  // Freshness
  "current": 1,
  "needs refresh": 2,
  "stale": 3,
  "stale / refresh needed": 3,

  // Confidence / Priority
  "very high": 0,
  "high": 1,
  "medium": 2,
  "low": 3,

  // Verification / Ingestion
  "verified": 1,
  "reconstructed": 2,
  "provisional": 2,
  "unverified": 3,

  // Privacy
  "public": 1,
  "internal": 2,
  "sensitive": 3,
  "pii": 4,
  "restricted": 5,

  // Materialization mode
  "virtual": 1,
  "materialized": 2,
};

export function getStatusRank(statusStr, customRankOrder) {
  if (statusStr === undefined || statusStr === null || statusStr === "") return 999;
  const s = String(statusStr).trim().toLowerCase();
  if (customRankOrder) {
    if (Array.isArray(customRankOrder)) {
      const idx = customRankOrder.findIndex(
        item => String(item).trim().toLowerCase() === s
      );
      if (idx !== -1) return idx + 1;
    } else if (typeof customRankOrder === "object" && customRankOrder[s] !== undefined) {
      return customRankOrder[s];
    }
  }
  return GOVERNED_STATUS_RANKS[s] ?? 999;
}

export function compareValues(valA, valB, colDef = {}, sortDir = "asc") {
  // Handle empty / null values — push to bottom in both directions
  const isNoneA = valA === undefined || valA === null || valA === "";
  const isNoneB = valB === undefined || valB === null || valB === "";
  if (isNoneA && isNoneB) return 0;
  if (isNoneA) return 1;
  if (isNoneB) return -1;

  const type = colDef.type || inferType(valA);

  let cmp = 0;
  switch (type) {
    case "status": {
      const rankA = getStatusRank(valA, colDef.statusRankOrder);
      const rankB = getStatusRank(valB, colDef.statusRankOrder);
      cmp = rankA - rankB;
      if (cmp === 0) {
        cmp = String(valA).localeCompare(String(valB), undefined, { sensitivity: "base" });
      }
      break;
    }
    case "number":
    case "numeric":
    case "currency":
    case "percentage": {
      const numA = typeof valA === "number" ? valA : Number(String(valA).replace(/[^0-9.-]+/g, ""));
      const numB = typeof valB === "number" ? valB : Number(String(valB).replace(/[^0-9.-]+/g, ""));
      if (!isNaN(numA) && !isNaN(numB)) {
        cmp = numA - numB;
      } else {
        cmp = String(valA).localeCompare(String(valB));
      }
      break;
    }
    case "date":
    case "datetime": {
      const dtA = Date.parse(valA);
      const dtB = Date.parse(valB);
      if (!isNaN(dtA) && !isNaN(dtB)) {
        cmp = dtA - dtB;
      } else {
        cmp = String(valA).localeCompare(String(valB));
      }
      break;
    }
    case "boolean": {
      const boolA = valA ? 1 : 0;
      const boolB = valB ? 1 : 0;
      cmp = boolA - boolB;
      break;
    }
    case "identifier": {
      cmp = String(valA).localeCompare(String(valB), undefined, { numeric: true, sensitivity: "base" });
      break;
    }
    default: {
      cmp = String(valA).localeCompare(String(valB), undefined, { sensitivity: "base" });
      break;
    }
  }

  return sortDir === "desc" ? -cmp : cmp;
}

function inferType(val) {
  if (typeof val === "number") return "number";
  if (typeof val === "boolean") return "boolean";
  if (typeof val === "string") {
    const s = val.trim();
    if (/^-?\d+(\.\d+)?$/.test(s.replace(/,/g, ""))) return "number";
    if (/^\d{4}-\d{2}-\d{2}/.test(s)) return "date";
  }
  return "text";
}
