import React, { useState } from "react";
import {
  TrendingUp,
  BarChart3,
  PieChart,
  ShieldCheck,
  Award,
  Layers,
  Sparkles,
  ChevronRight
} from "lucide-react";

// Safe inline Markdown parser for **bold** text runs
function FormattedText({ text, defaultColor }) {
  if (!text) return null;
  const parts = String(text).split(/(\*\*[^*]+\*\*)/g);
  return (
    <span>
      {parts.map((part, idx) => {
        if (part.startsWith("**") && part.endsWith("**")) {
          return (
            <strong key={idx} style={{ fontWeight: 700, color: "var(--brand-color, #ff8a62)" }}>
              {part.slice(2, -2)}
            </strong>
          );
        }
        return <span key={idx} style={{ color: defaultColor }}>{part}</span>;
      })}
    </span>
  );
}

// Lightweight interactive SVG Chart Renderer for browser presentations
function SlideChart({ chart, theme }) {
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
  const series = chart.series && chart.series.length > 0
    ? chart.series[0]
    : { name: "Value", values: categories.map(() => 0) };
  const values = (series.values || []).map(v => Number(v) || 0);

  const maxVal = Math.max(...values, 1);
  const minVal = Math.min(...values, 0);

  if (chartType === "donut" || chartType === "pie") {
    const total = values.reduce((a, b) => a + b, 0) || 1;
    let accumulatedAngle = 0;
    const slices = values.map((val, idx) => {
      const angle = (val / total) * 360;
      const startAngle = accumulatedAngle;
      accumulatedAngle += angle;
      return {
        label: categories[idx],
        value: val,
        pct: Math.round((val / total) * 100),
        color: palette[idx % palette.length],
        startAngle,
        angle
      };
    });

    return (
      <div className="slide-chart-container donut-view">
        <div className="donut-graphic-wrap">
          <svg viewBox="0 0 100 100" className="donut-svg">
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
          </svg>
          <div className="donut-center-label">
            <span className="donut-total">{total.toLocaleString()}</span>
            <span className="donut-sub">Total</span>
          </div>
        </div>

        <div className="donut-legend">
          {slices.map((s, i) => (
            <div key={i} className="donut-legend-item">
              <span className="legend-dot" style={{ backgroundColor: s.color }} />
              <span className="legend-name">{s.label}</span>
              <span className="legend-val">{s.pct}%</span>
            </div>
          ))}
        </div>
      </div>
    );
  }

  if (chartType === "line") {
    const width = 460;
    const height = 220;
    const padding = 35;
    const points = values.map((v, i) => {
      const x = padding + (i / Math.max(values.length - 1, 1)) * (width - padding * 2);
      const range = maxVal - minVal || 1;
      const y = height - padding - ((v - minVal) / range) * (height - padding * 2);
      return { x, y, val: v, cat: categories[i] };
    });

    const pathD = points.reduce((acc, p, i) => `${acc} ${i === 0 ? "M" : "L"} ${p.x} ${p.y}`, "");

    return (
      <div className="slide-chart-container line-view">
        <svg viewBox={`0 0 ${width} ${height}`} className="line-svg">
          <defs>
            <linearGradient id="lineGrad" x1="0%" y1="0%" x2="0%" y2="100%">
              <stop offset="0%" stopColor={palette[0]} stopOpacity="0.4" />
              <stop offset="100%" stopColor={palette[0]} stopOpacity="0.0" />
            </linearGradient>
          </defs>
          {/* Grid lines */}
          <line x1={padding} y1={padding} x2={width - padding} y2={padding} stroke="rgba(255,255,255,0.08)" strokeDasharray="3 3" />
          <line x1={padding} y1={height / 2} x2={width - padding} y2={height / 2} stroke="rgba(255,255,255,0.08)" strokeDasharray="3 3" />
          <line x1={padding} y1={height - padding} x2={width - padding} y2={height - padding} stroke="rgba(255,255,255,0.15)" />

          {/* Area fill */}
          {points.length > 1 && (
            <path
              d={`${pathD} L ${points[points.length - 1].x} ${height - padding} L ${points[0].x} ${height - padding} Z`}
              fill="url(#lineGrad)"
            />
          )}

          {/* Line stroke */}
          <path d={pathD} fill="none" stroke={palette[0]} strokeWidth="3" strokeLinecap="round" strokeLinejoin="round" />

          {/* Dots */}
          {points.map((p, i) => (
            <g key={i} className="line-point-group">
              <circle cx={p.x} cy={p.y} r="4" fill={palette[0]} stroke="#ffffff" strokeWidth="1.5" />
            </g>
          ))}
        </svg>
        <div className="line-axis-labels">
          <span>{categories[0]}</span>
          <span>{categories[Math.floor(categories.length / 2)]}</span>
          <span>{categories[categories.length - 1]}</span>
        </div>
      </div>
    );
  }

  // Default: Bar / Horizontal Bar / Column Chart
  const isHorizontal = chartType === "bar" || chartType === "horizontal_bar";

  if (isHorizontal) {
    return (
      <div className="slide-chart-container bar-view">
        <div className="bars-list">
          {categories.slice(0, 8).map((cat, idx) => {
            const val = values[idx] || 0;
            const pct = Math.min(100, Math.max(4, Math.round((val / maxVal) * 100)));
            const color = palette[idx % palette.length];
            return (
              <div key={idx} className="bar-row">
                <span className="bar-label" title={cat}>{cat}</span>
                <div className="bar-track">
                  <div className="bar-fill" style={{ width: `${pct}%`, backgroundColor: color }} />
                </div>
                <span className="bar-val">
                  {val > 1000 ? `$${(val / 1000).toFixed(1)}k` : val.toLocaleString()}
                </span>
              </div>
            );
          })}
        </div>
      </div>
    );
  }

  // Vertical Column Chart
  return (
    <div className="slide-chart-container column-view">
      <div className="columns-wrap">
        {categories.slice(0, 10).map((cat, idx) => {
          const val = values[idx] || 0;
          const pct = Math.min(100, Math.max(6, Math.round((val / maxVal) * 100)));
          const color = palette[idx % palette.length];
          return (
            <div key={idx} className="col-item">
              <span className="col-val">{val > 1000 ? `${(val / 1000).toFixed(0)}k` : val}</span>
              <div className="col-track">
                <div className="col-fill" style={{ height: `${pct}%`, backgroundColor: color }} />
              </div>
              <span className="col-label" title={cat}>{cat}</span>
            </div>
          );
        })}
      </div>
    </div>
  );
}

export default function PresentationSlideContent({
  slide,
  theme,
  isEditable = false,
  onUpdate = () => {}
}) {
  const [isEditingTitle, setIsEditingTitle] = useState(false);
  const [titleVal, setTitleVal] = useState(slide.title);

  const [isEditingNarrative, setIsEditingNarrative] = useState(false);
  const [narrativeVal, setNarrativeVal] = useState(slide.narrative);

  const layout = slide.layout || "chart_narrative";

  const handleTitleBlur = () => {
    setIsEditingTitle(false);
    if (titleVal !== slide.title) {
      onUpdate({ ...slide, title: titleVal });
    }
  };

  const handleNarrativeBlur = () => {
    setIsEditingNarrative(false);
    if (narrativeVal !== slide.narrative) {
      onUpdate({ ...slide, narrative: narrativeVal });
    }
  };

  const renderHeader = () => (
    <div className="slide-header-block">
      <div className="slide-category-tag" style={{ color: theme.brand_color }}>
        {slide.category || "EXECUTIVE REVIEW"}
      </div>
      {isEditable && isEditingTitle ? (
        <input
          type="text"
          className="slide-title-input"
          value={titleVal}
          onChange={e => setTitleVal(e.target.value)}
          onBlur={handleTitleBlur}
          onKeyDown={e => e.key === "Enter" && handleTitleBlur()}
          autoFocus
        />
      ) : (
        <h2
          className={`slide-main-title ${isEditable ? "editable-cursor" : ""}`}
          style={{ color: theme.primary_text }}
          onClick={() => isEditable && setIsEditingTitle(true)}
          title={isEditable ? "Click to edit title" : undefined}
        >
          {slide.title}
        </h2>
      )}
      {slide.subtitle && (
        <div className="slide-subtitle" style={{ color: theme.accent_color }}>
          {slide.subtitle}
        </div>
      )}
    </div>
  );

  const renderFooter = () => {
    const sources = slide.evidence_sources || [];
    const limitations = slide.limitations;
    return (
      <div className="slide-footer-block" style={{ color: theme.secondary_text }}>
        <div className="footer-left">
          <ShieldCheck size={13} style={{ color: theme.success_color }} />
          <span>
            {sources.length > 0 ? `Evidence: ${sources.join(" · ")}` : "Verified Deterministic Ground Truth Engine"}
          </span>
        </div>
        {limitations && (
          <div className="footer-right">
            <span>Scope: {limitations}</span>
          </div>
        )}
      </div>
    );
  };

  return (
    <div
      className={`slide-card-wrapper layout-${layout}`}
      style={{
        backgroundColor: theme.bg_color,
        color: theme.primary_text,
        "--brand-color": theme.brand_color,
        "--accent-color": theme.accent_color,
        "--card-bg": theme.card_bg,
        "--card-border": theme.card_border,
        "--primary-text": theme.primary_text,
        "--secondary-text": theme.secondary_text
      }}
    >
      {renderHeader()}

      <div className="slide-body-content">
        {/* LAYOUT 1: title_hero */}
        {layout === "title_hero" && (
          <div className="layout-grid title-hero-grid">
            <div className="hero-narrative-card" style={{ backgroundColor: theme.card_bg, borderColor: theme.card_border }}>
              {isEditable && isEditingNarrative ? (
                <textarea
                  className="slide-narrative-textarea"
                  value={narrativeVal}
                  onChange={e => setNarrativeVal(e.target.value)}
                  onBlur={handleNarrativeBlur}
                  autoFocus
                  rows={4}
                />
              ) : (
                <p
                  className={`hero-narrative-p ${isEditable ? "editable-cursor" : ""}`}
                  onClick={() => isEditable && setIsEditingNarrative(true)}
                  title={isEditable ? "Click to edit narrative" : undefined}
                >
                  <FormattedText text={slide.narrative} defaultColor={theme.primary_text} />
                </p>
              )}

              {slide.bullets && slide.bullets.length > 0 && (
                <ul className="hero-bullet-list">
                  {slide.bullets.map((b, i) => (
                    <li key={i} className="hero-bullet-item">
                      <span className="bullet-indicator" style={{ backgroundColor: theme.brand_color }} />
                      <FormattedText text={b} defaultColor={theme.secondary_text} />
                    </li>
                  ))}
                </ul>
              )}
            </div>

            <div className="hero-metrics-column">
              {(slide.metrics || []).map((m, i) => (
                <div key={i} className="hero-metric-tile" style={{ backgroundColor: theme.card_bg, borderColor: theme.card_border }}>
                  <div className="metric-tile-val" style={{ color: theme.brand_color }}>{m.value}</div>
                  <div className="metric-tile-lbl" style={{ color: theme.primary_text }}>{m.label}</div>
                  <div className="metric-tile-sub" style={{ color: theme.secondary_text }}>{m.subtext}</div>
                </div>
              ))}
            </div>
          </div>
        )}

        {/* LAYOUT 2: kpi_summary */}
        {layout === "kpi_summary" && (
          <div className="layout-kpi-summary">
            {slide.narrative && (
              <div className="kpi-top-narrative" style={{ color: theme.primary_text }}>
                <FormattedText text={slide.narrative} defaultColor={theme.primary_text} />
              </div>
            )}

            <div className="kpi-cards-row">
              {(slide.metrics || []).map((m, i) => (
                <div key={i} className="kpi-score-card" style={{ backgroundColor: theme.card_bg, borderColor: theme.card_border }}>
                  <div className="kpi-card-header">
                    <span className="kpi-card-label" style={{ color: theme.brand_color }}>{m.label}</span>
                    <TrendingUp size={15} style={{ color: theme.accent_color }} />
                  </div>
                  <div className="kpi-card-value" style={{ color: theme.primary_text }}>{m.value}</div>
                  <div className="kpi-card-sub" style={{ color: theme.secondary_text }}>{m.subtext}</div>
                </div>
              ))}
            </div>

            {slide.bullets && slide.bullets.length > 0 && (
              <div className="kpi-takeaways-card" style={{ backgroundColor: theme.card_bg, borderColor: theme.card_border }}>
                <div className="takeaways-header" style={{ color: theme.accent_color }}>
                  <Award size={14} />
                  <span>KEY OBSERVATIONS & THRESHOLDS</span>
                </div>
                <div className="takeaways-bullets">
                  {slide.bullets.map((b, i) => (
                    <div key={i} className="takeaway-item">
                      <span className="bullet-dot" style={{ backgroundColor: theme.brand_color }} />
                      <FormattedText text={b} defaultColor={theme.secondary_text} />
                    </div>
                  ))}
                </div>
              </div>
            )}
          </div>
        )}

        {/* LAYOUT 3: chart_narrative */}
        {layout === "chart_narrative" && (
          <div className="layout-grid chart-narrative-grid">
            <div className="narrative-side-card" style={{ backgroundColor: theme.card_bg, borderColor: theme.card_border }}>
              {isEditable && isEditingNarrative ? (
                <textarea
                  className="slide-narrative-textarea"
                  value={narrativeVal}
                  onChange={e => setNarrativeVal(e.target.value)}
                  onBlur={handleNarrativeBlur}
                  autoFocus
                  rows={4}
                />
              ) : (
                <p
                  className={`narrative-lead ${isEditable ? "editable-cursor" : ""}`}
                  onClick={() => isEditable && setIsEditingNarrative(true)}
                  title={isEditable ? "Click to edit narrative" : undefined}
                >
                  <FormattedText text={slide.narrative} defaultColor={theme.primary_text} />
                </p>
              )}

              {slide.bullets && slide.bullets.length > 0 && (
                <ul className="slide-bullets-stack">
                  {slide.bullets.map((b, i) => (
                    <li key={i} className="slide-bullet-row">
                      <ChevronRight size={14} style={{ color: theme.brand_color, flexShrink: 0, marginTop: 3 }} />
                      <FormattedText text={b} defaultColor={theme.secondary_text} />
                    </li>
                  ))}
                </ul>
              )}

              {slide.metrics && slide.metrics.length > 0 && (
                <div className="callout-metrics-row">
                  {slide.metrics.map((m, i) => (
                    <div key={i} className="mini-callout-pill" style={{ borderColor: theme.card_border }}>
                      <span className="pill-val" style={{ color: theme.brand_color }}>{m.value}</span>
                      <span className="pill-lbl" style={{ color: theme.secondary_text }}>{m.label}</span>
                    </div>
                  ))}
                </div>
              )}
            </div>

            <div className="chart-side-card" style={{ backgroundColor: theme.card_bg, borderColor: theme.card_border }}>
              <SlideChart chart={slide.chart} theme={theme} />
            </div>
          </div>
        )}

        {/* LAYOUT 4: comparison_split */}
        {layout === "comparison_split" && (
          <div className="layout-grid comparison-split-grid">
            <div className="recommendations-card" style={{ backgroundColor: theme.card_bg, borderColor: theme.card_border }}>
              <h3 className="card-subhead" style={{ color: theme.accent_color }}>Operational Recommendations</h3>
              <p className="rec-narrative">
                <FormattedText text={slide.narrative} defaultColor={theme.primary_text} />
              </p>
              <div className="rec-bullets-list">
                {(slide.bullets || []).map((b, i) => (
                  <div key={i} className="rec-bullet-box">
                    <span className="rec-number" style={{ color: theme.brand_color }}>0{i+1}</span>
                    <FormattedText text={b} defaultColor={theme.secondary_text} />
                  </div>
                ))}
              </div>
            </div>

            <div className="priorities-card-stack">
              {(slide.metrics || [
                { label: "Phase 1", value: "Immediate Alignment", subtext: "0 - 30 Days" },
                { label: "Phase 2", value: "Variance Mitigation", subtext: "Quarterly Review" },
                { label: "Phase 3", value: "Automated Governance", subtext: "Long-term Monitoring" }
              ]).map((m, i) => (
                <div key={i} className="priority-tier-card" style={{ backgroundColor: theme.card_bg, borderColor: theme.card_border }}>
                  <div className="priority-step" style={{ color: theme.accent_color }}>{m.label}</div>
                  <div className="priority-title" style={{ color: theme.brand_color }}>{m.value}</div>
                  <div className="priority-sub" style={{ color: theme.secondary_text }}>{m.subtext}</div>
                </div>
              ))}
            </div>
          </div>
        )}

        {/* LAYOUT 5: table_detail */}
        {layout === "table_detail" && (
          <div className="layout-table-detail">
            {slide.narrative && (
              <p className="table-intro-narrative" style={{ color: theme.secondary_text }}>
                <FormattedText text={slide.narrative} defaultColor={theme.secondary_text} />
              </p>
            )}

            {slide.table && (
              <div className="table-responsive-container" style={{ borderColor: theme.card_border }}>
                <table className="presentation-data-table">
                  <thead>
                    <tr>
                      {(slide.table.headers || []).map((h, i) => (
                        <th key={i} style={{ color: theme.brand_color, backgroundColor: theme.card_bg }}>{h}</th>
                      ))}
                    </tr>
                  </thead>
                  <tbody>
                    {(slide.table.rows || []).slice(0, 8).map((row, rIdx) => (
                      <tr key={rIdx} style={{ borderBottomColor: theme.card_border }}>
                        {row.map((cell, cIdx) => (
                          <td key={cIdx} style={{ color: cIdx === 0 ? theme.primary_text : theme.secondary_text }}>
                            {String(cell)}
                          </td>
                        ))}
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          </div>
        )}
      </div>

      {renderFooter()}
    </div>
  );
}
