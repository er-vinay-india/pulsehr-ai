import React, { useState } from 'react';
import MarkdownView from './MarkdownView';

export default function VisualAnalyticsPanel({ charts, forecast }) {
  const [hoveredBar, setHoveredBar] = useState(null);
  const [hoveredSlice, setHoveredSlice] = useState(null);
  const [hoveredForecast, setHoveredForecast] = useState(null);

  const [selectedMetric, setSelectedMetric] = useState(null);
  const [selectedCategory, setSelectedCategory] = useState(null);
  const [selectedForecastMetric, setSelectedForecastMetric] = useState(null);

  // 1. Resolve Active Bar Chart
  const availableMetrics = (
    charts?.available_metrics?.map(m => m.column) || 
    Object.keys(charts?.bar_charts || {})
  ).filter(Boolean);

  const activeMetric = (selectedMetric && charts?.bar_charts?.[selectedMetric]) 
    ? selectedMetric 
    : (charts?.primary_metric && charts?.bar_charts?.[charts.primary_metric] 
        ? charts.primary_metric 
        : availableMetrics[0]);

  const activeBarChart = charts?.bar_charts?.[activeMetric] || charts?.bar;
  const barData = activeBarChart?.bars || [];

  // 2. Resolve Active Donut Chart
  const availableCategories = (
    charts?.available_categories || 
    Object.keys(charts?.donut_charts || {})
  ).filter(Boolean);

  const activeCategory = (selectedCategory && charts?.donut_charts?.[selectedCategory])
    ? selectedCategory
    : (charts?.primary_category && charts?.donut_charts?.[charts.primary_category]
        ? charts.primary_category
        : availableCategories[0]);

  const activeDonutChart = charts?.donut_charts?.[activeCategory] || charts?.donut;
  const donutSlices = activeDonutChart?.slices || [];

  // 3. Resolve Active Forecast
  const availableForecastMetrics = (
    forecast?.available_metrics || 
    (forecast?.forecasts ? Object.keys(forecast.forecasts) : [])
  ).filter(Boolean);

  const activeForecastMetric = (selectedForecastMetric && forecast?.forecasts?.[selectedForecastMetric])
    ? selectedForecastMetric
    : (forecast?.primary_metric && forecast?.forecasts?.[forecast.primary_metric]
        ? forecast.primary_metric
        : availableForecastMetrics[0]);

  const activeForecastData = (forecast?.forecasts && activeForecastMetric && forecast.forecasts[activeForecastMetric])
    ? forecast.forecasts[activeForecastMetric]
    : forecast;

  const forecastPoints = activeForecastData?.forecast || [];
  const historicalPoints = activeForecastData?.historical || [];

  // ==========================
  // 1. SVG Bar Chart Geometry
  // ==========================
  const maxBarVal = Math.max(...barData.map(b => b.value), 1);
  const barSvgWidth = 540;
  const barSvgHeight = 220;
  const barMargin = { top: 25, right: 20, bottom: 45, left: 55 };
  const innerWidth = barSvgWidth - barMargin.left - barMargin.right;
  const innerHeight = barSvgHeight - barMargin.top - barMargin.bottom;

  const barCount = Math.max(barData.length, 1);
  const barSlotWidth = innerWidth / barCount;
  const barWidth = Math.min(36, barSlotWidth * 0.65);

  // ============================
  // 2. SVG Donut Chart Geometry
  // ============================
  const donutSize = 220;
  const donutRadius = 90;
  const donutInnerRadius = 55;
  const donutCenter = donutSize / 2;
  const totalDonutCount = donutSlices.reduce((acc, s) => acc + (s.count || 0), 0);

  // Compute SVG arc path slices
  let cumulativeAngle = -Math.PI / 2;
  const renderedArcs = donutSlices.map((slice) => {
    const sliceAngle = totalDonutCount > 0 ? (slice.count / totalDonutCount) * (2 * Math.PI) : 0;
    const startAngle = cumulativeAngle;
    const endAngle = cumulativeAngle + sliceAngle;
    cumulativeAngle += sliceAngle;

    const x1 = donutCenter + donutRadius * Math.cos(startAngle);
    const y1 = donutCenter + donutRadius * Math.sin(startAngle);
    const x2 = donutCenter + donutRadius * Math.cos(endAngle);
    const y2 = donutCenter + donutRadius * Math.sin(endAngle);

    const ix1 = donutCenter + donutInnerRadius * Math.cos(endAngle);
    const iy1 = donutCenter + donutInnerRadius * Math.sin(endAngle);
    const ix2 = donutCenter + donutInnerRadius * Math.cos(startAngle);
    const iy2 = donutCenter + donutInnerRadius * Math.sin(startAngle);

    const largeArcFlag = sliceAngle > Math.PI ? 1 : 0;

    const pathData = totalDonutCount > 0 && slice.count > 0 ? `
      M ${x1} ${y1}
      A ${donutRadius} ${donutRadius} 0 ${largeArcFlag} 1 ${x2} ${y2}
      L ${ix1} ${iy1}
      A ${donutInnerRadius} ${donutInnerRadius} 0 ${largeArcFlag} 0 ${ix2} ${iy2}
      Z
    ` : '';

    return { ...slice, pathData, sliceAngle };
  });

  // ======================================
  // 3. SVG Time-Series Forecasting Geometry
  // ======================================
  const tsSvgWidth = 680;
  const tsSvgHeight = 240;
  const tsMargin = { top: 25, right: 30, bottom: 40, left: 55 };
  const tsInnerW = tsSvgWidth - tsMargin.left - tsMargin.right;
  const tsInnerH = tsSvgHeight - tsMargin.top - tsMargin.bottom;

  // Combine historical and forecast for scale
  const allPoints = [
    ...historicalPoints.map((p, i) => ({ ...p, isForecast: false, idx: i, val: p.actual })),
    ...forecastPoints.map((p, i) => ({ ...p, isForecast: true, idx: historicalPoints.length + i, val: p.forecast }))
  ];

  const minVal = Math.max(0, Math.min(...allPoints.map(p => Math.min(p.val, p.lower_95 != null ? p.lower_95 : p.val)), 0));
  const maxVal = Math.max(...allPoints.map(p => Math.max(p.val, p.upper_95 != null ? p.upper_95 : p.val)), 10) * 1.1;

  const getTsX = (index) => {
    if (allPoints.length <= 1) return tsMargin.left + tsInnerW / 2;
    return tsMargin.left + (index / (allPoints.length - 1)) * tsInnerW;
  };

  const getTsY = (val) => {
    return tsMargin.top + tsInnerH - ((val - minVal) / (maxVal - minVal || 1)) * tsInnerH;
  };

  // Build SVG path strings
  let histPath = '';
  historicalPoints.forEach((p, i) => {
    const x = getTsX(i);
    const y = getTsY(p.actual);
    histPath += i === 0 ? `M ${x} ${y}` : ` L ${x} ${y}`;
  });

  let forecastPath = '';
  if (historicalPoints.length > 0 && forecastPoints.length > 0) {
    const lastHist = historicalPoints[historicalPoints.length - 1];
    forecastPath = `M ${getTsX(historicalPoints.length - 1)} ${getTsY(lastHist.actual)}`;
    forecastPoints.forEach((p, i) => {
      const x = getTsX(historicalPoints.length + i);
      const y = getTsY(p.forecast);
      forecastPath += ` L ${x} ${y}`;
    });
  }

  // Build 95% Confidence Interval polygon
  let ciPolygon = '';
  if (historicalPoints.length > 0 && forecastPoints.length > 0) {
    const lastHist = historicalPoints[historicalPoints.length - 1];
    const topPoints = [`${getTsX(historicalPoints.length - 1)},${getTsY(lastHist.actual)}`];
    const bottomPoints = [`${getTsX(historicalPoints.length - 1)},${getTsY(lastHist.actual)}`];

    forecastPoints.forEach((p, i) => {
      const x = getTsX(historicalPoints.length + i);
      topPoints.push(`${x},${getTsY(p.upper_95)}`);
      bottomPoints.push(`${x},${getTsY(p.lower_95)}`);
    });

    bottomPoints.reverse();
    ciPolygon = topPoints.concat(bottomPoints).join(' ');
  }

  return (
    <div className="visual-analytics-panel">
      <div className="section-title-row">
        <div>
          <h3>Visual Analytics & Time-Series Intelligence</h3>
          <p className="subtitle">
            Universal multi-metric distributions and Holt-Winters trend forecasting with out-of-sample prediction intervals.
          </p>
        </div>
      </div>

      <div className="charts-dual-grid">
        {/* Bar Chart */}
        <div className="chart-box">
          <div className="chart-header">
            <h4>{activeBarChart?.title || `${activeMetric || 'Metric'} Breakdown`}</h4>
            <span className="badge-sub">{activeBarChart?.unit || 'value'}</span>
          </div>

          {/* Metric Selector Pills */}
          {availableMetrics.length > 1 && (
            <div className="metric-pills-row">
              <span className="pills-label">Metric:</span>
              {availableMetrics.map(col => (
                <button
                  key={col}
                  className={`metric-pill ${activeMetric === col ? 'active' : ''}`}
                  onClick={() => {
                    setSelectedMetric(col);
                    setHoveredBar(null);
                  }}
                >
                  {col}
                </button>
              ))}
            </div>
          )}

          {barData.length === 0 ? (
            <div className="chart-empty">No categorical breakdown available for this metric.</div>
          ) : (
            <div className="chart-svg-wrap">
              <svg viewBox={`0 0 ${barSvgWidth} ${barSvgHeight}`} className="responsive-svg">
                {/* Grid horizontal lines */}
                {[0, 0.25, 0.5, 0.75, 1].map((ratio) => {
                  const y = barMargin.top + innerHeight * (1 - ratio);
                  const val = Math.round(maxBarVal * ratio);
                  return (
                    <g key={ratio}>
                      <line
                        x1={barMargin.left}
                        y1={y}
                        x2={barSvgWidth - barMargin.right}
                        y2={y}
                        stroke="var(--border-color, #334155)"
                        strokeDasharray="3 3"
                        opacity={0.4}
                      />
                      <text
                        x={barMargin.left - 8}
                        y={y + 4}
                        textAnchor="end"
                        fontSize="10"
                        fill="var(--text-muted, #94a3b8)"
                      >
                        {val}
                      </text>
                    </g>
                  );
                })}

                {/* Bars */}
                {barData.map((bar, idx) => {
                  const barH = (bar.value / maxBarVal) * innerHeight;
                  const x = barMargin.left + idx * barSlotWidth + (barSlotWidth - barWidth) / 2;
                  const y = barMargin.top + innerHeight - barH;
                  const isHovered = hoveredBar === idx;

                  return (
                    <g
                      key={idx}
                      onMouseEnter={() => setHoveredBar(idx)}
                      onMouseLeave={() => setHoveredBar(null)}
                      style={{ cursor: 'pointer' }}
                    >
                      <rect
                        x={x}
                        y={y}
                        width={barWidth}
                        height={Math.max(barH, 2)}
                        rx="4"
                        fill={isHovered ? 'var(--primary-color, #38bdf8)' : 'var(--bar-color, #0ea5e9)'}
                        opacity={isHovered ? 1 : 0.85}
                        style={{ transition: 'all 0.2s ease' }}
                      />
                      {/* Bar Value Tooltip on top */}
                      <text
                        x={x + barWidth / 2}
                        y={y - 6}
                        textAnchor="middle"
                        fontSize="11"
                        fontWeight="600"
                        fill={isHovered ? 'var(--text-bright, #fff)' : 'var(--text-muted, #94a3b8)'}
                      >
                        {bar.value}
                      </text>
                      {/* X-axis label */}
                      <text
                        x={x + barWidth / 2}
                        y={barSvgHeight - 12}
                        textAnchor="middle"
                        fontSize="10"
                        fill="var(--text-muted, #94a3b8)"
                      >
                        {bar.label.length > 8 ? `${bar.label.slice(0, 7)}…` : bar.label}
                      </text>
                    </g>
                  );
                })}
              </svg>
            </div>
          )}
        </div>

        {/* Donut Chart */}
        <div className="chart-box">
          <div className="chart-header">
            <h4>{activeDonutChart?.title || `${activeCategory || 'Category'} Profile`}</h4>
            <span className="badge-sub">{totalDonutCount} total records</span>
          </div>

          {/* Category Selector Pills */}
          {availableCategories.length > 1 && (
            <div className="metric-pills-row">
              <span className="pills-label">Segment:</span>
              {availableCategories.map(cat => (
                <button
                  key={cat}
                  className={`metric-pill ${activeCategory === cat ? 'active' : ''}`}
                  onClick={() => {
                    setSelectedCategory(cat);
                    setHoveredSlice(null);
                  }}
                >
                  {cat}
                </button>
              ))}
            </div>
          )}

          {donutSlices.length === 0 ? (
            <div className="chart-empty">No distribution segments available.</div>
          ) : (
            <div className="donut-layout">
              <div className="donut-svg-wrap">
                <svg viewBox={`0 0 ${donutSize} ${donutSize}`} className="donut-svg">
                  {renderedArcs.map((arc, idx) => (
                    <path
                      key={idx}
                      d={arc.pathData}
                      fill={arc.color || `hsl(${idx * 75 + 180}, 70%, 55%)`}
                      stroke="var(--bg-card, #0f172a)"
                      strokeWidth="2.5"
                      opacity={hoveredSlice === idx ? 1 : 0.9}
                      transform={hoveredSlice === idx ? 'scale(1.03) translate(-3, -3)' : ''}
                      onMouseEnter={() => setHoveredSlice(idx)}
                      onMouseLeave={() => setHoveredSlice(null)}
                      style={{ cursor: 'pointer', transition: 'transform 0.15s ease' }}
                    />
                  ))}
                  {/* Donut Center Count */}
                  <text
                    x={donutCenter}
                    y={donutCenter - 4}
                    textAnchor="middle"
                    fontSize="20"
                    fontWeight="700"
                    fill="var(--text-bright, #fff)"
                  >
                    {hoveredSlice != null ? donutSlices[hoveredSlice]?.count : totalDonutCount}
                  </text>
                  <text
                    x={donutCenter}
                    y={donutCenter + 16}
                    textAnchor="middle"
                    fontSize="11"
                    fill="var(--text-muted, #94a3b8)"
                  >
                    {hoveredSlice != null ? donutSlices[hoveredSlice]?.label : 'Total Analyzed'}
                  </text>
                </svg>
              </div>

              <div className="donut-legend">
                {donutSlices.map((slice, idx) => (
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
          )}
        </div>
      </div>

      {/* Time-Series Forecasting Chart */}
      {activeForecastData && (
        <div className="chart-box forecast-card" style={{ marginTop: '20px' }}>
          <div className="forecast-header">
            <div>
              <div className="forecast-title-row">
                <h4>AI Time-Series Forecasting: {activeForecastData.target_column || activeForecastMetric}</h4>
                <span className={`trend-badge ${activeForecastData.metrics?.trend_direction?.toLowerCase().replace(/[^a-z]/g, '-')}`}>
                  {activeForecastData.metrics?.trend_direction || 'Damped Trend'}
                </span>
              </div>

              {/* Measure Selector Pills */}
              {availableForecastMetrics.length > 1 && (
                <div className="metric-pills-row" style={{ marginTop: '0.4rem', marginBottom: '0.5rem' }}>
                  <span className="pills-label">Measure:</span>
                  {availableForecastMetrics.map(col => (
                    <button
                      key={col}
                      className={`metric-pill ${activeForecastMetric === col ? 'active' : ''}`}
                      onClick={() => {
                        setSelectedForecastMetric(col);
                        setHoveredForecast(null);
                      }}
                    >
                      {col}
                    </button>
                  ))}
                </div>
              )}

              <div className="forecast-narrative">
                <MarkdownView content={activeForecastData.narrative} />
              </div>
            </div>

            <div className="forecast-metrics-pill-row">
              <div className="forecast-pill">
                <span className="pill-title">Fit R²</span>
                <span className="pill-value">{activeForecastData.metrics?.r_squared}</span>
              </div>
              <div className="forecast-pill">
                <span className="pill-title">MAPE Error</span>
                <span className="pill-value">{activeForecastData.metrics?.mape_pct}%</span>
              </div>
              <div className="forecast-pill">
                <span className="pill-title">Projected Shift</span>
                <span className="pill-value" style={{ color: activeForecastData.metrics?.projected_change_pct >= 0 ? '#10b981' : '#f59e0b' }}>
                  {activeForecastData.metrics?.projected_change_pct >= 0 ? `+${activeForecastData.metrics?.projected_change_pct}%` : `${activeForecastData.metrics?.projected_change_pct}%`}
                </span>
              </div>
            </div>
          </div>

          <div className="chart-svg-wrap">
            <svg viewBox={`0 0 ${tsSvgWidth} ${tsSvgHeight}`} className="responsive-svg">
              <defs>
                <linearGradient id="forecastConeGrad" x1="0" y1="0" x2="0" y2="1">
                  <stop offset="0%" stopColor="#818cf8" stopOpacity="0.28" />
                  <stop offset="100%" stopColor="#818cf8" stopOpacity="0.05" />
                </linearGradient>
              </defs>

              {/* Horizontal Grid lines */}
              {[0, 0.33, 0.66, 1].map((ratio) => {
                const y = tsMargin.top + tsInnerH * (1 - ratio);
                const val = (minVal + (maxVal - minVal) * ratio).toFixed(1);
                return (
                  <g key={ratio}>
                    <line
                      x1={tsMargin.left}
                      y1={y}
                      x2={tsSvgWidth - tsMargin.right}
                      y2={y}
                      stroke="var(--border-color, #334155)"
                      strokeDasharray="4 4"
                      opacity={0.35}
                    />
                    <text
                      x={tsMargin.left - 8}
                      y={y + 4}
                      textAnchor="end"
                      fontSize="10"
                      fill="var(--text-muted, #94a3b8)"
                    >
                      {val}
                    </text>
                  </g>
                );
              })}

              {/* Confidence Interval Shaded Cone */}
              {ciPolygon && (
                <polygon points={ciPolygon} fill="url(#forecastConeGrad)" />
              )}

              {/* Historical Trend Line (Solid Cyan) */}
              {histPath && (
                <path
                  d={histPath}
                  fill="none"
                  stroke="#38bdf8"
                  strokeWidth="2.5"
                  strokeLinecap="round"
                />
              )}

              {/* Forecast Line (Dashed Purple) */}
              {forecastPath && (
                <path
                  d={forecastPath}
                  fill="none"
                  stroke="#a855f7"
                  strokeWidth="2.5"
                  strokeDasharray="6 4"
                  strokeLinecap="round"
                />
              )}

              {/* Historical Markers */}
              {historicalPoints.map((p, idx) => {
                const x = getTsX(idx);
                const y = getTsY(p.actual);
                const isHovered = hoveredForecast?.idx === idx;
                return (
                  <g
                    key={`hist-${idx}`}
                    onMouseEnter={() => setHoveredForecast({ ...p, idx, isForecast: false, x, y })}
                    onMouseLeave={() => setHoveredForecast(null)}
                    style={{ cursor: 'pointer' }}
                  >
                    <circle
                      cx={x}
                      cy={y}
                      r={isHovered ? 6 : 3.5}
                      fill="#38bdf8"
                      stroke="var(--bg-card, #0f172a)"
                      strokeWidth="2"
                    />
                  </g>
                );
              })}

              {/* Forecast Markers */}
              {forecastPoints.map((p, idx) => {
                const overallIdx = historicalPoints.length + idx;
                const x = getTsX(overallIdx);
                const y = getTsY(p.forecast);
                const isHovered = hoveredForecast?.idx === overallIdx;
                return (
                  <g
                    key={`fc-${idx}`}
                    onMouseEnter={() => setHoveredForecast({ ...p, idx: overallIdx, isForecast: true, x, y })}
                    onMouseLeave={() => setHoveredForecast(null)}
                    style={{ cursor: 'pointer' }}
                  >
                    <circle
                      cx={x}
                      cy={y}
                      r={isHovered ? 6 : 4}
                      fill="#a855f7"
                      stroke="#fff"
                      strokeWidth="2"
                    />
                  </g>
                );
              })}

              {/* Legend Bottom */}
              <g transform={`translate(${tsMargin.left}, ${tsSvgHeight - 12})`}>
                <line x1="0" y1="0" x2="20" y2="0" stroke="#38bdf8" strokeWidth="2.5" />
                <text x="25" y="4" fontSize="10" fill="var(--text-muted, #94a3b8)">Historical Observations</text>

                <line x1="160" y1="0" x2="180" y2="0" stroke="#a855f7" strokeWidth="2.5" strokeDasharray="5 3" />
                <text x="185" y="4" fontSize="10" fill="var(--text-muted, #94a3b8)">Holt's Damped Forecast</text>

                <rect x="335" y="-6" width="16" height="12" fill="#818cf8" opacity="0.3" rx="2" />
                <text x="358" y="4" fontSize="10" fill="var(--text-muted, #94a3b8)">95% Confidence Interval Cone</text>
              </g>

              {/* Active Tooltip */}
              {hoveredForecast && (
                <g transform={`translate(${Math.min(hoveredForecast.x + 10, tsSvgWidth - 140)}, ${Math.max(hoveredForecast.y - 45, 10)})`}>
                  <rect
                    width="130"
                    height="42"
                    rx="6"
                    fill="var(--bg-popup, #1e293b)"
                    stroke="var(--border-color, #475569)"
                    strokeWidth="1"
                    filter="drop-shadow(0 4px 6px rgba(0,0,0,0.3))"
                  />
                  <text x="8" y="16" fontSize="10" fill="#94a3b8">
                    {hoveredForecast.period}
                  </text>
                  <text x="8" y="32" fontSize="12" fontWeight="700" fill="#fff">
                    {hoveredForecast.isForecast
                      ? `Projected: ${hoveredForecast.forecast}`
                      : `Actual: ${hoveredForecast.actual}`}
                  </text>
                </g>
              )}
            </svg>
          </div>
        </div>
      )}
    </div>
  );
}
