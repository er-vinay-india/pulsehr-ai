import React from 'react';
import DataChart from './DataChart';
export default function ExecutiveDonutChart({ slices = [], metricName = 'Composition', height = 250, unit = '' }) {
  return <DataChart type="donut" items={slices.map(s => ({ label: s.label || s.name, value: s.count ?? s.value }))} metric={metricName} unit={unit} height={height} />;
}
