import React from 'react';
import SafeReactECharts from '../charts/SafeReactECharts';
import { cartesian, numeric } from '../charts/chartOptions';
export default function ForecastChart({ data }) {
  const history = data?.historical || [], forecast = data?.forecast || [];
  if (!history.length && !forecast.length) return <p>No forecast data available.</p>;
  const option = cartesian([...history, ...forecast].map(p => p.period), [
    { name: 'Observed', type: 'line', data: [...history.map(p => numeric(p.actual)), ...forecast.map(() => null)] },
    { name: 'Forecast', type: 'line', lineStyle: { type: 'dashed' }, data: [...history.map((p,i) => i === history.length - 1 ? numeric(p.actual) : null), ...forecast.map(p => numeric(p.forecast))] },
    { name: 'Lower 95% bound', type: 'line', symbol: 'none', lineStyle: { type: 'dotted' }, data: [...history.map(() => null), ...forecast.map(p => numeric(p.lower_95))] },
    { name: 'Upper 95% bound', type: 'line', symbol: 'none', lineStyle: { type: 'dotted' }, data: [...history.map(() => null), ...forecast.map(p => numeric(p.upper_95))] }
  ], false, data?.unit || '');
  return <SafeReactECharts option={option} />;
}
