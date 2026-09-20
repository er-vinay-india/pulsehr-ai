import React, { useEffect, useRef, useState } from "react";
import Reveal from "reveal.js";
import "reveal.js/reset.css";
import "reveal.js/reveal.css";
import { ChevronLeft, ChevronRight, Maximize2, Smartphone, Monitor } from "lucide-react";
import PresentationSlideContent from "./PresentationSlideContent.jsx";

export default function PresentationRevealDeck({
  slides = [],
  theme = {},
  activeSlideIndex = 0,
  onSlideChange = () => {},
  isEditable = false,
  onUpdateSlide = () => {}
}) {
  const deckRef = useRef(null);
  const revealInstance = useRef(null);
  const [isMobileViewport, setIsMobileViewport] = useState(() => typeof window !== "undefined" && window.innerWidth <= 768);
  const [forceMobileMode, setForceMobileMode] = useState(false);

  useEffect(() => {
    const handleResize = () => {
      setIsMobileViewport(window.innerWidth <= 768);
    };
    window.addEventListener("resize", handleResize);
    return () => window.removeEventListener("resize", handleResize);
  }, []);

  const showMobileView = isMobileViewport || forceMobileMode;

  useEffect(() => {
    if (showMobileView) {
      if (revealInstance.current) {
        try {
          revealInstance.current.destroy();
          revealInstance.current = null;
        } catch (e) {
          // ignore
        }
      }
      return;
    }

    if (!deckRef.current) return;

    const deck = new Reveal(deckRef.current, {
      embedded: true,
      width: 1200,
      height: 675,
      margin: 0.04,
      minScale: 0.2,
      maxScale: 2.0,
      controls: true,
      progress: true,
      slideNumber: "c/t",
      keyboard: true,
      overview: true,
      center: false,
      hash: false,
      transition: "slide",
      respondToHashChanges: false,
    });

    deck.initialize().then(() => {
      revealInstance.current = deck;
      deck.on("slidechanged", event => {
        onSlideChange(event.indexh);
      });
      if (activeSlideIndex > 0) {
        deck.slide(activeSlideIndex, 0);
      }
    }).catch(err => {
      console.warn("Reveal init warning:", err);
    });

    return () => {
      if (revealInstance.current) {
        try {
          revealInstance.current.destroy();
          revealInstance.current = null;
        } catch (e) {
          // ignore
        }
      }
    };
  }, [showMobileView]);

  // Sync external index changes to Reveal
  useEffect(() => {
    if (revealInstance.current && !showMobileView) {
      try {
        const indices = revealInstance.current.getIndices();
        if (indices && indices.h !== activeSlideIndex) {
          revealInstance.current.slide(activeSlideIndex, 0);
        }
      } catch (e) {
        // ignore
      }
    }
  }, [activeSlideIndex, showMobileView]);

  // Sync slides and theme updates to Reveal
  useEffect(() => {
    if (revealInstance.current && !showMobileView) {
      try {
        revealInstance.current.sync();
      } catch (e) {
        // ignore
      }
    }
  }, [slides, theme, showMobileView]);

  // Mobile Reflow View
  if (showMobileView) {
    const currentSlide = slides[activeSlideIndex] || slides[0];

    return (
      <div className="mobile-presentation-reflow">
        <div className="mobile-deck-header">
          <div className="mobile-deck-pagination">
            Slide {activeSlideIndex + 1} of {slides.length}
          </div>
          <button
            type="button"
            className="btn-ghost-sm"
            onClick={() => setForceMobileMode(!forceMobileMode)}
            title={forceMobileMode ? "Switch to 16:9 Widescreen" : "Switch to Mobile Reflow"}
          >
            {forceMobileMode ? <Monitor size={14} /> : <Smartphone size={14} />}
            <span>{forceMobileMode ? "16:9 View" : "Reflow View"}</span>
          </button>
        </div>

        <div className="mobile-slide-card-container">
          {currentSlide && (
            <PresentationSlideContent
              slide={currentSlide}
              theme={theme}
              isEditable={isEditable}
              onUpdate={updated => onUpdateSlide(activeSlideIndex, updated)}
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

  // Desktop Reveal.js 16:9 View
  return (
    <div className="desktop-reveal-viewport">
      <div className="reveal-top-bar">
        <div className="viewport-badge">16:9 Executive Presentation (Reveal.js)</div>
        <button
          type="button"
          className="btn-ghost-sm"
          onClick={() => setForceMobileMode(true)}
          title="Switch to Mobile Reflow view"
        >
          <Smartphone size={14} />
          <span>Reflow View</span>
        </button>
      </div>

      <div className="reveal-wrapper-16x9">
        <div className="reveal" ref={deckRef}>
          <div className="slides">
            {slides.map((slide, idx) => (
              <section key={slide.id || idx} data-transition="slide">
                <PresentationSlideContent
                  slide={slide}
                  theme={theme}
                  isEditable={isEditable && activeSlideIndex === idx}
                  onUpdate={updated => onUpdateSlide(idx, updated)}
                />
              </section>
            ))}
          </div>
        </div>
      </div>
    </div>
  );
}
