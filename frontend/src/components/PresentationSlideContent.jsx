import React, { useState } from "react";
import { ShieldCheck } from "lucide-react";
import FormattedText from "./presentation/slides/FormattedText.jsx";
import SlideChart from "./presentation/slides/SlideChart.jsx";
import { SlideTalent9BoxMatrix, SlideBurnoutStrainPanel } from "./presentation/slides/SlidePanels.jsx";
import SlideLayoutViews from "./presentation/slides/SlideLayoutViews.jsx";

export { FormattedText, SlideChart, SlideTalent9BoxMatrix, SlideBurnoutStrainPanel, SlideLayoutViews };

export default function PresentationSlideContent({
  slide,
  theme = {},
  slideIndex,
  totalSlides,
  isEditable = false,
  onUpdate = () => {},
  onViewEvidence = () => {}
}) {
  const activeTheme = {
    bg_color: theme?.bg_color || "var(--slide-bg, #0f172a)",
    card_bg: theme?.card_bg || "var(--card-bg, #1e293b)",
    card_border: theme?.card_border || "var(--card-border, rgba(255, 255, 255, 0.08))",
    primary_text: theme?.primary_text || "var(--text-primary, #f8fafc)",
    secondary_text: theme?.secondary_text || "var(--text-secondary, #94a3b8)",
    brand_color: theme?.brand_color || "var(--accent-color, #ff8a62)",
    accent_color: theme?.accent_color || "var(--accent-color, #ff8a62)",
    chart_palette: theme?.chart_palette || ["#ff8a62", "#7ee7d9", "#8ef0c8", "#a78bfa", "#fbbf24", "#f43f5e"],
    success_color: theme?.success_color || "#10b981",
    warning_color: theme?.warning_color || "#f59e0b",
    danger_color: theme?.danger_color || "#ef4444",
    ...(theme || {})
  };
  theme = activeTheme;

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
      <div className="slide-header-top-line">
        <div className="slide-category-tag" style={{ color: theme.brand_color }}>
          {slide.category || "EXECUTIVE REVIEW"}
        </div>
        {slide.evidence_id && (
          <button
            type="button"
            className="slide-evidence-badge-btn"
            onClick={() => onViewEvidence && onViewEvidence(slide)}
            title="Inspect calculation methodology, evidence sources & board scrutiny briefing"
          >
            <ShieldCheck size={12} />
            <span>{slide.evidence_id}</span>
            {slide.finding_type && (
              <span className="finding-type-subtag">
                · {slide.finding_type.replace("_", " ").toUpperCase()}
              </span>
            )}
          </button>
        )}
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
      <div className="slide-subtitle-row">
        {slide.subtitle && (
          <div className="slide-subtitle" style={{ color: theme.accent_color }}>
            {slide.subtitle}
          </div>
        )}
        {(slide.is_partial_year || slide.limitations?.includes("Partial Year")) && (
          <span className="slide-partial-year-badge" title="Covers fewer than 330 days in annual cycle">
            Partial Year Data
          </span>
        )}
      </div>
    </div>
  );

  const renderFooter = () => {
    const sources = slide.evidence_sources || [];
    const limitations = slide.limitations;
    const slideNumber = slide.order || slideIndex || 1;
    const totalCount = slide.total_slides || totalSlides || 8;
    return (
      <div className="slide-footer-block" style={{ color: theme.secondary_text }}>
        <div
          className="footer-left clickable-evidence"
          onClick={() => onViewEvidence && onViewEvidence(slide)}
          title="Click to inspect verifiable evidence & board briefing"
        >
          <ShieldCheck size={13} style={{ color: theme.success_color }} />
          <span>
            {slide.evidence_id ? `[${slide.evidence_id}] ` : ""}
            {sources.length > 0 ? `Evidence: ${sources.join(" · ")}` : "Verified Deterministic Ground Truth Engine"}
          </span>
          <span className="footer-inspect-cta">View Evidence &rarr;</span>
        </div>
        <div className="footer-right">
          {limitations && <span className="footer-scope">Scope: {limitations}</span>}
          <span className="footer-slide-number" style={{ color: theme.brand_color }}>
            Slide {slideNumber} of {totalCount}
          </span>
        </div>
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

      <SlideLayoutViews
        layout={layout}
        slide={slide}
        theme={theme}
        isEditable={isEditable}
        isEditingNarrative={isEditingNarrative}
        setIsEditingNarrative={setIsEditingNarrative}
        narrativeVal={narrativeVal}
        setNarrativeVal={setNarrativeVal}
        handleNarrativeBlur={handleNarrativeBlur}
      />

      {renderFooter()}
    </div>
  );
}
