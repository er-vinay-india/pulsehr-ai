import React, { useState } from 'react';

export default function RelationalInsightCard({ relationalData }) {
  if (!relationalData) return null;

  const {
    left_sheet_name = '',
    right_sheet_name = '',
    matching_pairs = 0,
    metric_x = 'Measure A',
    metric_y = 'Measure B',
    unit_x = '',
    unit_y = '',
    correlation = null,
    quadrant_configs = {},
    quadrants = {},
    narrative = '',
    model_used = ''
  } = relationalData;

  const quadrantKeys = Object.keys(quadrants).length > 0 ? Object.keys(quadrants) : ['q1', 'q2', 'q3', 'q4'];
  const [activeQuadrant, setActiveQuadrant] = useState(quadrantKeys[0] || 'q1');

  const quadrantConfigs = quadrantKeys.map((k) => {
    const conf = quadrant_configs[k] || {};
    return {
      key: k,
      title: conf.title || `Quadrant ${k.toUpperCase()}`,
      subtitle: conf.subtitle || `${metric_x} vs ${metric_y}`,
      count: quadrants[k]?.length || 0,
      badgeColor: conf.badgeColor || '#38bdf8',
      icon: conf.icon || '📊',
      desc: conf.desc || `Entities segmented by ${metric_x} and ${metric_y}.`
    };
  });

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
      if (trimmed.startsWith('#### ')) {
        return <h5 key={i} className="story-heading-4">{trimmed.replace('#### ', '')}</h5>;
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
              {left_sheet_name} ↔ {right_sheet_name} ({matching_pairs} matched records)
            </span>
            {correlation != null && (
              <span className={`correlation-pill ${correlation < 0 ? 'negative' : 'positive'}`}>
                Pearson r = {correlation} {correlation < 0 ? '(Inverted Correlation)' : '(Positive Correlation)'}
              </span>
            )}
          </div>
          <p className="panel-sub">
            AI relationship mining connecting <strong>{metric_x}</strong> with <strong>{metric_y}</strong> across joined workforce records.
          </p>
        </div>
      </div>

      {/* Relational Narrative */}
      <div className="relational-narrative-box">
        {formatMarkdown(narrative)}
      </div>

      {/* 4-Quadrant Matrix */}
      <div className="quadrant-section">
        <div className="quadrant-header">
          <h4>4-Quadrant Dynamic Segmentation: {metric_x} vs {metric_y}</h4>
          <span className="text-muted">Click any quadrant to inspect the matched roster</span>
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
                  background: isSelected ? 'var(--bg-card-selected, rgba(255,255,255,0.06))' : 'var(--bg-card-alt, rgba(255,255,255,0.02))'
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

        {/* Selected Quadrant Entity Drill-down */}
        <div className="quadrant-drilldown">
          <div className="drilldown-header">
            <div>
              <strong>{activeQuadrantObj?.icon} {activeQuadrantObj?.title} ({activeEmployees.length} entities)</strong>
              <p className="text-muted"><small>{activeQuadrantObj?.desc}</small></p>
            </div>
          </div>

          {activeEmployees.length === 0 ? (
            <p className="text-muted" style={{ padding: '12px 0' }}>No entities currently matched in this quadrant.</p>
          ) : (
            <div className="quadrant-table-wrap">
              <table className="quadrant-table">
                <thead>
                  <tr>
                    <th>Entity / Key</th>
                    <th>Department</th>
                    <th>{metric_x} ({unit_x})</th>
                    <th>{metric_y} ({unit_y})</th>
                  </tr>
                </thead>
                <tbody>
                  {activeEmployees.slice(0, 20).map((emp, i) => (
                    <tr key={i}>
                      <td><strong>{emp.name}</strong></td>
                      <td><span className="dept-tag">{emp.dept}</span></td>
                      <td><code>{emp.val_x != null ? emp.val_x : emp.absent} {unit_x}</code></td>
                      <td>
                        <span className="perf-badge">
                          {emp.val_y != null ? emp.val_y : emp.perf} {unit_y}
                        </span>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
              {activeEmployees.length > 20 && (
                <div className="table-more-hint">
                  <small>Showing top 20 of {activeEmployees.length} matched entities.</small>
                </div>
              )}
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
