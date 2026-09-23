export const palette = ['#7dd3fc', '#c4b5fd', '#99cbbb', '#e7bd83', '#b5bdca', '#e5a8bd'];
export const numeric = value => value == null || value === '' || !Number.isFinite(Number(value)) ? null : Number(value);
export const formatValue = (value, unit = '') => numeric(value) == null ? '—' : `${unit === '$' ? '$' : ''}${Number(value).toLocaleString(undefined, { maximumFractionDigits: 2 })}${unit && unit !== '$' ? ` ${unit}` : ''}`;
export function cartesian(categories, series, horizontal = false, unit = '') {
  const category = { type: 'category', data: categories, inverse: horizontal, axisTick: { show: false }, axisLabel: { hideOverlap: true, width: horizontal ? 115 : 90, overflow: 'truncate' } };
  const value = { type: 'value', axisLabel: { formatter: v => formatValue(v, unit) } };
  return { grid: { left: 12, right: 24, top: series.length > 1 ? 44 : 20, bottom: categories.length > 12 ? 48 : 20, containLabel: true },
    tooltip: { trigger: 'axis', valueFormatter: v => formatValue(v, unit) },
    legend: { show: series.length > 1, type: 'scroll', top: 0 },
    xAxis: horizontal ? value : category, yAxis: horizontal ? category : value,
    dataZoom: categories.length > 12 ? [{ type: 'slider', ...(horizontal ? { yAxisIndex: 0, right: 0, width: 12 } : { xAxisIndex: 0, bottom: 0, height: 18 }), start: 0, end: Math.min(100, 12 / categories.length * 100) }] : [],
    series: series.map(s => ({ barMaxWidth: 20, symbolSize: 5, connectNulls: false, ...s })) };
}
