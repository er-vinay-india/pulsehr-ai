import React from "react";
import {
  RotateCw,
  CheckCircle2,
  Presentation,
  Download,
  AlertTriangle,
  RefreshCw,
  Sliders
} from "lucide-react";

export default function DeckGeneratingView({
  stages,
  jobStage,
  jobProgress,
  jobStageLabel,
  jobError,
  slideProgressData,
  onOpenInStudio,
  onExportPptx,
  onExportHtml,
  onResetAndStartGeneration,
  onGoBackToConfig,
  onCancelGeneration
}) {
  return (
    <div className="pres-generating-body">
      <div className="generating-header-card">
        <div className="pipeline-spinner-badge">
          {jobStage === "ready" || jobProgress >= 100 ? (
            <CheckCircle2 size={28} style={{ color: "var(--brand-400, #ffad85)" }} />
          ) : (
            <RotateCw size={24} className="spin-icon" />
          )}
        </div>
        <h4>
          {jobStage === "ready" || jobProgress >= 100
            ? "Presentation Ready!"
            : "Synthesizing Presentation Intelligence"}
        </h4>
        <p className="generating-active-subtext">{jobStageLabel}</p>
        {jobStage === "building_slides" && slideProgressData?.total_slides > 0 && (
          <div className="active-slide-info-card">
            <div className="active-slide-badge">
              <RotateCw size={13} className="spin-icon" />
              <span>
                {slideProgressData.current_slide < slideProgressData.total_slides
                  ? `Assembling Slide ${(slideProgressData.current_slide || 0) + 1} of ${slideProgressData.total_slides}`
                  : `All ${slideProgressData.total_slides} Slides Assembled`}
              </span>
            </div>
            {slideProgressData.current_slide_title && (
              <div className="active-slide-title-text">
                <span className="active-slide-name">{slideProgressData.current_slide_title}</span>
                {slideProgressData.current_slide_category && (
                  <span className="active-slide-category-tag">{slideProgressData.current_slide_category}</span>
                )}
              </div>
            )}
          </div>
        )}

        {/* Progress bar */}
        <div className="pipeline-progress-track">
          <div
            className="pipeline-progress-bar"
            style={{ width: `${Math.max(5, jobProgress)}%` }}
          />
        </div>
        <span className="pipeline-progress-pct">{jobProgress}% Complete</span>

        {(jobStage === "ready" || jobProgress >= 100) && (
          <div style={{ display: "flex", gap: "10px", marginTop: "16px", justifyContent: "center" }}>
            <button
              type="button"
              className="btn-primary btn-sm"
              onClick={onOpenInStudio}
            >
              <Presentation size={14} />
              <span>Open in Studio</span>
            </button>
            <button
              type="button"
              className="btn-secondary btn-sm"
              onClick={onExportPptx}
            >
              <Download size={14} />
              <span>Download .PPTX</span>
            </button>
            <button
              type="button"
              className="btn-secondary btn-sm"
              onClick={onExportHtml}
              title="Download Standalone Zero-Dependency HTML Presentation"
            >
              <Download size={14} />
              <span>Download HTML</span>
            </button>
          </div>
        )}
      </div>

      {/* Stages Stepper */}
      <div className="pipeline-stages-list">
        {stages.map((st, idx) => {
          const currentStageIdx = stages.findIndex(s => s.id === jobStage);
          const isPassed = currentStageIdx > idx || jobProgress >= 100;
          const isCurrent = jobStage === st.id;

          return (
            <div
              key={st.id}
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
                <span className="stage-title">{st.label}</span>
                <span className="stage-desc">{isCurrent && st.id === "building_slides" ? jobStageLabel : st.desc}</span>
                {st.id === "building_slides" && (isCurrent || isPassed) && slideProgressData?.total_slides > 0 && (
                  <div className="stage-slide-pills-container">
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
                    {isCurrent && slideProgressData.current_slide_title && (
                      <div className="stage-active-slide-indicator">
                        <span className="indicator-dot" />
                        <span className="indicator-text">
                          Active: <strong>{slideProgressData.current_slide_title}</strong>
                        </span>
                      </div>
                    )}
                  </div>
                )}
              </div>
              {isCurrent && <span className="stage-active-pulse">Running</span>}
            </div>
          );
        })}
      </div>

      {jobError && (
        <div className="pres-error-callout">
          <AlertTriangle size={20} />
          <div className="error-callout-content">
            <strong>Generation Interrupted</strong>
            <p>{jobError}</p>
            <div className="error-callout-actions">
              <button
                type="button"
                className="btn-primary btn-sm"
                onClick={onResetAndStartGeneration}
              >
                <RefreshCw size={14} />
                <span>Generate Again</span>
              </button>
              <button
                type="button"
                className="btn-secondary btn-sm"
                onClick={onGoBackToConfig}
              >
                <Sliders size={14} />
                <span>Back to Setup</span>
              </button>
            </div>
          </div>
        </div>
      )}

      <div className="generating-actions-row">
        <button
          type="button"
          className="btn-primary"
          onClick={onResetAndStartGeneration}
          title="Restart presentation generation immediately"
        >
          <RefreshCw size={14} />
          <span>Generate Again</span>
        </button>
        <button
          type="button"
          className="btn-secondary"
          onClick={onGoBackToConfig}
          title="Return to configuration form to adjust parameters or scope"
        >
          <Sliders size={14} />
          <span>Back to Configuration</span>
        </button>
        <button
          type="button"
          className="btn-danger"
          onClick={onCancelGeneration}
        >
          Cancel Generation
        </button>
      </div>
    </div>
  );
}
