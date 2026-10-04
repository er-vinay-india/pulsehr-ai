/**
 * Chart Spec Schema Validator (Zero-Dependency)
 * Validates semantic chart contracts before React rendering.
 */

export const SUPPORTED_CHART_TYPES = new Set([
  'bar',
  'column',
  'line',
  'donut',
  'pie',
  'scatter',
  'variance_waterfall',
  'waterfall',
  'breakdown_tree',
  'heatmap',
  'gauge',
  'table'
]);

export const SchemaErrorCode = {
  INVALID_INPUT: 'INVALID_INPUT',
  UNSUPPORTED_TYPE: 'UNSUPPORTED_TYPE',
  EMPTY_SERIES: 'EMPTY_SERIES',
  MISSING_CATEGORIES: 'MISSING_CATEGORIES',
  INVALID_METRIC_DATA: 'INVALID_METRIC_DATA',
  CORRUPTED_TREE: 'CORRUPTED_TREE'
};

/**
 * Validates raw chart specification against system contract.
 * @param {object} spec 
 * @returns {{ isValid: boolean, errors: Array<{ field: string, message: string, code: string }>, cleanType: string }}
 */
export function validateChartSpec(spec) {
  const errors = [];

  if (!spec || typeof spec !== 'object') {
    return {
      isValid: false,
      cleanType: 'unknown',
      errors: [{ field: 'root', message: 'Chart specification must be an object', code: SchemaErrorCode.INVALID_INPUT }]
    };
  }

  // Determine chart type
  const rawType = spec.chart_type || spec.type || spec.chartType || 'column';
  const cleanType = String(rawType).toLowerCase().trim();

  if (!SUPPORTED_CHART_TYPES.has(cleanType)) {
    // If series contains echart type, tolerate it
    const seriesType = spec.series?.[0]?.type;
    if (!seriesType || !SUPPORTED_CHART_TYPES.has(String(seriesType).toLowerCase())) {
      errors.push({
        field: 'type',
        message: `Unsupported chart type "${rawType}". Supported: ${[...SUPPORTED_CHART_TYPES].join(', ')}`,
        code: SchemaErrorCode.UNSUPPORTED_TYPE
      });
    }
  }

  // Breakdown Tree Specifics
  if (cleanType === 'breakdown_tree' || spec.tree_data) {
    const tree = spec.tree_data || spec.treeData;
    if (!tree || typeof tree !== 'object' || !tree.name) {
      errors.push({
        field: 'tree_data',
        message: 'Breakdown tree chart requires a valid tree_data object with a root "name"',
        code: SchemaErrorCode.CORRUPTED_TREE
      });
    }
    return {
      isValid: errors.length === 0,
      cleanType: 'breakdown_tree',
      errors
    };
  }

  // Pie / Donut Specifics
  if (cleanType === 'donut' || cleanType === 'pie') {
    const seriesData = spec.series?.[0]?.data || spec.data || spec.items;
    if (!Array.isArray(seriesData) || seriesData.length === 0) {
      errors.push({
        field: 'series.data',
        message: 'Donut/Pie chart requires a non-empty data array with items having name and value',
        code: SchemaErrorCode.EMPTY_SERIES
      });
    }
    return {
      isValid: errors.length === 0,
      cleanType,
      errors
    };
  }

  // Cartesian checks (Bar, Column, Line, Waterfall, Scatter)
  const series = spec.series;
  const categories = spec.categories || spec.xAxis?.data || spec.x_categories;

  if (Array.isArray(series) && series.length > 0) {
    let hasValidData = false;
    for (let i = 0; i < series.length; i++) {
      const s = series[i];
      if (Array.isArray(s?.data) && s.data.length > 0) {
        hasValidData = true;
        break;
      }
    }
    if (!hasValidData) {
      errors.push({
        field: 'series.data',
        message: 'Chart series must contain at least one non-empty numerical data series',
        code: SchemaErrorCode.EMPTY_SERIES
      });
    }
  } else if (!Array.isArray(spec.items) || spec.items.length === 0) {
    errors.push({
      field: 'series',
      message: 'Chart specification requires a valid "series" or "items" array',
      code: SchemaErrorCode.EMPTY_SERIES
    });
  }

  // Ensure categories exist for discrete axis charts
  if (!categories && cleanType !== 'scatter') {
    // If spec is an ECharts direct option with numerical xAxis, that is acceptable
    if (spec.xAxis?.type !== 'value' && !spec.items) {
      errors.push({
        field: 'categories',
        message: 'Discrete Cartesian chart requires "categories" or "xAxis.data"',
        code: SchemaErrorCode.MISSING_CATEGORIES
      });
    }
  }

  return {
    isValid: errors.length === 0,
    cleanType,
    errors
  };
}
