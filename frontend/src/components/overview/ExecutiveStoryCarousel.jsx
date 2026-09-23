import React, { useState } from 'react';
import { ChevronLeft, ChevronRight, CheckCircle2, AlertCircle, Compass } from 'lucide-react';

export default function ExecutiveStoryCarousel({
  findings = [],
  onInspectEvidence
}) {
  const [currentIndex, setCurrentIndex] = useState(0);

  if (!findings || findings.length === 0) return null;

  const total = findings.length;
  const current = findings[currentIndex] || findings[0];

  const goNext = () => setCurrentIndex((prev) => (prev + 1) % total);
  const goPrev = () => setCurrentIndex((prev) => (prev - 1 + total) % total);

  return (
    <div className="executive-story-carousel card-panel">
      <div className="carousel-top-bar">
        <div className="carousel-title-group">
          <Compass size={16} color="var(--accent)" />
          <h3>Strategic Narrative Stepper</h3>
          <span className="carousel-counter-badge">
            {currentIndex + 1} of {total} Priorities
          </span>
        </div>

        <div className="carousel-controls">
          <button
            type="button"
            className="btn-carousel-nav"
            onClick={goPrev}
            aria-label="Previous priority"
          >
            <ChevronLeft size={16} />
          </button>
          <div className="carousel-dots">
            {findings.map((_, idx) => (
              <button
                key={idx}
                type="button"
                className={`carousel-dot ${idx === currentIndex ? 'active' : ''}`}
                onClick={() => setCurrentIndex(idx)}
                aria-label={`Go to priority ${idx + 1}`}
              />
            ))}
          </div>
          <button
            type="button"
            className="btn-carousel-nav"
            onClick={goNext}
            aria-label="Next priority"
          >
            <ChevronRight size={16} />
          </button>
        </div>
      </div>

      <div className="carousel-slide-card">
        <div className="slide-card-header">
          <span className="slide-eyebrow">Priority #{currentIndex + 1} · {current.kind}</span>
          <h4 className="slide-title">{current.title}</h4>
        </div>

        <div className="slide-three-column-grid">
          {/* Column 1: Observation */}
          <div className="slide-col slide-col--observation">
            <span className="col-label">
              <AlertCircle size={13} color="#38bdf8" /> 1. Operational Signal
            </span>
            <p className="col-text">{current.observation}</p>
          </div>

          {/* Column 2: Implication */}
          <div className="slide-col slide-col--implication">
            <span className="col-label">
              <Compass size={13} color="#f59e0b" /> 2. Business Impact
            </span>
            <p className="col-text">{current.implication}</p>
          </div>

          {/* Column 3: Leadership Move */}
          <div className="slide-col slide-col--action">
            <span className="col-label">
              <CheckCircle2 size={13} color="#10b981" /> 3. Leadership Decision
            </span>
            <p className="col-text action-highlight">{current.action}</p>
            <small className="owner-tag">Owner: {current.owner || 'Operating Committee'}</small>
          </div>
        </div>

        {onInspectEvidence && (
          <div className="slide-footer-row">
            <button
              type="button"
              className="btn-slide-inspect"
              onClick={() => onInspectEvidence(current)}
            >
              View Data Evidence & Methodology
            </button>
          </div>
        )}
      </div>
    </div>
  );
}
