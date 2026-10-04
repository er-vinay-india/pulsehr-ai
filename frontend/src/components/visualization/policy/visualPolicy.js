/**
 * Presentation Guard: Visual Policy & Invariants
 * Enforces non-negotiable geometric and typographical rules.
 */

export const VISUAL_POLICY = {
  // Typography
  MIN_AXIS_FONT_SIZE: 12,
  MIN_TITLE_FONT_SIZE: 16,
  MIN_LABEL_FONT_SIZE: 11,
  MAX_TITLE_LINES: 2,

  // Spatial Dimensions
  MIN_CONTAINER_HEIGHT: 280,
  DEFAULT_CHART_HEIGHT: 320,
  MIN_PLOT_AREA_RATIO: 0.60, // Plot canvas must take >= 60% of card height
  MAX_NARRATIVE_RATIO: 0.35, // Text narrative must take <= 35% of card height

  // Categorical Density Rules
  MAX_CATEGORIES_VERTICAL: 10,  // Flips to horizontal bar if > 10 items
  MAX_LABEL_CHARS_VERTICAL: 16, // Flips to horizontal bar if label > 16 chars
  TOP_N_CONSOLIDATION_THRESHOLD: 25, // Consolidates to Top 10 + Other if > 25
  DEFAULT_TOP_N: 10,

  // Margins
  MIN_LEFT_MARGIN: 48,
  MAX_LEFT_MARGIN: 220,
  DEFAULT_BOTTOM_MARGIN: 40,
  BOTTOM_MARGIN_WITH_LEGEND: 64,
  CHAR_PIXEL_WIDTH_ESTIMATE: 7.2,

  // Contrast & Safety
  WCAG_MIN_CONTRAST: 7.0, // WCAG AAA
};

/**
 * Checks whether category count and string lengths require a horizontal orientation.
 * @param {number} count 
 * @param {number} maxCharLength 
 * @returns {boolean}
 */
export function requiresHorizontalOrientation(count, maxCharLength) {
  if (count > VISUAL_POLICY.MAX_CATEGORIES_VERTICAL) return true;
  if (maxCharLength > VISUAL_POLICY.MAX_LABEL_CHARS_VERTICAL) return true;
  return false;
}

/**
 * Evaluates whether narrative content exceeds the safe text-to-chart ratio.
 * @param {number} narrativeHeight 
 * @param {number} totalHeight 
 * @returns {boolean}
 */
export function isNarrativeOverflow(narrativeHeight, totalHeight) {
  if (!totalHeight || totalHeight <= 0) return false;
  return (narrativeHeight / totalHeight) > VISUAL_POLICY.MAX_NARRATIVE_RATIO;
}
