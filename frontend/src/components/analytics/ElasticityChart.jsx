import React, { useState } from 'react';

export default function ElasticityChart({ data, onInvestigate }) {
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
