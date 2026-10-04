import { lightTokens, darkTokens, getThemeTokens } from '../../theme/tokens';
import { calculateMargins } from '../visualization/layout/calculateMargins';
import { VISUAL_POLICY } from '../visualization/policy/visualPolicy';

export const lightPalette = lightTokens.chart.palette;
export const darkPalette = darkTokens.chart.palette;

export const palette = lightPalette;
export const hridayPalette = lightPalette;
export const hridayDarkPalette = darkPalette;

export const getChartPalette = (isDark = false) => (isDark ? darkPalette : lightPalette);

export function isCurrentThemeDark(isDark) {
  if (typeof isDark === 'boolean') return isDark;
  if (typeof document !== 'undefined') {
    return document.documentElement.getAttribute('data-theme') === 'dark';
  }
  return false;
}

export const numeric = value => value == null || value === '' || !Number.isFinite(Number(value)) ? null : Number(value);
const suffix = unit => !unit || /^(units?)$/i.test(unit) ? '' : unit === '%' ? '%' : ` ${unit}`;
export const formatFullValue = (value, unit = '') => numeric(value) == null ? '—' : `${unit === '$' ? '$' : ''}${Number(value).toLocaleString('en-US', { maximumFractionDigits: 20 })}${unit === '$' ? '' : suffix(unit)}`;
export const formatValue = (value, unit = '') => {
  const n = numeric(value);
  if (n == null) return '—';
  const abs = Math.abs(n);
  let scale = unit === '%' ? 1 : abs >= 1e9 ? 1e9 : abs >= 1e6 ? 1e6 : abs >= 1e3 ? 1e3 : 1;
  if (scale < 1e9 && scale > 1 && Math.abs(Number((n / scale).toFixed(2))) >= 1000) scale *= 1000;
  const marker = scale === 1e9 ? 'B' : scale === 1e6 ? 'M' : scale === 1e3 ? 'K' : '';
  return `${unit === '$' ? '$' : ''}${(n / scale).toLocaleString('en-US', { maximumFractionDigits: 2 })}${marker}${unit === '$' ? '' : suffix(unit)}`;
};
export const metricUnit = (metric, unit = '') => unit || (/%|\bpercent(?:age)?\b/i.test(metric) ? '%' : '');

export function cartesian(categories, series, horizontal = false, unit = '', themeDark) {
  const isDark = isCurrentThemeDark(themeDark);
  const chartTokens = getThemeTokens(isDark).chart;
  const activePalette = chartTokens.palette;
  const textColor = chartTokens.text;
  const headingColor = chartTokens.title;
  const lineColor = chartTokens.axisLine;
  const splitLineColor = chartTokens.splitLine;
  const tooltipBg = chartTokens.tooltipBg;
  const tooltipBorder = chartTokens.tooltipBorder;


  const category = {
    type: 'category',
    data: categories,
    inverse: horizontal,
    triggerEvent: true,
    axisTick: { show: false },
    axisLine: { lineStyle: { color: lineColor } },
    axisLabel: {
      hideOverlap: true,
      width: horizontal ? 140 : 90,
      overflow: horizontal ? 'break' : 'truncate',
      color: textColor,
      fontSize: VISUAL_POLICY.MIN_AXIS_FONT_SIZE
    }
  };
  const value = {
    type: 'value',
    axisLabel: {
      formatter: v => formatValue(v, unit),
      color: textColor,
      fontSize: VISUAL_POLICY.MIN_AXIS_FONT_SIZE
    },
    splitLine: {
      lineStyle: {
        color: splitLineColor,
        type: 'dashed'
      }
    }
  };

  const dynamicGrid = calculateMargins({
    categories,
    isVertical: !horizontal,
    hasLegend: series.length > 1
  });

  return {
    color: activePalette,
    grid: {
      ...dynamicGrid,
      top: series.length > 1 ? 44 : 20,
      bottom: categories.length > 12 ? Math.max(dynamicGrid.bottom, 48) : dynamicGrid.bottom,
      containLabel: true
    },
    tooltip: {
      trigger: 'axis',
      valueFormatter: v => formatFullValue(v, unit),
      backgroundColor: tooltipBg,
      borderColor: tooltipBorder,
      borderWidth: 1,
      textStyle: { color: headingColor, fontSize: 12 },
      extraCssText: isDark ? 'box-shadow: 0 4px 16px rgba(0, 0, 0, 0.4); border-radius: 8px;' : 'box-shadow: 0 4px 14px rgba(11, 31, 58, 0.12); border-radius: 8px;'
    },
    legend: {
      show: series.length > 1,
      type: 'scroll',
      top: 0,
      triggerEvent: true,
      tooltip: { show: true },
      textStyle: { color: headingColor, fontSize: 11, fontWeight: 600 }
    },
    xAxis: horizontal ? value : category,
    yAxis: horizontal ? category : value,
    dataZoom: categories.length > 12 ? [{ type: 'slider', ...(horizontal ? { yAxisIndex: 0, right: 0, width: 12 } : { xAxisIndex: 0, bottom: 0, height: 18 }), start: 0, end: Math.min(100, 12 / categories.length * 100) }] : [],
    series: series.map(s => ({ barMaxWidth: 20, symbolSize: 5, connectNulls: false, ...s }))
  };
}
