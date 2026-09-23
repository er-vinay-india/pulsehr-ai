import DataChart from '../charts/DataChart';
import React, { useState, useMemo } from 'react';
import { PieChart, BarChart2, Table } from 'lucide-react';
import ChartDetailModal from './ChartDetailModal';

export default function DynamicDonutChart({ data, onInvestigate, metricName }) {
  const rawSlices = data?.slices || [];
  const total = data?.total || 0;
  const [viewMode, setViewMode] = useState('donut'); // 'donut' | 'ranked'
  const [showDetailModal, setShowDetailModal] = useState(false);

  const isHighCardinality = rawSlices.length > 6;

  // If >6 slices, group top 5 and group remaining into 'Other'
  const displaySlices = useMemo(() => {
    if (!isHighCardinality || viewMode === 'ranked') return rawSlices;
    const top5 = rawSlices.slice(0, 5);
    const rest = rawSlices.slice(5);
    const restCount = rest.reduce((acc, s) => acc + (s.count || 0), 0);
    const restPct = total > 0 ? ((restCount / total) * 100).toFixed(1) : 0;
    return [
      ...top5,
      {
        label: `Other (${rest.length} segments)`,
        count: restCount,
        pct: Number(restPct),
        color: '#64748b',
        isGrouped: true
      }
    ];
  }, [rawSlices, isHighCardinality, viewMode, total]);

  const slicesWithRanks = useMemo(() => {
    return rawSlices.map((s, idx) => ({
      rank: idx + 1,
      label: s.label,
      value: s.count
    }));
  }, [rawSlices]);

  return (
    <div className="dynamic-donut-wrap bounded-chart-container">
      {/* High Cardinality Switcher Bar */}
      {isHighCardinality && (
        <div className="donut-density-bar">
          <span className="donut-cardinality-badge">
            {rawSlices.length} Distinct Segments
          </span>
          <div className="donut-mode-toggle">
            <button
              type="button"
              className={`donut-toggle-btn ${viewMode === 'donut' ? 'active' : ''}`}
              onClick={() => setViewMode('donut')}
              title="Donut Composition View"
            >
              <PieChart size={12} />
              <span>Donut</span>
            </button>
            <button
              type="button"
              className={`donut-toggle-btn ${viewMode === 'ranked' ? 'active' : ''}`}
              onClick={() => setViewMode('ranked')}
              title="Ranked List View"
            >
              <BarChart2 size={12} />
              <span>Ranked List</span>
            </button>
            <button
              type="button"
              className="donut-toggle-btn"
              onClick={() => setShowDetailModal(true)}
              title="View full table"
            >
              <Table size={12} />
              <span>Table</span>
            </button>
          </div>
        </div>
      )}

      <DataChart type={viewMode === 'donut' ? 'donut' : 'bar'} items={displaySlices.map(s => ({ ...s, value: s.count }))} metric={metricName || 'Count'}
        onSelect={slice => slice && !slice.isGrouped && onInvestigate?.({ entityType: 'category', targetId: slice.label, metric: metricName })} />
      {/* Detail Table Modal */}
      <ChartDetailModal
        isOpen={showDetailModal}
        onClose={() => setShowDetailModal(false)}
        title="Categorical Distribution Composition"
        subtitle={`Full distribution across ${rawSlices.length} categories · Total count: ${total}`}
        items={slicesWithRanks}
        benchmarkTotal={total}
        unit="entries"
        entityLabel="Category"
        metricName={metricName || "Frequency Count"}
        population={`${total} total entries`}
        entityType="category"
        onInvestigate={onInvestigate}
      />
    </div>
  );
}
