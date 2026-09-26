import React from 'react';
import SafeReactECharts from '../charts/SafeReactECharts';
import { numeric } from '../charts/chartOptions';
export default function ElasticityChart({ data, onInvestigate }) {
  const points = (data?.scatter_points || []).filter(p => numeric(p.absent_days) != null && numeric(p.performance) != null);
  if (!points.length) return <p>No paired observations available.</p>;
  return <div><p>Slope: {data?.beta_coefficient ?? '—'} · R²: {data?.r_squared ?? '—'}</p>
    <SafeReactECharts option={{
      backgroundColor: 'transparent',
      grid: { left: 55, right: 20, top: 24, bottom: 48 },
      tooltip: {
        trigger: 'item',
        renderMode: 'richText',
        backgroundColor: '#1c1815',
        borderColor: '#524940',
        textStyle: { color: '#ded5cb' },
        formatter: p => `${p.data.name}\nAbsent days: ${p.value[0]}\nPerformance: ${p.value[1]}`
      },
      xAxis: {
        type: 'value',
        name: 'Absent days',
        nameLocation: 'middle',
        nameGap: 28,
        nameTextStyle: { color: '#ded5cb' },
        axisLabel: { color: '#ded5cb' },
        splitLine: { lineStyle: { color: '#524940', type: 'dashed' } }
      },
      yAxis: {
        type: 'value',
        name: 'Performance',
        nameTextStyle: { color: '#ded5cb' },
        axisLabel: { color: '#ded5cb' },
        splitLine: { lineStyle: { color: '#524940', type: 'dashed' } }
      },
      series: [{
        type: 'scatter',
        symbolSize: 7,
        itemStyle: { color: '#ff8a62' },
        data: points.map(p => ({ name: p.name, value: [Number(p.absent_days), Number(p.performance)] })),
        ...(numeric(data?.tipping_point_days) != null ? {
          markLine: {
            symbol: 'none',
            lineStyle: { color: '#fbbb27', type: 'dashed', width: 2 },
            label: { color: '#ded5cb' },
            data: [{ xAxis: Number(data.tipping_point_days), name: 'Reported threshold' }]
          }
        } : {})
      }]
    }}
      onEvents={{ click: p => onInvestigate?.({ entityType: 'employee', targetId: p.data.name, metric: 'Performance Score' }) }} />
  </div>;
}
