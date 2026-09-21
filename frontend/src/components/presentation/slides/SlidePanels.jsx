import React from "react";

export function SlideTalent9BoxMatrix({ data, theme }) {
  const cells = data?.cells || [];
  return (
    <div className="slide-9box-container">
      <div className="slide-9box-grid">
        {cells.map((cell) => {
          const hasStaff = cell.count > 0;
          return (
            <div
              key={cell.key}
              className={`slide-9box-cell ${hasStaff ? 'has-staff' : ''}`}
              style={{ borderTop: `3px solid ${cell.color || theme?.brand_color || '#ff8a62'}` }}
            >
              <div className="cell-header-line">
                <span className="cell-title">{cell.title}</span>
                <span className="cell-count-pill" style={{ backgroundColor: cell.color || theme?.brand_color || '#ff8a62' }}>
                  {cell.count}
                </span>
              </div>
              <div className="cell-sub">{cell.desc || `${cell.count} staff`}</div>
            </div>
          );
        })}
      </div>
    </div>
  );
}

export function SlideBurnoutStrainPanel({ data, theme }) {
  const depts = data?.departments || [];
  return (
    <div className="slide-strain-list">
      {depts.slice(0, 6).map((d, idx) => {
        const pct = Math.min(100, Math.max(0, Number(d.strain_index_pct || d.strain_pct || 0)));
        const isHigh = pct >= 20;
        const barColor = isHigh ? (theme?.danger_color || '#ef4444') : (theme?.brand_color || '#ff8a62');
        return (
          <div key={idx} className="slide-strain-item">
            <div className="strain-meta-line">
              <span className="strain-dept-name">{d.department || d.name || `Dept ${idx + 1}`}</span>
              <span className="strain-pct-val" style={{ color: barColor }}>{pct.toFixed(1)}%</span>
            </div>
            <div className="strain-progress-track">
              <div
                className="strain-progress-bar"
                style={{ width: `${pct}%`, backgroundColor: barColor }}
              />
            </div>
          </div>
        );
      })}
    </div>
  );
}
