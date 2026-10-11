/**
 * PresentationLabelResolver.js
 *
 * Centralized presentation-layer label resolution.
 * Prevents raw machine identifiers, screaming snake_case, and database column keys
 * from leaking into the executive user interface.
 *
 * Resolution Order:
 * 1. Explicit semantic label dictionary
 * 2. Domain label registry (Workforce, Environmental, Retail)
 * 3. Safe machine-key humanizer fallback preserving known domain acronyms
 */

const KNOWN_ACRONYMS = new Set([
  'WFO',
  'WF',
  'KPI',
  'SOP',
  'FTE',
  'HR',
  'EDA',
  'PM10',
  'PM25',
  'PM2.5',
  'SO2',
  'NO2',
  'CO2',
  'AQI',
  'NAAQS',
  'NRP',
  'RQI',
  'LLP',
  'UI',
  'API',
  'ID',
  'MT',
  'ESG'
]);

const EXPLICIT_SEMANTIC_LABELS = {
  // Analytical Intents
  TARGET_VS_ACTUAL: 'Target vs Actual',
  LEADERSHIP_FOCUS: 'Leadership Focus',
  POLICY_COMPLIANCE: 'Policy Compliance',
  WORKFORCE_HR: 'Workforce Operations',
  DISTRIBUTIONS_AND_VARIANCE: 'Distributions & Variance',
  COMPARATIVE_BENCHMARKS: 'Comparative Benchmarks',
  DECISION_SIMULATOR: 'Decision Simulator',
  CORRELATION_MATRIX: 'Correlation Matrix',
  RANKING: 'Ranking',
  DISTRIBUTION: 'Distribution',
  RELATIONSHIP: 'Relationship',
  TREND: 'Trend',
  ANOMALY: 'Anomaly',
  VARIANCE: 'Variance',
  COMPOSITION: 'Composition',
  PART_TO_WHOLE: 'Part to Whole',
  GAP_EXPLANATION: 'Gap Explanation',
  MATRIX: 'Matrix',

  // Section & Eyebrow Badges
  LEADERSHIP_BRIEF: 'Leadership Brief',
  PRIORITY_DECISIONS: 'Priority Decisions',
  DIAGNOSTIC_INSIGHTS: 'Diagnostic Insights',
  SUPPORTING_ANALYSIS: 'Supporting Analysis',
  SCENARIO_ANALYSIS: 'Scenario Analysis',
  VERIFIED_SINGLE_DOMAIN: 'Verified Single-Domain Analysis',
  LIVE_VERIFIED: 'Live Verified',

  // Common Column & Domain Concepts
  TOTAL_ATTENDANCE: 'Total Attendance',
  FINAL_ATTENDANCE: 'Final Attendance',
  APPROVED_LEAVES: 'Approved Leaves',
  OFFICE_PRESENCE_RATE: 'Office Presence Rate',
  APPROVED_LEAVE_RATE: 'Approved Leave Rate',
  DEPARTMENT_ATTENDANCE_GAP: 'Department Attendance Gap',
  AVERAGE_PM10_LEVEL: 'Average PM10 Level',
  AVERAGE_PM25_LEVEL: 'Average PM2.5 Level',
  AVERAGE_NO2_LEVEL: 'Average NO2 Level',
  AVERAGE_SO2_LEVEL: 'Average SO2 Level',
  MONITORED_COVERAGE: 'Monitored Coverage'
};

/**
 * Resolves a raw machine key or identifier into a clean, human-readable label.
 * @param {string} rawKey - The incoming key (e.g. "LEADERSHIP_FOCUS", "target_vs_actual", "department_name")
 * @param {string} [fallback] - Optional fallback string if rawKey is empty
 * @returns {string} Human-readable formatted string
 */
export function resolvePresentationLabel(rawKey, fallback = '') {
  if (!rawKey || typeof rawKey !== 'string') {
    return fallback;
  }

  const trimmed = rawKey.trim();
  if (!trimmed) return fallback;

  // 1. Check explicit uppercase dictionary
  const normalizedUpper = trimmed.toUpperCase();
  if (EXPLICIT_SEMANTIC_LABELS[normalizedUpper]) {
    return EXPLICIT_SEMANTIC_LABELS[normalizedUpper];
  }

  // 2. If it does not contain underscores and does not match machine patterns, return as-is
  if (!trimmed.includes('_') && !/^[A-Z0-9]{3,}$/.test(trimmed)) {
    return trimmed;
  }

  // 3. Fallback: split by underscores/hyphens and capitalize words while preserving acronyms
  const words = trimmed
    .split(/[_\-\s]+/)
    .filter(Boolean)
    .map(word => {
      const upperWord = word.toUpperCase();
      if (KNOWN_ACRONYMS.has(upperWord)) {
        return upperWord === 'PM25' ? 'PM2.5' : upperWord;
      }
      // Standard title casing
      return word.charAt(0).toUpperCase() + word.slice(1).toLowerCase();
    });

  return words.join(' ');
}

export default resolvePresentationLabel;
