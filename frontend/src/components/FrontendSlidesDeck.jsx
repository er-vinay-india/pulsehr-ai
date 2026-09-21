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
  const [forceMobileMode, setForceMobileMode] = useState(false);
  const [inlineEditActive, setInlineEditActive] = useState(false);
  const [showEditPrompt, setShowEditPrompt] = useState(false);
  const hidePromptTimeout = useRef(null);
  const touchStartX = useRef(null);
  const touchStartY = useRef(null);
  const lastWheelTime = useRef(0);

  const themeName = theme?.name || theme?.id || "bold_signal";

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
  }, [computeStageScale, forceMobileMode]);

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
        (target.tagName === "INPUT" ||
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
    if (forceMobileMode || isMobileViewport) return;
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

  const showMobileView = isMobileViewport || forceMobileMode;
  const currentSlide = slides[activeSlideIndex] || slides[0];
  const progressPct = slides.length > 1 ? ((activeSlideIndex + 1) / slides.length) * 100 : 100;

  // Render Mobile Reflow View
  if (showMobileView) {
    return (
      <div className={`mobile-presentation-reflow theme-${themeName}`} data-slide-theme={themeName}>
        <div className="mobile-deck-header">
          <div className="mobile-deck-pagination">
            Slide {activeSlideIndex + 1} of {slides.length}
          </div>
          <div style={{ display: "flex", gap: "6px", alignItems: "center" }}>
            <button
              type="button"
              className="btn-ghost-sm"
              onClick={() => setForceMobileMode(false)}
              title="Switch to 16:9 Widescreen Fixed Stage"
            >
              <Monitor size={14} />
              <span>16:9 Stage</span>
            </button>
          </div>
        </div>

        <div
          className="mobile-slide-card-container"
          onTouchStart={handleTouchStart}
          onTouchEnd={handleTouchEnd}
        >
          {currentSlide && (
            <PresentationSlideContent
              slide={currentSlide}
              theme={theme}
              slideIndex={activeSlideIndex + 1}
              totalSlides={slides.length}
              isEditable={!readOnly && (isEditable || inlineEditActive)}
              onUpdate={updated => onUpdateSlide(activeSlideIndex, updated)}
              onViewEvidence={onViewEvidence}
            />
          )}
        </div>

        <div className="mobile-deck-nav-bar">
          <button
            type="button"
            className="btn-secondary"
            disabled={activeSlideIndex <= 0}
            onClick={() => onSlideChange(Math.max(0, activeSlideIndex - 1))}
          >
            <ChevronLeft size={16} />
            <span>Previous</span>
          </button>
          <span className="mobile-step-pill">{activeSlideIndex + 1} / {slides.length}</span>
          <button
            type="button"
            className="btn-secondary"
            disabled={activeSlideIndex >= slides.length - 1}
            onClick={() => onSlideChange(Math.min(slides.length - 1, activeSlideIndex + 1))}
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
      data-slide-theme={themeName}
      onWheel={handleWheel}
      onTouchStart={handleTouchStart}
      onTouchEnd={handleTouchEnd}
    >
      {/* Top Header Bar */}
      <div className="frontend-slides-top-bar">
        <div className="deck-brand-pill">
          <span>16:9 Stage (Frontend Slides)</span>
          <span style={{ opacity: 0.6 }}>•</span>
          <span style={{ textTransform: "capitalize" }}>{themeName.replace(/_/g, " ")}</span>
        </div>

        <div className="deck-actions">
          {onExportHtml && (
            <button
              type="button"
              className="btn-ghost-sm"
              onClick={onExportHtml}
              title="Download Standalone HTML Presentation (Offline Zero-Dependency)"
            >
              <Download size={14} />
              <span>HTML Deck</span>
            </button>
          )}

          <button
            type="button"
            className="btn-ghost-sm"
            onClick={() => !readOnly && setInlineEditActive(prev => !prev)}
            disabled={readOnly}
            title={readOnly ? "Verified findings are fixed; regenerate from source to change them" : "Toggle Inline Slide Text Editing (Shortcut: E)"}
            style={inlineEditActive ? { background: "rgba(255, 87, 34, 0.15)", color: "var(--accent-color)" } : {}}
          >
            <Edit3 size={14} />
            <span>{readOnly ? "Evidence locked" : inlineEditActive ? "Editing Mode" : "Edit Slide"}</span>
          </button>

          <button
            type="button"
            className="btn-ghost-sm"
            onClick={() => setForceMobileMode(true)}
            title="Switch to Mobile Reflow View"
          >
            <Smartphone size={14} />
            <span>Reflow View</span>
          </button>

          <button
            type="button"
            className="btn-ghost-sm"
            onClick={toggleFullscreen}
            title={isFullscreen ? "Exit Fullscreen" : "Enter Fullscreen (Shortcut: F)"}
          >
            {isFullscreen ? <Minimize2 size={14} /> : <Maximize2 size={14} />}
          </button>
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

      {/* 1920x1080 Fixed Canvas Stage Container */}
      <div className="frontend-slides-stage-container" ref={containerRef}>
        <div className="frontend-slides-stage" id="deckStage" ref={stageRef}>
          {slides.map((slide, idx) => {
            const isActive = idx === activeSlideIndex;
            return (
              <div
                key={slide.id || idx}
                className={`slide ${isActive ? "active visible" : ""}`}
                data-slide-index={idx}
              >
                <PresentationSlideContent
                  slide={slide}
                  theme={theme}
                  slideIndex={idx + 1}
                  totalSlides={slides.length}
                  isEditable={!readOnly && (isEditable || inlineEditActive) && isActive}
                  onUpdate={updated => onUpdateSlide(idx, updated)}
                  onViewEvidence={onViewEvidence}
                />
              </div>
            );
          })}
        </div>
      </div>

      {/* Floating Presentation Controls */}
      <div className="frontend-slides-controls">
        <button
          type="button"
          className="nav-btn"
          disabled={activeSlideIndex <= 0}
          onClick={() => onSlideChange(Math.max(0, activeSlideIndex - 1))}
          title="Previous Slide (Left Arrow / Page Up)"
        >
          <ChevronLeft size={18} />
        </button>

        <div className="slide-indicator">
          {activeSlideIndex + 1} / {slides.length}
        </div>

        <button
          type="button"
          className="nav-btn"
          disabled={activeSlideIndex >= slides.length - 1}
          onClick={() => onSlideChange(Math.min(slides.length - 1, activeSlideIndex + 1))}
          title="Next Slide (Right Arrow / Space / Page Down)"
        >
          <ChevronRight size={18} />
        </button>
      </div>

      {/* Dynamic Slide Progress Bar */}
      <div
        className="frontend-slides-progress-bar"
        style={{ width: `${progressPct}%` }}
      />

      {/* Acoustic Executive AI Orb Presenter */}
      {(deckId || deckSpec?.id) && (
        <AcousticOrbPresenter
          deckId={deckId || deckSpec?.id}
          deckSpec={deckSpec}
          currentSlideOrder={activeSlideIndex + 1}
          totalSlides={slides.length}
          onAdvanceSlide={() => onSlideChange(Math.min(slides.length - 1, activeSlideIndex + 1))}
          onPrevSlide={() => onSlideChange(Math.max(0, activeSlideIndex - 1))}
        />
      )}
    </div>
  );
}
