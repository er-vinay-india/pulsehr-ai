import { VISUAL_POLICY, requiresHorizontalOrientation } from '../policy/visualPolicy.js';
import { calculateMargins } from './calculateMargins.js';
import { humanizeLabel } from './formatters.js';

/**
 * Calculates optimal pre-render layout, orientation, and margins.
 * @param {object} params
 * @param {string} params.type
 * @param {string[]} params.categories
 * @param {Array<{ name: string, data: number[] }>} params.series
 * @param {boolean} [params.hasLegend]
 * @returns {object}
 */
export function calculateChartLayout({
  type = 'column',
  categories = [],
  series = [],
  hasLegend = false
}) {
  const cleanCategories = categories.map(c => typeof c === 'string' ? humanizeLabel(c) : c);
  const cleanType = String(type).toLowerCase();
  const catCount = cleanCategories.length;
  const maxLabelLen = cleanCategories.reduce((max, c) => Math.max(max, String(c || '').length), 0);

  // 1. Determine orientation for Cartesian bar/column
  let isVertical = true;
  if (cleanType === 'column' || cleanType === 'bar') {
    if (cleanType === 'bar') {
      isVertical = false;
    } else if (requiresHorizontalOrientation(catCount, maxLabelLen)) {
      isVertical = false; // Auto-flip to horizontal bar to avoid crowding
    }
  }

  // 2. High-cardinality Top-N consolidation (if > 25 categories)
  let layoutCategories = [...cleanCategories];
  let layoutSeries = series.map(s => ({ ...s, name: humanizeLabel(s.name), data: [...(s.data || [])] }));
  let isConsolidated = false;
  let hiddenCount = 0;

  if (catCount > VISUAL_POLICY.TOP_N_CONSOLIDATION_THRESHOLD && layoutSeries[0]?.data) {
    const topN = VISUAL_POLICY.DEFAULT_TOP_N;
    // Pair categories with primary metric
    const primaryData = layoutSeries[0].data;
    const paired = categories.map((cat, idx) => ({
      category: cat,
      values: layoutSeries.map(s => Number(s.data[idx]) || 0),
      sortVal: Math.abs(Number(primaryData[idx]) || 0)
    }));

    paired.sort((a, b) => b.sortVal - a.sortVal);

    const topItems = paired.slice(0, topN);
    const tailItems = paired.slice(topN);
    hiddenCount = tailItems.length;

    if (hiddenCount > 0) {
      isConsolidated = true;
      layoutCategories = topItems.map(item => item.category);
      layoutCategories.push(`Other (${hiddenCount} items)`);

      layoutSeries = layoutSeries.map((s, sIdx) => {
        const topValues = topItems.map(item => item.values[sIdx]);
        const otherSum = tailItems.reduce((sum, item) => sum + item.values[sIdx], 0);
        return {
          ...s,
          data: [...topValues, otherSum]
        };
      });
    }
  }

  // 3. Compute safe domain bounds across all series values
  let minVal = Infinity;
  let maxVal = -Infinity;

  layoutSeries.forEach(s => {
    (s.data || []).forEach(val => {
      const num = Number(val);
      if (!Number.isNaN(num)) {
        if (num < minVal) minVal = num;
        if (num > maxVal) maxVal = num;
      }
    });
  });

  if (minVal === Infinity) minVal = 0;
  if (maxVal === -Infinity) maxVal = 100;

  const domain = {
    min: minVal < 0 ? Math.floor(minVal * 1.1) : 0,
    max: maxVal > 0 ? Math.ceil(maxVal * 1.08) : 0
  };

  // 4. Calculate dynamic margins
  const margins = calculateMargins({
    categories: layoutCategories,
    isVertical,
    hasLegend,
    maxCategoryCharLength: maxLabelLen
  });

  return {
    isVertical,
    effectiveType: isVertical ? 'bar' : 'horizontal_bar',
    categories: layoutCategories,
    series: layoutSeries,
    margins,
    domain,
    isConsolidated,
    hiddenCount
  };
}
