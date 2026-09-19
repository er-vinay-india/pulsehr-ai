import React, { useState } from 'react';
import MarkdownView from './MarkdownView';

// ============================================================================
// 1. Grouped Comparative Bar Chart (Cross-Sheet Intelligence)
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

  const s1 = series[0] || { name: 'Metric 1', unit: '', color: '#10b981' };
  const s2 = series[1] || { name: 'Metric 2', unit: '', color: '#f43f5e' };

  const maxVal1 = Math.max(...items.map(d => d.val1 || 0), 1);
  const maxVal2 = Math.max(...items.map(d => d.val2 || 0), 1);

  const svgW = 560;
  const svgH = 220;
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
          {/* Horizontal gridlines */}
          {[0, 0.25, 0.5, 0.75, 1].map((ratio) => {
            const y = margin.top + innerH * (1 - ratio);
            return (
              <line
                key={ratio}
                x1={margin.left}
                y1={y}
                x2={svgW - margin.right}
                y2={y}
                stroke="var(--border-color, #334155)"
                strokeDasharray="3 3"
                opacity={0.3}
              />
            );
          })}

          {/* Grouped Bars */}
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
                {/* Highlight band */}
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

                {/* Bar 1 */}
                <rect
                  x={x1}
                  y={y1}
                  width={barW}
                  height={h1}
                  rx="3"
                  fill={s1.color}
                  opacity={isHovered ? 1 : 0.85}
                  style={{ transition: 'all 0.2s ease' }}
                />
                <text
                  x={x1 + barW / 2}
                  y={y1 - 4}
                  textAnchor="middle"
                  fontSize="9"
                  fontWeight="600"
                  fill={s1.color}
                >
                  {d.val1}
                </text>

                {/* Bar 2 */}
                <rect
                  x={x2}
                  y={y2}
                  width={barW}
                  height={h2}
                  rx="3"
                  fill={s2.color}
                  opacity={isHovered ? 1 : 0.85}
                  style={{ transition: 'all 0.2s ease' }}
                />
                <text
                  x={x2 + barW / 2}
                  y={y2 - 4}
                  textAnchor="middle"
                  fontSize="9"
                  fontWeight="600"
                  fill={s2.color}
                >
                  {d.val2}
                </text>

                {/* X Axis Label */}
                <text
                  x={centerX}
                  y={svgH - 12}
                  textAnchor="middle"
                  fontSize="10"
                  fontWeight={isHovered ? '600' : '400'}
                  fill={isHovered ? 'var(--text-bright, #fff)' : 'var(--text-muted, #94a3b8)'}
                >
                  {d.label.length > 10 ? `${d.label.slice(0, 9)}…` : d.label}
                </text>
              </g>
            );
          })}
        </svg>
      </div>

      {/* Floating Hover Details */}
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
// 2. Single Metric Bar Chart
// ============================================================================
function SingleBarChart({ data }) {
  const [hoveredIdx, setHoveredIdx] = useState(null);
  const bars = data?.bars || [];
  const unit = data?.unit || '';

  if (!bars.length) {
    return <div className="chart-empty">No distribution data available.</div>;
  }

  const maxVal = Math.max(...bars.map(b => b.value || 0), 1);
  const svgW = 540;
  const svgH = 200;
  const margin = { top: 22, right: 20, bottom: 40, left: 45 };
  const innerW = svgW - margin.left - margin.right;
  const innerH = svgH - margin.top - margin.bottom;

  const slotW = innerW / Math.max(bars.length, 1);
  const barW = Math.min(32, slotW * 0.55);

  return (
    <div className="single-bar-wrap">
      <div className="chart-svg-wrap">
        <svg viewBox={`0 0 ${svgW} ${svgH}`} className="responsive-svg">
          {[0, 0.25, 0.5, 0.75, 1].map((ratio) => {
            const y = margin.top + innerH * (1 - ratio);
            const val = Math.round(maxVal * ratio);
            return (
              <g key={ratio}>
                <line
                  x1={margin.left}
                  y1={y}
                  x2={svgW - margin.right}
                  y2={y}
                  stroke="var(--border-color, #334155)"
                  strokeDasharray="3 3"
                  opacity={0.3}
                />
                <text
                  x={margin.left - 6}
                  y={y + 3}
                  textAnchor="end"
                  fontSize="9"
                  fill="var(--text-muted, #94a3b8)"
                >
                  {val}
                </text>
              </g>
            );
          })}

          {bars.map((b, idx) => {
            const h = Math.max(3, (b.value / maxVal) * innerH);
            const x = margin.left + idx * slotW + (slotW - barW) / 2;
            const y = margin.top + innerH - h;
            const isHovered = hoveredIdx === idx;

            return (
              <g
                key={idx}
                onMouseEnter={() => setHoveredIdx(idx)}
                onMouseLeave={() => setHoveredIdx(null)}
                style={{ cursor: 'pointer' }}
              >
                <rect
                  x={x}
                  y={y}
                  width={barW}
                  height={h}
                  rx="3"
                  fill={isHovered ? '#38bdf8' : '#0ea5e9'}
                  opacity={isHovered ? 1 : 0.85}
                  style={{ transition: 'all 0.2s ease' }}
                />
                <text
                  x={x + barW / 2}
                  y={y - 5}
                  textAnchor="middle"
                  fontSize="10"
                  fontWeight="600"
                  fill={isHovered ? '#ffffff' : 'var(--text-muted, #94a3b8)'}
                >
                  {b.value}
                </text>
                <text
                  x={x + barW / 2}
                  y={svgH - 12}
                  textAnchor="middle"
                  fontSize="10"
                  fontWeight={isHovered ? '600' : '400'}
                  fill={isHovered ? '#ffffff' : 'var(--text-muted, #94a3b8)'}
                >
                  {b.label.length > 9 ? `${b.label.slice(0, 8)}…` : b.label}
                </text>
              </g>
            );
          })}
        </svg>
      </div>

      {hoveredIdx != null && bars[hoveredIdx] && (
        <div className="hover-tooltip-strip">
          <span>{bars[hoveredIdx].label}: <strong>{bars[hoveredIdx].value} {unit}</strong></span>
        </div>
      )}
    </div>
  );
}

// ============================================================================
// 3. Donut Distribution Chart
// ============================================================================
function DonutChart({ data }) {
  const [hoveredSlice, setHoveredSlice] = useState(null);
  const slices = data?.slices || [];
  const total = data?.total || slices.reduce((acc, s) => acc + (s.count || 0), 0);

  if (!slices.length) {
    return <div className="chart-empty">No categorical composition available.</div>;
  }

  const size = 180;
  const radius = 78;
  const innerRadius = 48;
  const center = size / 2;

  let cumulativeAngle = -Math.PI / 2;
  const arcs = slices.map((slice) => {
    const angle = total > 0 ? (slice.count / total) * (2 * Math.PI) : 0;
    const start = cumulativeAngle;
    const end = cumulativeAngle + angle;
    cumulativeAngle += angle;

    const x1 = center + radius * Math.cos(start);
    const y1 = center + radius * Math.sin(start);
    const x2 = center + radius * Math.cos(end);
    const y2 = center + radius * Math.sin(end);

    const ix1 = center + innerRadius * Math.cos(end);
    const iy1 = center + innerRadius * Math.sin(end);
    const ix2 = center + innerRadius * Math.cos(start);
    const iy2 = center + innerRadius * Math.sin(start);

    const largeArc = angle > Math.PI ? 1 : 0;
    const path = total > 0 && slice.count > 0 ? `
      M ${x1} ${y1}
      A ${radius} ${radius} 0 ${largeArc} 1 ${x2} ${y2}
      L ${ix1} ${iy1}
      A ${innerRadius} ${innerRadius} 0 ${largeArc} 0 ${ix2} ${iy2}
      Z
    ` : '';

    return { ...slice, path };
  });

  return (
    <div className="donut-layout">
      <div className="donut-svg-wrap">
        <svg viewBox={`0 0 ${size} ${size}`} className="donut-svg">
          {arcs.map((arc, idx) => (
            <path
              key={idx}
              d={arc.path}
              fill={arc.color || `hsl(${idx * 55 + 160}, 75%, 55%)`}
              stroke="var(--bg-card, #0f172a)"
              strokeWidth="2"
              opacity={hoveredSlice === idx ? 1 : 0.88}
              transform={hoveredSlice === idx ? 'scale(1.03) translate(-2, -2)' : ''}
              onMouseEnter={() => setHoveredSlice(idx)}
              onMouseLeave={() => setHoveredSlice(null)}
              style={{ cursor: 'pointer', transition: 'transform 0.15s ease' }}
            />
          ))}
          <text
            x={center}
            y={center - 2}
            textAnchor="middle"
            fontSize="17"
            fontWeight="700"
            fill="var(--text-bright, #fff)"
          >
            {hoveredSlice != null ? slices[hoveredSlice]?.count : total}
          </text>
          <text
            x={center}
            y={center + 14}
            textAnchor="middle"
            fontSize="9"
            fill="var(--text-muted, #94a3b8)"
          >
            {hoveredSlice != null ? `${slices[hoveredSlice]?.pct}%` : 'Total'}
          </text>
        </svg>
      </div>

      <div className="donut-legend">
        {slices.map((slice, idx) => (
          <div
            key={idx}
            className={`legend-item ${hoveredSlice === idx ? 'active' : ''}`}
            onMouseEnter={() => setHoveredSlice(idx)}
            onMouseLeave={() => setHoveredSlice(null)}
          >
            <span className="legend-dot" style={{ backgroundColor: slice.color }} />
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
// 4. Time-Series / Longitudinal Forecast Chart
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

  const getX = (i) => {
    if (allPoints.length <= 1) return margin.left + innerW / 2;
    return margin.left + (i / (allPoints.length - 1)) * innerW;
  };

  const getY = (val) => {
    return margin.top + innerH - ((val - minVal) / (maxVal - minVal || 1)) * innerH;
  };

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
      const x = getX(historical.length + i);
      const y = getY(p.forecast);
      forecastPath += ` L ${x} ${y}`;
    });
  }

  let ciPolygon = '';
  if (historical.length > 0 && forecast.length > 0) {
    const lastHist = historical[historical.length - 1];
    const topPts = [`${getX(historical.length - 1)},${getY(lastHist.actual)}`];
    const botPts = [`${getX(historical.length - 1)},${getY(lastHist.actual)}`];
    forecast.forEach((p, i) => {
      const x = getX(historical.length + i);
      topPts.push(`${x},${getY(p.upper_95)}`);
      botPts.push(`${x},${getY(p.lower_95)}`);
    });
    botPts.reverse();
    ciPolygon = topPts.concat(botPts).join(' ');
  }

  const trendClass = metrics.trend_direction?.toLowerCase().replace(/[^a-z]/g, '-') || 'stable';

  return (
    <div className="forecast-chart-wrap">
      <div className="forecast-badge-row">
        <span className={`trend-badge ${trendClass}`}>
          {metrics.trend_direction || 'Holt Damped Trend'}
        </span>
        <span className="forecast-chip">
          Shift: <strong>{metrics.projected_change_pct >= 0 ? `+${metrics.projected_change_pct}%` : `${metrics.projected_change_pct}%`}</strong>
        </span>
        <span className="forecast-chip">
          Fit: <strong>R² = {metrics.r_squared}</strong>
        </span>
      </div>

      <div className="chart-svg-wrap">
        <svg viewBox={`0 0 ${svgW} ${svgH}`} className="responsive-svg">
          <defs>
            <linearGradient id="forecastConeGrad2" x1="0" y1="0" x2="0" y2="1">
              <stop offset="0%" stopColor="#818cf8" stopOpacity="0.25" />
              <stop offset="100%" stopColor="#818cf8" stopOpacity="0.04" />
            </linearGradient>
          </defs>

          {/* Gridlines */}
          {[0, 0.33, 0.66, 1].map((ratio) => {
            const y = margin.top + innerH * (1 - ratio);
            const val = (minVal + (maxVal - minVal) * ratio).toFixed(1);
            return (
              <g key={ratio}>
                <line
                  x1={margin.left}
                  y1={y}
                  x2={svgW - margin.right}
                  y2={y}
                  stroke="var(--border-color, #334155)"
                  strokeDasharray="3 3"
                  opacity={0.3}
                />
                <text
                  x={margin.left - 6}
                  y={y + 3}
                  textAnchor="end"
                  fontSize="9"
                  fill="var(--text-muted, #94a3b8)"
                >
                  {val}
                </text>
              </g>
            );
          })}

          {/* 95% Confidence Interval Polygon */}
          {ciPolygon && (
            <polygon points={ciPolygon} fill="url(#forecastConeGrad2)" />
          )}

          {/* Historical Path */}
          {histPath && (
            <path
              d={histPath}
              fill="none"
              stroke="#06b6d4"
              strokeWidth="2.5"
              strokeLinecap="round"
              strokeLinejoin="round"
            />
          )}

          {/* Forecast Path */}
          {forecastPath && (
            <path
              d={forecastPath}
              fill="none"
              stroke="#f59e0b"
              strokeWidth="2.5"
              strokeDasharray="5 4"
              strokeLinecap="round"
              strokeLinejoin="round"
            />
          )}

          {/* Historical Points */}
          {historical.map((p, i) => {
            const x = getX(i);
            const y = getY(p.actual);
            const isHov = hoveredPt?.idx === i;
            return (
              <circle
                key={`h-${i}`}
                cx={x}
                cy={y}
                r={isHov ? 5 : 3}
                fill="#06b6d4"
                stroke="#0f172a"
                strokeWidth="1.5"
                onMouseEnter={() => setHoveredPt({ ...p, idx: i, val: p.actual, isForecast: false })}
                onMouseLeave={() => setHoveredPt(null)}
                style={{ cursor: 'pointer', transition: 'r 0.15s ease' }}
              />
            );
          })}

          {/* Forecast Points */}
          {forecast.map((p, i) => {
            const idx = historical.length + i;
            const x = getX(idx);
            const y = getY(p.forecast);
            const isHov = hoveredPt?.idx === idx;
            return (
              <circle
                key={`f-${i}`}
                cx={x}
                cy={y}
                r={isHov ? 5.5 : 3.5}
                fill="#f59e0b"
                stroke="#0f172a"
                strokeWidth="1.5"
                onMouseEnter={() => setHoveredPt({ ...p, idx, val: p.forecast, isForecast: true })}
                onMouseLeave={() => setHoveredPt(null)}
                style={{ cursor: 'pointer', transition: 'r 0.15s ease' }}
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
// MAIN VISUAL ANALYTICS PANEL COMPONENT
// ============================================================================
export default function VisualAnalyticsPanel({ visualDashboard, charts, forecast, selectedSheetId }) {
  const [activeCategory, setActiveCategory] = useState('All');

  // If new visualDashboard is available, use the autonomous multi-chart gallery
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
              <h3>Autonomous AI Visual Intelligence Suite</h3>
              <span className="badge-ai-count">{allVis.length} Projected Visualizations</span>
            </div>
            <p className="subtitle">
              Multi-sheet relational projections, domain breakdowns, and Holt-Winters longitudinal forecasts synthesized across your uploaded workspace.
            </p>
          </div>
        </div>

        {/* Category Pill Filters */}
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
              <div key={v.id} className={`visual-card ${isCrossSheet ? 'card-cross-sheet' : ''}`}>
                {/* Card Top Badges */}
                <div className="card-top-badges">
                  <span className={`sheet-source-badge ${isCrossSheet ? 'badge-cross-accent' : ''}`}>
                    {isCrossSheet ? '🔗 ' : '📄 '}
                    {v.sheet_badge}
                  </span>
                  <span className="category-pill-badge">{v.category}</span>
                  <span className="type-pill-badge">
                    {v.chart_type === 'comparative_bar' && '📊 Grouped Bar'}
                    {v.chart_type === 'bar' && '📊 Bar Breakdown'}
                    {v.chart_type === 'donut' && '🍩 Distribution'}
                    {v.chart_type === 'forecast' && '📈 Holt Forecast'}
                  </span>
                </div>

                {/* Card Title & Subtitle */}
                <div className="card-title-group">
                  <h4>{v.title}</h4>
                  {v.subtitle && <p className="card-sub">{v.subtitle}</p>}
                </div>

                {/* Card Visual Body */}
                <div className="card-visual-body">
                  {v.chart_type === 'comparative_bar' && (
                    <ComparativeBarChart data={v.comparative_data} />
                  )}
                  {v.chart_type === 'bar' && (
                    <SingleBarChart data={v.bar_data} />
                  )}
                  {v.chart_type === 'donut' && (
                    <DonutChart data={v.donut_data} />
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
                      <span className="insight-title">AI Strategic Takeaway</span>
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

  // Fallback: Legacy 3-slot layout if visualDashboard is empty
  return null;
}
