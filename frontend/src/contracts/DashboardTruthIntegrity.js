/**
 * DashboardTruthIntegrity.js
 *
 * Enforces HighView Governed Truth Integrity (Layer 1).
 * UI-visible factual values must originate from governed payloads.
 *
 * Forbids:
 * - hardcoded analytical fallbacks
 * - fake counts
 * - default percentages
 * - default relationships
 * - default findings
 * - sample values in production render paths
 */

export const TRUTH_STATES = Object.freeze({
  VALUE: "VALUE",
  KNOWN_EMPTY: "KNOWN_EMPTY",
  NOT_APPLICABLE: "NOT_APPLICABLE",
  UNAVAILABLE: "UNAVAILABLE",
});

/**
 * Resolve an analytical count or metric safely without synthetic numerical defaults.
 */
export function resolveGovernedCount(rawCount, allowZero = true) {
  if (typeof rawCount === "number" && !isNaN(rawCount)) {
    if (rawCount === 0 && !allowZero) {
      return { state: TRUTH_STATES.KNOWN_EMPTY, value: 0, text: "0" };
    }
    return { state: TRUTH_STATES.VALUE, value: rawCount, text: String(rawCount) };
  }
  return { state: TRUTH_STATES.UNAVAILABLE, value: null, text: "—" };
}

/**
 * Entitlement verification for factual claims in executive copy.
 */
export function verifyClaimEntitlement(claimText, governedPayload) {
  if (!claimText || typeof claimText !== "string") return true;

  // Static product / UI copy is exempt
  const isStaticCopy =
    claimText.includes("Upload a spreadsheet") ||
    claimText.includes("No Workbooks Ingested") ||
    claimText.includes("No datasets or spreadsheets have been uploaded");
  if (isStaticCopy) return true;

  // Dynamic claims containing numbers must have backing governed data
  const hasNumericalClaim = /\d+\s+(validated|cross-source|findings|relationships|records|departments|employees)/i.test(
    claimText
  );
  if (hasNumericalClaim && !governedPayload) {
    return false; // Dynamic factual claim without governed payload is forbidden
  }

  return true;
}
