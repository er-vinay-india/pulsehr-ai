import React from 'react';
import SafeReactECharts from '../charts/SafeReactECharts';
import { numeric } from '../charts/chartOptions';
export default function ElasticityChart({ data, onInvestigate }) {
  const points = (data?.scatter_points || []).filter(p => numeric(p.absent_days) != null && numeric(p.performance) != null);
  if (!points.length) return <p>No paired observations available.</p>;
  return <div><p>Slope: {data?.beta_coefficient ?? '—'} · R²: {data?.r_squared ?? '—'}</p>
    <SafeReactECharts option={{ grid: { left: 55, right: 20, top: 24, bottom: 48 }, tooltip: { trigger: 'item', renderMode: 'richText', formatter: p => `${p.data.name}\nAbsent days: ${p.value[0]}\nPerformance: ${p.value[1]}` },
      xAxis: { type: 'value', name: 'Absent days', nameLocation: 'middle', nameGap: 28 }, yAxis: { type: 'value', name: 'Performance' },
      series: [{ type: 'scatter', symbolSize: 7, data: points.map(p => ({ name: p.name, value: [Number(p.absent_days), Number(p.performance)] })),
        ...(numeric(data?.tipping_point_days) != null ? { markLine: { symbol: 'none', data: [{ xAxis: Number(data.tipping_point_days), name: 'Reported threshold' }] } } : {}) }] }}
      onEvents={{ click: p => onInvestigate?.({ entityType: 'employee', targetId: p.data.name, metric: 'Performance Score' }) }} />
  </div>;
}
