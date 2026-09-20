import React, { useState } from 'react';
import {
  FileSpreadsheet,
  Layers,
  Search,
  ExternalLink,
  ChevronRight,
  TrendingUp,
  AlertCircle
} from 'lucide-react';
import MarkdownView from './MarkdownView';

// ============================================================================
// Standard Evidence Identification Bar Component
// ============================================================================
function ChartEvidenceHeader({ visualization, onInvestigate }) {
  const metric = visualization.measured_metric || visualization.title;
  const unit = visualization.unit || 'units';
  const pop = visualization.population || 'All Active Records';
  const sources = visualization.source_sheets || [visualization.sheet_badge];
  const coverage = visualization.coverage_pct != null ? `${visualization.coverage_pct}%` : '100%';
  const missing = visualization.missing_records || 0;

  return (
    <div className="chart-evidence-header-bar">
      <div className="evidence-meta-row">
        <div className="evidence-meta-pill" title="Measured Metric and Unit">
          <span className="meta-label">Measuring:</span>
          <span className="meta-value">{metric} ({unit})</span>
        </div>
        <div className="evidence-meta-pill" title="Population Cohort and Active Scope">
          <span className="meta-label">Population:</span>
          <span className="meta-value">{pop}</span>
        </div>
        <div className="evidence-meta-pill" title="Source Worksheets">
          <span className="meta-label">Source:</span>
          <span className="meta-value">{sources.join(', ')}</span>
        </div>
        <div className="evidence-meta-pill" title="Data Completeness">
          <span className="meta-label">Coverage:</span>
          <span className="meta-value coverage-green">{coverage}</span>
          {missing > 0 && <span className="meta-missing">({missing} omitted)</span>}
        </div>
      </div>

      {onInvestigate && (
        <button
          type="button"
          className="btn-chart-investigate-action"
          onClick={() =>
            onInvestigate({
              entityType: visualization.chart_type === 'burnout_strain' || visualization.chart_type === 'bradford_factor' ? 'department' : 'model_group',
              targetId: visualization.title,
              metric: metric,
              chartId: visualization.id,
              sheetId: visualization.sheet_ids?.[0]
            })
          }
          title="Open deep investigation panel for this chart"
        >
          <span>Investigate Evidence</span>
          <ExternalLink size={12} />
        </button>
      )}
    </div>
  );
}

// ============================================================================
// 1. McKinsey / GE 9-Box Talent & Risk Matrix Component
// ============================================================================
function Talent9BoxMatrix({ data, onInvestigate }) {
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

// ============================================================================
// 2. Bradford Factor Absenteeism Disruption Spectrum
// ============================================================================
function BradfordFactorChart({ data, onInvestigate }) {
  const departments = data?.departments || [];
  const maxScore = Math.max(...departments.map((d) => d.avg_bradford_score || 0), 250);

  return (
    <div className="bradford-spectrum-container">
      <div className="bradford-tiers-legend">
        <span className="tier-tag tier-normal">● &lt; 50: Normal</span>
        <span className="tier-tag tier-moderate">● 51–200: Moderate</span>
        <span className="tier-tag tier-high">● 201–500: High Disruption</span>
        <span className="tier-tag tier-critical">● &gt; 500: Critical Escalation</span>
      </div>

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
            <div
              key={idx}
              className="bradford-dept-row interactive-row"
              onClick={() =>
                onInvestigate &&
                onInvestigate({
                  entityType: 'department',
                  targetId: dept.department,
                  metric: 'Absent ( no of days )'
                })
              }
              title={`Click to investigate ${dept.department} department absence records`}
            >
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
function BurnoutStrainChart({ data, onInvestigate }) {
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
            <div
              key={idx}
              className={`strain-dept-card interactive-card ${isCritical ? 'critical' : (isElevated ? 'elevated' : 'sustainable')}`}
              onClick={() =>
                onInvestigate &&
                onInvestigate({
                  entityType: 'department',
                  targetId: dept.department,
                  metric: 'Overtime Hours'
                })
              }
              title={`Click to investigate workload in ${dept.department}`}
            >
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
              <div className="strain-factors-list">
                <div className="factor-row">
                  <span>Avg Overtime:</span>
                  <strong>{dept.avg_overtime_hours} hrs/mo</strong>
                </div>
                <div className="factor-row">
                  <span>Total Absences:</span>
                  <strong>{dept.total_absent_days} days</strong>
                </div>
                <div className="factor-row">
                  <span>Staff Headcount:</span>
                  <strong>{dept.headcount} staff</strong>
                </div>
              </div>
              <div className="card-click-prompt">Click to view source evidence →</div>
            </div>
          );
        })}
      </div>
    </div>
  );
}

// ============================================================================
// 4. Cross-Sheet Performance-Absenteeism Statistical Elasticity Chart
// ============================================================================
function ElasticityChart({ data, onInvestigate }) {
  const points = data?.scatter_points || [];
  const beta = data?.beta_coefficient;
  const r2 = data?.r_squared;
  const tippingPoint = data?.tipping_point_days;
  const [hoveredPoint, setHoveredPoint] = useState(null);

  const maxAbs = Math.max(...points.map((p) => p.absent_days), 10);
  const minPerf = Math.min(...points.map((p) => p.performance), 60);
  const maxPerf = Math.max(...points.map((p) => p.performance), 100);

  const svgW = 600;
  const svgH = 220;
  const pad = 40;

  const getX = (abs) => pad + (abs / maxAbs) * (svgW - pad * 2);
  const getY = (perf) => svgH - pad - ((perf - minPerf) / (maxPerf - minPerf || 1)) * (svgH - pad * 2);

  return (
    <div className="elasticity-container">
      <div className="elasticity-metrics-summary">
        <div className="elasticity-kpi">
          <span className="kpi-tag">Slope (β)</span>
          <span className="kpi-number">{beta} pts / absent day</span>
        </div>
        <div className="elasticity-kpi">
          <span className="kpi-tag">Tipping Point</span>
          <span className="kpi-number" style={{ color: '#f59e0b' }}>&gt; {tippingPoint} absent days</span>
        </div>
        <div className="elasticity-kpi">
          <span className="kpi-tag">OLS Model Fit</span>
          <span className="kpi-number">R² = {r2}</span>
        </div>
      </div>

      <div className="scatter-svg-wrap">
        <svg viewBox={`0 0 ${svgW} ${svgH}`} className="elasticity-svg">
          <line x1={pad} y1={pad} x2={pad} y2={svgH - pad} stroke="rgba(255,255,255,0.15)" strokeWidth="1" />
          <line x1={pad} y1={svgH - pad} x2={svgW - pad} y2={svgH - pad} stroke="rgba(255,255,255,0.15)" strokeWidth="1" />

          {tippingPoint && (
            <line
              x1={getX(tippingPoint)}
              y1={pad}
              x2={getX(tippingPoint)}
              y2={svgH - pad}
              stroke="#f59e0b"
              strokeDasharray="4,4"
              strokeWidth="1.5"
            />
          )}

          {points.map((pt, idx) => (
            <circle
              key={idx}
              cx={getX(pt.absent_days)}
              cy={getY(pt.performance)}
              r={hoveredPoint?.idx === idx ? 6 : 4.5}
              fill={pt.is_below_tipping ? '#f43f5e' : '#10b981'}
              stroke="#0f172a"
              strokeWidth="1"
              onMouseEnter={() => setHoveredPoint({ ...pt, idx })}
              onMouseLeave={() => setHoveredPoint(null)}
              onClick={() =>
                onInvestigate &&
                onInvestigate({
                  entityType: 'employee',
                  targetId: pt.name,
                  metric: 'Performance Score'
                })
              }
              style={{ cursor: 'pointer' }}
            />
          ))}
        </svg>
      </div>

      {hoveredPoint && (
        <div className="hover-tooltip-strip">
          <span>
            👤 <strong>{hoveredPoint.name}</strong> ({hoveredPoint.department}): Absent: {hoveredPoint.absent_days}d · Score: {hoveredPoint.performance} pts
          </span>
          <span style={{ marginLeft: 8, color: hoveredPoint.is_below_tipping ? '#f43f5e' : '#10b981' }}>
            {hoveredPoint.is_below_tipping ? '● Past Tipping Point' : '● Sustainable'}
          </span>
        </div>
      )}
    </div>
  );
}

// ============================================================================
// 5. Cross-Sheet Comparative Bar Chart
// ============================================================================
function ComparativeBarChart({ data, onInvestigate }) {
  const items = data?.items || [];
  const series = data?.series || [];

  const maxVal = Math.max(
    ...items.map((i) => Math.max(i.val1 || 0, i.val2 || 0)),
    10
  );

  return (
    <div className="comparative-chart-container">
      <div className="comp-legend-row">
        {series.map((s, idx) => (
          <div key={idx} className="comp-legend-item">
            <span className="legend-dot" style={{ backgroundColor: s.color }} />
            <span>{s.name} ({s.unit})</span>
          </div>
        ))}
      </div>

      <div className="comp-bars-list">
        {items.map((item, idx) => {
          const w1 = Math.min(100, Math.max(6, (item.val1 / maxVal) * 100));
          const w2 = Math.min(100, Math.max(6, (item.val2 / maxVal) * 100));

          return (
            <div
              key={idx}
              className="comp-item-row interactive-row"
              onClick={() =>
                onInvestigate &&
                onInvestigate({
                  entityType: 'department',
                  targetId: item.label,
                  metric: series[0]?.name || 'Department Performance'
                })
              }
              title={`Click to investigate ${item.label}`}
            >
              <div className="comp-label">{item.label}</div>
              <div className="comp-dual-track">
                <div className="dual-track-row">
                  <div className="bar-sub-fill" style={{ width: `${w1}%`, backgroundColor: series[0]?.color || '#10b981' }}>
                    <span>{item.val1} {series[0]?.unit}</span>
                  </div>
                </div>
                <div className="dual-track-row">
                  <div className="bar-sub-fill" style={{ width: `${w2}%`, backgroundColor: series[1]?.color || '#f43f5e' }}>
                    <span>{item.val2} {series[1]?.unit}</span>
                  </div>
                </div>
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
}

// ============================================================================
// 6. Dynamic Categorical Bar Chart (Rankings & Benchmarks)
// ============================================================================
function DynamicBarChart({ visualization, onInvestigate }) {
  const bars = visualization.bars || [];
  const [showAll, setShowAll] = useState(false);
  const maxVal = Math.max(...bars.map((b) => b.value), 1);
  const unit = visualization.unit || '';
  const isCurrency = unit === '$';

  const visibleBars = bars.length > 15 && !showAll ? bars.slice(0, 15) : bars;

  const isStore =
    visualization.category_col?.toLowerCase().includes('store') ||
    bars.some((b) => String(b.label).toLowerCase().startsWith('store'));

  const formatVal = (v) => {
    if (isCurrency) {
      if (Math.abs(v) >= 1_000_000) return `$${(v / 1_000_000).toFixed(2)}M`;
      if (Math.abs(v) >= 1_000) return `$${(v / 1_000).toFixed(1)}k`;
      return `$${v.toFixed(2)}`;
    }
    return `${v.toLocaleString()} ${unit}`;
  };

  return (
    <div className="dynamic-bar-chart-wrap">
      <div className="dynamic-bars-list">
        {visibleBars.map((bar, idx) => {
          const pct = Math.min(100, Math.max(6, (bar.value / maxVal) * 100));
          return (
            <div
              key={idx}
              className="dynamic-bar-row interactive-row"
              onClick={() =>
                onInvestigate &&
                onInvestigate({
                  entityType: isStore
                    ? 'store'
                    : visualization.category_col?.toLowerCase().includes('dept')
                    ? 'department'
                    : 'category',
                  targetId: bar.label,
                  metric: visualization.metric_col || visualization.measured_metric,
                  sheetId: visualization.sheet_ids?.[0]
                })
              }
              title={`Click to investigate ${bar.label}`}
            >
              <span className="dynamic-bar-label">{bar.label}</span>
              <div className="dynamic-track">
                <div className="dynamic-fill" style={{ width: `${pct}%` }}>
                  <span className="dynamic-val">{formatVal(bar.value)}</span>
                </div>
              </div>
            </div>
          );
        })}
      </div>
      {bars.length > 15 && (
        <div className="bar-pagination-row" style={{ marginTop: '0.75rem', textAlign: 'center' }}>
          <button
            type="button"
            className="btn-show-more-bars"
            onClick={() => setShowAll(!showAll)}
          >
            {showAll ? `Show Top 15 Entries` : `Show All ${bars.length} Entries (${bars.length - 15} more)`}
          </button>
        </div>
      )}
    </div>
  );
}

// ============================================================================
// 6b. Dynamic Chronological Line Chart (Sequential Trajectories & Peaks)
// ============================================================================
function DynamicLineChart({ visualization, onInvestigate }) {
  const lineData = visualization.line_data || {};
  const points = lineData.points || [];
  const unit = visualization.unit || '';
  const isCurrency = unit === '$';
  const [hoveredPoint, setHoveredPoint] = useState(null);

  if (!points || points.length === 0) {
    return (
      <div className="dynamic-line-empty" style={{ padding: '2rem', textAlign: 'center', color: 'var(--text-muted)' }}>
        <p>No continuous chronological observations available for plotting.</p>
      </div>
    );
  }

  const values = points.map((p) => p.value);
  const minVal = Math.min(...values);
  const maxVal = Math.max(...values);
  const valRange = Math.max(1, maxVal - minVal);

  const svgW = 700;
  const svgH = 220;
  const padX = 55;
  const padY = 30;

  const getX = (idx) => padX + (idx / Math.max(1, points.length - 1)) * (svgW - padX * 2);
  const getY = (val) => svgH - padY - ((val - minVal) / valRange) * (svgH - padY * 2);

  const pointsStr = points.map((p, i) => `${getX(i)},${getY(p.value)}`).join(' ');
  const areaPointsStr = `${getX(0)},${svgH - padY} ${pointsStr} ${getX(points.length - 1)},${svgH - padY}`;

  const formatVal = (v) => {
    if (isCurrency) {
      if (Math.abs(v) >= 1_000_000_000) return `$${(v / 1_000_000_000).toFixed(2)}B`;
      if (Math.abs(v) >= 1_000_000) return `$${(v / 1_000_000).toFixed(2)}M`;
      if (Math.abs(v) >= 1_000) return `$${(v / 1_000).toFixed(1)}k`;
      return `$${v.toFixed(2)}`;
    }
    return `${v.toLocaleString()} ${unit}`;
  };

  const tickCount = Math.min(6, points.length);
  const tickIndices = Array.from({ length: tickCount }, (_, i) =>
    Math.round((i / (tickCount - 1)) * (points.length - 1))
  );

  return (
    <div className="dynamic-line-chart-wrap">
      <div className="line-chart-svg-container">
        <svg viewBox={`0 0 ${svgW} ${svgH}`} className="dynamic-line-svg" style={{ width: '100%', height: 'auto', display: 'block' }}>
          <defs>
            <linearGradient id={`grad-${visualization.id}`} x1="0" y1="0" x2="0" y2="1">
              <stop offset="0%" stopColor="#38bdf8" stopOpacity="0.32" />
              <stop offset="100%" stopColor="#38bdf8" stopOpacity="0.0" />
            </linearGradient>
          </defs>

          {/* Grid lines */}
          <line x1={padX} y1={padY} x2={svgW - padX} y2={padY} stroke="rgba(255,255,255,0.08)" strokeDasharray="3,3" />
          <line x1={padX} y1={(padY + svgH - padY) / 2} x2={svgW - padX} y2={(padY + svgH - padY) / 2} stroke="rgba(255,255,255,0.08)" strokeDasharray="3,3" />
          <line x1={padX} y1={svgH - padY} x2={svgW - padX} y2={svgH - padY} stroke="rgba(255,255,255,0.18)" strokeWidth="1" />

          {/* Y-axis labels */}
          <text x={padX - 8} y={padY + 4} textAnchor="end" fill="var(--fg-secondary, #94a3b8)" fontSize="10">
            {formatVal(maxVal)}
          </text>
          <text x={padX - 8} y={svgH - padY} textAnchor="end" fill="var(--fg-secondary, #94a3b8)" fontSize="10">
            {formatVal(minVal)}
          </text>

          {/* Area Fill */}
          <polygon points={areaPointsStr} fill={`url(#grad-${visualization.id})`} />

          {/* Polyline path */}
          <polyline points={pointsStr} fill="none" stroke="#38bdf8" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round" />

          {/* Interactive data point circles */}
          {points.map((p, i) => {
            const cx = getX(i);
            const cy = getY(p.value);
            const isHovered = hoveredPoint?.period === p.period;

            return (
              <circle
                key={i}
                cx={cx}
                cy={cy}
                r={isHovered ? 6 : (points.length > 50 ? 2.5 : 3.5)}
                fill={isHovered ? "#f59e0b" : "#38bdf8"}
                stroke="#0f172a"
                strokeWidth="1.5"
                onMouseEnter={() => setHoveredPoint(p)}
                onClick={() =>
                  onInvestigate &&
                  onInvestigate({
                    entityType: 'time_series',
                    targetId: p.period,
                    metric: visualization.metric_col || visualization.measured_metric,
                    sheetId: visualization.sheet_ids?.[0]
                  })
                }
                style={{ cursor: 'pointer' }}
              />
            );
          })}

          {/* X-axis tick labels */}
          {tickIndices.map((idx) => {
            const p = points[idx];
            if (!p) return null;
            return (
              <text
                key={idx}
                x={getX(idx)}
                y={svgH - padY + 18}
                textAnchor="middle"
                fill="var(--fg-secondary, #94a3b8)"
                fontSize="10"
              >
                {p.period}
              </text>
            );
          })}
        </svg>
      </div>

      {/* Interactive Tooltip & Click Prompt */}
      {hoveredPoint ? (
        <div
          className="line-hover-pill active"
          onClick={() =>
            onInvestigate &&
            onInvestigate({
              entityType: 'time_series',
              targetId: hoveredPoint.period,
              metric: visualization.metric_col || visualization.measured_metric,
              sheetId: visualization.sheet_ids?.[0]
            })
          }
          style={{ cursor: 'pointer' }}
        >
          <span>Period: <strong>{hoveredPoint.period}</strong></span>
          <span className="pill-sep" style={{ margin: '0 8px' }}>·</span>
          <span>{visualization.metric_col || 'Measure'}: <strong>{formatVal(hoveredPoint.value)}</strong></span>
          <span className="pill-click-hint" style={{ marginLeft: 12, color: 'var(--accent, #38bdf8)' }}>Click to investigate period →</span>
        </div>
      ) : (
        <div className="line-hover-pill idle">
          <span>{points.length} Chronological Observations ({points[0]?.period} to {points[points.length - 1]?.period})</span>
          <span className="pill-hint" style={{ marginLeft: 12, color: 'var(--text-muted, #64748b)' }}>Hover or click any data point to drill down</span>
        </div>
      )}
    </div>
  );
}

// ============================================================================
// 7. Dynamic Categorical Donut Chart (Proportional Composition)
// ============================================================================
function DynamicDonutChart({ data, onInvestigate, metricName }) {
  const slices = data?.slices || [];
  const total = data?.total || 0;
  const [hoveredSlice, setHoveredSlice] = useState(null);

  let cumulativeAngle = 0;
  const radius = 60;
  const cx = 80;
  const cy = 80;

  return (
    <div className="dynamic-donut-wrap">
      <div className="donut-svg-col">
        <svg viewBox="0 0 160 160" className="donut-svg">
          {slices.map((slice, idx) => {
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
                  onInvestigate &&
                  onInvestigate({
                    entityType: 'category',
                    targetId: slice.label,
                    metric: metricName
                  })
                }
                style={{ cursor: 'pointer' }}
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
        {slices.map((slice, idx) => (
          <div
            key={idx}
            className={`donut-legend-row ${hoveredSlice?.label === slice.label ? 'highlighted' : ''}`}
            onMouseEnter={() => setHoveredSlice(slice)}
            onMouseLeave={() => setHoveredSlice(null)}
            onClick={() =>
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
  );
}

// ============================================================================
// 8. Longitudinal Trajectory & Forecast Chart
// ============================================================================
function ForecastChart({ data, onInvestigate }) {
  const historical = data?.historical || [];
  const forecast = data?.forecast || [];
  const unit = data?.unit || 'hrs';
  const [hoveredPt, setHoveredPt] = useState(null);

  const allVals = [
    ...historical.map((p) => p.actual),
    ...forecast.map((p) => p.forecast)
  ];
  const minVal = Math.min(...allVals, 0);
  const maxVal = Math.max(...allVals, 10);

  const svgW = 600;
  const svgH = 200;
  const pad = 35;
  const totalPts = historical.length + forecast.length;

  const getX = (idx) => pad + (idx / Math.max(1, totalPts - 1)) * (svgW - pad * 2);
  const getY = (val) => svgH - pad - ((val - minVal) / Math.max(1, maxVal - minVal)) * (svgH - pad * 2);

  const histPointsStr = historical.map((p, i) => `${getX(i)},${getY(p.actual)}`).join(' ');
  const lastHistX = getX(historical.length - 1);
  const lastHistY = getY(historical[historical.length - 1]?.actual || 0);
  const forePointsStr = `${lastHistX},${lastHistY} ` + forecast.map((p, i) => `${getX(historical.length + i)},${getY(p.forecast)}`).join(' ');

  return (
    <div className="forecast-chart-container">
      <div className="forecast-legend-strip">
        <span className="legend-item"><span className="legend-dot dot-actual" /> Historical Observation</span>
        <span className="legend-item"><span className="legend-dot dot-forecast" /> 7-Day Holt-Winters Projection</span>
        <span className="legend-item"><span className="legend-dot dot-confidence" /> 95% Confidence Band</span>
      </div>

      <div className="forecast-svg-wrap">
        <svg viewBox={`0 0 ${svgW} ${svgH}`} className="forecast-svg">
          <line x1={pad} y1={pad} x2={pad} y2={svgH - pad} stroke="rgba(255,255,255,0.15)" strokeWidth="1" />
          <line x1={pad} y1={svgH - pad} x2={svgW - pad} y2={svgH - pad} stroke="rgba(255,255,255,0.15)" strokeWidth="1" />

          {/* Confidence interval polygon */}
          {forecast.length > 0 && (
            <polygon
              points={
                forecast.map((p, i) => `${getX(historical.length + i)},${getY(p.upper_95)}`).join(' ') +
                ' ' +
                forecast.slice().reverse().map((p, i) => `${getX(historical.length + forecast.length - 1 - i)},${getY(p.lower_95)}`).join(' ')
              }
              fill="rgba(245, 158, 11, 0.12)"
              stroke="none"
            />
          )}

          {/* Historical line */}
          {historical.length > 1 && (
            <polyline points={histPointsStr} fill="none" stroke="#06b6d4" strokeWidth="2.5" />
          )}

          {/* Forecast line */}
          {forecast.length > 0 && (
            <polyline points={forePointsStr} fill="none" stroke="#f59e0b" strokeWidth="2.5" strokeDasharray="5,4" />
          )}

          {/* Circles */}
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
          <span>{hoveredPt.period}: <strong>{hoveredPt.val} {unit}</strong> ({hoveredPt.isForecast ? 'Forecast Projection' : 'Actual Recorded'})</span>
          {hoveredPt.lower_95 != null && (
            <span style={{ marginLeft: 8, color: 'var(--text-muted)' }}>[95% Confidence: {hoveredPt.lower_95} – {hoveredPt.upper_95}]</span>
          )}
        </div>
      )}
    </div>
  );
}

// ============================================================================
// MAIN VISUAL ANALYTICS PANEL COMPONENT (EXECUTIVE OVERVIEW)
// ============================================================================
export default function VisualAnalyticsPanel({
  visualDashboard,
  charts,
  forecast,
  selectedSheetId,
  onInvestigate
}) {
  const [activeCategory, setActiveCategory] = useState('All');

  if (visualDashboard && visualDashboard.visualizations?.length > 0) {
    const allVis = visualDashboard.visualizations;
    const categories = visualDashboard.categories || ['All'];
    const catCounts = visualDashboard.category_counts || {};

    const filteredVis = activeCategory === 'All'
      ? allVis
      : allVis.filter((v) => v.category === activeCategory);

    return (
      <div className="visual-analytics-panel">
        <div className="section-title-row">
          <div>
            <div style={{ display: 'flex', alignItems: 'center', gap: '0.6rem', flexWrap: 'wrap' }}>
              <h3>Primary Visual Intelligence & Analytics</h3>
              <span className="badge-ai-count">{allVis.length} Visualizations Ready</span>
            </div>
            <p className="subtitle">
              Dynamic, evidence-backed charts profiling trends, performance distribution, and operational patterns.
            </p>
          </div>
        </div>

        {/* Category Filter Pills */}
        <div className="dashboard-filter-bar">
          <span className="filter-label">Filter View:</span>
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
              <div key={v.id} id={v.id} className={`visual-card ${isCrossSheet ? 'card-cross-sheet' : ''}`}>
                {/* Standard Evidence Header Identification */}
                <ChartEvidenceHeader visualization={v} onInvestigate={onInvestigate} />

                {/* Card Top Badges */}
                <div className="card-top-badges">
                  <span className={`sheet-source-badge ${isCrossSheet ? 'badge-cross-accent' : ''}`}>
                    {v.chart_type === 'talent_9box' && '🎯 '}
                    {v.chart_type === 'bradford_factor' && '⚠️ '}
                    {v.chart_type === 'burnout_strain' && '🔥 '}
                    {v.chart_type === 'elasticity' && '📐 '}
                    {v.chart_type === 'comparative_bar' && '🔗 '}
                    {v.chart_type === 'forecast' && '📈 '}
                    {v.chart_type === 'bar' && '📊 '}
                    {v.chart_type === 'donut' && '🍩 '}
                    {v.chart_type === 'line' && '📈 '}
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
                    {v.chart_type === 'bar' && 'Rankings & Distribution'}
                    {v.chart_type === 'donut' && 'Parts of a Whole'}
                    {v.chart_type === 'line' && 'Sequential Trend'}
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
                    <Talent9BoxMatrix data={v.talent_9box_data} onInvestigate={onInvestigate} />
                  )}
                  {v.chart_type === 'bradford_factor' && (
                    <BradfordFactorChart data={v.bradford_data} onInvestigate={onInvestigate} />
                  )}
                  {v.chart_type === 'burnout_strain' && (
                    <BurnoutStrainChart data={v.burnout_data} onInvestigate={onInvestigate} />
                  )}
                  {v.chart_type === 'elasticity' && (
                    <ElasticityChart data={v.elasticity_data} onInvestigate={onInvestigate} />
                  )}
                  {v.chart_type === 'comparative_bar' && (
                    <ComparativeBarChart data={v.comparative_data} onInvestigate={onInvestigate} />
                  )}
                  {v.chart_type === 'forecast' && (
                    <ForecastChart data={v.forecast_data} onInvestigate={onInvestigate} />
                  )}
                  {v.chart_type === 'bar' && (
                    <DynamicBarChart visualization={v} onInvestigate={onInvestigate} />
                  )}
                  {v.chart_type === 'donut' && (
                    <DynamicDonutChart data={v.donut_data} onInvestigate={onInvestigate} metricName={v.measured_metric} />
                  )}
                  {v.chart_type === 'line' && (
                    <DynamicLineChart visualization={v} onInvestigate={onInvestigate} />
                  )}
                </div>

                {/* AI Strategic Takeaway Banner */}
                {v.ai_insight && (
                  <div className="chart-ai-insight-banner">
                    <div className="insight-header">
                      <span className="insight-icon">💡</span>
                      <span className="insight-title">Strategic Observation</span>
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
