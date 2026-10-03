import DeckControl from './presentation/DeckControl.jsx';
import { getSlideTheme, slideCssVariables } from '../theme/slideTokens.js';
import React, { useEffect, useRef, useState, useCallback } from "react";
import {
  ChevronLeft,
  ChevronRight,
  Maximize2,
  Minimize2,
  Smartphone,
  Monitor,
  Edit3,
  Check,
  Download,
  FileText
} from "lucide-react";
import PresentationSlideContent from "./PresentationSlideContent.jsx";
import AcousticOrbPresenter from "./presentation/AcousticOrbPresenter.jsx";
import "../styles/frontend-slides.scss";

export default function FrontendSlidesDeck({
  slides = [],
  theme = {},
  activeSlideIndex = 0,
  onSlideChange = () => {},
  isEditable = false,
  readOnly = false,
  onUpdateSlide = () => {},
  onViewEvidence = () => {},
  onExportHtml = null,
  deckId = null,
  deckSpec = null
}) {
  const containerRef = useRef(null);
  const stageRef = useRef(null);
  const [scale, setScale] = useState(1);
  const [stagePosition, setStagePosition] = useState({ x: 0, y: 0 });
  const [isFullscreen, setIsFullscreen] = useState(false);
  const [isMobileViewport, setIsMobileViewport] = useState(() => typeof window !== "undefined" && window.innerWidth <= 768);
  const [forceDesktopMode, setForceDesktopMode] = useState(false);
  const [forceMobileMode, setForceMobileMode] = useState(false);
  const [inlineEditActive, setInlineEditActive] = useState(false);
  const [showEditPrompt, setShowEditPrompt] = useState(false);
  const hidePromptTimeout = useRef(null);
  const touchStartX = useRef(null);
  const touchStartY = useRef(null);
  const lastWheelTime = useRef(0);

  theme = getSlideTheme(theme);
  const themeName = theme.id;
  const slideVariables = slideCssVariables(theme);

  // Compute fixed 16:9 stage scaling (1920x1080 canvas)
  const computeStageScale = useCallback(() => {
    if (!containerRef.current || !stageRef.current) return;
    const container = containerRef.current;
    const cw = container.clientWidth || window.innerWidth;
    const ch = container.clientHeight || window.innerHeight;

    if (cw <= 0 || ch <= 0) return;

    // Uniform 16:9 aspect scaling
    const factor = Math.min(cw / 1920, ch / 1080);
    const x = Math.max(0, (cw - 1920 * factor) / 2);
    const y = Math.max(0, (ch - 1080 * factor) / 2);

    setScale(factor);
    setStagePosition({ x, y });

    stageRef.current.style.transform = `translate(${x}px, ${y}px) scale(${factor})`;
  }, []);

  // Monitor viewport size & container resize
  useEffect(() => {
    const handleResize = () => {
      setIsMobileViewport(window.innerWidth <= 768);
      computeStageScale();
    };

    window.addEventListener("resize", handleResize);

    const resizeObserver = new ResizeObserver(() => {
      computeStageScale();
    });

    if (containerRef.current) {
      resizeObserver.observe(containerRef.current);
    }

    // Initial scale calculation
    computeStageScale();
    const timer = setTimeout(computeStageScale, 50);

    return () => {
      window.removeEventListener("resize", handleResize);
      resizeObserver.disconnect();
      clearTimeout(timer);
    };
  }, [computeStageScale, forceMobileMode, forceDesktopMode, isMobileViewport]);

  // Fullscreen toggle
  const toggleFullscreen = () => {
    if (!document.fullscreenElement) {
      if (containerRef.current?.parentElement?.requestFullscreen) {
        containerRef.current.parentElement.requestFullscreen().then(() => setIsFullscreen(true)).catch(() => {});
      }
    } else {
      if (document.exitFullscreen) {
        document.exitFullscreen().then(() => setIsFullscreen(false)).catch(() => {});
      }
    }
  };

  useEffect(() => {
    const onFullscreenChange = () => {
      setIsFullscreen(!!document.fullscreenElement);
      setTimeout(computeStageScale, 100);
    };
    document.addEventListener("fullscreenchange", onFullscreenChange);
    return () => document.removeEventListener("fullscreenchange", onFullscreenChange);
  }, [computeStageScale]);

  // Keyboard navigation & Shortcuts (Arrows, Space, Page Up/Down, Home, End, F, E)
  useEffect(() => {
    const handleKeyDown = (e) => {
      // Don't intercept if editing text inside input / textarea / contenteditable
      const target = e.target;
      if (
        target &&
        (target.closest?.("[role=dialog], summary") ||
          target.tagName === "BUTTON" || target.tagName === "SELECT" ||
          target.tagName === "INPUT" ||
          target.tagName === "TEXTAREA" ||
          target.isContentEditable)
      ) {
        return;
      }

      if (e.key === "ArrowRight" || e.key === "PageDown" || e.key === " ") {
        e.preventDefault();
        if (activeSlideIndex < slides.length - 1) {
          onSlideChange(activeSlideIndex + 1);
        }
      } else if (e.key === "ArrowLeft" || e.key === "PageUp") {
        e.preventDefault();
        if (activeSlideIndex > 0) {
          onSlideChange(activeSlideIndex - 1);
        }
      } else if (e.key === "Home") {
        e.preventDefault();
        onSlideChange(0);
      } else if (e.key === "End") {
        e.preventDefault();
        onSlideChange(slides.length - 1);
      } else if (e.key === "f" || e.key === "F") {
        e.preventDefault();
        toggleFullscreen();
      } else if (e.key === "e" || e.key === "E") {
        e.preventDefault();
        if (!readOnly) setInlineEditActive(prev => !prev);
      }
    };

    window.addEventListener("keydown", handleKeyDown);
    return () => window.removeEventListener("keydown", handleKeyDown);
  }, [activeSlideIndex, slides.length, onSlideChange, readOnly]);

  // Touch / Swipe gestures (>44px)
  const handleTouchStart = (e) => {
    if (e.touches && e.touches[0]) {
      touchStartX.current = e.touches[0].clientX;
      touchStartY.current = e.touches[0].clientY;
    }
  };

  const handleTouchEnd = (e) => {
    if (touchStartX.current === null || touchStartY.current === null) return;
    const touchEndX = e.changedTouches[0].clientX;
    const touchEndY = e.changedTouches[0].clientY;
    const diffX = touchStartX.current - touchEndX;
    const diffY = touchStartY.current - touchEndY;

    if (Math.abs(diffX) > Math.abs(diffY) && Math.abs(diffX) > 44) {
      if (diffX > 0 && activeSlideIndex < slides.length - 1) {
        onSlideChange(activeSlideIndex + 1);
      } else if (diffX < 0 && activeSlideIndex > 0) {
        onSlideChange(activeSlideIndex - 1);
      }
    }
    touchStartX.current = null;
    touchStartY.current = null;
  };

  // Mouse wheel slide transitions (debounced 400ms)
  const handleWheel = (e) => {
    if (!isFullscreen || inlineEditActive || forceMobileMode || isMobileViewport) return;
    const now = Date.now();
    if (now - lastWheelTime.current < 400) return;

    if (Math.abs(e.deltaY) > 30) {
      lastWheelTime.current = now;
      if (e.deltaY > 0 && activeSlideIndex < slides.length - 1) {
        onSlideChange(activeSlideIndex + 1);
      } else if (e.deltaY < 0 && activeSlideIndex > 0) {
        onSlideChange(activeSlideIndex - 1);
      }
    }
  };

  // Hotzone hover with 400ms grace period for inline edit toggle
  const handleHotzoneEnter = () => {
    clearTimeout(hidePromptTimeout.current);
    setShowEditPrompt(true);
  };

  const handleHotzoneLeave = () => {
    hidePromptTimeout.current = setTimeout(() => {
      if (!inlineEditActive) setShowEditPrompt(false);
    }, 400);
  };

  const showMobileView = (isMobileViewport && !forceDesktopMode) || forceMobileMode;
  const currentSlide = slides[activeSlideIndex] || slides[0];
  const progressPct = slides.length > 1 ? ((activeSlideIndex + 1) / slides.length) * 100 : 100;

  const editor = isEditable && !readOnly && inlineEditActive && currentSlide && (
    <div id="deck-slide-text-editor" className="pres-slide-text-editor" key={currentSlide.id} role="region" aria-label="Edit slide text">
      {[['title', 'Title'], ['subtitle', 'Subtitle'], ['narrative', 'Body'], ['bullets', 'Takeaways (one per line)']].map(([field, label]) => (
        <label key={field}>{label}
          <textarea aria-label={`Slide ${label}`} rows={field === "bullets" ? 3 : 2}
            key={`${currentSlide.id}-${field}-${JSON.stringify(currentSlide[field])}`}
            defaultValue={field === "bullets" ? (currentSlide.bullets || []).map(item => typeof item === "string" ? item : item.text).join("\n") : currentSlide[field] || ""}
            onBlur={event => {
              const value = field === "bullets" ? event.target.value.split("\n").filter(Boolean) : event.target.value;
              if (JSON.stringify(value) === JSON.stringify(currentSlide[field] || (field === "bullets" ? [] : ""))) return;
              const updated = { ...currentSlide, [field]: value, provenance: "USER_OVERRIDE" };
              if (updated.visual_spec) updated.visual_spec = { ...updated.visual_spec, [field === "title" ? "headline" : field === "bullets" ? "insights" : field]: value };
              onUpdateSlide(activeSlideIndex, updated);
            }} />
        </label>
      ))}
    </div>
  );

  // Render Mobile Reflow View
  if (showMobileView) {
    return (
      <div className={`mobile-presentation-reflow theme-${themeName}`} data-slide-theme={themeName} style={slideVariables}>
        <div className="mobile-deck-header" role="navigation" aria-label="Quick slide navigation">
          <button type="button" className="btn-secondary" disabled={activeSlideIndex <= 0}
            onClick={() => onSlideChange(Math.max(0, activeSlideIndex - 1))} aria-label="Previous Slide">
            <ChevronLeft size={18} aria-hidden="true" />
          </button>
          <div className="mobile-deck-pagination" aria-live="polite" aria-atomic="true">
            Slide {activeSlideIndex + 1} of {slides.length}
          </div>
          <button type="button" className="btn-secondary" disabled={activeSlideIndex >= slides.length - 1}
            onClick={() => onSlideChange(Math.min(slides.length - 1, activeSlideIndex + 1))} aria-label="Next Slide">
            <ChevronRight size={18} aria-hidden="true" />
          </button>
        </div>
        <div className="mobile-deck-view-tools">
          {isEditable && !readOnly && <button type="button" className="btn-secondary"
            aria-expanded={inlineEditActive} aria-controls="deck-slide-text-editor"
            onClick={() => setInlineEditActive(value => !value)}>
            <Edit3 size={16} aria-hidden="true" />{inlineEditActive ? "Close editor" : "Edit text"}
          </button>}
          <button type="button" className="btn-secondary"
            onClick={() => { setForceMobileMode(false); setForceDesktopMode(true); }}>
            <Monitor size={16} aria-hidden="true" />Slide preview
          </button>
        </div>
        {editor}
        <div
          className="mobile-slide-card-container"
          onTouchStart={handleTouchStart}
          onTouchEnd={handleTouchEnd}
        >
          {currentSlide && (
            <PresentationSlideContent
              slide={currentSlide}
              reflow
              theme={theme}
              slideIndex={activeSlideIndex + 1}
              totalSlides={slides.length}
              isEditable={!readOnly && (isEditable && inlineEditActive)}
              onUpdate={updated => onUpdateSlide(activeSlideIndex, updated)}
              onViewEvidence={onViewEvidence}
            />
          )}
        </div>

        <div className="mobile-deck-nav-bar" role="navigation" aria-label="Mobile slide navigation">
          <button
            type="button"
            className="btn-secondary"
            disabled={activeSlideIndex <= 0}
            onClick={() => onSlideChange(Math.max(0, activeSlideIndex - 1))}
            aria-label="Previous Slide"
          >
            <ChevronLeft size={16} />
            <span>Previous</span>
          </button>
          <span className="mobile-step-pill" aria-live="polite" aria-atomic="true">
            {activeSlideIndex + 1} / {slides.length}
          </span>
          <button
            type="button"
            className="btn-secondary"
            disabled={activeSlideIndex >= slides.length - 1}
            onClick={() => onSlideChange(Math.min(slides.length - 1, activeSlideIndex + 1))}
            aria-label="Next Slide"
          >
            <span>Next</span>
            <ChevronRight size={16} />
          </button>
        </div>

      </div>
    );
  }

  // Render 16:9 Fixed Stage View (Frontend Slides Engine)
  return (
    <div
      className={`frontend-slides-viewport theme-${themeName}`}
      data-slide-theme={themeName} style={slideVariables}
      onWheel={handleWheel}
      onTouchStart={handleTouchStart}
      onTouchEnd={handleTouchEnd}
    >
      {/* Top Header Bar */}
      <div className="frontend-slides-top-bar">
        <DeckControl className="symbolic-brand-wrap">
          <div className="symbolic-brand-pill">
            <Monitor size={13} />
            <span className="brand-dot" />
            <span className="brand-label-responsive">{themeName.replace(/_/g, " ")}</span>
          </div>
          <span className="symbolic-tooltip">16:9 Stage · Theme: {themeName.replace(/_/g, " ")}</span>
        </DeckControl>

        <div className="deck-actions">
          {onExportHtml && (
            <DeckControl className="symbolic-btn-wrap">
              <button
                type="button"
                className="symbolic-action-btn"
                onClick={onExportHtml}
                aria-label="Download Standalone HTML Presentation"
              >
                <Download size={14} />
                <span className="btn-label-responsive">HTML</span>
              </button>
              <span className="symbolic-tooltip">Download Standalone HTML Deck (Zero-Dependency)</span>
            </DeckControl>
          )}

          <DeckControl className="symbolic-btn-wrap">
            <button
              type="button"
              className={`symbolic-action-btn ${inlineEditActive ? "active" : ""}`}
              onClick={() => !readOnly && setInlineEditActive(prev => !prev)}
              disabled={readOnly}
              aria-label="Toggle Inline Edit"
            >
              <Edit3 size={14} />
              <span className="btn-label-responsive">{readOnly ? "Locked" : inlineEditActive ? "Editing" : "Edit"}</span>
            </button>
            <span className="symbolic-tooltip">{readOnly ? "Evidence Locked by Governance" : "Inline Text Editing (Shortcut: E)"}</span>
          </DeckControl>

          <DeckControl className="symbolic-btn-wrap">
            <button
              type="button"
              className="symbolic-action-btn"
              onClick={() => { setForceDesktopMode(false); setForceMobileMode(true); }}
              aria-label="Switch to Mobile Reflow View"
            >
              <Smartphone size={14} />
              <span className="btn-label-responsive">Reflow</span>
            </button>
            <span className="symbolic-tooltip">Mobile Reflow View: Vertical scrolling responsive deck</span>
          </DeckControl>

          <DeckControl className="symbolic-btn-wrap">
            <button
              type="button"
              className="symbolic-action-btn"
              onClick={toggleFullscreen}
              aria-label={isFullscreen ? "Exit Fullscreen" : "Enter Fullscreen"}
            >
              {isFullscreen ? <Minimize2 size={14} /> : <Maximize2 size={14} />}
            </button>
            <span className="symbolic-tooltip">{isFullscreen ? "Exit Fullscreen" : "Fullscreen Stage (Shortcut: F)"}</span>
          </DeckControl>
        </div>
      </div>

      {/* Edit Hotzone for Hover Trigger */}
      {!readOnly && <><div
        className="edit-hotzone"
        onMouseEnter={handleHotzoneEnter}
        onMouseLeave={handleHotzoneLeave}
        onClick={() => !readOnly && setInlineEditActive(prev => !prev)}
      />
      <div
        className={`edit-toggle-badge ${showEditPrompt || inlineEditActive ? "show" : ""} ${inlineEditActive ? "active" : ""}`}
        onMouseEnter={handleHotzoneEnter}
        onMouseLeave={handleHotzoneLeave}
        onClick={() => !readOnly && setInlineEditActive(prev => !prev)}
      >
        <Edit3 size={13} />
        <span>{inlineEditActive ? "Editing active (press E to lock)" : "Click or press E to edit"}</span>
      </div></>}

      {editor}
      {/* 1920x1080 Fixed Canvas Stage Container */}
      <div className="frontend-slides-stage-container" ref={containerRef}>
        <div
          className="frontend-slides-stage"
          id="deckStage"
          ref={stageRef}
          role="region"
          aria-label="Slide stage"
          aria-roledescription="presentation slide stage"
        >
          {slides.slice(activeSlideIndex, activeSlideIndex + 1).map((slide) => {
            const idx = activeSlideIndex;
            const isActive = idx === activeSlideIndex;
            return (
              <div
                key={slide.id || idx}
                className={`slide ${isActive ? "active visible" : ""}`}
                data-transition={slide.transition || deckSpec?.metadata?.transition || "none"}
                data-animation={slide.animation || "none"}
                data-slide-index={idx}
                role="group"
                aria-roledescription="slide"
                aria-hidden={!isActive}
                aria-label={`Slide ${idx + 1} of ${slides.length}: ${slide.title || ""}`}
              >
                <PresentationSlideContent
                  slide={slide}
                  theme={theme}
                  slideIndex={idx + 1}
                  totalSlides={slides.length}
                  isEditable={!readOnly && (isEditable && inlineEditActive) && isActive}
                  onUpdate={updated => onUpdateSlide(idx, updated)}
                  onViewEvidence={onViewEvidence}
                />
              </div>
            );
          })}
        </div>
      </div>

      {/* Floating Presentation Controls */}
      <div className="frontend-slides-controls" role="toolbar" aria-label="Slide navigation controls">
        <button
          type="button"
          className="nav-btn"
          disabled={activeSlideIndex <= 0}
          onClick={() => onSlideChange(Math.max(0, activeSlideIndex - 1))}
          title="Previous Slide (Left Arrow / Page Up)"
          aria-label="Previous Slide"
        >
          <ChevronLeft size={18} />
        </button>

        <div className="slide-indicator" aria-live="polite" aria-atomic="true">
          {activeSlideIndex + 1} / {slides.length}
        </div>

        <button
          type="button"
          className="nav-btn"
          disabled={activeSlideIndex >= slides.length - 1}
          onClick={() => onSlideChange(Math.min(slides.length - 1, activeSlideIndex + 1))}
          title="Next Slide (Right Arrow / Space / Page Down)"
          aria-label="Next Slide"
        >
          <ChevronRight size={18} />
        </button>
      </div>

      {/* Dynamic Slide Progress Bar */}
      <div
        className="frontend-slides-progress-bar"
        style={{ width: `${progressPct}%` }}
        role="progressbar"
        aria-valuenow={activeSlideIndex + 1}
        aria-valuemin={1}
        aria-valuemax={slides.length}
        aria-label="Presentation deck progress"
      />

      {/* Acoustic Executive AI Orb Presenter */}

    </div>
  );
}
