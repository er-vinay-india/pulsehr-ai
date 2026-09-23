import React from 'react';
import DataChart from './DataChart';
export default function ExecutiveBarComparisonChart({ groups = [], metricName = 'Comparison', baseline, unit = '', height = 260 }) {
  return <DataChart items={groups.map(g => ({ label: g.group || g.label, value: g.value }))} metric={metricName} unit={unit} baseline={baseline} height={height} />;
}
