import React, { useState } from 'react';

export default function RelationalInsightCard({ relationalData }) {
  if (!relationalData) return null;

  const [activeQuadrant, setActiveQuadrant] = useState('burnout_risk');

  const {
    left_sheet_name = '',
    right_sheet_name = '',
    matching_pairs = 0,
    correlation = null,
    narrative = '',
    quadrants = { burnout_risk: [], attrition_risk: [], core_anchors: [], underperforming: [] },
    model_used = ''
  } = relationalData;

  const quadrantConfigs = [
    {
      key: 'burnout_risk',
      title: 'Burnout Risk',
      subtitle: 'High Performance · High Absence',
      count: quadrants.burnout_risk?.length || 0,
      badgeColor: '#f97316',
      icon: '🔥',
      desc: 'Top talent putting in extra effort but showing heavy absence signals. High vulnerability to fatigue.'
    },
    {
      key: 'attrition_risk',
      title: 'Attrition Risk',
      subtitle: 'Sub-threshold Rating · High Absence',
      count: quadrants.attrition_risk?.length || 0,
      badgeColor: '#ef4444',
      icon: '⚠️',
      desc: 'Employees with declining ratings paired with recurring absences. Candidate for proactive engagement intervention.'
    },
    {
      key: 'core_anchors',
      title: 'Core Anchors',
      subtitle: 'High Performance · Dependable Attendance',
      count: quadrants.core_anchors?.length || 0,
      badgeColor: '#10b981',
      icon: '⚓',
      desc: 'Solid operational pillars with strong ratings and steady attendance.'
    },
    {
      key: 'underperforming',
      title: 'Development Focus',
      subtitle: 'Lower Rating · Normal Attendance',
      count: quadrants.underperforming?.length || 0,
      badgeColor: '#64748b',
      icon: '🎯',
      desc: 'Present and dependable, but require targeted upskilling or role realignment.'
    }
  ];

  const activeQuadrantObj = quadrantConfigs.find(q => q.key === activeQuadrant) || quadrantConfigs[0];
  const activeEmployees = quadrants[activeQuadrant] || [];

  // Format simple markdown
  const formatMarkdown = (text) => {
    if (!text) return null;
    return text.split('\n').map((line, i) => {
      const trimmed = line.trim();
      if (!trimmed) return <div key={i} style={{ height: '6px' }} />;
      if (trimmed.startsWith('### ')) {
        return <h4 key={i} className="story-heading-3">{trimmed.replace('### ', '')}</h4>;
      }
      if (trimmed.startsWith('- ') || trimmed.startsWith('* ')) {
        return (
          <li
            key={i}
            className="story-bullet"
            dangerouslySetInnerHTML={{
              __html: trimmed.substring(2).replace(/\*\*(.*?)\*\*/g, '<strong>$1</strong>')
            }}
          />
        );
      }
      return (
        <p
          key={i}
          className="story-paragraph"
          dangerouslySetInnerHTML={{
            __html: trimmed.replace(/\*\*(.*?)\*\*/g, '<strong>$1</strong>')
          }}
        />
      );
    });
  };

  return (
    <div className="card-panel relational-panel" style={{ marginTop: '20px' }}>
      <div className="panel-header">
        <div>
          <div className="relational-title-row">
            <h3>Cross-Sheet Relational Intelligence</h3>
            <span className="relationship-tag">
              {left_sheet_name} ↔ {right_sheet_name} ({matching_pairs} matched employees)
            </span>
            {correlation != null && (
              <span className={`correlation-pill ${correlation < 0 ? 'negative' : 'positive'}`}>
                Pearson r = {correlation} {correlation < 0 ? '(Inverted Correlation)' : '(Positive Correlation)'}
              </span>
            )}
          </div>
          <p className="panel-sub">
            AI relationship mining connecting workforce attendance records directly with performance ratings.
          </p>
        </div>
      </div>

      {/* Relational Narrative */}
      <div className="relational-narrative-box">
        {formatMarkdown(narrative)}
      </div>

      {/* 4-Quadrant Talent Matrix */}
      <div className="quadrant-section">
        <div className="quadrant-header">
          <h4>4-Quadrant Talent Classification Matrix</h4>
          <span className="text-muted">Click any quadrant to inspect employee segment</span>
        </div>

        <div className="quadrant-grid">
          {quadrantConfigs.map((q) => {
            const isSelected = activeQuadrant === q.key;
            return (
              <div
                key={q.key}
                className={`quadrant-card ${isSelected ? 'selected' : ''}`}
                onClick={() => setActiveQuadrant(q.key)}
                style={{
                  borderLeftColor: q.badgeColor,
                  background: isSelected ? 'var(--bg-card-selected, rgba(255,255,255,0.05))' : 'var(--bg-card-alt, rgba(255,255,255,0.02))'
                }}
              >
                <div className="quadrant-top">
                  <span className="quadrant-icon">{q.icon}</span>
                  <span className="quadrant-count" style={{ color: q.badgeColor }}>
                    {q.count}
                  </span>
                </div>
                <div className="quadrant-title" style={{ color: isSelected ? q.badgeColor : 'inherit' }}>
                  {q.title}
                </div>
                <div className="quadrant-sub">{q.subtitle}</div>
                <div className="quadrant-desc">{q.desc}</div>
              </div>
            );
          })}
        </div>

        {/* Selected Quadrant Employee Drill-down */}
        <div className="quadrant-drilldown">
          <div className="drilldown-header">
            <div>
              <strong>{activeQuadrantObj.icon} {activeQuadrantObj.title} Roster ({activeEmployees.length} employees)</strong>
              <p className="text-muted"><small>{activeQuadrantObj.desc}</small></p>
            </div>
          </div>

          {activeEmployees.length === 0 ? (
            <p className="text-muted" style={{ padding: '12px 0' }}>No employees currently matched in this quadrant.</p>
          ) : (
            <div className="quadrant-table-wrap">
              <table className="quadrant-table">
                <thead>
                  <tr>
                    <th>Employee Name / Key</th>
                    <th>Department</th>
                    <th>Absent Days</th>
                    <th>Performance Rating</th>
                  </tr>
                </thead>
                <tbody>
                  {activeEmployees.slice(0, 15).map((emp, i) => (
                    <tr key={i}>
                      <td><strong>{emp.name}</strong></td>
                      <td><span className="dept-tag">{emp.dept}</span></td>
                      <td><code>{emp.absent} days</code></td>
                      <td>
                        <span className="perf-badge" style={{ color: emp.perf >= 6 ? '#10b981' : '#f59e0b' }}>
                          ★ {emp.perf}
                        </span>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
              {activeEmployees.length > 15 && (
                <div className="table-more-hint">
                  <small>Showing top 15 of {activeEmployees.length} matched employees.</small>
                </div>
              )}
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
