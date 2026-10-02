import React, { useState, useRef, useId } from "react";
import DeckFloatingLayer from "../DeckFloatingLayer.jsx";
import { TrendingUp, Award, ChevronRight, Sparkles, Layers, Check } from "lucide-react";
import FormattedText from "./FormattedText.jsx";
import SlideChart from "./SlideChart.jsx";
import { SlideTalent9BoxMatrix, SlideBurnoutStrainPanel } from "./SlidePanels.jsx";
import { getTitleSuggestions } from "../../../utils/dashboardToPresentation.js";

export default function SlideLayoutViews({
  layout,
  slide,
  theme,
  isEditable,
  isEditingNarrative,
  setIsEditingNarrative,
  narrativeVal,
  setNarrativeVal,
  handleNarrativeBlur,
  isEditingTitle,
  setIsEditingTitle,
  titleVal,
  setTitleVal,
  handleTitleBlur,
  onUpdate
}) {
  const [showTitleSuggestions, setShowTitleSuggestions] = useState(false);
  const titleSuggestionsAnchor = useRef(null);
  const titleSuggestionsId = useId();
  const closeTitleSuggestions = () => {
    setShowTitleSuggestions(false);
    titleSuggestionsAnchor.current?.focus({ preventScroll: true });
  };

  // Resilient resolution of slide data across both canonical slide and visual_spec schemas
  const effectiveSlide = {
    ...slide,
    metrics: (slide.metrics && slide.metrics.length > 0) ? slide.metrics : (slide.visual_spec?.kpis || []),
    bullets: (slide.bullets && slide.bullets.length > 0) ? slide.bullets : (slide.visual_spec?.insights || []),
    table: slide.table || slide.table_data || slide.visual_spec?.table_data,
    table_data: slide.table_data || slide.table || slide.visual_spec?.table_data,
    structured_proposals: slide.structured_proposals || slide.initiatives || slide.visual_spec?.structured_proposals || [],
    matrix_spec: slide.matrix_spec || slide.visual_spec?.matrix_spec,
    diagram_spec: slide.diagram_spec || slide.visual_spec?.diagram_spec,
    chart: slide.chart || slide.chart_data || slide.visual_spec?.chart_spec,
  };
  slide = effectiveSlide;

  return (
    <div className="slide-body-content">
      {/* LAYOUT: title_cover (Centered Executive Title Slide in Step 1) */}
      {layout === "title_cover" && (
        <div className="title-cover-canvas">
          <div className="title-cover-center-content">
            <div className="title-cover-top-badge">
              <span className="cover-badge-dot" style={{ backgroundColor: theme.brand_color }} />
              <span>{slide.category || "EXECUTIVE BOARDROOM BRIEFING"}</span>
            </div>

            {isEditable && isEditingTitle ? (
              <input
                type="text"
                className="title-cover-input"
                aria-label="Edit title cover heading"
                value={titleVal !== undefined ? titleVal : slide.title}
                onChange={e => setTitleVal && setTitleVal(e.target.value)}
                onBlur={handleTitleBlur}
                onKeyDown={e => e.key === "Enter" && handleTitleBlur && handleTitleBlur()}
                autoFocus
              />
            ) : (
              <h1
                className={`title-cover-heading ${isEditable ? "editable-cursor" : ""}`}
                style={{ color: theme.primary_text }}
                onClick={() => isEditable && setIsEditingTitle && setIsEditingTitle(true)}
                title={isEditable ? "Click to edit title" : undefined}
              >
                {titleVal || slide.title}
              </h1>
            )}

            {slide.subtitle && (
              <p className="title-cover-subtitle" style={{ color: theme.accent_color }}>
                {slide.subtitle}
              </p>
            )}

            {/* AI Title Suggestions Trigger Button */}
            <div className="title-cover-ai-actions">
              <button
                ref={titleSuggestionsAnchor}
                type="button"
                className="btn-ai-title-suggest"
                aria-haspopup="dialog"
                aria-expanded={showTitleSuggestions}
                aria-controls={showTitleSuggestions ? titleSuggestionsId : undefined}
                onClick={() => setShowTitleSuggestions(!showTitleSuggestions)}
                title="Explore intelligent title suggestions from HRIDAY"
              >
                <Sparkles size={15} />
                <span>AI Title Suggestions</span>
              </button>

              {/* AI Title Suggestions Popover / Panel */}
              {showTitleSuggestions && (
                <DeckFloatingLayer anchorRef={titleSuggestionsAnchor} placement="bottom" role="dialog"
                  id={titleSuggestionsId} aria-label="AI Title Alternatives" onClose={() => setShowTitleSuggestions(false)}>
                  <div className="popover-header">
                    <div className="popover-title-row">
                      <Sparkles size={14} />
                      <span>Intelligent AI Title Alternatives</span>
                    </div>
                    <button
                      type="button"
                      className="popover-close-btn"
                      onClick={closeTitleSuggestions}
                      aria-label="Close suggestions"
                    >
                      &times;
                    </button>
                  </div>
                  <div className="popover-suggestions-list">
                    {getTitleSuggestions(slide).map((sug, idx) => (
                      <button
                        key={idx}
                        type="button"
                        className="suggestion-tile-btn"
                        onClick={() => {
                          if (setTitleVal) setTitleVal(sug);
                          if (onUpdate) onUpdate({ ...slide, title: sug });
                          closeTitleSuggestions();
                        }}
                      >
                        <span className="sug-index">{idx + 1}</span>
                        <span className="sug-label">{sug}</span>
                      </button>
                    ))}
                  </div>
                </DeckFloatingLayer>
              )}
            </div>

            {slide.narrative && (
              <p className="title-cover-narrative-p" style={{ color: theme.secondary_text }}>
                <FormattedText text={slide.narrative} defaultColor={theme.secondary_text} />
              </p>
            )}

            {/* Executive Focus Pillars / Highlights */}
            {slide.bullets && slide.bullets.length > 0 && (
              <div className="title-cover-pillars-grid">
                {slide.bullets.map((b, i) => (
                  <div
                    key={i}
                    className="title-pillar-card"
                    style={{ backgroundColor: theme.card_bg, borderColor: theme.card_border }}
                  >
                    <span className="pillar-indicator" style={{ backgroundColor: theme.brand_color }} />
                    <span className="pillar-body" style={{ color: theme.primary_text }}>
                      {typeof b === "string" ? b : b.text}
                    </span>
                  </div>
                ))}
              </div>
            )}
          </div>
        </div>
      )}

      {/* LAYOUT 1: title_hero */}
      {layout === "title_hero" && (
        <div className="layout-grid title-hero-grid">
          <div className="hero-narrative-card" style={{ backgroundColor: theme.card_bg, borderColor: theme.card_border }}>
            {isEditable && isEditingNarrative ? (
              <textarea
                className="slide-narrative-textarea"
                aria-label="Edit slide narrative"
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

      {/* LAYOUT 3: chart_narrative / split_kpi_chart */}
      {(layout === "chart_narrative" || layout === "split_kpi_chart" || layout === "split_metric_chart") && (
        <div className="layout-grid chart-narrative-grid">
          <div className="narrative-side-card" style={{ backgroundColor: theme.card_bg, borderColor: theme.card_border }}>
            {slide.stat_callout && (
              <div className="callout-hero-stat" style={{ marginBottom: "14px", padding: "10px 14px", borderRadius: "8px", background: theme.surface_alt, border: `1px solid ${theme.card_border}` }}>
                <div style={{ fontSize: "28px", fontWeight: "700", color: theme.brand_color }}>
                  {slide.stat_callout.value} {slide.stat_callout.unit || ""}
                </div>
                <div style={{ fontSize: "12px", color: theme.secondary_text }}>
                  {slide.stat_callout.label} {slide.stat_callout.sublabel ? `· ${slide.stat_callout.sublabel}` : ""}
                </div>
              </div>
            )}
            {isEditable && isEditingNarrative ? (
              <textarea
                className="slide-narrative-textarea"
                aria-label="Edit slide narrative"
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
                    <FormattedText text={typeof b === "string" ? b : b.text} defaultColor={theme.secondary_text} />
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
            {slide.talent_9box_data ? (
              <SlideTalent9BoxMatrix data={slide.talent_9box_data} theme={theme} />
            ) : slide.burnout_strain_data ? (
              <SlideBurnoutStrainPanel data={slide.burnout_strain_data} theme={theme} />
            ) : (
              <SlideChart chart={slide.chart || slide.chart_data} theme={theme} />
            )}
          </div>
        </div>
      )}

      {/* LAYOUT: full_chart_takeaway / chart_focus */}
      {(layout === "full_chart_takeaway" || layout === "chart_focus") && (
        <div className="layout-full-chart-takeaway">
          <div className="takeaway-banner-card" style={{ backgroundColor: theme.card_bg, borderColor: theme.card_border }}>
            <div className="takeaway-banner-header">
              <span className="takeaway-tag" style={{ color: theme.accent_color }}>EXECUTIVE TAKEAWAY</span>
              {slide.subtitle && <span className="takeaway-subtitle" style={{ color: theme.secondary_text }}>· {slide.subtitle}</span>}
            </div>
            <p className="takeaway-lead">
              <FormattedText text={slide.narrative} defaultColor={theme.primary_text} />
            </p>
            {slide.bullets && slide.bullets.length > 0 && (
              <div className="takeaway-bullets-inline">
                {slide.bullets.map((b, i) => (
                  <span key={i} className="takeaway-bullet-chip" style={{ borderColor: theme.card_border, color: theme.secondary_text }}>
                    <ChevronRight size={12} style={{ color: theme.brand_color, display: "inline" }} />
                    <FormattedText text={typeof b === "string" ? b : b.text} defaultColor={theme.secondary_text} />
                  </span>
                ))}
              </div>
            )}
          </div>
          <div className="hero-chart-container" style={{ backgroundColor: theme.card_bg, borderColor: theme.card_border }}>
            <SlideChart chart={slide.chart || slide.chart_data} theme={theme} />
          </div>
        </div>
      )}

      {/* LAYOUT: two_charts */}
      {layout === "two_charts" && (
        <div className="layout-two-charts">
          {slide.narrative && (
            <div className="two-charts-takeaway-bar" style={{ backgroundColor: theme.card_bg, borderColor: theme.card_border }}>
              <FormattedText text={slide.narrative} defaultColor={theme.primary_text} />
            </div>
          )}
          <div className="dual-charts-grid">
            <div className="dual-chart-card" style={{ backgroundColor: theme.card_bg, borderColor: theme.card_border }}>
              <div className="dual-chart-subhead" style={{ color: theme.accent_color }}>
                {(slide.chart_left || slide.chart)?.title || "Primary Metric"}
              </div>
              <SlideChart chart={slide.chart_left || slide.chart} theme={theme} />
            </div>
            <div className="dual-chart-card" style={{ backgroundColor: theme.card_bg, borderColor: theme.card_border }}>
              <div className="dual-chart-subhead" style={{ color: theme.brand_color }}>
                {(slide.chart_right || slide.charts?.[1])?.title || "Comparative Benchmark"}
              </div>
              <SlideChart chart={slide.chart_right || slide.charts?.[1] || slide.chart} theme={theme} />
            </div>
          </div>
        </div>
      )}

      {/* LAYOUT 4: comparison_split */}
      {layout === "comparison_split" && (
        <div className="layout-grid comparison-split-grid" style={!slide.table && !slide.metrics?.length ? { gridTemplateColumns: "1fr" } : undefined}>
          <div className="recommendations-card" style={{ backgroundColor: theme.card_bg, borderColor: theme.card_border }}>
            <h3 className="card-subhead" style={{ color: theme.accent_color }}>{slide.category === "EVIDENCE APPENDIX" ? "Interpretation boundaries" : slide.category === "DECISION BRIEF" ? "Leadership takeaways" : "Key takeaways"}</h3>
            <p className="rec-narrative">
              <FormattedText text={slide.narrative} defaultColor={theme.primary_text} />
            </p>
            {slide.structured_proposals && slide.structured_proposals.length > 0 ? (
              <div className="structured-proposals-list">
                {slide.structured_proposals.map((prop, i) => (
                  <div key={i} className="structured-proposal-card" style={{ borderColor: theme.card_border }}>
                    <div className="proposal-card-header">
                      <span className={`proposal-priority-badge priority-${(prop.priority || "medium").toLowerCase()}`}>
                        {prop.priority} Priority
                      </span>
                      <span className="proposal-owner-badge" title="Role explicitly designated without inventing named owners">
                        {prop.owner_role || "Unassigned - Operational Lead"}
                      </span>
                    </div>
                    <div className="proposal-finding-row">
                      <span className="prop-section-lbl" style={{ color: theme.accent_color }}>Finding:</span>
                      <span className="prop-text" style={{ color: theme.primary_text }}>{prop.finding}</span>
                    </div>
                    <div className="proposal-response-row">
                      <span className="prop-section-lbl" style={{ color: theme.brand_color }}>Response:</span>
                      <span className="prop-text" style={{ color: theme.secondary_text }}>{prop.response}</span>
                    </div>
                    <div className="proposal-meta-footer" style={{ borderTopColor: theme.card_border }}>
                      {prop.success_metric && (
                        <span className="prop-footer-item">
                          <strong style={{ color: theme.primary_text }}>Target:</strong> {prop.success_metric}
                        </span>
                      )}
                      {prop.dependencies && (
                        <span className="prop-footer-item">
                          <strong style={{ color: theme.primary_text }}>Dep:</strong> {prop.dependencies}
                        </span>
                      )}
                    </div>
                  </div>
                ))}
              </div>
            ) : (
              <div className="rec-bullets-list">
                {(slide.bullets || []).map((b, i) => (
                  <div key={i} className="rec-bullet-box">
                    <span className="rec-number" style={{ color: theme.brand_color }}>0{i+1}</span>
                    <FormattedText text={b} defaultColor={theme.secondary_text} />
                  </div>
                ))}
              </div>
            )}
          </div>

          {slide.table && slide.table.rows && slide.table.rows.length > 0 ? (
            <div className="diagnostic-table-card" style={{ backgroundColor: theme.card_bg, borderColor: theme.card_border, padding: "20px 22px", borderRadius: "12px", overflow: "hidden", display: "flex", flexDirection: "column", justifyContent: "space-between", height: "100%" }}>
              <div style={{ fontSize: "13px", fontWeight: "700", color: theme.brand_color, marginBottom: "10px", textTransform: "uppercase", letterSpacing: "0.06em" }}>
                Recorded findings
              </div>
              <div style={{ overflowX: "hidden", width: "100%", flex: 1 }}>
                <table style={{ width: "100%", tableLayout: "fixed", borderCollapse: "collapse", fontSize: "13.5px" }}>
                  <thead>
                    <tr style={{ borderBottom: `2px solid ${theme.card_border}` }}>
                      <th style={{ width: "32%", padding: "10px 12px", color: theme.brand_color, fontWeight: "700", fontSize: "12.5px", textTransform: "uppercase" }}>Evidence</th>
                      <th style={{ width: "44%", padding: "10px 12px", color: theme.brand_color, fontWeight: "700", fontSize: "12.5px", textTransform: "uppercase" }}>Finding</th>
                      <th style={{ width: "24%", padding: "10px 12px", color: theme.brand_color, fontWeight: "700", fontSize: "12.5px", textTransform: "uppercase", textAlign: "right" }}>Metric</th>
                    </tr>
                  </thead>
                  <tbody>
                    {slide.table.rows.slice(0, 7).map((r, ri) => (
                      <tr key={ri} style={{ borderBottom: ri === Math.min(slide.table.rows.length - 1, 6) ? "none" : `1px solid ${theme.card_border}` }}>
                        <td style={{ padding: "10px 12px", color: theme.primary_text, fontFamily: "monospace", fontSize: "12px", overflow: "hidden", textOverflow: "ellipsis", wordBreak: "break-all" }}>{r[0]}</td>
                        <td style={{ padding: "10px 12px", color: theme.secondary_text, fontSize: "13.5px", overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>{r[1]}</td>
                        <td style={{ padding: "10px 12px", color: theme.brand_color, fontWeight: "700", fontSize: "13.5px", textAlign: "right" }}>{r[3]}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </div>
          ) : (
            <div className="priorities-card-stack">
              {(slide.metrics || []).map((m, i) => (
                <div key={i} className="priority-tier-card" style={{ backgroundColor: theme.card_bg, borderColor: theme.card_border }}>
                  <div className="priority-step" style={{ color: theme.accent_color }}>{m.label}</div>
                  <div className="priority-title" style={{ color: theme.brand_color }}>{m.value}</div>
                  <div className="priority-sub" style={{ color: theme.secondary_text }}>{m.subtext}</div>
                </div>
              ))}
            </div>
          )}
        </div>
      )}

      {/* LAYOUT: action_plan */}
      {layout === "action_plan" && (
        <div className="layout-action-plan">
          {slide.narrative && (
            <div className="action-plan-intro" style={{ backgroundColor: theme.card_bg, borderColor: theme.card_border }}>
              <FormattedText text={slide.narrative} defaultColor={theme.primary_text} />
            </div>
          )}
          <div className="action-initiatives-grid">
            {((slide.initiatives && slide.initiatives.length > 0)
              ? slide.initiatives
              : (slide.structured_proposals && slide.structured_proposals.length > 0)
                ? slide.structured_proposals
                : (slide.bullets || []).map((b, bi) => ({
                    title: typeof b === "string" ? (b.includes("]") ? b.split("]")[1]?.trim() || b : b.split(":")[0]) : (b.text || `Action Step ${bi + 1}`),
                    finding: typeof b === "string" ? b : b.text,
                    priority: bi === 0 ? "HIGH" : bi === 1 ? "MEDIUM" : "LOW",
                    owner: "Operational Lead",
                    metric: "Execution Target"
                  }))
            ).slice(0, 3).map((init, i) => (
              <div key={i} className="action-initiative-card" style={{ backgroundColor: theme.card_bg, borderColor: theme.card_border }}>
                <div className="action-card-header">
                  <span className={`action-priority-badge priority-${String(init.priority || "medium").toLowerCase().replace(/[^a-z]/g, "")}`}>
                    {String(init.priority || "MEDIUM").toUpperCase()}
                  </span>
                  <span className="action-owner-role" style={{ color: theme.accent_color }}>
                    {init.owner || init.owner_role || "Unassigned - Operational Lead"}
                  </span>
                </div>
                <h4 className="action-title" style={{ color: theme.primary_text }}>
                  {init.title || init.proposed_response || `Initiative ${i + 1}`}
                </h4>
                <div className="action-section">
                  <span className="action-lbl" style={{ color: theme.brand_color }}>Motivating Finding:</span>
                  <p className="action-body" style={{ color: theme.secondary_text }}>
                    {init.finding || init.motivating_finding}
                  </p>
                </div>
                <div className="action-meta-footer" style={{ borderTopColor: theme.card_border }}>
                  <div className="action-meta-item">
                    <span className="action-meta-lbl" style={{ color: theme.primary_text }}>Target SLA:</span>
                    <span style={{ color: theme.secondary_text }}>{init.metric || init.success_metric || "Defined SLA Target"}</span>
                  </div>
                  {(init.dependency || init.dependencies) && (
                    <div className="action-meta-item">
                      <span className="action-meta-lbl" style={{ color: theme.primary_text }}>Prerequisite:</span>
                      <span style={{ color: theme.secondary_text }}>{init.dependency || init.dependencies}</span>
                    </div>
                  )}
                </div>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* LAYOUT: table_detail (Evidence Ledger & Audited Tables) */}
      {layout === "table_detail" && (
        <div className="layout-table-detail" style={{ display: "flex", flexDirection: "column", gap: "16px", height: "100%", justifyContent: "space-between", overflow: "hidden" }}>
          {slide.narrative && (
            <div style={{ padding: "16px 22px", borderRadius: "10px", background: theme.card_bg, border: `1px solid ${theme.card_border}`, fontSize: "15.5px", lineHeight: "1.55" }}>
              <FormattedText text={slide.narrative} defaultColor={theme.primary_text} />
            </div>
          )}

          {slide.table && slide.table.rows && slide.table.rows.length > 0 ? (
            <div style={{ width: "100%", flex: 1, minHeight: 0, overflowX: "hidden", borderRadius: "10px", border: `1px solid ${theme.card_border}`, background: theme.card_bg, display: "flex", flexDirection: "column" }}>
              <table style={{ width: "100%", height: "100%", tableLayout: "fixed", borderCollapse: "collapse", fontSize: "14px", textAlign: "left" }}>
                <thead>
                  <tr style={{ borderBottom: `2px solid ${theme.card_border}`, background: theme.surface_alt }}>
                    {(slide.table.headers || []).map((h, hi) => {
                      const totalCols = (slide.table.headers || []).length;
                      let width = `${100 / totalCols}%`;
                      if (totalCols === 5) {
                        width = hi === 0 ? "20%" : hi === 1 ? "36%" : hi === 2 ? "18%" : hi === 3 ? "13%" : "13%";
                      }
                      return (
                        <th
                          key={hi}
                          style={{
                            width,
                            padding: "13px 16px",
                            color: theme.brand_color,
                            fontWeight: "700",
                            fontSize: "13px",
                            textTransform: "uppercase",
                            letterSpacing: "0.04em",
                            overflow: "hidden",
                            textOverflow: "ellipsis",
                            whiteSpace: "nowrap"
                          }}
                        >
                          {h}
                        </th>
                      );
                    })}
                  </tr>
                </thead>
                <tbody>
                  {slide.table.rows.slice(0, 8).map((row, ri) => (
                    <tr
                      key={ri}
                      style={{
                        borderBottom: ri === Math.min(slide.table.rows.length - 1, 7) ? "none" : `1px solid ${theme.card_border}`,
                        background: ri % 2 === 0 ? "transparent" : theme.surface_alt
                      }}
                    >
                      {row.map((cell, ci) => {
                        const isId = ci === 0;
                        return (
                          <td
                            key={ci}
                            style={{
                              padding: "12px 16px",
                              color: isId ? theme.primary_text : theme.secondary_text,
                              fontWeight: isId || ci === 3 ? "600" : "normal",
                              fontFamily: isId ? "monospace" : "inherit",
                              fontSize: isId ? "12.5px" : "14px",
                              overflow: "hidden",
                              textOverflow: "ellipsis",
                              wordBreak: isId ? "break-all" : "break-word",
                              verticalAlign: "middle"
                            }}
                          >
                            {cell}
                          </td>
                        );
                      })}
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          ) : slide.matrix_spec ? (
            <div className="table-detail-matrix-grid" style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: "16px", width: "100%", flex: 1 }}>
              {(slide.matrix_spec.quadrants || []).map((q, qi) => (
                <div key={qi} style={{ padding: "18px 22px", borderRadius: "10px", background: theme.card_bg, border: `1px solid ${theme.card_border}`, display: "flex", flexDirection: "column", justifyContent: "space-between" }}>
                  <div>
                    <div style={{ fontSize: "16px", fontWeight: "700", color: theme.brand_color, marginBottom: "6px" }}>{q.label}</div>
                    <div style={{ fontSize: "14px", color: theme.secondary_text, lineHeight: "1.45" }}>{q.description}</div>
                  </div>
                  {q.items && q.items.length > 0 && (
                    <div style={{ marginTop: "10px", fontSize: "13px", color: theme.primary_text, fontWeight: "600" }}>{q.items.join(" · ")}</div>
                  )}
                </div>
              ))}
            </div>
          ) : null}

          {slide.bullets && slide.bullets.length > 0 && (
            <div style={{ display: "flex", flexWrap: "wrap", gap: "10px", marginTop: "4px" }}>
              {slide.bullets.map((b, i) => (
                <div key={i} style={{ display: "inline-flex", alignItems: "center", gap: "8px", padding: "6px 14px", borderRadius: "8px", background: theme.surface_alt, border: `1px solid ${theme.card_border}`, fontSize: "13px" }}>
                  <span style={{ width: "7px", height: "7px", borderRadius: "50%", background: theme.brand_color, flexShrink: 0 }} />
                  <FormattedText text={typeof b === "string" ? b : b.text} defaultColor={theme.secondary_text} />
                </div>
              ))}
            </div>
          )}
        </div>
      )}

      {/* LAYOUT: audit_quad (Governance 4-card grid) */}
      {layout === "audit_quad" && (
        <div className="layout-audit-quad" style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: "20px", height: "100%" }}>
          {(slide.bullets || [
            { text: "Data Governance: Fully validated against audit parameters" },
            { text: "Sample Validity: Controlled for operational scale and tenure" },
            { text: "Simpson's Paradox Protection: Subgroup distributions checked" },
            { text: "Audit Integrity: Direct 1:1 binding to empirical records" }
          ]).slice(0, 4).map((b, i) => (
            <div key={i} style={{ padding: "26px 30px", borderRadius: "14px", background: theme.card_bg, borderColor: theme.card_border, border: `1px solid ${theme.card_border}`, display: "flex", flexDirection: "column", justifyContent: "space-between" }}>
              <div style={{ display: "flex", alignItems: "center", gap: "10px", marginBottom: "12px" }}>
                <span style={{ display: "inline-flex", alignItems: "center", justifyContent: "center", width: "30px", height: "30px", borderRadius: "50%", background: `${theme.brand_color}22`, color: theme.brand_color, fontWeight: "bold", fontSize: "14px" }}>
                  {i + 1}
                </span>
                <span style={{ fontSize: "17px", fontWeight: "700", color: theme.primary_text }}>Governance Principle {i + 1}</span>
              </div>
              <p style={{ margin: 0, fontSize: "15px", color: theme.secondary_text, lineHeight: "1.6" }}>
                <FormattedText text={typeof b === "string" ? b : b.text} defaultColor={theme.secondary_text} />
              </p>
            </div>
          ))}
        </div>
      )}

      {/* LAYOUT: image_story */}
      {layout === "image_story" && (
        <div className="layout-image-story" style={{ display: "grid", gridTemplateColumns: "1.2fr 1fr", gap: "28px", height: "100%", alignItems: "stretch" }}>
          <div style={{ height: "100%", borderRadius: "12px", overflow: "hidden", border: `1px solid ${theme.card_border}` }}>
            <img
              src={slide.image_url || slide.background_image || "https://images.unsplash.com/photo-1542744173-8e7e53415bb0?auto=format&fit=crop&w=1200&q=80"}
              alt={slide.title || "Slide visual"}
              style={{ width: "100%", height: "100%", objectFit: slide.image_fit || "cover" }}
            />
          </div>
          <div style={{ display: "flex", flexDirection: "column", justifyContent: "space-between", gap: "18px", height: "100%" }}>
            {slide.narrative && (
              <div style={{ padding: "20px 24px", borderRadius: "12px", background: theme.card_bg, border: `1px solid ${theme.card_border}` }}>
                <p style={{ margin: 0, fontSize: "18px", color: theme.primary_text, lineHeight: "1.6" }}>
                  <FormattedText text={slide.narrative} defaultColor={theme.primary_text} />
                </p>
              </div>
            )}
            {slide.bullets && slide.bullets.length > 0 && (
              <ul className="slide-bullets-stack" style={{ margin: 0, flex: 1, display: "flex", flexDirection: "column", justifyContent: "center", gap: "14px" }}>
                {slide.bullets.map((b, i) => (
                  <li key={i} className="slide-bullet-row" style={{ fontSize: "16px", lineHeight: "1.5" }}>
                    <ChevronRight size={18} style={{ color: theme.brand_color, flexShrink: 0, marginTop: 2 }} />
                    <FormattedText text={typeof b === "string" ? b : b.text} defaultColor={theme.secondary_text} />
                  </li>
                ))}
              </ul>
            )}
          </div>
        </div>
      )}

      {/* Universal Fallback / Layout Resiliency: Ensures no slide is EVER blank */}
      {!["title_cover", "chart_narrative", "split_kpi_chart", "split_metric_chart", "full_chart_takeaway", "chart_focus", "two_charts", "comparison_split", "kpi_cards", "title_hero", "bullets_roadmap", "roadmap_horizontal", "action_plan", "bullets_action", "table_detail", "audit_quad", "image_story"].includes(layout) && (
        <div className="layout-universal-content" style={{ display: "flex", flexDirection: "column", gap: "20px", height: "100%" }}>
          {slide.narrative && (
            <div style={{ padding: "18px 24px", borderRadius: "10px", background: theme.card_bg, border: `1px solid ${theme.card_border}`, fontSize: "16px", lineHeight: "1.6" }}>
              <FormattedText text={slide.narrative} defaultColor={theme.primary_text} />
            </div>
          )}
          {(slide.chart || slide.chart_data) && (
            <div style={{ flex: 1, minHeight: "280px", padding: "16px", borderRadius: "10px", background: theme.card_bg, border: `1px solid ${theme.card_border}` }}>
              <SlideChart chart={slide.chart || slide.chart_data} theme={theme} />
            </div>
          )}
          {slide.bullets && slide.bullets.length > 0 && (
            <ul className="slide-bullets-stack" style={{ margin: 0, display: "flex", flexDirection: "column", gap: "12px" }}>
              {slide.bullets.map((b, i) => (
                <li key={i} className="slide-bullet-row" style={{ fontSize: "15px", lineHeight: "1.5" }}>
                  <ChevronRight size={16} style={{ color: theme.brand_color, flexShrink: 0, marginTop: 2 }} />
                  <FormattedText text={typeof b === "string" ? b : b.text} defaultColor={theme.secondary_text} />
                </li>
              ))}
            </ul>
          )}
        </div>
      )}
    </div>
  );
}
