import React from "react";
import { TrendingUp, Award, ChevronRight } from "lucide-react";
import FormattedText from "./FormattedText.jsx";
import SlideChart from "./SlideChart.jsx";
import { SlideTalent9BoxMatrix, SlideBurnoutStrainPanel } from "./SlidePanels.jsx";

export default function SlideLayoutViews({
  layout,
  slide,
  theme,
  isEditable,
  isEditingNarrative,
  setIsEditingNarrative,
  narrativeVal,
  setNarrativeVal,
  handleNarrativeBlur
}) {
  return (
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
            {slide.talent_9box_data ? (
              <SlideTalent9BoxMatrix data={slide.talent_9box_data} theme={theme} />
            ) : slide.burnout_strain_data ? (
              <SlideBurnoutStrainPanel data={slide.burnout_strain_data} theme={theme} />
            ) : (
              <SlideChart chart={slide.chart} theme={theme} />
            )}
          </div>
        </div>
      )}

      {/* LAYOUT: full_chart_takeaway */}
      {layout === "full_chart_takeaway" && (
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
                    <FormattedText text={b} defaultColor={theme.secondary_text} />
                  </span>
                ))}
              </div>
            )}
          </div>
          <div className="hero-chart-container" style={{ backgroundColor: theme.card_bg, borderColor: theme.card_border }}>
            <SlideChart chart={slide.chart} theme={theme} />
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
        <div className="layout-grid comparison-split-grid">
          <div className="recommendations-card" style={{ backgroundColor: theme.card_bg, borderColor: theme.card_border }}>
            <h3 className="card-subhead" style={{ color: theme.accent_color }}>{slide.category === "EVIDENCE APPENDIX" ? "Interpretation boundaries" : slide.category === "DECISION BRIEF" ? "Leadership takeaways" : "Operational Recommendations"}</h3>
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

      {/* LAYOUT: action_plan */}
      {layout === "action_plan" && (
        <div className="layout-action-plan">
          {slide.narrative && (
            <div className="action-plan-intro" style={{ backgroundColor: theme.card_bg, borderColor: theme.card_border }}>
              <FormattedText text={slide.narrative} defaultColor={theme.primary_text} />
            </div>
          )}
          <div className="action-initiatives-grid">
            {(slide.initiatives || slide.structured_proposals || []).slice(0, 3).map((init, i) => (
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
  );
}
