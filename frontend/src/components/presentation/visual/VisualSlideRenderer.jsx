import React from "react";
import { ShieldCheck, ArrowRight } from "lucide-react";
import SlideChart from "../slides/SlideChart.jsx";
import FormattedText from "../slides/FormattedText.jsx";

export default function VisualSlideRenderer({
  slide,
  visualSpec,
  theme = {},
  isEditable = false,
  onUpdate = () => {},
  onViewEvidence = () => {}
}) {
  const spec = visualSpec || slide?.visual_spec;
  if (!spec) return null;

  const tokens = spec.design_tokens || {};
  const primaryText = tokens.primary_text || theme.primary_text || "#f8fafc";
  const secondaryText = tokens.secondary_text || theme.secondary_text || "#94a3b8";
  const accentColor = tokens.accent || theme.accent_color || "#ff5722";
  const cardBg = tokens.surface || theme.card_bg || "#1e293b";
  const cardBorder = tokens.border || theme.card_border || "rgba(255, 255, 255, 0.08)";

  const headline = spec.headline || slide.title || "Executive Briefing";
  const subtitle = spec.subtitle || slide.subtitle || "";
  const kpis = spec.kpis || slide.metrics || [];
  const insights = spec.insights || slide.bullets || [];
  const tableData = spec.table_data || slide.table;
  const footer = spec.source_footer || {};

  // Render Diagram / Process
  const renderDiagram = () => {
    if (!spec.diagram_spec) return null;
    const nodes = spec.diagram_spec.nodes || [];
    return (
      <div className="visual-process-container">
        {nodes.map((n, idx) => (
          <React.Fragment key={n.id || idx}>
            <div className="process-node" style={{ borderColor: accentColor }}>
              <div className="node-label" style={{ color: primaryText }}>{n.label}</div>
              {n.sublabel && <div className="node-sublabel" style={{ color: secondaryText }}>{n.sublabel}</div>}
            </div>
            {idx < nodes.length - 1 && (
              <div className="process-arrow" style={{ color: secondaryText }}>
                <ArrowRight size={18} />
              </div>
            )}
          </React.Fragment>
        ))}
      </div>
    );
  };

  // Render Matrix
  const renderMatrix = () => {
    if (!spec.matrix_spec) return null;
    const quadrants = spec.matrix_spec.quadrants || [];
    return (
      <div className="visual-matrix-container">
        {quadrants.map((q, idx) => (
          <div key={q.id || idx} className="matrix-quadrant" style={{ borderColor: cardBorder }}>
            <div className="quadrant-title" style={{ color: accentColor }}>{q.label}</div>
            <div className="quadrant-desc" style={{ color: secondaryText }}>{q.description}</div>
            {q.items && q.items.length > 0 && (
              <div style={{ marginTop: 6, fontSize: "11px", color: primaryText, fontWeight: 500 }}>
                {q.items.join(" · ")}
              </div>
            )}
          </div>
        ))}
      </div>
    );
  };

  // Render Table
  const renderTable = () => {
    if (!tableData || !tableData.rows || tableData.rows.length === 0) return null;
    return (
      <div className="card h-100" style={{ background: cardBg, borderColor: cardBorder }}>
        <div className="card-body p-2" style={{ overflowX: "auto" }}>
          <table className="w-100" style={{ borderCollapse: "collapse" }}>
            <thead>
              <tr>
                {(tableData.headers || []).map((h, idx) => (
                  <th
                    key={idx}
                    style={{
                      padding: "8px 12px",
                      borderBottom: `2px solid ${cardBorder}`,
                      textAlign: "left",
                      fontSize: "12px",
                      color: secondaryText,
                      fontWeight: 600
                    }}
                  >
                    {h}
                  </th>
                ))}
              </tr>
            </thead>
            <tbody>
              {tableData.rows.slice(0, 7).map((r, rIdx) => (
                <tr key={rIdx}>
                  {(Array.isArray(r) ? r : Object.values(r)).map((cell, cIdx) => (
                    <td
                      key={cIdx}
                      style={{
                        padding: "8px 12px",
                        borderBottom: `1px solid ${cardBorder}`,
                        fontSize: "12px",
                        color: primaryText
                      }}
                    >
                      {cell}
                    </td>
                  ))}
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>
    );
  };

  const hasChart = Boolean(spec.chart_spec || slide.chart);
  const chartPayload = slide.chart || (spec.chart_spec ? {
    chart_type: spec.chart_spec.family?.toLowerCase()?.includes("line") ? "line" : (spec.chart_spec.family?.toLowerCase()?.includes("donut") ? "donut" : "bar"),
    title: spec.chart_spec.title || headline,
    subtitle: spec.chart_spec.subtitle || subtitle,
    categories: spec.chart_spec.categories,
    series: spec.chart_spec.series?.map(s => ({ name: s.name, values: s.data })) || []
  } : null);

  return (
    <div
      className="presentation-runtime w-100 h-100 d-flex flex-column justify-content-between"
      style={{
        padding: "24px 32px",
        background: tokens.background || theme.bg_color || "#0f172a",
        color: primaryText
      }}
    >
      {/* 1. SLIDE HEADER */}
      <header className="mb-3">
        <div className="d-flex justify-content-between align-items-center mb-1">
          <span
            className="text-uppercase fw-bold"
            style={{ fontSize: "11px", letterSpacing: "0.08em", color: accentColor }}
          >
            {spec.visual_story?.primary_message ? "Strategic Analysis" : "Executive Briefing"}
          </span>
          {slide.evidence_id && (
            <button
              type="button"
              className="slide-evidence-badge-btn"
              onClick={() => onViewEvidence && onViewEvidence(slide)}
              title="Inspect ground-truth evidence audit trail"
            >
              <ShieldCheck size={12} />
              <span>{slide.evidence_id}</span>
            </button>
          )}
        </div>
        <h2
          className="fw-bold mb-1"
          style={{ fontSize: "26px", lineHeight: "1.25", color: primaryText }}
        >
          <FormattedText text={headline} />
        </h2>
        {subtitle && (
          <p className="mb-0" style={{ fontSize: "14px", color: secondaryText, lineHeight: "1.4" }}>
            <FormattedText text={subtitle} />
          </p>
        )}
      </header>

      {/* 2. SLIDE BODY: GRID LAYOUT */}
      <main className="flex-grow-1 d-flex flex-column gap-3" style={{ minHeight: 0 }}>
        {/* KPI Row (if present) */}
        {kpis && kpis.length > 0 && (
          <div className="visual-kpi-grid">
            {kpis.map((k, idx) => (
              <div key={idx} className="visual-kpi-card">
                <div className="kpi-label">{k.label}</div>
                <div className="kpi-value" style={{ color: accentColor }}>{k.value}</div>
                {k.subtext && <div className="kpi-subtext">{k.subtext}</div>}
              </div>
            ))}
          </div>
        )}

        {/* Visual & Insights Content Row */}
        <div className="row flex-grow-1 g-3" style={{ minHeight: 0 }}>
          {/* Main Visual Column */}
          <div className={insights && insights.length > 0 ? "col-8" : "col-12"} style={{ display: "flex", flexDirection: "column", minHeight: 0 }}>
            {hasChart && chartPayload && (
              <div className="card h-100" style={{ background: cardBg, borderColor: cardBorder }}>
                <div className="card-body p-2 d-flex flex-column">
                  <SlideChart chartData={chartPayload} theme={theme} />
                </div>
              </div>
            )}
            {spec.diagram_spec && renderDiagram()}
            {spec.matrix_spec && renderMatrix()}
            {tableData && renderTable()}
          </div>

          {/* Key Insights Aside Column */}
          {insights && insights.length > 0 && (
            <div className="col-4" style={{ minHeight: 0 }}>
              <div className="visual-insight-panel">
                <div className="insight-panel-title" style={{ color: accentColor }}>
                  Key Findings & Takeaways
                </div>
                <div style={{ flex: 1, overflowY: "auto" }}>
                  {insights.map((item, idx) => (
                    <div key={idx} className="insight-item">
                      <div className="insight-bullet" style={{ background: accentColor }} />
                      <div style={{ color: primaryText }}>
                        <FormattedText text={item} />
                      </div>
                    </div>
                  ))}
                </div>
              </div>
            </div>
          )}
        </div>
      </main>

      {/* 3. SLIDE FOOTER */}
      <footer
        className="d-flex justify-content-between align-items-center mt-3 pt-2"
        style={{ borderTop: `1px solid ${cardBorder}`, fontSize: "11px", color: secondaryText }}
      >
        <div className="d-flex align-items-center gap-2">
          <span>{footer.confidence_statement || "Audited Ground Truth Engine"}</span>
          {slide.evidence_id && (
            <span
              style={{
                background: "rgba(255, 255, 255, 0.06)",
                padding: "2px 6px",
                borderRadius: "4px",
                color: accentColor,
                fontWeight: 600
              }}
            >
              [{slide.evidence_id}]
            </span>
          )}
        </div>
        <div>
          Slide {slide.order || 1} of {slide.total_slides || 8}
        </div>
      </footer>
    </div>
  );
}
