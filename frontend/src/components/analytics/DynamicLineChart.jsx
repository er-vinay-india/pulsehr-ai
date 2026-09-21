import React, { useState, useMemo } from 'react';
import { Table } from 'lucide-react';
import { formatDisplayLabel } from '../../utils/displayFormatters';
import ChartDetailModal from './ChartDetailModal';

export default function DynamicLineChart({ visualization, onInvestigate }) {
  const lineData = visualization.line_data || {};
  const points = lineData.points || [];
  const unit = visualization.unit || '';
  const isCurrency = unit === '$';
  const availableYears = lineData.available_years || [];
  const isDense = points.length > 30;

  const [rangeMode, setRangeMode] = useState('all');
  const [hoveredPoint, setHoveredPoint] = useState(null);
  const [showDetailModal, setShowDetailModal] = useState(false);

  const activePoints = useMemo(() => {
    if (!isDense || rangeMode === 'all') return points;
    if (rangeMode === 'last52') return points.slice(-52);
    if (rangeMode.startsWith('year:')) {
      const yr = rangeMode.split(':')[1];
      return points.filter((p) => p.period.startsWith(yr));
    }
    return points;
  }, [points, isDense, rangeMode]);

  if (!points || points.length === 0) {
    return (
      <div className="dynamic-line-empty" style={{ padding: '2rem', textAlign: 'center', color: 'var(--text-muted)' }}>
        <p>No continuous chronological observations available for plotting.</p>
      </div>
    );
  }

  const values = activePoints.map((p) => p.value);
  const minVal = values.length > 0 ? Math.min(...values) : 0;
  const maxVal = values.length > 0 ? Math.max(...values) : 1;
  const valRange = Math.max(1, maxVal - minVal);
  const rangeMean = values.length > 0 ? values.reduce((a, b) => a + b, 0) / values.length : 0;

  const svgW = 700;
  const svgH = 210;
  const padX = 55;
  const padY = 25;

  const getX = (idx) => padX + (idx / Math.max(1, activePoints.length - 1)) * (svgW - padX * 2);
  const getY = (val) => svgH - padY - ((val - minVal) / valRange) * (svgH - padY * 2);

  const pointsStr = activePoints.map((p, i) => `${getX(i)},${getY(p.value)}`).join(' ');
  const areaPointsStr = `${getX(0)},${svgH - padY} ${pointsStr} ${getX(activePoints.length - 1)},${svgH - padY}`;

  const formatVal = (v) => {
    if (v == null || isNaN(v)) return '—';
    if (isCurrency) {
      if (Math.abs(v) >= 1_000_000_000) return `$${(v / 1_000_000_000).toFixed(2)}B`;
      if (Math.abs(v) >= 1_000_000) return `$${(v / 1_000_000).toFixed(2)}M`;
      if (Math.abs(v) >= 1_000) return `$${(v / 1_000).toFixed(1)}k`;
      return `$${Number(v).toFixed(2)}`;
    }
    return `${Number(v).toLocaleString()} ${unit}`;
  };

  const tickCount = Math.min(6, activePoints.length);
  const tickIndices = Array.from({ length: tickCount }, (_, i) =>
    Math.round((i / Math.max(1, tickCount - 1)) * (activePoints.length - 1))
  );

  const pointsWithRanks = useMemo(() => {
    return points.map((p, idx) => ({
      rank: idx + 1,
      label: p.period,
      value: p.value
    }));
  }, [points]);

  return (
    <div className="dynamic-line-chart-wrap bounded-chart-container">
      {/* Dense Time-Series Range Presets & Table Button */}
      {isDense && (
        <div className="line-range-toolbar">
          <div className="range-pills-group">
            <button
              type="button"
              className={`range-pill-btn ${rangeMode === 'all' ? 'active' : ''}`}
              onClick={() => setRangeMode('all')}
            >
              All ({points.length} wks)
            </button>
            <button
              type="button"
              className={`range-pill-btn ${rangeMode === 'last52' ? 'active' : ''}`}
              onClick={() => setRangeMode('last52')}
            >
              Last 52 Wks (1Y)
            </button>
            {availableYears.map((yr) => (
              <button
                key={yr}
                type="button"
                className={`range-pill-btn ${rangeMode === `year:${yr}` ? 'active' : ''}`}
                onClick={() => setRangeMode(`year:${yr}`)}
              >
                {yr}
              </button>
            ))}
          </div>

          <button
            type="button"
            className="btn-line-table-view"
            onClick={() => setShowDetailModal(true)}
            title="View complete time-series table"
          >
            <Table size={12} />
            <span>Table View</span>
          </button>
        </div>
      )}

      {/* SVG Canvas (Bounded Height) */}
      <div className="line-chart-svg-container">
        <svg viewBox={`0 0 ${svgW} ${svgH}`} className="dynamic-line-svg" preserveAspectRatio="none">
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
          {activePoints.map((p, i) => {
            const cx = getX(i);
            const cy = getY(p.value);
            const isHovered = hoveredPoint?.period === p.period;

            return (
              <circle
                key={i}
                cx={cx}
                cy={cy}
                r={isHovered ? 6 : (activePoints.length > 50 ? 2.5 : 3.5)}
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
            const p = activePoints[idx];
            if (!p) return null;
            return (
              <text
                key={idx}
                x={getX(idx)}
                y={svgH - padY + 16}
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

      {/* Interactive Tooltip & Status Strip */}
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
          <span>Date: <strong>{hoveredPoint.period}</strong></span>
          <span className="pill-sep">·</span>
          <span>{visualization.metric_label || formatDisplayLabel(visualization.metric_col || 'Measure')}: <strong>{formatVal(hoveredPoint.value)}</strong></span>
          {rangeMean > 0 && (
            <>
              <span className="pill-sep">·</span>
              <span style={{ color: hoveredPoint.value >= rangeMean ? '#10b981' : '#f43f5e' }}>
                {hoveredPoint.value >= rangeMean ? '+' : ''}{(((hoveredPoint.value - rangeMean) / rangeMean) * 100).toFixed(1)}% vs period avg
              </span>
            </>
          )}
          <span className="pill-click-hint">Click to investigate date →</span>
        </div>
      ) : (
        <div className="line-hover-pill idle">
          <span>
            Showing <strong>{activePoints.length}</strong> of <strong>{points.length}</strong> dates ({activePoints[0]?.period} to {activePoints[activePoints.length - 1]?.period}) · Avg: <strong>{formatVal(rangeMean)}</strong>
          </span>
          <span className="pill-hint">Hover point for detail · Click to investigate</span>
        </div>
      )}

      {/* Detail Table Modal */}
      <ChartDetailModal
        isOpen={showDetailModal}
        onClose={() => setShowDetailModal(false)}
        title={visualization.title}
        subtitle={visualization.subtitle}
        items={pointsWithRanks}
        benchmarkMean={rangeMean}
        unit={unit}
        isCurrency={isCurrency}
        entityLabel="Period Date"
        metricName={visualization.metric_label || formatDisplayLabel(visualization.metric_col || visualization.measured_metric)}
        population={visualization.population}
        entityType="time_series"
        sheetId={visualization.sheet_ids?.[0]}
        onInvestigate={onInvestigate}
      />
    </div>
  );
}
