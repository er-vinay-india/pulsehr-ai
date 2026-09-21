import React, { useMemo } from 'react';

export default function ComparativeBarChart({ data, onInvestigate }) {
  const items = data?.items || [];
  const series = data?.series || [];

  // Compute maximums per series for accurate proportional scaling
  const maxVal1 = Math.max(
    ...items.map((i) => Number(i.val1) || 0),
    1
  );
  const maxVal2 = Math.max(
    ...items.map((i) => Number(i.val2) || 0),
    1
  );

  const sortedItemsWithRanks = useMemo(() => {
    return items.map((item, idx) => ({
      ...item,
      rank: idx + 1
    }));
  }, [items]);

  const s1 = series[0] || { name: 'Performance Score', unit: 'pts', color: '#10b981' };
  const s2 = series[1] || { name: 'Absent Days', unit: 'days', color: '#f43f5e' };

  return (
    <div className="dynamic-bar-chart-wrap bounded-chart-container comparative-bar-chart-wrap">
      {/* Comparative Legend Toolbar */}
      <div className="comp-toolbar">
        <div className="comp-legend-group">
          <div className="comp-legend-badge">
            <span className="comp-dot" style={{ backgroundColor: s1.color || '#10b981' }} />
            <span className="comp-legend-title">{s1.name}</span>
            <span className="comp-legend-unit">({s1.unit})</span>
          </div>
          <div className="comp-legend-badge">
            <span className="comp-dot" style={{ backgroundColor: s2.color || '#f43f5e' }} />
            <span className="comp-legend-title">{s2.name}</span>
            <span className="comp-legend-unit">({s2.unit})</span>
          </div>
        </div>
        <div className="comp-meta-chip">
          <span className="badge-pulse">●</span> {items.length} Evaluated Departments
        </div>
      </div>

      {/* Grouped Comparative Bar Visual List */}
      <div className="dynamic-bars-list density-bars-fixed-list comp-bars-list">
        {sortedItemsWithRanks.map((item) => {
          const v1Num = Number(item.val1) || 0;
          const v2Num = Number(item.val2) || 0;
          const w1 = Math.min(100, Math.max(6, (v1Num / maxVal1) * 100));
          const w2 = Math.min(100, Math.max(6, (v2Num / maxVal2) * 100));

          return (
            <div
              key={item.rank}
              className="dynamic-bar-row comp-bar-row interactive-row"
              onClick={() =>
                onInvestigate &&
                onInvestigate({
                  entityType: 'department',
                  targetId: item.label,
                  metric: s1.name || 'Department Performance'
                })
              }
              title={`#${item.rank} ${item.label} · ${s1.name}: ${item.val1} ${s1.unit} · ${s2.name}: ${item.val2} ${s2.unit} · Click to investigate`}
            >
              {/* Rank Chip matching DynamicBarChart */}
              <span className={`bar-rank-badge ${item.rank <= 3 ? 'rank-podium' : ''}`}>
                #{item.rank}
              </span>

              {/* Department Entity Label matching DynamicBarChart */}
              <span className="dynamic-bar-label comp-bar-label" title={item.label}>
                {item.label}
              </span>

              {/* Grouped Dual Progress Tracks */}
              <div className="comp-dual-tracks">
                {/* Series 1 Track */}
                <div className="dynamic-track comp-single-track" title={`${s1.name}: ${item.val1} ${s1.unit}`}>
                  <div
                    className="dynamic-fill comp-fill-s1"
                    style={{
                      width: `${w1}%`,
                      backgroundColor: s1.color || '#10b981'
                    }}
                  >
                    <span className="dynamic-val comp-val-text">{item.val1} {s1.unit}</span>
                  </div>
                </div>

                {/* Series 2 Track */}
                <div className="dynamic-track comp-single-track" title={`${s2.name}: ${item.val2} ${s2.unit}`}>
                  <div
                    className="dynamic-fill comp-fill-s2"
                    style={{
                      width: `${w2}%`,
                      backgroundColor: s2.color || '#f43f5e'
                    }}
                  >
                    <span className="dynamic-val comp-val-text">{item.val2} {s2.unit}</span>
                  </div>
                </div>
              </div>

              {/* Dual Value Badges on Right */}
              <div className="comp-values-column">
                <span className="comp-val-pill s1" title={`${s1.name}: ${item.val1} ${s1.unit}`}>
                  {item.val1} {s1.unit}
                </span>
                <span className="comp-val-pill s2" title={`${s2.name}: ${item.val2} ${s2.unit}`}>
                  {item.val2} {s2.unit}
                </span>
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
}
