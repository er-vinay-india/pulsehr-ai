import { getSlideTheme, slideCssVariables } from '../../../theme/slideTokens.js';
import { slideBackground } from "../../../utils/slideBackground";
import React, { useState } from "react";
import { ArrowRight, Edit3, Image as ImageIcon } from "lucide-react";
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

  theme = getSlideTheme(theme?.id ? theme : spec.design_tokens?.theme_id);
  const tokens = spec.design_tokens || {};
  const primaryText = theme.primary_text;
  const secondaryText = theme.secondary_text;
  const accentColor = theme.accent_color;
  const cardBg = theme.card_bg;
  const cardBorder = theme.card_border;

  const [isEditingTitle, setIsEditingTitle] = useState(false);
  const [titleVal, setTitleVal] = useState(spec.headline || slide.title || "Executive Briefing");

  const [isEditingSubtitle, setIsEditingSubtitle] = useState(false);
  const [subtitleVal, setSubtitleVal] = useState(spec.subtitle || slide.subtitle || "");

  const [isEditingNarrative, setIsEditingNarrative] = useState(false);
  const [narrativeVal, setNarrativeVal] = useState(slide.narrative || "");

  const [editingInsightIdx, setEditingInsightIdx] = useState(null);
  const [insightText, setInsightText] = useState("");

  const [editingKpiIdx, setEditingKpiIdx] = useState(null);
  const [kpiVal, setKpiVal] = useState("");

  // Sync state whenever slide or visual spec changes
  React.useEffect(() => {
    setTitleVal(spec.headline || slide.title || "Executive Briefing");
    setSubtitleVal(spec.subtitle || slide.subtitle || "");
    setNarrativeVal(slide.narrative || "");
    setIsEditingTitle(false);
    setIsEditingSubtitle(false);
    setIsEditingNarrative(false);
    setEditingInsightIdx(null);
    setEditingKpiIdx(null);
  }, [slide.id, spec.headline, spec.subtitle, slide.title, slide.subtitle, slide.narrative]);

  const headline = titleVal;
  const subtitle = subtitleVal;
  const kpis = slide.metrics || spec.kpis || [];
  const rawInsights = slide.bullets || spec.insights || [];
  const insights = rawInsights.map(i => (typeof i === "string" ? i : i.text || ""));
  const tableData = spec.table_data || slide.table;
  const footer = spec.source_footer || {};

  const handleTitleBlur = () => {
    setIsEditingTitle(false);
    if (titleVal !== (spec.headline || slide.title)) {
      onUpdate({
        ...slide,
        title: titleVal,
        visual_spec: { ...spec, headline: titleVal }
      });
    }
  };

  const handleSubtitleBlur = () => {
    setIsEditingSubtitle(false);
    if (subtitleVal !== (spec.subtitle || slide.subtitle)) {
      onUpdate({
        ...slide,
        subtitle: subtitleVal,
        visual_spec: { ...spec, subtitle: subtitleVal }
      });
    }
  };

  const handleNarrativeBlur = () => {
    setIsEditingNarrative(false);
    if (narrativeVal !== slide.narrative) {
      onUpdate({
        ...slide,
        narrative: narrativeVal
      });
    }
  };

  const handleInsightSave = (idx) => {
    setEditingInsightIdx(null);
    const updatedInsights = [...insights];
    updatedInsights[idx] = insightText;
    onUpdate({
      ...slide,
      bullets: updatedInsights,
      visual_spec: { ...spec, insights: updatedInsights }
    });
  };

  const handleKpiSave = (idx) => {
    setEditingKpiIdx(null);
    const updatedKpis = [...kpis];
    const prev = updatedKpis[idx] || {};
    updatedKpis[idx] = {
      ...prev,
      value: kpiVal,
      provenance: "USER_OVERRIDE" // Mark metric as manually overridden per Requirement 8
    };
    onUpdate({
      ...slide,
      metrics: updatedKpis,
      visual_spec: { ...spec, kpis: updatedKpis }
    });
  };

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
                      padding: "12px 14px",
                      borderBottom: `2px solid ${cardBorder}`,
                      textAlign: "left",
                      fontSize: "13px",
                      color: secondaryText,
                      fontWeight: 700,
                      textTransform: "uppercase",
                      letterSpacing: "0.04em"
                    }}
                  >
                    {h}
                  </th>
                ))}
              </tr>
            </thead>
            <tbody>
              {tableData.rows.slice(0, 8).map((r, rIdx) => (
                <tr key={rIdx}>
                  {(Array.isArray(r) ? r : Object.values(r)).map((cell, cIdx) => (
                    <td
                      key={cIdx}
                      style={{
                        padding: "10px 14px",
                        borderBottom: `1px solid ${cardBorder}`,
                        fontSize: "14px",
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

  const hasChart = Boolean(spec.chart_spec || slide.chart || slide.chart_data);
  const chartPayload = slide.chart || slide.chart_data || (spec.chart_spec ? {
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
        ...slideCssVariables(theme),
        ...slideBackground(slide, theme),
        color: primaryText,
        overflow: "hidden"
      }}
    >
      {/* 1. SLIDE HEADER */}
      <header className="mb-3">
        <div className="d-flex justify-content-between align-items-center mb-1">
          <span
            className="text-uppercase fw-bold"
            style={{ fontSize: "13px", letterSpacing: "0.08em", color: accentColor }}
          >
            {spec.visual_story?.primary_message ? "Strategic Analysis" : "Executive Briefing"}
          </span>
        </div>
        {isEditable && isEditingTitle ? (
          <input
            type="text"
            className="slide-title-input"
            aria-label="Edit slide title"
            value={titleVal}
            onChange={(e) => setTitleVal(e.target.value)}
            onBlur={handleTitleBlur}
            onKeyDown={(e) => e.key === "Enter" && handleTitleBlur()}
            autoFocus
            style={{
              fontSize: "36px",
              fontWeight: 800,
              width: "100%",
              background: theme.surface_alt,
              color: primaryText,
              border: `1px solid ${accentColor}`,
              borderRadius: "6px",
              padding: "6px 12px"
            }}
          />
        ) : (
          <h2
            className={`fw-bold mb-1 ${isEditable ? "editable-cursor" : ""}`}
            style={{ fontSize: "36px", lineHeight: "1.2", fontWeight: 800, color: primaryText }}
            onClick={() => isEditable && setIsEditingTitle(true)}
            title={isEditable ? "Click to edit title" : undefined}
          >
            <FormattedText text={headline} />
          </h2>
        )}

        {isEditable && isEditingSubtitle ? (
          <input
            type="text"
            aria-label="Edit slide subtitle"
            value={subtitleVal}
            onChange={(e) => setSubtitleVal(e.target.value)}
            onBlur={handleSubtitleBlur}
            onKeyDown={(e) => e.key === "Enter" && handleSubtitleBlur()}
            autoFocus
            style={{
              fontSize: "18px",
              width: "100%",
              background: theme.surface_alt,
              color: secondaryText,
              border: `1px solid ${accentColor}`,
              borderRadius: "4px",
              padding: "4px 10px"
            }}
          />
        ) : (
          subtitle && (
            <p
              className={`mb-0 ${isEditable ? "editable-cursor" : ""}`}
              style={{ fontSize: "18px", color: secondaryText, lineHeight: "1.4" }}
              onClick={() => isEditable && setIsEditingSubtitle(true)}
              title={isEditable ? "Click to edit subtitle" : undefined}
            >
              <FormattedText text={subtitle} />
            </p>
          )
        )}
      </header>

      {/* 2. SLIDE BODY: GRID LAYOUT */}
      <main className="flex-grow-1 d-flex flex-column gap-3" style={{ minHeight: 0 }}>
        {/* KPI Row (if present) */}
        {kpis && kpis.length > 0 && (
          <div className="visual-kpi-grid">
            {kpis.map((k, idx) => {
              const isOverridden = k.provenance === "USER_OVERRIDE";
              return (
                <div key={idx} className="visual-kpi-card" style={{ position: "relative" }}>
                  <div className="kpi-label">{k.label}</div>
                  {isEditable && editingKpiIdx === idx ? (
                    <input
                      type="text"
                      value={kpiVal}
                      onChange={(e) => setKpiVal(e.target.value)}
                      onBlur={() => handleKpiSave(idx)}
                      onKeyDown={(e) => e.key === "Enter" && handleKpiSave(idx)}
                      autoFocus
                      style={{
                        fontSize: "20px",
                        fontWeight: 700,
                        width: "100%",
                        background: theme.surface_alt,
                        color: accentColor,
                        border: `1px solid ${accentColor}`,
                        borderRadius: "4px"
                      }}
                    />
                  ) : (
                    <div
                      className={`kpi-value ${isEditable ? "editable-cursor" : ""}`}
                      style={{ color: accentColor }}
                      onClick={() => {
                        if (isEditable) {
                          setEditingKpiIdx(idx);
                          setKpiVal(k.value);
                        }
                      }}
                      title={isEditable ? "Click to override verified metric" : undefined}
                    >
                      {k.value}
                    </div>
                  )}
                  {k.subtext && <div className="kpi-subtext">{k.subtext}</div>}
                  {isOverridden && (
                    <span
                      style={{
                        position: "absolute",
                        top: "4px",
                        right: "6px",
                        fontSize: "9px",
                        color: theme.warning_color,
                        fontWeight: 600
                      }}
                      title="User Override (manual modification)"
                    >
                      USER OVERRIDE
                    </span>
                  )}
                </div>
              );
            })}
          </div>
        )}

        {/* Executive Narrative / Analytical Synthesis */}
        {(narrativeVal || slide.narrative) && (
          <div
            className="visual-narrative-box"
            style={{
              padding: "14px 20px",
              background: cardBg,
              border: `1px solid ${cardBorder}`,
              borderLeft: `4px solid ${accentColor}`,
              borderRadius: "8px",
              fontSize: "16.5px",
              lineHeight: "1.55",
              color: primaryText
            }}
          >
            {isEditable && isEditingNarrative ? (
              <textarea
                value={narrativeVal}
                onChange={(e) => setNarrativeVal(e.target.value)}
                onBlur={handleNarrativeBlur}
                autoFocus
                rows={2}
                style={{
                  width: "100%",
                  background: "transparent",
                  color: primaryText,
                  border: `1px solid ${accentColor}`,
                  borderRadius: "4px",
                  fontSize: "16.5px",
                  outline: "none"
                }}
              />
            ) : (
              <div
                onClick={() => isEditable && setIsEditingNarrative(true)}
                className={isEditable ? "editable-cursor" : ""}
                title={isEditable ? "Click to edit narrative" : undefined}
              >
                <FormattedText text={narrativeVal || slide.narrative} defaultColor={primaryText} />
              </div>
            )}
          </div>
        )}

        {/* Visual & Insights Content Row */}
        {(() => {
          const hasVisual = Boolean(
            slide.image_url ||
            (hasChart && chartPayload) ||
            spec.diagram_spec ||
            spec.matrix_spec ||
            tableData
          );

          return (
            <div className="row flex-grow-1 g-3" style={{ minHeight: 0 }}>
              {/* Main Visual Column */}
              {hasVisual && (
                <div className={insights && insights.length > 0 ? "col-7" : "col-12"} style={{ display: "flex", flexDirection: "column", minHeight: 0 }}>
                  {slide.image_url ? (
                    <div className="card h-100" style={{ background: cardBg, borderColor: cardBorder, overflow: "hidden" }}>
                      <img
                        src={slide.image_url}
                        alt={headline}
                        style={{ width: "100%", height: "100%", objectFit: slide.image_fit || "cover", maxHeight: "380px" }}
                      />
                    </div>
                  ) : hasChart && chartPayload ? (
                    <div className="card h-100" style={{ background: cardBg, borderColor: cardBorder }}>
                      <div className="card-body p-2 d-flex flex-column" style={{ minHeight: "260px" }}>
                        <SlideChart chart={chartPayload} chartData={chartPayload} theme={theme} />
                      </div>
                    </div>
                  ) : null}
                  {spec.diagram_spec && renderDiagram()}
                  {spec.matrix_spec && renderMatrix()}
                  {tableData && renderTable()}
                </div>
              )}

              {/* Key Insights Aside Column */}
              {insights && insights.length > 0 && (
                <div className={hasVisual ? "col-5" : "col-12"} style={{ minHeight: 0 }}>
                  <div className="visual-insight-panel" style={{ height: "100%", display: "flex", flexDirection: "column" }}>
                    <div className="insight-panel-title" style={{ color: accentColor }}>
                      Key Findings & Takeaways
                    </div>
                    <div style={{
                      flex: 1,
                      overflowY: "auto",
                      display: hasVisual ? "block" : "grid",
                      gridTemplateColumns: hasVisual ? "1fr" : "repeat(auto-fit, minmax(min(100%, 260px), 1fr))",
                      gap: "10px"
                    }}>
                      {insights.map((item, idx) => (
                        <div key={idx} className="insight-item">
                          <div className="insight-bullet" style={{ background: accentColor }} />
                          <div style={{ color: primaryText, flex: 1 }}>
                            {isEditable && editingInsightIdx === idx ? (
                              <textarea
                                value={insightText}
                                onChange={(e) => setInsightText(e.target.value)}
                                onBlur={() => handleInsightSave(idx)}
                                autoFocus
                                rows={2}
                                style={{
                                  width: "100%",
                                  background: theme.surface_alt,
                                  color: primaryText,
                                  border: `1px solid ${accentColor}`,
                                  borderRadius: "4px",
                                  fontSize: "13px"
                                }}
                              />
                            ) : (
                              <div
                                className={isEditable ? "editable-cursor" : ""}
                                onClick={() => {
                                  if (isEditable) {
                                    setEditingInsightIdx(idx);
                                    setInsightText(item);
                                  }
                                }}
                                title={isEditable ? "Click to edit takeaway" : undefined}
                              >
                                <FormattedText text={item} />
                              </div>
                            )}
                          </div>
                        </div>
                      ))}
                    </div>
                  </div>
                </div>
              )}
            </div>
          );
        })()}
      </main>

      {/* 3. SLIDE FOOTER */}
      <footer
        className="d-flex justify-content-between align-items-center mt-3 pt-2"
        style={{ borderTop: `1px solid ${cardBorder}`, fontSize: "13px", color: secondaryText }}
      >
        <div className="d-flex align-items-center gap-2">
          <span>{footer.dataset_label ? `Source: ${footer.dataset_label}` : "HighView Presentation Studio"}</span>
        </div>
        <div>
          Slide {slide.order || 1} of {slide.total_slides || 8}
        </div>
      </footer>
    </div>
  );
}
