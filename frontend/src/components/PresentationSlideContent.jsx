import ResolvedSlideContent from './presentation/slides/ResolvedSlideContent.jsx';
import { SLIDE_LAYOUT_GEOMETRY } from '../theme/slideLayout.generated.js';
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
  reflow = false,
  onUpdate = () => {},
  onViewEvidence = () => {},
  deckId = null,
  deckSpec = null,
  stageMode = "html"
}) {
  theme = getSlideTheme(theme);

  const [isEditingTitle, setIsEditingTitle] = useState(false);
  const [titleVal, setTitleVal] = useState(slide.title);

  const [isEditingNarrative, setIsEditingNarrative] = useState(false);
  const [narrativeVal, setNarrativeVal] = useState(slide.narrative);

  const [imgLoaded, setImgLoaded] = useState(false);
  const [imgError, setImgError] = useState(false);

  // Sync state whenever active slide changes
  React.useEffect(() => {
    setTitleVal(slide.title || "");
    setNarrativeVal(slide.narrative || "");
    setIsEditingTitle(false);
    setIsEditingNarrative(false);
  }, [slide.id, slide.title, slide.narrative]);

  const effectiveDeckId = deckId || deckSpec?.id;
  const slideId = slide.physical_slide_id || slide.id || (slideIndex ? `slide-${slideIndex}` : null);
  const isLayered = Boolean(
    slide.physical_slide_id ||
    slide.thumbnail_url ||
    slide.zones ||
    deckSpec?.metadata?.pipeline_mode?.toLowerCase() === "layered" ||
    deckSpec?.metadata?.pipeline_mode === "LAYERED"
  );
  const renderUrl = slide.render_url || slide.thumbnail_url || (effectiveDeckId && slideId ? `/api/presentations/decks/${effectiveDeckId}/slides/${slideId}/thumbnail` : null);

  React.useEffect(() => {
    setImgLoaded(false);
    setImgError(false);
  }, [renderUrl]);

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

  const htmlUrl = effectiveDeckId && slideId ? `/api/presentations/decks/${effectiveDeckId}/slides/${slideId}/html` : null;

  if (isLayered) {
    if (stageMode === "html" && htmlUrl) {
      return (
        <div
          className="slide-card-wrapper layout-layered-slide"
          style={{
            ...slideCssVariables(theme),
            backgroundColor: theme.bg_color || "#0B0F19",
            width: "100%",
            height: "100%",
            position: "relative",
            overflow: "hidden"
          }}
        >
          <iframe
            key={htmlUrl}
            src={htmlUrl}
            title={slide.title || `Slide ${slideIndex || 1}`}
            style={{
              width: "100%",
              height: "100%",
              border: "none",
              display: "block",
              background: "transparent",
              userSelect: "text"
            }}
            loading="eager"
          />
        </div>
      );
    }

    if (renderUrl) {
      return (
        <div
          className="slide-card-wrapper layout-layered-slide"
          style={{
            ...slideCssVariables(theme),
            backgroundColor: theme.bg_color || "#0B0F19",
            width: "100%",
            height: "100%",
            display: "flex",
            alignItems: "center",
            justifyContent: "center",
            position: "relative",
            overflow: "hidden"
          }}
        >
          {!imgLoaded && !imgError && (
            <div
              className="layered-slide-loading"
              style={{
                display: "flex",
                flexDirection: "column",
                alignItems: "center",
                justifyContent: "center",
                gap: "12px",
                color: theme.secondary_text || "#94A3B8"
              }}
            >
              <div
                className="spinner-border animate-spin"
                style={{
                  width: "28px",
                  height: "28px",
                  border: `3px solid ${theme.card_border || "rgba(255,255,255,0.15)"}`,
                  borderTopColor: theme.brand_color || "#38BDF8",
                  borderRadius: "50%"
                }}
              />
              <span style={{ fontSize: "14px", fontWeight: 500 }}>Rendering slide preview…</span>
            </div>
          )}
          <img
            src={renderUrl}
            alt={slide.title || `Slide ${slideIndex || 1}`}
            onLoad={() => setImgLoaded(true)}
            onError={() => setImgError(true)}
            style={{
              width: "100%",
              height: "100%",
              objectFit: "contain",
              display: imgLoaded ? "block" : "none",
              userSelect: "none"
            }}
            loading="eager"
          />
          {imgError && (
            <div style={{ color: "#EF4444", fontSize: "14px", fontWeight: 500 }}>
              Unable to load slide preview
            </div>
          )}
        </div>
      );
    }

    return (
      <div
        className="slide-card-wrapper layout-layered-slide"
        style={{
          ...slideCssVariables(theme),
          backgroundColor: theme.bg_color || "#0B0F19",
          width: "100%",
          height: "100%",
          display: "flex",
          alignItems: "center",
          justifyContent: "center"
        }}
      >
        <div
          style={{
            display: "flex",
            flexDirection: "column",
            alignItems: "center",
            justifyContent: "center",
            gap: "12px",
            color: theme.secondary_text || "#94A3B8"
          }}
        >
          <div
            className="spinner-border animate-spin"
            style={{
              width: "28px",
              height: "28px",
              border: `3px solid ${theme.card_border || "rgba(255,255,255,0.15)"}`,
              borderTopColor: theme.brand_color || "#38BDF8",
              borderRadius: "50%"
            }}
          />
          <span style={{ fontSize: "14px", fontWeight: 500 }}>Rendering slide preview…</span>
        </div>
      </div>
    );
  }

  if (SLIDE_LAYOUT_GEOMETRY.supported_layouts.includes(layout) && !slide.image_url && !slide.background_image && !slide.talent_9box_data && !slide.burnout_strain_data) {
    return <ResolvedSlideContent slide={slide} theme={theme} slideIndex={slideIndex || slide.order || 1}
      totalSlides={totalSlides || slide.total_slides || 1} reflow={reflow} isEditable={isEditable} onUpdate={onUpdate} />;
  }

  if (layout === "visual_intelligence" || layout === "process_flow" || (!slide.layout && slide?.visual_spec)) {
    return (
      <div className={`slide-card-wrapper layout-${layout} visual-spec-active`} style={{ ...slideCssVariables(theme), ...slideBackground(slide, theme) }}>
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
