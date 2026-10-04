import { VISUAL_POLICY } from '../policy/visualPolicy.js';

/**
 * Calculates deterministic ECharts grid margins preventing label clipping.
 * @param {object} params
 * @param {string[]} params.categories
 * @param {boolean} params.isVertical
 * @param {boolean} params.hasLegend
 * @param {number} [params.maxCategoryCharLength]
 * @param {number} [params.maxValueCharLength=6]
 * @returns {{ top: number, right: number, bottom: number, left: number, containLabel: boolean }}
 */
export function calculateMargins({
  categories = [],
  isVertical = true,
  hasLegend = false,
  maxCategoryCharLength,
  maxValueCharLength = 6
}) {
  const maxCatLen = maxCategoryCharLength ?? categories.reduce(
    (max, cat) => Math.max(max, String(cat || '').length),
    0
  );

  let left = VISUAL_POLICY.MIN_LEFT_MARGIN;
  let bottom = VISUAL_POLICY.DEFAULT_BOTTOM_MARGIN;
  let right = 24;
  let top = 36;

  if (isVertical) {
    // Left margin accommodates Y-axis value labels
    const valuePixels = maxValueCharLength * VISUAL_POLICY.CHAR_PIXEL_WIDTH_ESTIMATE + 16;
    left = Math.max(VISUAL_POLICY.MIN_LEFT_MARGIN, Math.min(valuePixels, 85));

    // Bottom margin accommodates X-axis category labels
    if (maxCatLen > 10) {
      bottom = 56; // Tilted labels require more bottom clearance
    }
  } else {
    // Horizontal layout: Left margin accommodates category labels
    const catPixels = maxCatLen * VISUAL_POLICY.CHAR_PIXEL_WIDTH_ESTIMATE + 20;
    left = Math.max(
      VISUAL_POLICY.MIN_LEFT_MARGIN,
      Math.min(catPixels, VISUAL_POLICY.MAX_LEFT_MARGIN)
    );

    // Bottom margin accommodates value axis ticks
    bottom = 44;
  }

  if (hasLegend) {
    bottom += 24;
  }

  return {
    top,
    right,
    bottom,
    left: Math.round(left),
    containLabel: true
  };
}
