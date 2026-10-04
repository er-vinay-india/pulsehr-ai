import { validateChartSpec } from '../schema/chartSchema.js';
import { VISUAL_POLICY } from '../policy/visualPolicy.js';
import { calculateChartLayout } from '../layout/calculateChartLayout.js';
import { formatCompactNumber } from '../layout/formatters.js';

/**
 * Normalizes a raw chart specification into a safe, guaranteed ECharts option.
 * @param {object} rawSpec 
 * @param {object} [options]
 * @param {boolean} [options.isDark=false]
 * @param {object} [options.themeTokens]
 * @returns {{ option: object, meta: object, isValid: boolean, errors?: Array }}
 */
export function normalizeChartSpec(rawSpec, options = {}) {
  const validation = validateChartSpec(rawSpec);
  if (!validation.isValid) {
    return {
      isValid: false,
      errors: validation.errors,
      option: null,
      meta: { cleanType: validation.cleanType }
    };
  }

  const { isDark = false, themeTokens = {} } = options;
  const cleanType = validation.cleanType;

  // Extract core fields
  const title = rawSpec.title || rawSpec.chart_title || '';
  const unit = rawSpec.unit || '';
  const rawCategories = rawSpec.categories || rawSpec.xAxis?.data || (rawSpec.items ? rawSpec.items.map(i => i.label) : []);
  const rawSeries = rawSpec.series || (rawSpec.items ? [{ name: rawSpec.metric || 'Value', data: rawSpec.items.map(i => i.value) }] : []);
  const hasLegend = Boolean(rawSeries.length > 1 || rawSpec.legend);

  // 1. Direct Tree Chart
  if (cleanType === 'breakdown_tree' || rawSpec.tree_data) {
    const treeData = rawSpec.tree_data || rawSpec.treeData;
    return {
      isValid: true,
      meta: { cleanType: 'breakdown_tree' },
      option: {
        title: title ? { text: title, left: 'center', textStyle: { fontSize: VISUAL_POLICY.MIN_TITLE_FONT_SIZE } } : undefined,
        tooltip: { trigger: 'item', confine: true },
        series: [{
          type: 'tree',
          data: [treeData],
          top: '8%',
          left: '12%',
          bottom: '8%',
          right: '20%',
          symbolSize: 12,
          orient: 'LR',
          initialTreeDepth: 3,
          label: { position: 'left', verticalAlign: 'middle', align: 'right', fontSize: 12 },
          leaves: { label: { position: 'right', verticalAlign: 'middle', align: 'left', fontSize: 12 } }
        }]
      }
    };
  }

  // 2. Donut / Pie Chart
  if (cleanType === 'donut' || cleanType === 'pie') {
    const pieData = (rawSeries[0]?.data || rawSpec.data || rawSpec.items || []).map(item => {
      if (typeof item === 'object' && item !== null) {
        return { name: String(item.name || item.label || ''), value: Number(item.value) || 0 };
      }
      return { name: '', value: Number(item) || 0 };
    });

    return {
      isValid: true,
      meta: { cleanType },
      option: {
        title: title ? { text: title, left: 'center', textStyle: { fontSize: VISUAL_POLICY.MIN_TITLE_FONT_SIZE } } : undefined,
        tooltip: {
          trigger: 'item',
          confine: true,
          formatter: params => `${params.name}: <b>${formatCompactNumber(params.value, unit)}</b> (${params.percent}%)`
        },
        legend: {
          type: 'scroll',
          bottom: 4,
          textStyle: { fontSize: VISUAL_POLICY.MIN_LABEL_FONT_SIZE }
        },
        series: [{
          type: 'pie',
          radius: cleanType === 'donut' ? ['45%', '70%'] : '68%',
          center: ['50%', '46%'],
          avoidLabelOverlap: true,
          label: { show: false },
          emphasis: { label: { show: true, fontSize: 13, fontWeight: 'bold' } },
          data: pieData
        }]
      }
    };
  }

  // 3. Cartesian Layout (Column, Bar, Line, Scatter, Waterfall)
  const layout = calculateChartLayout({
    type: cleanType,
    categories: rawCategories,
    series: rawSeries,
    hasLegend
  });

  const { isVertical, categories, series, margins, domain, isConsolidated, hiddenCount } = layout;

  // Build X and Y axes depending on vertical/horizontal orientation
  let xAxis, yAxis;

  if (isVertical) {
    xAxis = {
      type: 'category',
      data: categories,
      axisLabel: {
        fontSize: VISUAL_POLICY.MIN_AXIS_FONT_SIZE,
        interval: 0,
        rotate: categories.length > 6 ? 30 : 0
      },
      axisTick: { alignWithLabel: true }
    };
    yAxis = {
      type: 'value',
      min: domain.min,
      max: domain.max,
      axisLabel: {
        fontSize: VISUAL_POLICY.MIN_AXIS_FONT_SIZE,
        formatter: val => formatCompactNumber(val, unit)
      },
      splitLine: { show: true }
    };
  } else {
    // Horizontal Bar
    xAxis = {
      type: 'value',
      min: domain.min,
      max: domain.max,
      axisLabel: {
        fontSize: VISUAL_POLICY.MIN_AXIS_FONT_SIZE,
        formatter: val => formatCompactNumber(val, unit)
      },
      splitLine: { show: true }
    };
    yAxis = {
      type: 'category',
      data: categories,
      inverse: true, // Top category at the top
      axisLabel: {
        fontSize: VISUAL_POLICY.MIN_AXIS_FONT_SIZE
      }
    };
  }

  // Build Series
  const formattedSeries = series.map((s, idx) => {
    const sType = cleanType === 'line' ? 'line' : 'bar';
    return {
      name: s.name || `Series ${idx + 1}`,
      type: sType,
      data: s.data,
      smooth: sType === 'line',
      barMaxWidth: 36,
      itemStyle: {
        borderRadius: sType === 'bar' ? (isVertical ? [4, 4, 0, 0] : [0, 4, 4, 0]) : 0
      }
    };
  });

  return {
    isValid: true,
    meta: {
      cleanType,
      isVertical,
      isConsolidated,
      hiddenCount,
      categoryCount: categories.length
    },
    option: {
      title: title ? { text: title, left: 'left', textStyle: { fontSize: VISUAL_POLICY.MIN_TITLE_FONT_SIZE } } : undefined,
      grid: margins,
      tooltip: {
        trigger: 'axis',
        confine: true,
        axisPointer: { type: 'shadow' },
        valueFormatter: val => formatCompactNumber(val, unit)
      },
      ...(hasLegend ? {
        legend: {
          type: 'scroll',
          bottom: 4,
          textStyle: { fontSize: VISUAL_POLICY.MIN_LABEL_FONT_SIZE }
        }
      } : {}),
      xAxis,
      yAxis,
      series: formattedSeries
    }
  };
}
