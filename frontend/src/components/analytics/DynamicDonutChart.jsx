import React, { useState, useMemo } from 'react';
import { PieChart, BarChart2, Table } from 'lucide-react';
import ChartDetailModal from './ChartDetailModal';

export default function DynamicDonutChart({ data, onInvestigate, metricName }) {
  const rawSlices = data?.slices || [];
  const total = data?.total || 0;
  const [hoveredSlice, setHoveredSlice] = useState(null);
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

  let cumulativeAngle = 0;
  const radius = 60;
  const cx = 80;
  const cy = 80;

  const maxSliceCount = Math.max(...rawSlices.map((s) => s.count || 0), 1);

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

      {viewMode === 'donut' ? (
        <div className="donut-visual-content">
          <div className="donut-svg-col">
            <svg viewBox="0 0 160 160" className="donut-svg">
              {displaySlices.map((slice, idx) => {
                const angle = (slice.count / (total || 1)) * 360;
                const startAngle = cumulativeAngle;
                cumulativeAngle += angle;

                const rad1 = ((startAngle - 90) * Math.PI) / 180.0;
                const rad2 = ((startAngle + angle - 90) * Math.PI) / 180.0;

                const x1 = cx + radius * Math.cos(rad1);
                const y1 = cy + radius * Math.sin(rad1);
                const x2 = cx + radius * Math.cos(rad2);
                const y2 = cy + radius * Math.sin(rad2);

                const largeArc = angle > 180 ? 1 : 0;
                const d = `M ${cx} ${cy} L ${x1} ${y1} A ${radius} ${radius} 0 ${largeArc} 1 ${x2} ${y2} Z`;

                return (
                  <path
                    key={idx}
                    d={d}
                    fill={slice.color}
                    opacity={hoveredSlice?.label === slice.label ? 1 : 0.85}
                    stroke="#0f172a"
                    strokeWidth="2"
                    onMouseEnter={() => setHoveredSlice(slice)}
                    onMouseLeave={() => setHoveredSlice(null)}
                    onClick={() =>
                      !slice.isGrouped &&
                      onInvestigate &&
                      onInvestigate({
                        entityType: 'category',
                        targetId: slice.label,
                        metric: metricName
                      })
                    }
                    style={{ cursor: slice.isGrouped ? 'default' : 'pointer' }}
                  />
                );
              })}
              {/* Inner cutout for donut hole */}
              <circle cx={cx} cy={cy} r="35" fill="var(--surface-primary, #0f172a)" />
              <text x={cx} y={cy - 2} textAnchor="middle" fill="var(--fg-primary)" fontSize="14" fontWeight="700">
                {total}
              </text>
              <text x={cx} y={cy + 12} textAnchor="middle" fill="var(--fg-secondary)" fontSize="9">
                Total
              </text>
            </svg>
          </div>

          <div className="donut-legend-col">
            {displaySlices.map((slice, idx) => (
              <div
                key={idx}
                className={`donut-legend-row ${hoveredSlice?.label === slice.label ? 'highlighted' : ''}`}
                onMouseEnter={() => setHoveredSlice(slice)}
                onMouseLeave={() => setHoveredSlice(null)}
                onClick={() =>
                  !slice.isGrouped &&
                  onInvestigate &&
                  onInvestigate({
                    entityType: 'category',
                    targetId: slice.label,
                    metric: metricName
                  })
                }
              >
                <span className="legend-chip-dot" style={{ backgroundColor: slice.color }} />
                <span className="legend-label">{slice.label}</span>
                <span className="legend-count">{slice.count}</span>
                <span className="legend-pct">({slice.pct}%)</span>
              </div>
            ))}
          </div>
        </div>
      ) : (
        /* Ranked List View for Donut Data */
        <div className="donut-ranked-list density-bars-scroll-list">
          {rawSlices.map((slice, idx) => {
            const pct = Math.min(100, Math.max(6, (slice.count / maxSliceCount) * 100));
            return (
              <div
                key={idx}
                className="dynamic-bar-row interactive-row"
                onClick={() =>
                  onInvestigate &&
                  onInvestigate({
                    entityType: 'category',
                    targetId: slice.label,
                    metric: metricName
                  })
                }
              >
                <span className="bar-rank-badge">#{idx + 1}</span>
                <span className="dynamic-bar-label">{slice.label}</span>
                <div className="dynamic-track">
                  <div className="dynamic-fill" style={{ width: `${pct}%`, backgroundColor: slice.color }}>
                    <span className="dynamic-val">{slice.count} ({slice.pct}%)</span>
                  </div>
                </div>
              </div>
            );
          })}
        </div>
      )}

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
