import React from "react";
import {
  CheckCircle2,
  RotateCw,
  AlertTriangle,
  Presentation,
  Download
} from "lucide-react";

const STAGE_ALIASES = {
  brief_setup: "brief_setup",
  reviewing_coverage: "brief_setup",
  recovering: "brief_setup",
  evidence_audit: "evidence_audit",
  collecting_findings: "evidence_audit",
  narrative_arc: "narrative_arc",
  planning_coverage: "narrative_arc",
  planning_presentation: "headlines",
  headings: "headlines",
  headlines: "headlines",
  layout: "layout_selection",
  layout_selection: "layout_selection",
  data_math: "math_reconciliation",
  deriving_metrics: "math_reconciliation",
  math_reconciliation: "math_reconciliation",
  narrative_ai: "headlines",
  building_slides: "headlines",
  graphics: "graphics_charts",
  rendering_graphics: "graphics_charts",
  graphics_charts: "graphics_charts",
  enrichment: "executive_polish",
  executive_polish: "executive_polish",
  polishing_tone: "executive_polish",
  text: "visual_qa",
  checking_evidence: "visual_qa",
  visual_qa: "visual_qa",
  animation: "animation",
  transitions: "animation",
  transcript: "speaker_notes",
  speaker_notes: "speaker_notes",
  formatting: "export_qa",
  checking_layout: "export_qa",
  repairing_issues: "export_qa",
  export_qa: "export_qa",
  finalizing_presentation: "export_qa",
  ready: "ready",
};

/**
 * SlideTrain Component
 *
 * Layman explanation:
 * Renders a compact, sleek single row of slide pills.
 * Look and feel is completely unified across both running and completed phases:
 * - Completed slides show: Slide 1 ✓
 * - Active slide shows: Slide 2 ⟳ (subtle glowing active indicator)
 * - Upcoming slides show: Slide 3
 * Compact, lightweight, single horizontal line, zero clutter, zero AI badges.
 */
function SlideTrain({ totalSlides, currentSlide, isPassed, isCurrent }) {
  if (!totalSlides || totalSlides <= 0) return null;

  return (
    <div className="stage-slide-pills-row">
      {Array.from({ length: totalSlides }, (_, i) => {
        const slideNum = i + 1;
        const isDone = isPassed || slideNum < currentSlide || (currentSlide === totalSlides);
        const isActive = isCurrent && slideNum === currentSlide && currentSlide < totalSlides;

        return (
          <span
            key={slideNum}
            className={`slide-step-pill ${isDone ? "done" : isActive ? "building" : "pending"}`}
            title={`Slide ${slideNum}`}
          >
            Slide {slideNum}
            {isDone ? (
              <span className="pill-status-mark"> ✓</span>
            ) : isActive ? (
              <RotateCw size={10} className="pill-spin spin-icon" />
            ) : null}
          </span>
        );
      })}
    </div>
  );
}

export default function DeckGeneratingView({
  stages = [],
  jobStage = "layout",
  jobProgress = 0,
  jobStageLabel = "",
  jobError = null,
  slideProgressData = null,
  onGoBackToConfig,
  onCancelGeneration,
  onResetAndStartGeneration,
  onOpenInStudio,
  onExportPptx,
  onExportHtml,
}) {
  const currentStageId = STAGE_ALIASES[jobStage] || jobStage;
  let index = stages.findIndex((s) => s.id === currentStageId);
  if (index === -1) {
    index = Math.min(stages.length - 1, Math.max(0, Math.floor((jobProgress / 100) * stages.length)));
  }
  const currentStage = stages[index] || stages[0];

  return (
    <div className="pres-generating-body" aria-busy={!jobError}>
      {/* Top Header Card */}
      <div className="generating-header-card" role="status" aria-live="polite">
        <div className="pipeline-spinner-badge" aria-hidden="true">
          <RotateCw size={26} className="spin-icon" />
        </div>

        <p className="generating-subtitle">HRIDAY · Building your presentation</p>

        <h4 className="generating-phase-title">
          {jobError
            ? "Generation paused"
            : `Phase ${index + 1} of ${stages.length}: ${currentStage?.label || "Processing"}`}
        </h4>

        {/* Unified progress message with zero duplication */}
        <p className="generating-detail-label">
          {jobStageLabel || "Synthesizing executive briefing from ground-truth data..."}
        </p>

        {/* Progress bar */}
        <div
          className="pipeline-progress-track"
          role="progressbar"
          aria-valuenow={jobProgress}
          aria-valuemin={0}
          aria-valuemax={100}
          aria-label="Presentation generation progress"
        >
          <div
            className="pipeline-progress-bar"
            style={{ width: `${Math.max(5, Math.min(100, jobProgress))}%` }}
          />
        </div>
        <span className="pipeline-progress-pct">{jobProgress}% Complete</span>

        {!jobError && jobStage === "ready" && onOpenInStudio && (
          <div style={{ display: "flex", gap: "10px", marginTop: "16px", justifyContent: "center" }}>
            <button
              type="button"
              className="btn-primary btn-sm"
              onClick={onOpenInStudio}
            >
              <Presentation size={14} />
              <span>Open in Studio</span>
            </button>
            {onExportPptx && (
              <button
                type="button"
                className="btn-secondary btn-sm"
                onClick={onExportPptx}
              >
                <Download size={14} />
                <span>Download .PPTX</span>
              </button>
            )}
            {onExportHtml && (
              <button
                type="button"
                className="btn-secondary btn-sm"
                onClick={onExportHtml}
              >
                <Download size={14} />
                <span>Download HTML</span>
              </button>
            )}
          </div>
        )}
      </div>

      {/* 8-Phase Sequential Stepper List */}
      <div className="pipeline-stages-list" role="list" aria-label="8-phase generation sequence">
        {stages.map((st, idx) => {
          const isPassed = !jobError && (index > idx || jobStage === "ready");
          const isCurrent = index === idx && !jobError;

          return (
            <div
              key={st.id}
              role="listitem"
              className={`pipeline-stage-row ${isPassed ? "completed" : ""} ${isCurrent ? "active" : ""}`}
            >
              <div className="stage-status-icon">
                {isPassed ? (
                  <CheckCircle2 size={18} className="icon-success" />
                ) : isCurrent ? (
                  <RotateCw size={18} className="icon-active spin-icon" />
                ) : (
                  <span className="stage-num">{idx + 1}</span>
                )}
              </div>

              <div className="stage-meta">
                <div className="stage-title-row">
                  <span className="stage-title">Phase {idx + 1}: {st.label}</span>
                </div>
                <span className="stage-desc">
                  {isCurrent && jobStageLabel ? jobStageLabel : (st.desc || st.label)}
                </span>

                {/* Unified, compact SlideTrain across active and completed phases */}
                {(isCurrent || isPassed) && slideProgressData?.total_slides > 0 && (
                  <SlideTrain
                    totalSlides={slideProgressData.total_slides}
                    currentSlide={slideProgressData.current_slide || 0}
                    isPassed={isPassed}
                    isCurrent={isCurrent}
                  />
                )}
              </div>

              {isCurrent && <span className="stage-active-pulse">Running</span>}
            </div>
          );
        })}
      </div>

      {/* Error Callout */}
      {jobError && (
        <div className="pres-error-callout" role="alert" aria-live="assertive">
          <AlertTriangle size={20} />
          <div className="error-callout-content">
            <strong>Generation Interrupted</strong>
            <p>{jobError}</p>
          </div>
        </div>
      )}

      {/* Action Row - Navigation locked while generating */}
      <div className="generating-actions-row">
        <button
          type="button"
          className="btn-secondary"
          disabled={!jobError}
          onClick={() => onGoBackToConfig()}
          title={!jobError ? "Navigation locked while presentation is generating" : "Return to configuration setup"}
          aria-disabled={!jobError}
        >
          Back to setup
        </button>

        {jobError ? (
          <button
            type="button"
            className="btn-primary"
            onClick={() => onResetAndStartGeneration()}
          >
            Try again
          </button>
        ) : (
          <button
            type="button"
            className="btn-secondary"
            onClick={onCancelGeneration}
          >
            Cancel generation
          </button>
        )}
      </div>
    </div>
  );
}
