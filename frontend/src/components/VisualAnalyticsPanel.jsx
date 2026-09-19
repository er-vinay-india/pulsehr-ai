import React, { useState } from 'react';
import MarkdownView from './MarkdownView';

// ============================================================================
// 1. McKinsey / GE 9-Box Talent & Risk Matrix Component
// ============================================================================
function Talent9BoxMatrix({ data }) {
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
            <span style={{ color: selectedCell.color, fontWeight: 700 }}>● {selectedCell.title}</span>
            <span className="drawer-subtitle">{selectedCell.roster.length} Staff Mapped ({selectedCell.pct}% of evaluated workforce)</span>
            <button className="btn-close-drilldown" onClick={() => setSelectedCell(null)}>✕</button>
          </div>
          <div className="roster-list-chips">
            {selectedCell.roster.map((person, pIdx) => (
              <div key={pIdx} className="roster-person-card">
                <span className="person-name">👤 {person.name}</span>
                <span className="person-dept">{person.department}</span>
                <span className="person-perf">Score: <strong>{person.performance} pts</strong></span>
                <span className={`person-risk risk-${person.risk_level?.toLowerCase()}`}>Risk: {person.risk_level}</span>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}

// ============================================================================
// 2. Bradford Factor Absenteeism Disruption Spectrum
// ============================================================================
function BradfordFactorChart({ data }) {
  const departments = data?.departments || [];
  const maxScore = Math.max(...departments.map(d => d.avg_bradford_score || 0), 250);

  return (
    <div className="bradford-spectrum-container">
      {/* Reference Tiers Legend */}
      <div className="bradford-tiers-legend">
        <span className="tier-tag tier-normal">● &lt; 50: Normal</span>
        <span className="tier-tag tier-moderate">● 51–200: Moderate</span>
        <span className="tier-tag tier-high">● 201–500: High Disruption</span>
        <span className="tier-tag tier-critical">● &gt; 500: Critical Escalation</span>
      </div>

      {/* Department Breakdown Bars */}
      <div className="bradford-dept-list">
        {departments.map((dept, idx) => {
          const score = dept.avg_bradford_score;
          const barWidthPct = Math.min(100, Math.max(8, (score / maxScore) * 100));

          let tierColor = '#10b981';
          let tierLabel = 'Normal';
          if (score > 500) { tierColor = '#f43f5e'; tierLabel = 'Critical Disruption'; }
          else if (score > 200) { tierColor = '#f59e0b'; tierLabel = 'High Disruption'; }
          else if (score > 50) { tierColor = '#06b6d4'; tierLabel = 'Moderate'; }

          return (
            <div key={idx} className="bradford-dept-row">
              <div className="dept-label-col">
                <span className="dept-name">{dept.department}</span>
                <span className="dept-headcount">{dept.headcount} staff · {dept.total_absent_days}d lost</span>
              </div>
              <div className="dept-bar-track">
                <div
                  className="dept-bar-fill"
                  style={{ width: `${barWidthPct}%`, backgroundColor: tierColor }}
                >
                  <span className="bar-val-text">{score} pts</span>
                </div>
              </div>
              <div className="dept-tier-badge" style={{ color: tierColor, borderColor: `${tierColor}55` }}>
                {tierLabel}
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
}

// ============================================================================
// 3. Workforce Workload & Burnout Strain Diagnostic
// ============================================================================
function BurnoutStrainChart({ data }) {
  const departments = data?.departments || [];

  return (
    <div className="burnout-strain-container">
      <div className="strain-header-note">
        <span>Sustainable Strain Threshold: <strong>&lt; 10%</strong></span>
        <span style={{ color: '#f43f5e', fontWeight: 600 }}>Critical Burnout Limit: <strong>&gt; 20%</strong></span>
      </div>

      <div className="strain-dept-grid">
        {departments.map((dept, idx) => {
          const strain = dept.strain_index_pct;
          const isCritical = strain >= 20.0;
          const isElevated = strain >= 10.0 && strain < 20.0;

          return (
            <div key={idx} className={`strain-dept-card ${isCritical ? 'critical' : (isElevated ? 'elevated' : 'sustainable')}`}>
              <div className="card-top">
                <span className="dept-title">{dept.department}</span>
                <span className="strain-badge" style={{ backgroundColor: dept.status_color }}>
                  {dept.status}
                </span>
              </div>
              <div className="strain-metric-val">
                <span className="big-pct">{strain}%</span>
                <span className="metric-label">Workload Strain</span>
              </div>
              <div className="strain-sub-stats">
                <span>Avg Overtime: <strong>{dept.avg_overtime_hours} hrs</strong></span>
                <span>Avg Absent: <strong>{dept.avg_absent_days} days</strong></span>
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
}

// ============================================================================
// 4. Statistical Cross-Sheet Elasticity & Tipping Point
// ============================================================================
function ElasticityChart({ data }) {
  return (
    <div className="elasticity-container">
      <div className="elasticity-kpi-grid">
        <div className="el-kpi-box">
          <span className="el-label">Empirical Penalty (β)</span>
          <span className="el-value" style={{ color: data.beta_coefficient < 0 ? '#f43f5e' : '#10b981' }}>
            {data.beta_coefficient} pts
          </span>
          <small>Performance loss per absent day</small>
        </div>
        <div className="el-kpi-box">
          <span className="el-label">Critical Tipping Point</span>
          <span className="el-value" style={{ color: '#f59e0b' }}>
            {data.tipping_point_days} Days
          </span>
          <small>Productivity steep degradation threshold</small>
        </div>
        <div className="el-kpi-box">
          <span className="el-label">Model Fit (R²)</span>
          <span className="el-value">
            {data.r_squared}
          </span>
          <small>Pearson r = {data.pearson_correlation}</small>
        </div>
        <div className="el-kpi-box">
          <span className="el-label">Matched Sample</span>
          <span className="el-value">
            {data.matched_records} Staff
          </span>
          <small>Verified cross-table equality joins</small>
        </div>
      </div>
    </div>
  );
}

// ============================================================================
// 5. Grouped Comparative Bar Chart (Cross-Sheet Intelligence)
// ============================================================================
function ComparativeBarChart({ data }) {
  const [hoveredIdx, setHoveredIdx] = useState(null);
  const items = data?.items || [];
  const series = data?.series || [
    { name: 'Metric 1', unit: '', color: '#10b981' },
    { name: 'Metric 2', unit: '', color: '#f43f5e' }
  ];

  if (!items.length) {
    return <div className="chart-empty">No comparative data points available.</div>;
  }

  const s1 = series[0];
  const s2 = series[1];
  const maxVal1 = Math.max(...items.map(d => d.val1 || 0), 1);
  const maxVal2 = Math.max(...items.map(d => d.val2 || 0), 1);

  const svgW = 560;
  const svgH = 210;
  const margin = { top: 25, right: 20, bottom: 42, left: 45 };
  const innerW = svgW - margin.left - margin.right;
  const innerH = svgH - margin.top - margin.bottom;

  const slotW = innerW / Math.max(items.length, 1);
  const barW = Math.min(22, slotW * 0.38);

  return (
    <div className="comparative-chart-wrap">
      <div className="chart-legend-row">
        <div className="legend-chip">
          <span className="chip-dot" style={{ backgroundColor: s1.color }} />
          <span className="chip-label">{s1.name} {s1.unit ? `(${s1.unit})` : ''}</span>
        </div>
        <div className="legend-chip">
          <span className="chip-dot" style={{ backgroundColor: s2.color }} />
          <span className="chip-label">{s2.name} {s2.unit ? `(${s2.unit})` : ''}</span>
        </div>
      </div>

      <div className="chart-svg-wrap">
        <svg viewBox={`0 0 ${svgW} ${svgH}`} className="responsive-svg">
          {[0, 0.25, 0.5, 0.75, 1].map((ratio) => (
            <line
              key={ratio}
              x1={margin.left}
              y1={margin.top + innerH * (1 - ratio)}
              x2={svgW - margin.right}
              y2={margin.top + innerH * (1 - ratio)}
              stroke="var(--border-color, #334155)"
              strokeDasharray="3 3"
              opacity={0.3}
            />
          ))}

          {items.map((d, i) => {
            const centerX = margin.left + i * slotW + slotW / 2;
            const x1 = centerX - barW - 2;
            const x2 = centerX + 2;

            const h1 = Math.max(3, (d.val1 / maxVal1) * innerH);
            const h2 = Math.max(3, (d.val2 / maxVal2) * innerH);

            const y1 = margin.top + innerH - h1;
            const y2 = margin.top + innerH - h2;
            const isHovered = hoveredIdx === i;

            return (
              <g
                key={i}
                onMouseEnter={() => setHoveredIdx(i)}
                onMouseLeave={() => setHoveredIdx(null)}
                style={{ cursor: 'pointer' }}
              >
                {isHovered && (
                  <rect
                    x={margin.left + i * slotW + 2}
                    y={margin.top}
                    width={slotW - 4}
                    height={innerH}
                    fill="var(--primary-color, #38bdf8)"
                    opacity={0.08}
                    rx="4"
                  />
                )}
                <rect x={x1} y={y1} width={barW} height={h1} rx="3" fill={s1.color} opacity={isHovered ? 1 : 0.85} />
                <text x={x1 + barW / 2} y={y1 - 4} textAnchor="middle" fontSize="9" fontWeight="600" fill={s1.color}>{d.val1}</text>

                <rect x={x2} y={y2} width={barW} height={h2} rx="3" fill={s2.color} opacity={isHovered ? 1 : 0.85} />
                <text x={x2 + barW / 2} y={y2 - 4} textAnchor="middle" fontSize="9" fontWeight="600" fill={s2.color}>{d.val2}</text>

                <text x={centerX} y={svgH - 12} textAnchor="middle" fontSize="10" fontWeight={isHovered ? '600' : '400'} fill={isHovered ? 'var(--text-bright, #fff)' : 'var(--text-muted, #94a3b8)'}>
                  {d.label.length > 10 ? `${d.label.slice(0, 9)}…` : d.label}
                </text>
              </g>
            );
          })}
        </svg>
      </div>

      {hoveredIdx != null && items[hoveredIdx] && (
        <div className="hover-tooltip-strip">
          <span className="tooltip-dept"><strong>{items[hoveredIdx].label}</strong>:</span>
          <span style={{ color: s1.color }}>{s1.name}: <strong>{items[hoveredIdx].val1} {s1.unit}</strong></span>
          <span className="tooltip-sep">·</span>
          <span style={{ color: s2.color }}>{s2.name}: <strong>{items[hoveredIdx].val2} {s2.unit}</strong></span>
        </div>
      )}
    </div>
  );
}

// ============================================================================
// 6. Longitudinal 712-Day Attendance Trajectory Forecast
// ============================================================================
function ForecastChart({ data }) {
  const [hoveredPt, setHoveredPt] = useState(null);
  const historical = data?.historical || [];
  const forecast = data?.forecast || [];
  const unit = data?.unit || '';
  const metrics = data?.metrics || {};

  const allPoints = [
    ...historical.map((p, i) => ({ ...p, isForecast: false, idx: i, val: p.actual })),
    ...forecast.map((p, i) => ({ ...p, isForecast: true, idx: historical.length + i, val: p.forecast }))
  ];

  if (!allPoints.length) {
    return <div className="chart-empty">No forecast trajectory available.</div>;
  }

  const svgW = 560;
  const svgH = 200;
  const margin = { top: 22, right: 25, bottom: 35, left: 45 };
  const innerW = svgW - margin.left - margin.right;
  const innerH = svgH - margin.top - margin.bottom;

  const minVal = Math.max(0, Math.min(...allPoints.map(p => Math.min(p.val, p.lower_95 != null ? p.lower_95 : p.val)), 0));
  const maxVal = Math.max(...allPoints.map(p => Math.max(p.val, p.upper_95 != null ? p.upper_95 : p.val)), 10) * 1.08;

  const getX = (i) => allPoints.length <= 1 ? margin.left + innerW / 2 : margin.left + (i / (allPoints.length - 1)) * innerW;
  const getY = (val) => margin.top + innerH - ((val - minVal) / (maxVal - minVal || 1)) * innerH;

  let histPath = '';
  historical.forEach((p, i) => {
    const x = getX(i);
    const y = getY(p.actual);
    histPath += i === 0 ? `M ${x} ${y}` : ` L ${x} ${y}`;
  });

  let forecastPath = '';
  if (historical.length > 0 && forecast.length > 0) {
    const lastHist = historical[historical.length - 1];
    forecastPath = `M ${getX(historical.length - 1)} ${getY(lastHist.actual)}`;
    forecast.forEach((p, i) => {
      forecastPath += ` L ${getX(historical.length + i)} ${getY(p.forecast)}`;
    });
  }

  let ciPolygon = '';
  if (historical.length > 0 && forecast.length > 0) {
    const lastHist = historical[historical.length - 1];
    const topPts = [`${getX(historical.length - 1)},${getY(lastHist.actual)}`];
    const botPts = [`${getX(historical.length - 1)},${getY(lastHist.actual)}`];
    forecast.forEach((p, i) => {
      topPts.push(`${getX(historical.length + i)},${getY(p.upper_95)}`);
      botPts.push(`${getX(historical.length + i)},${getY(p.lower_95)}`);
    });
    botPts.reverse();
    ciPolygon = topPts.concat(botPts).join(' ');
  }

  const trendClass = metrics.trend_direction?.toLowerCase().replace(/[^a-z]/g, '-') || 'stable';

  return (
    <div className="forecast-chart-wrap">
      <div className="forecast-badge-row">
        <span className={`trend-badge ${trendClass}`}>{metrics.trend_direction || 'Holt Damped Trend'}</span>
        <span className="forecast-chip">Shift: <strong>{metrics.projected_change_pct >= 0 ? `+${metrics.projected_change_pct}%` : `${metrics.projected_change_pct}%`}</strong></span>
        <span className="forecast-chip">Fit: <strong>R² = {metrics.r_squared}</strong></span>
      </div>

      <div className="chart-svg-wrap">
        <svg viewBox={`0 0 ${svgW} ${svgH}`} className="responsive-svg">
          <defs>
            <linearGradient id="forecastConeGrad2" x1="0" y1="0" x2="0" y2="1">
              <stop offset="0%" stopColor="#818cf8" stopOpacity="0.25" />
              <stop offset="100%" stopColor="#818cf8" stopOpacity="0.04" />
            </linearGradient>
          </defs>

          {[0, 0.33, 0.66, 1].map((ratio) => {
            const y = margin.top + innerH * (1 - ratio);
            const val = (minVal + (maxVal - minVal) * ratio).toFixed(1);
            return (
              <g key={ratio}>
                <line x1={margin.left} y1={y} x2={svgW - margin.right} y2={y} stroke="var(--border-color, #334155)" strokeDasharray="3 3" opacity={0.3} />
                <text x={margin.left - 6} y={y + 3} textAnchor="end" fontSize="9" fill="var(--text-muted, #94a3b8)">{val}</text>
              </g>
            );
          })}

          {ciPolygon && <polygon points={ciPolygon} fill="url(#forecastConeGrad2)" />}
          {histPath && <path d={histPath} fill="none" stroke="#06b6d4" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round" />}
          {forecastPath && <path d={forecastPath} fill="none" stroke="#f59e0b" strokeWidth="2.5" strokeDasharray="5 4" strokeLinecap="round" strokeLinejoin="round" />}

          {historical.map((p, i) => (
            <circle
              key={`h-${i}`}
              cx={getX(i)}
              cy={getY(p.actual)}
              r={hoveredPt?.idx === i ? 5 : 3}
              fill="#06b6d4"
              stroke="#0f172a"
              strokeWidth="1.5"
              onMouseEnter={() => setHoveredPt({ ...p, idx: i, val: p.actual, isForecast: false })}
              onMouseLeave={() => setHoveredPt(null)}
              style={{ cursor: 'pointer' }}
            />
          ))}

          {forecast.map((p, i) => {
            const idx = historical.length + i;
            return (
              <circle
                key={`f-${i}`}
                cx={getX(idx)}
                cy={getY(p.forecast)}
                r={hoveredPt?.idx === idx ? 5.5 : 3.5}
                fill="#f59e0b"
                stroke="#0f172a"
                strokeWidth="1.5"
                onMouseEnter={() => setHoveredPt({ ...p, idx, val: p.forecast, isForecast: true })}
                onMouseLeave={() => setHoveredPt(null)}
                style={{ cursor: 'pointer' }}
              />
            );
          })}
        </svg>
      </div>

      {hoveredPt && (
        <div className="hover-tooltip-strip">
          <span>{hoveredPt.period}: <strong>{hoveredPt.val} {unit}</strong> ({hoveredPt.isForecast ? 'Out-of-sample Forecast' : 'Historical Observation'})</span>
          {hoveredPt.lower_95 != null && (
            <span style={{ marginLeft: 8, color: 'var(--text-muted)' }}>[95% Range: {hoveredPt.lower_95} – {hoveredPt.upper_95}]</span>
          )}
        </div>
      )}
    </div>
  );
}

// ============================================================================
// MAIN VISUAL ANALYTICS PANEL COMPONENT (EXECUTIVE OVERVIEW)
// ============================================================================
export default function VisualAnalyticsPanel({ visualDashboard, charts, forecast, selectedSheetId }) {
  const [activeCategory, setActiveCategory] = useState('All');

  if (visualDashboard && visualDashboard.visualizations?.length > 0) {
    const allVis = visualDashboard.visualizations;
    const categories = visualDashboard.categories || ['All'];
    const catCounts = visualDashboard.category_counts || {};

    const filteredVis = activeCategory === 'All'
      ? allVis
      : allVis.filter(v => v.category === activeCategory);

    return (
      <div className="visual-analytics-panel">
        <div className="section-title-row">
          <div>
            <div style={{ display: 'flex', alignItems: 'center', gap: '0.6rem', flexWrap: 'wrap' }}>
              <h3>Industrial People Analytics & Strategic Diagnostic Suite</h3>
              <span className="badge-ai-count">{allVis.length} Formula Models Active</span>
            </div>
            <p className="subtitle">
              Verified industrial HR formulas: Bradford Factor Disruption, 9-Box Talent Matrix, Burnout Strain Ratios, and OLS Cross-Sheet Elasticity.
            </p>
          </div>
        </div>

        {/* Category Filter Pills */}
        <div className="dashboard-filter-bar">
          <span className="filter-label">Analytics Scope:</span>
          {categories.map((cat) => {
            const count = catCounts[cat] || (cat === 'All' ? allVis.length : 0);
            return (
              <button
                key={cat}
                className={`dashboard-filter-pill ${activeCategory === cat ? 'active' : ''}`}
                onClick={() => setActiveCategory(cat)}
              >
                <span>{cat}</span>
                <span className="pill-count-chip">{count}</span>
              </button>
            );
          })}
        </div>

        {/* Multi-Chart Gallery Grid */}
        <div className="visual-dashboard-grid">
          {filteredVis.map((v) => {
            const isCrossSheet = v.category === 'Cross-Sheet Intelligence';

            return (
              <div key={v.id} className={`visual-card ${isCrossSheet ? 'card-cross-sheet' : ''}`}>
                {/* Card Top Badges */}
                <div className="card-top-badges">
                  <span className={`sheet-source-badge ${isCrossSheet ? 'badge-cross-accent' : ''}`}>
                    {v.chart_type === 'talent_9box' && '🎯 '}
                    {v.chart_type === 'bradford_factor' && '⚠️ '}
                    {v.chart_type === 'burnout_strain' && '🔥 '}
                    {v.chart_type === 'elasticity' && '📐 '}
                    {v.chart_type === 'comparative_bar' && '🔗 '}
                    {v.chart_type === 'forecast' && '📈 '}
                    {v.sheet_badge}
                  </span>
                  <span className="category-pill-badge">{v.category}</span>
                  <span className="type-pill-badge">
                    {v.chart_type === 'talent_9box' && '9-Box Matrix'}
                    {v.chart_type === 'bradford_factor' && 'Disruption Index'}
                    {v.chart_type === 'burnout_strain' && 'Strain Gauge'}
                    {v.chart_type === 'elasticity' && 'OLS Regression'}
                    {v.chart_type === 'comparative_bar' && 'Grouped Comparative'}
                    {v.chart_type === 'forecast' && 'Longitudinal Trajectory'}
                  </span>
                </div>

                {/* Card Title & Subtitle */}
                <div className="card-title-group">
                  <h4>{v.title}</h4>
                  {v.subtitle && <p className="card-sub">{v.subtitle}</p>}
                </div>

                {/* Card Visual Body */}
                <div className="card-visual-body">
                  {v.chart_type === 'talent_9box' && (
                    <Talent9BoxMatrix data={v.talent_9box_data} />
                  )}
                  {v.chart_type === 'bradford_factor' && (
                    <BradfordFactorChart data={v.bradford_data} />
                  )}
                  {v.chart_type === 'burnout_strain' && (
                    <BurnoutStrainChart data={v.burnout_data} />
                  )}
                  {v.chart_type === 'elasticity' && (
                    <ElasticityChart data={v.elasticity_data} />
                  )}
                  {v.chart_type === 'comparative_bar' && (
                    <ComparativeBarChart data={v.comparative_data} />
                  )}
                  {v.chart_type === 'forecast' && (
                    <ForecastChart data={v.forecast_data} />
                  )}
                </div>

                {/* AI Strategic Takeaway Banner */}
                {v.ai_insight && (
                  <div className="chart-ai-insight-banner">
                    <div className="insight-header">
                      <span className="insight-icon">💡</span>
                      <span className="insight-title">AI Strategic Diagnostic</span>
                    </div>
                    <div className="insight-content">
                      <MarkdownView content={v.ai_insight} />
                    </div>
                  </div>
                )}

                {/* Stats Pills Row */}
                {v.stats_pills && v.stats_pills.length > 0 && (
                  <div className="card-stats-row">
                    {v.stats_pills.map((pill, pIdx) => (
                      <div key={pIdx} className="stat-pill-chip">
                        <span className="stat-pill-label">{pill.label}:</span>
                        <span className="stat-pill-value">{pill.value}</span>
                      </div>
                    ))}
                  </div>
                )}
              </div>
            );
          })}
        </div>
      </div>
    );
  }

  return null;
}
