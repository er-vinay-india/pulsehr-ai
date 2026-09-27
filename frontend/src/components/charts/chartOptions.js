export const lightPalette = [
  '#005A6B', // Accessible Teal (7.7:1 on #FFFFFF - AAA)
  '#123B5D', // Deep Blue (11.2:1 on #FFFFFF - AAA)
  '#365314', // Accessible Green (7.8:1 on #FFFFFF - AAA)
  '#155EEF', // Primary Blue (4.8:1 on #FFFFFF - AA)
  '#0F766E', // Dark Teal (5.4:1 on #FFFFFF - AA)
  '#0B1F3A', // Deep Navy (16.9:1 on #FFFFFF - AAA)
  '#6B21A8', // Deep Purple (10.0:1 on #FFFFFF - AAA)
  '#C2410C', // Rust Amber (4.8:1 on #FFFFFF - AA)
];

export const darkPalette = [
  '#5EEAD4', // Interactive Teal (12.1:1 on #0F1B2D - AAA)
  '#93C5FD', // Interactive Blue (9.8:1 on #0F1B2D - AAA)
  '#2DD4BF', // Mint Teal (9.5:1 on #0F1B2D - AAA)
  '#60A5FA', // Electric Blue (7.0:1 on #0F1B2D - AAA)
  '#C084FC', // Soft Violet (6.7:1 on #0F1B2D - AA)
  '#F8FAFC', // Pure Slate (16.6:1 on #0F1B2D - AAA)
  '#38BDF8', // Bright Sky (9.8:1 on #0F1B2D - AAA)
  '#FBBF24', // Warm Amber (10.5:1 on #0F1B2D - AAA)
];

export const palette = lightPalette;
export const hridayPalette = ['#0F766E', '#0891B2', '#365314', '#102A43', '#B7791F'];
export const hridayDarkPalette = ['#2DD4BF', '#5EEAD4', '#A3E635', '#F8FAFC', '#FBBF24'];

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
  const activePalette = isDark ? darkPalette : lightPalette;
  const textColor = isDark ? '#CBD5E1' : '#334155';
  const headingColor = isDark ? '#F8FAFC' : '#0B1F3A';
  const lineColor = isDark ? '#26384D' : '#CBD5E1';
  const splitLineColor = isDark ? 'rgba(248, 250, 252, 0.08)' : 'rgba(11, 31, 58, 0.08)';
  const tooltipBg = isDark ? '#172A40' : '#FFFFFF';
  const tooltipBorder = isDark ? '#26384D' : '#CBD5E1';

  const category = {
    type: 'category',
    data: categories,
    inverse: horizontal,
    axisTick: { show: false },
    axisLine: { lineStyle: { color: lineColor } },
    axisLabel: {
      hideOverlap: true,
      width: horizontal ? 140 : 90,
      overflow: horizontal ? 'break' : 'truncate',
      color: textColor,
      fontSize: 11
    }
  };
  const value = {
    type: 'value',
    axisLabel: {
      formatter: v => formatValue(v, unit),
      color: textColor,
      fontSize: 11
    },
    splitLine: {
      lineStyle: {
        color: splitLineColor,
        type: 'dashed'
      }
    }
  };
  return {
    color: activePalette,
    grid: { left: 12, right: 24, top: series.length > 1 ? 44 : 20, bottom: categories.length > 12 ? 48 : 20, containLabel: true },
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
      textStyle: { color: headingColor, fontSize: 11, fontWeight: 600 }
    },
    xAxis: horizontal ? value : category,
    yAxis: horizontal ? category : value,
    dataZoom: categories.length > 12 ? [{ type: 'slider', ...(horizontal ? { yAxisIndex: 0, right: 0, width: 12 } : { xAxisIndex: 0, bottom: 0, height: 18 }), start: 0, end: Math.min(100, 12 / categories.length * 100) }] : [],
    series: series.map(s => ({ barMaxWidth: 20, symbolSize: 5, connectNulls: false, ...s }))
  };
}
