import React from 'react';
import DataChart from './DataChart';
export default function ExecutiveTrendChart({ points = [], metricName = 'Trend', unit = '', baseline, height = 240 }) {
  return <DataChart type="line" items={points.map(p => ({ label: p.period || p.label, value: p.value }))} metric={metricName} unit={unit} baseline={baseline} height={height} />;
}
