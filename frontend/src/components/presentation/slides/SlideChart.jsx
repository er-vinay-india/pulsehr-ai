import React from "react";
import { BarChart3 } from "lucide-react";

// Lightweight interactive SVG Chart Renderer for browser presentations
export default function SlideChart({ chart, theme }) {
  if (!chart || !chart.categories || chart.categories.length === 0) {
    return (
      <div className="slide-chart-placeholder">
        <BarChart3 size={32} />
        <span>No chart data available</span>
      </div>
    );
  }

  const chartType = (chart.type || chart.chart_type || "column").toLowerCase();
  const palette = theme?.chart_palette || ["#ff8a62", "#7ee7d9", "#8ef0c8", "#a78bfa", "#fbbf24", "#f43f5e"];
  const categories = chart.categories;
  const seriesList = chart.series && chart.series.length > 0
    ? chart.series
    : [{ name: "Value", values: categories.map(() => 0) }];
  const unit = chart.unit || "";

  const formatNumber = (val) => {
    if (typeof val !== "number" || isNaN(val)) return "0";
    if (unit === "$") {
      if (val >= 1000000) return `$${(val / 1000000).toFixed(1)}M`;
      if (val >= 1000) return `$${(val / 1000).toFixed(1)}k`;
      return `$${val.toFixed(0)}`;
    }
    if (unit === "%") return `${val.toFixed(1)}%`;
    if (val >= 1000000) return `${(val / 1000000).toFixed(1)}M`;
    if (val >= 1000) return `${(val / 1000).toFixed(1)}k`;
    return val % 1 === 0 ? val.toString() : val.toFixed(1);
  };

  // --- 1. PIE & DONUT CHARTS ---
  if (chartType === "donut" || chartType === "pie") {
    const isPie = chartType === "pie";
    const primarySeries = seriesList[0] || { values: [] };
    const values = (primarySeries.values || []).map(v => Math.max(0, Number(v) || 0));
    const total = values.reduce((a, b) => a + b, 0) || 1;

    let accumulatedAngle = 0;
    const slices = values.map((val, idx) => {
      const angle = (val / total) * 360;
      const startAngle = accumulatedAngle;
      accumulatedAngle += angle;
      return {
        label: categories[idx] || `Slice ${idx + 1}`,
        value: val,
        pct: Math.round((val / total) * 100),
        color: palette[idx % palette.length],
        startAngle,
        angle
      };
    });

    return (
      <div className={`slide-chart-container ${isPie ? "pie-view" : "donut-view"}`}>
        <div className="donut-graphic-wrap">
          <svg viewBox="0 0 100 100" className="donut-svg">
            {isPie ? (
              // Solid Pie Slices
              slices.map((slice, i) => {
                if (slice.angle >= 359.9) {
                  return <circle key={i} cx="50" cy="50" r="42" fill={slice.color} />;
                }
                const startRad = ((slice.startAngle - 90) * Math.PI) / 180;
                const endRad = ((slice.startAngle + slice.angle - 90) * Math.PI) / 180;
                const x1 = 50 + 42 * Math.cos(startRad);
                const y1 = 50 + 42 * Math.sin(startRad);
                const x2 = 50 + 42 * Math.cos(endRad);
                const y2 = 50 + 42 * Math.sin(endRad);
                const largeArc = slice.angle > 180 ? 1 : 0;
                const pathD = `M 50,50 L ${x1.toFixed(2)},${y1.toFixed(2)} A 42,42 0 ${largeArc},1 ${x2.toFixed(2)},${y2.toFixed(2)} Z`;
                return <path key={i} d={pathD} fill={slice.color} stroke="rgba(23,20,18,0.5)" strokeWidth="1" />;
              })
            ) : (
              // Donut Ring Slices
              <>
                <circle cx="50" cy="50" r="35" fill="none" stroke="rgba(255,255,255,0.08)" strokeWidth="18" />
                {slices.map((slice, i) => {
                  const r = 35;
                  const c = 2 * Math.PI * r;
                  const strokeDasharray = `${(slice.angle / 360) * c} ${c}`;
                  const strokeDashoffset = -((slice.startAngle / 360) * c);
                  return (
                    <circle
                      key={i}
                      cx="50"
                      cy="50"
                      r={r}
                      fill="none"
                      stroke={slice.color}
                      strokeWidth="18"
                      strokeDasharray={strokeDasharray}
                      strokeDashoffset={strokeDashoffset}
                      transform="rotate(-90 50 50)"
                      className="donut-segment"
                    />
                  );
                })}
              </>
            )}
          </svg>
          {!isPie && (
            <div className="donut-center-label">
              <span className="donut-total">{total >= 1000 ? `${(total / 1000).toFixed(1)}k` : total.toLocaleString()}</span>
              <span className="donut-sub">{chart.unit || "Total"}</span>
            </div>
          )}
        </div>

        <div className="donut-legend">
          {slices.map((s, i) => (
            <div key={i} className="donut-legend-item">
              <span className="legend-dot" style={{ backgroundColor: s.color }} />
              <span className="legend-name" title={s.label}>{s.label}</span>
              <span className="legend-val">{s.pct}%</span>
            </div>
          ))}
          {chart.aggregation_disclosure && (
            <div className="chart-aggregation-note" title={chart.aggregation_disclosure}>
              {chart.aggregation_disclosure}
            </div>
          )}
        </div>
      </div>
    );
  }

  // --- 2. LINE CHART (MULTI-SERIES SUPPORT) ---
  if (chartType === "line") {
    const width = 460;
    const height = 220;
    const padding = 35;

    let allVals = [];
    seriesList.forEach(s => {
      (s.values || []).forEach(v => {
        const n = Number(v);
        if (!isNaN(n)) allVals.push(n);
      });
    });
    const maxVal = allVals.length ? Math.max(...allVals) : 1;
    const minVal = allVals.length ? Math.min(...allVals, 0) : 0;
    const range = maxVal - minVal || 1;

    return (
      <div className="slide-chart-container line-view">
        {seriesList.length > 1 && (
          <div className="chart-series-legend-bar">
            {seriesList.map((s, idx) => (
              <div key={idx} className="chart-series-pill">
                <span className="legend-dot" style={{ backgroundColor: palette[idx % palette.length] }} />
                <span className="series-pill-name">{s.name}</span>
              </div>
            ))}
          </div>
        )}
        <svg viewBox={`0 0 ${width} ${height}`} className="line-svg">
          <defs>
            <linearGradient id="lineGrad0" x1="0%" y1="0%" x2="0%" y2="100%">
              <stop offset="0%" stopColor={palette[0]} stopOpacity="0.3" />
              <stop offset="100%" stopColor={palette[0]} stopOpacity="0.0" />
            </linearGradient>
          </defs>
          {/* Grid lines */}
          <line x1={padding} y1={padding} x2={width - padding} y2={padding} stroke="rgba(255,255,255,0.08)" strokeDasharray="3 3" />
          <line x1={padding} y1={height / 2} x2={width - padding} y2={height / 2} stroke="rgba(255,255,255,0.08)" strokeDasharray="3 3" />
          <line x1={padding} y1={height - padding} x2={width - padding} y2={height - padding} stroke="rgba(255,255,255,0.15)" />

          {/* Render each series */}
          {seriesList.map((s, sIdx) => {
            const vals = (s.values || []).map(v => Number(v) || 0);
            const color = palette[sIdx % palette.length];
            const pts = vals.map((v, i) => {
              const x = padding + (i / Math.max(vals.length - 1, 1)) * (width - padding * 2);
              const y = height - padding - ((v - minVal) / range) * (height - padding * 2);
              return { x, y, val: v };
            });
            const pathD = pts.reduce((acc, p, i) => `${acc} ${i === 0 ? "M" : "L"} ${p.x} ${p.y}`, "");

            return (
              <g key={sIdx} className={`line-series-${sIdx}`}>
                {sIdx === 0 && pts.length > 1 && (
                  <path
                    d={`${pathD} L ${pts[pts.length - 1].x} ${height - padding} L ${pts[0].x} ${height - padding} Z`}
                    fill="url(#lineGrad0)"
                  />
                )}
                <path d={pathD} fill="none" stroke={color} strokeWidth="3" strokeLinecap="round" strokeLinejoin="round" />
                {pts.map((p, i) => (
                  <circle key={i} cx={p.x} cy={p.y} r="3.5" fill={color} stroke="#171412" strokeWidth="1.5" />
                ))}
              </g>
            );
          })}
        </svg>
        <div className="line-axis-labels">
          <span>{categories[0]}</span>
          {categories.length > 2 && <span>{categories[Math.floor(categories.length / 2)]}</span>}
          <span>{categories[categories.length - 1]}</span>
        </div>
      </div>
    );
  }

  // --- 3. BAR / HORIZONTAL GROUPED BARS ---
  const isHorizontal = chartType === "bar" || chartType === "horizontal_bar";
  if (isHorizontal) {
    let allVals = [];
    seriesList.forEach(s => {
      (s.values || []).forEach(v => {
        const n = Number(v);
        if (!isNaN(n)) allVals.push(n);
      });
    });
    const maxVal = allVals.length ? Math.max(...allVals) : 1;

    return (
      <div className="slide-chart-container bar-view">
        {seriesList.length > 1 && (
          <div className="chart-series-legend-bar">
            {seriesList.map((s, idx) => (
              <div key={idx} className="chart-series-pill">
                <span className="legend-dot" style={{ backgroundColor: palette[idx % palette.length] }} />
                <span className="series-pill-name">{s.name}</span>
              </div>
            ))}
          </div>
        )}
        <div className="bars-list">
          {categories.slice(0, 8).map((cat, idx) => (
            <div key={idx} className="bar-category-group">
              <span className="bar-label" title={cat}>{cat}</span>
              <div className="bar-series-subrows">
                {seriesList.map((s, sIdx) => {
                  const val = Number(s.values?.[idx]) || 0;
                  const pct = Math.min(100, Math.max(4, Math.round((val / maxVal) * 100)));
                  const color = palette[sIdx % palette.length];
                  return (
                    <div key={sIdx} className="bar-subrow">
                      <div className="bar-track">
                        <div className="bar-fill" style={{ width: `${pct}%`, backgroundColor: color }} />
                      </div>
                      <span className="bar-val">{formatNumber(val)}</span>
                    </div>
                  );
                })}
              </div>
            </div>
          ))}
        </div>
      </div>
    );
  }

  // --- 4. VERTICAL COLUMN CHART (CLUSTERED / GROUPED) ---
  let allVals = [];
  seriesList.forEach(s => {
    (s.values || []).forEach(v => {
      const n = Number(v);
      if (!isNaN(n)) allVals.push(n);
    });
  });
  const maxVal = allVals.length ? Math.max(...allVals) : 1;

  return (
    <div className="slide-chart-container column-view">
      {seriesList.length > 1 && (
        <div className="chart-series-legend-bar">
          {seriesList.map((s, idx) => (
            <div key={idx} className="chart-series-pill">
              <span className="legend-dot" style={{ backgroundColor: palette[idx % palette.length] }} />
              <span className="series-pill-name">{s.name}</span>
            </div>
          ))}
        </div>
      )}
      <div className="columns-wrap">
        {categories.slice(0, 8).map((cat, idx) => (
          <div key={idx} className="col-item-group">
            <div className="col-tracks-clustered">
              {seriesList.map((s, sIdx) => {
                const val = Number(s.values?.[idx]) || 0;
                const pct = Math.min(100, Math.max(6, Math.round((val / maxVal) * 100)));
                const color = palette[sIdx % palette.length];
                return (
                  <div key={sIdx} className="col-track-single">
                    <span className="col-val">{formatNumber(val)}</span>
                    <div className="col-track">
                      <div className="col-fill" style={{ height: `${pct}%`, backgroundColor: color }} />
                    </div>
                  </div>
                );
              })}
            </div>
            <span className="col-label" title={cat}>{cat}</span>
          </div>
        ))}
      </div>
    </div>
  );
}
