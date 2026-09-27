import React from "react";
import {
  CheckCircle2,
  RotateCw,
  AlertTriangle,
  Presentation,
  Download
} from "lucide-react";

const STAGE_ALIASES = {
  reviewing_coverage: "layout",
  collecting_findings: "layout",
  planning_coverage: "layout",
  layout: "layout",
  planning_presentation: "headings",
  building_slides: "headings",
  headings: "headings",
  graphics: "graphics",
  rendering_graphics: "graphics",
  text: "text",
  checking_evidence: "text",
  animation: "animation",
  transitions: "transitions",
  transcript: "transcript",
  formatting: "formatting",
  checking_layout: "formatting",
  repairing_issues: "formatting",
  finalizing_presentation: "formatting",
  ready: "formatting",
};

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

        {(jobStage === "ready" || jobProgress >= 100) && onOpenInStudio && (
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
          const isPassed = index > idx || jobProgress >= 100;
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
                <span className="stage-title">Phase {idx + 1}: {st.label}</span>
                <span className="stage-desc">
                  {isCurrent && jobStageLabel ? jobStageLabel : (st.desc || st.label)}
                </span>

                {/* Sequential Slide Generation Progress - strictly on Slide Synthesis Phase (Phase 2) */}
                {st.id === "headings" && (isCurrent || isPassed) && slideProgressData?.total_slides > 0 && (
                  <div className="stage-slide-sequential-container">
                    <div className="stage-slide-pills-row">
                      {Array.from({ length: slideProgressData.total_slides }, (_, i) => {
                        const slideNum = i + 1;
                        const isDone = isPassed || slideNum <= (slideProgressData.current_slide || 0);
                        const isBuilding = isCurrent && slideNum === (slideProgressData.current_slide || 0) + 1;
                        return (
                          <span
                            key={slideNum}
                            className={`slide-step-pill ${isDone ? "done" : isBuilding ? "building" : "pending"}`}
                            title={`Slide ${slideNum}: ${isDone ? "Complete" : isBuilding ? "Building..." : "Pending"}`}
                          >
                            {isDone ? `Slide ${slideNum} ✓` : isBuilding ? `Slide ${slideNum} ⟳` : `Slide ${slideNum}`}
                          </span>
                        );
                      })}
                    </div>

                    {/* Sequential Log displaying which slides got generated */}
                    <div className="sequential-slide-generation-list">
                      {slideProgressData.slide_status_list && slideProgressData.slide_status_list.length > 0
                        ? slideProgressData.slide_status_list
                            .filter((s) => s.status === "complete" || (isCurrent && s.status === "building"))
                            .map((s) => (
                              <div key={s.order} className={`sequential-slide-row ${s.status}`}>
                                <span className="seq-slide-icon">
                                  {s.status === "complete" ? (
                                    <CheckCircle2 size={13} className="icon-success" />
                                  ) : (
                                    <RotateCw size={13} className="spin-icon icon-active" />
                                  )}
                                </span>
                                <span className="seq-slide-title">
                                  <strong>Slide {s.order}:</strong> {s.title || (s.status === "building" ? "Synthesizing content..." : `Slide ${s.order}`)}
                                </span>
                                {s.category && <span className="seq-slide-cat">{s.category}</span>}
                                <span className={`seq-slide-status-badge ${s.status}`}>
                                  {s.status === "complete" ? "Generated" : "Synthesizing"}
                                </span>
                              </div>
                            ))
                        : (
                          Array.from({ length: Math.min(slideProgressData.total_slides, (slideProgressData.current_slide || 0)) }, (_, i) => {
                            const slideNum = i + 1;
                            return (
                              <div key={slideNum} className="sequential-slide-row complete">
                                <span className="seq-slide-icon">
                                  <CheckCircle2 size={13} className="icon-success" />
                                </span>
                                <span className="seq-slide-title">
                                  <strong>Slide {slideNum}:</strong> {slideNum === slideProgressData.current_slide && slideProgressData.current_slide_title ? slideProgressData.current_slide_title : `Slide ${slideNum}`}
                                </span>
                                <span className="seq-slide-status-badge complete">Generated</span>
                              </div>
                            );
                          })
                        )}
                    </div>
                  </div>
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
