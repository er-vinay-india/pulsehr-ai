import React, { useState } from 'react';

export default function ForecastChart({ data, onInvestigate }) {
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
