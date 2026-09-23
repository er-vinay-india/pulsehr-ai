import DataChart from '../charts/DataChart';
import React, { useState, useMemo } from 'react';
import { Table } from 'lucide-react';
import { formatDisplayLabel } from '../../utils/displayFormatters';
import ChartDetailModal from './ChartDetailModal';

export default function DynamicLineChart({ visualization, onInvestigate }) {
  const lineData = visualization.line_data || {};
  const points = lineData.points || [];
  const unit = visualization.unit || '';
  const isCurrency = unit === '$';
  const availableYears = lineData.available_years || [];
  const isDense = points.length > 30;

  const [rangeMode, setRangeMode] = useState('all');
  const [showDetailModal, setShowDetailModal] = useState(false);

  const activePoints = useMemo(() => {
    if (!isDense || rangeMode === 'all') return points;
    if (rangeMode === 'last52') return points.slice(-52);
    if (rangeMode.startsWith('year:')) {
      const yr = rangeMode.split(':')[1];
      return points.filter((p) => p.period.startsWith(yr));
    }
    return points;
  }, [points, isDense, rangeMode]);

  if (!points || points.length === 0) {
    return (
      <div className="dynamic-line-empty" style={{ padding: '2rem', textAlign: 'center', color: 'var(--text-muted)' }}>
        <p>No continuous chronological observations available for plotting.</p>
      </div>
    );
  }

  const values = activePoints.map(p => p.value).filter(v => v != null && Number.isFinite(Number(v))).map(Number);
  const rangeMean = values.length ? values.reduce((a, b) => a + b, 0) / values.length : null;

  const pointsWithRanks = (() => {
    return points.map((p, idx) => ({
      rank: idx + 1,
      label: p.period,
      value: p.value
    }));
  })();

  return (
    <div className="dynamic-line-chart-wrap bounded-chart-container">
      {/* Dense Time-Series Range Presets & Table Button */}
      {isDense && (
        <div className="line-range-toolbar">
          <div className="range-pills-group">
            <button
              type="button"
              className={`range-pill-btn ${rangeMode === 'all' ? 'active' : ''}`}
              onClick={() => setRangeMode('all')}
            >
              All ({points.length} periods)
            </button>
            <button
              type="button"
              className={`range-pill-btn ${rangeMode === 'last52' ? 'active' : ''}`}
              onClick={() => setRangeMode('last52')}
            >
              Last 52 periods
            </button>
            {availableYears.map((yr) => (
              <button
                key={yr}
                type="button"
                className={`range-pill-btn ${rangeMode === `year:${yr}` ? 'active' : ''}`}
                onClick={() => setRangeMode(`year:${yr}`)}
              >
                {yr}
              </button>
            ))}
          </div>

          <button
            type="button"
            className="btn-line-table-view"
            onClick={() => setShowDetailModal(true)}
            title="View complete time-series table"
          >
            <Table size={12} />
            <span>Table View</span>
          </button>
        </div>
      )}

      <DataChart type="line" items={activePoints.map(p => ({ label: p.period, value: p.value }))} unit={unit}
        metric={visualization.metric_label || formatDisplayLabel(visualization.metric_col || 'Measure')}
        onSelect={p => p && onInvestigate?.({ entityType: 'time_series', targetId: p.label, metric: visualization.metric_col || visualization.measured_metric, sheetId: visualization.sheet_ids?.[0] })} />
      {/* Detail Table Modal */}
      <ChartDetailModal
        isOpen={showDetailModal}
        onClose={() => setShowDetailModal(false)}
        title={visualization.title}
        subtitle={visualization.subtitle}
        items={pointsWithRanks}
        benchmarkMean={rangeMean}
        unit={unit}
        isCurrency={isCurrency}
        entityLabel="Period Date"
        metricName={visualization.metric_label || formatDisplayLabel(visualization.metric_col || visualization.measured_metric)}
        population={visualization.population}
        entityType="time_series"
        sheetId={visualization.sheet_ids?.[0]}
        onInvestigate={onInvestigate}
      />
    </div>
  );
}
