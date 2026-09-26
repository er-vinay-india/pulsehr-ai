import React from 'react';
import SafeReactECharts from './SafeReactECharts';
import { cartesian, numeric, formatValue, formatFullValue, metricUnit, palette } from './chartOptions';
export default function DataChart({ items = [], type = 'bar', metric = 'Value', unit = '', onSelect, baseline, height = 300 }) {
  unit = metricUnit(metric, unit);
  if (!items.length) return <p className="executive-chart-empty">No chart data available.</p>;
  const pie = type === 'donut' || type === 'pie';
  const option = pie ? {
    color: palette,
    tooltip: {
      trigger: 'item',
      valueFormatter: v => formatFullValue(v, unit),
      backgroundColor: '#1c1815',
      borderColor: '#524940',
      textStyle: { color: '#fff9f2', fontSize: 12 }
    },
    legend: {
      type: 'scroll',
      bottom: 0,
      textStyle: { color: '#ded5cb', fontSize: 11 }
    },
    series: [{
      type: 'pie',
      name: metric,
      radius: type === 'donut' ? ['45%', '68%'] : '68%',
      center: ['50%', '44%'],
      label: { show: false },
      itemStyle: { borderColor: '#171412', borderWidth: 2 },
      data: items.filter(p => numeric(p.value) != null && Number(p.value) >= 0).map(p => ({ name: String(p.label), value: Number(p.value) }))
    }]
  } : cartesian(items.map(p => String(p.label)), [{ name: metric, type: type === 'line' ? 'line' : type === 'dot' ? 'scatter' : 'bar', data: items.map(p => numeric(p.value)),
    ...(numeric(baseline) != null ? { markLine: { symbol: 'none', label: { show: false }, data: [{ [type === 'line' ? 'yAxis' : 'xAxis']: Number(baseline) }] } } : {}) }], type !== 'line', unit);
  return <div style={{ minWidth: 0 }}>
    <SafeReactECharts option={option} style={{ height: type === 'dot' ? Math.max(height, Math.min(items.length, 12) * 48 + 60) : height, width: '100%' }} onEvents={{ click: p => onSelect?.(items.find(i => String(i.label) === p.name)) }} />
    {numeric(baseline) != null && <p style={{ fontSize: '0.8rem', color: '#cbd5e1', margin: '4px 0' }}>Dashed line: average <span tabIndex={0} title={formatFullValue(baseline, unit)} aria-label={formatFullValue(baseline, unit)}>{formatValue(baseline, unit)}</span></p>}
    <details className="chart-data-table"><summary>View data{onSelect ? ' and investigate' : ''}</summary><div style={{ maxHeight: 240, overflow: 'auto' }}><table><thead><tr><th>Category</th><th>{metric}</th></tr></thead><tbody>{items.map((p,i) => <tr key={i}><td>{onSelect ? <button type="button" onClick={() => onSelect(p)}>{p.label}</button> : p.label}</td><td title={formatFullValue(p.value, unit)} tabIndex={0} aria-label={formatFullValue(p.value, unit)}>{formatValue(p.value, unit)}</td></tr>)}</tbody></table></div></details>
  </div>;
}
