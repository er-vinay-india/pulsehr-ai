import React, { useState } from 'react';

export default function Talent9BoxMatrix({ data, onInvestigate }) {
  const [selectedCell, setSelectedCell] = useState(null);
  const cells = data?.cells || [];

  return (
    <div className="talent-9box-container">
      <div className="talent-9box-grid">
        {cells.map((cell) => {
          const isSelected = selectedCell?.id === cell.id;
          const hasStaff = cell.count > 0;

          return (
            <div
              key={cell.key}
              className={`box-cell ${isSelected ? 'active' : ''} ${hasStaff ? 'has-staff' : ''}`}
              style={{ borderTop: `3px solid ${cell.color}` }}
              onClick={() => setSelectedCell(isSelected ? null : cell)}
              role="button"
              tabIndex={0}
              onKeyDown={(e) => e.key === 'Enter' && setSelectedCell(isSelected ? null : cell)}
              aria-label={`${cell.title}: ${cell.count} staff`}
            >
              <div className="cell-top">
                <span className="cell-title">{cell.title}</span>
                <span className="cell-count-badge" style={{ backgroundColor: cell.color }}>
                  {cell.count}
                </span>
              </div>
              <p className="cell-desc">{cell.desc}</p>
              {hasStaff && (
                <span className="cell-action-hint">
                  {isSelected ? 'Hide Roster ▲' : `View ${cell.count} Personnel ▼`}
                </span>
              )}
            </div>
          );
        })}
      </div>

      {/* Roster Drilldown Panel when a cell is clicked */}
      {selectedCell && selectedCell.roster && selectedCell.roster.length > 0 && (
        <div className="roster-drilldown-drawer">
          <div className="drawer-header">
            <div>
              <span style={{ color: selectedCell.color, fontWeight: 700 }}>● {selectedCell.title}</span>
              <span className="drawer-subtitle" style={{ marginLeft: 8 }}>
                {selectedCell.roster.length} Staff Mapped ({selectedCell.pct}% of evaluated workforce)
              </span>
            </div>
            <button className="btn-close-drilldown" onClick={() => setSelectedCell(null)}>✕</button>
          </div>
          <div className="roster-list-chips">
            {selectedCell.roster.map((person, pIdx) => (
              <div
                key={pIdx}
                className="roster-person-card interactive-chip"
                onClick={() =>
                  onInvestigate &&
                  onInvestigate({
                    entityType: 'employee',
                    targetId: person.name,
                    metric: 'Performance Score'
                  })
                }
                title="Click to view full individual evidence profile"
              >
                <div className="person-row-top">
                  <span className="person-name">👤 {person.name}</span>
                  <span className={`person-risk risk-${person.risk_level?.toLowerCase()}`}>{person.risk_level} Risk</span>
                </div>
                <div className="person-row-sub">
                  <span className="person-dept">{person.department}</span>
                  <span className="person-perf">Score: <strong>{person.performance} pts</strong></span>
                </div>
                <span className="chip-action-text">Investigate Record →</span>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}
