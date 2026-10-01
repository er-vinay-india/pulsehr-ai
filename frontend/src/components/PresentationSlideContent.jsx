import { getSlideTheme, slideCssVariables } from '../theme/slideTokens.js';
import { slideBackground } from "../utils/slideBackground";
import React, { useState } from "react";
import FormattedText from "./presentation/slides/FormattedText.jsx";
import SlideChart from "./presentation/slides/SlideChart.jsx";
import { SlideTalent9BoxMatrix, SlideBurnoutStrainPanel } from "./presentation/slides/SlidePanels.jsx";
import SlideLayoutViews from "./presentation/slides/SlideLayoutViews.jsx";
import VisualSlideRenderer from "./presentation/visual/VisualSlideRenderer.jsx";

export { FormattedText, SlideChart, SlideTalent9BoxMatrix, SlideBurnoutStrainPanel, SlideLayoutViews, VisualSlideRenderer };

export default function PresentationSlideContent({
  slide,
  theme = {},
  slideIndex,
  totalSlides,
  isEditable = false,
  onUpdate = () => {},
  onViewEvidence = () => {}
}) {
  theme = getSlideTheme(theme);

  const [isEditingTitle, setIsEditingTitle] = useState(false);
  const [titleVal, setTitleVal] = useState(slide.title);

  const [isEditingNarrative, setIsEditingNarrative] = useState(false);
  const [narrativeVal, setNarrativeVal] = useState(slide.narrative);

  // Sync state whenever active slide changes
  React.useEffect(() => {
    setTitleVal(slide.title || "");
    setNarrativeVal(slide.narrative || "");
    setIsEditingTitle(false);
    setIsEditingNarrative(false);
  }, [slide.id, slide.title, slide.narrative]);

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

  const renderHeader = () => {
    // For title_cover layout, title is centered in the hero body
    if (layout === "title_cover") {
      return (
        <div className="slide-header-block title-cover-header">
          <div className="slide-header-top-line">
            <div className="slide-category-tag" style={{ color: theme.brand_color }}>
              {slide.category || "EXECUTIVE REVIEW"}
            </div>
          </div>
        </div>
      );
    }

    return (
      <div className="slide-header-block">
        <div className="slide-header-top-line">
          <div className="slide-category-tag" style={{ color: theme.brand_color }}>
            {slide.category || "EXECUTIVE REVIEW"}
          </div>
        </div>
        {isEditable && isEditingTitle ? (
          <input
            type="text"
            className="slide-title-input"
            value={titleVal}
            onChange={e => setTitleVal(e.target.value)}
            onBlur={handleTitleBlur}
            onKeyDown={e => e.key === "Enter" && handleTitleBlur()}
            aria-label="Edit slide title"
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
  };

  const renderFooter = () => {
    const sources = slide.evidence_sources || [];
    const limitations = slide.limitations;
    const slideNumber = slide.order || slideIndex || 1;
    const totalCount = slide.total_slides || totalSlides || 8;
    return (
      <div className="slide-footer-block" style={{ color: theme.secondary_text }}>
        <div className="footer-left">
          <span>
            {sources.length > 0 ? `Sources: ${sources.join(" · ")}` : "HighView Executive Briefing"}
          </span>
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

  if (layout === "visual_intelligence" || layout === "process_flow" || (!slide.layout && slide?.visual_spec)) {
    return (
      <div className={`slide-card-wrapper layout-${layout} visual-spec-active`} style={slideCssVariables(theme)}>
        <VisualSlideRenderer
          slide={slide}
          visualSpec={slide.visual_spec}
          theme={theme}
          isEditable={isEditable}
          onUpdate={onUpdate}
          onViewEvidence={onViewEvidence}
        />
      </div>
    );
  }

  return (
    <div
      className={`slide-card-wrapper layout-${layout}`}
      style={{
        ...slideCssVariables(theme),
        ...slideBackground(slide, theme),
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
        isEditingTitle={isEditingTitle}
        setIsEditingTitle={setIsEditingTitle}
        titleVal={titleVal}
        setTitleVal={setTitleVal}
        handleTitleBlur={handleTitleBlur}
        onUpdate={onUpdate}
      />

      {renderFooter()}
    </div>
  );
}
