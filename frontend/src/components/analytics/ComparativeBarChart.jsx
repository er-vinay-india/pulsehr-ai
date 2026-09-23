import React from 'react';
import DataChart from '../charts/DataChart';
export default function ComparativeBarChart({ data, onInvestigate }) {
  const items = data?.items || [];
  return <div>{(data?.series || []).slice(0, 2).map((s, index) => <section key={index}>
    <h4>{s.name}{s.unit ? ` (${s.unit})` : ''}</h4>
    <DataChart items={items.map(i => ({ label: i.label, value: i[`val${index + 1}`] }))} metric={s.name} unit={s.unit}
      onSelect={p => onInvestigate?.({ entityType: 'department', targetId: p.label, metric: s.name })} />
  </section>)}</div>;
}
