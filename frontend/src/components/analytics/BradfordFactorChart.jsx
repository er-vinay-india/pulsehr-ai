import React from 'react';
import DataChart from '../charts/DataChart';
export default function BradfordFactorChart({ data, onInvestigate }) {
  return <DataChart items={(data?.departments || []).map(d => ({ label: d.department, value: d.avg_bradford_score }))}
    metric="Average Bradford score" unit="pts" onSelect={p => onInvestigate?.({ entityType: 'department', targetId: p.label, metric: 'Absent ( no of days )' })} />;
}
