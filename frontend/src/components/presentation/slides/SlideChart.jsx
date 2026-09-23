import React from 'react';
import SafeReactECharts from '../../charts/SafeReactECharts';
import DataChart from '../../charts/DataChart';
import { cartesian, numeric } from '../../charts/chartOptions';
export default function SlideChart({ chart }) {
  if (!chart?.categories?.length || !chart.series?.length) return <p>No chart data available.</p>;
  const type = (chart.type || chart.chart_type || 'column').toLowerCase();
  const pie = ['pie', 'donut'].includes(type);
  return <div style={{ width: '100%', minWidth: 0 }}>
    {pie ? <DataChart type={type} items={chart.categories.map((label, i) => ({ label, value: chart.series[0].values?.[i] }))} unit={chart.unit} metric={chart.series[0].name} /> :
      <SafeReactECharts option={cartesian(chart.categories, chart.series.map(s => ({ name: s.name, type: type === 'line' ? 'line' : 'bar', data: chart.categories.map((_,i) => numeric(s.values?.[i])) })), ['bar', 'horizontal_bar'].includes(type), chart.unit)} />}
    {chart.aggregation_disclosure && <p className="chart-aggregation-note">{chart.aggregation_disclosure}</p>}
  </div>;
}
