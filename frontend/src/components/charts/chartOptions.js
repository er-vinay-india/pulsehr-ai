export const palette = ['#155EEF', '#22C7F2', '#14B8A6', '#84CC16', '#0B1F3A', '#005A6B', '#123B5D'];
export const hridayPalette = ['#0F766E', '#0891B2', '#3F7D20', '#102A43', '#B7791F'];

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
export function cartesian(categories, series, horizontal = false, unit = '') {
  const category = {
    type: 'category',
    data: categories,
    inverse: horizontal,
    axisTick: { show: false },
    axisLine: { lineStyle: { color: '#E2E8F0' } },
    axisLabel: {
      hideOverlap: true,
      width: horizontal ? 140 : 90,
      overflow: horizontal ? 'break' : 'truncate',
      color: '#334155',
      fontSize: 11
    }
  };
  const value = {
    type: 'value',
    axisLabel: {
      formatter: v => formatValue(v, unit),
      color: '#334155',
      fontSize: 11
    },
    splitLine: {
      lineStyle: {
        color: '#E2E8F0',
        type: 'dashed'
      }
    }
  };
  return {
    color: palette,
    grid: { left: 12, right: 24, top: series.length > 1 ? 44 : 20, bottom: categories.length > 12 ? 48 : 20, containLabel: true },
    tooltip: {
      trigger: 'axis',
      valueFormatter: v => formatFullValue(v, unit),
      backgroundColor: '#FFFFFF',
      borderColor: '#CBD5E1',
      borderWidth: 1,
      textStyle: { color: '#0B1F3A', fontSize: 12 },
      extraCssText: 'box-shadow: 0 4px 14px rgba(11, 31, 58, 0.12); border-radius: 8px;'
    },
    legend: {
      show: series.length > 1,
      type: 'scroll',
      top: 0,
      textStyle: { color: '#0B1F3A', fontSize: 11, fontWeight: 600 }
    },
    xAxis: horizontal ? value : category,
    yAxis: horizontal ? category : value,
    dataZoom: categories.length > 12 ? [{ type: 'slider', ...(horizontal ? { yAxisIndex: 0, right: 0, width: 12 } : { xAxisIndex: 0, bottom: 0, height: 18 }), start: 0, end: Math.min(100, 12 / categories.length * 100) }] : [],
    series: series.map(s => ({ barMaxWidth: 20, symbolSize: 5, connectNulls: false, ...s }))
  };
}
