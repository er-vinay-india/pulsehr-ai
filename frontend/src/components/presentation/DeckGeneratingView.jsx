import React from "react";
import {
  CheckCircle2,
  RotateCw,
  AlertTriangle,
  Presentation,
  Download,
  Lock,
  Layout,
  Layers
} from "lucide-react";

const STAGE_ALIASES = {
  brief_setup: "understanding_data",
  reviewing_coverage: "understanding_data",
  recovering: "understanding_data",
  evidence_audit: "understanding_data",
  collecting_findings: "understanding_data",
  understanding_data: "understanding_data",
  narrative_arc: "planning_story",
  planning_coverage: "planning_story",
  planning_story: "planning_story",
  headlines: "preparing_slides",
  planning_presentation: "preparing_slides",
  headings: "preparing_slides",
  narrative_ai: "preparing_slides",
  building_slides: "preparing_slides",
  preparing_slides: "preparing_slides",
  layout: "arranging_content",
  layout_selection: "arranging_content",
  arranging_content: "arranging_content",
  graphics: "rendering_presentation",
  rendering_graphics: "rendering_presentation",
  graphics_charts: "rendering_presentation",
  rendering_presentation: "rendering_presentation",
  data_math: "checking_slide_quality",
  deriving_metrics: "checking_slide_quality",
  math_reconciliation: "checking_slide_quality",
  text: "checking_slide_quality",
  checking_evidence: "checking_slide_quality",
  visual_qa: "checking_slide_quality",
  checking_slide_quality: "checking_slide_quality",
  enrichment: "finalizing_presentation",
  executive_polish: "finalizing_presentation",
  polishing_tone: "finalizing_presentation",
  animation: "finalizing_presentation",
  transitions: "finalizing_presentation",
  transcript: "finalizing_presentation",
  speaker_notes: "finalizing_presentation",
  formatting: "finalizing_presentation",
  checking_layout: "finalizing_presentation",
  repairing_issues: "finalizing_presentation",
  export_qa: "finalizing_presentation",
  finalizing_presentation: "finalizing_presentation",
  ready: "ready",
};

export default function DeckGeneratingView({
  stages = [],
  jobStage = "understanding_data",
  jobProgress = 0,
  jobStageLabel = "",
  jobError = null,
  slideProgressData = null,
  manifestLocked = false,
  manifestSlides = [],
  onGoBackToConfig,
  onCancelGeneration,
  onResetAndStartGeneration,
  onOpenInStudio,
  onExportPptx,
  onExportHtml,
}) {
  const isFailed = Boolean(jobError) || jobStage === "failed";
  const isReady = !isFailed && jobStage === "ready";
  const progress = isReady ? 100 : Math.max(0, Math.min(99, Number(jobProgress) || 0));
  const currentStageId = STAGE_ALIASES[jobStage] || jobStage;
  let index = stages.findIndex((s) => s.id === currentStageId);
  if (index === -1) {
    index = Math.min(stages.length - 1, Math.max(0, Math.floor((jobProgress / 100) * stages.length)));
  }
  const currentStage = stages[index] || stages[0];
  const stageDetail = jobStageLabel.replace(/^Phase\s+\d+:\s*/i, "");

  const displaySlides = manifestSlides.length > 0
    ? manifestSlides
    : (slideProgressData?.slide_status_list?.length > 0
      ? slideProgressData.slide_status_list
      : (slideProgressData?.total_slides > 0
        ? Array.from({ length: slideProgressData.total_slides }, (_, i) => ({
            order: i + 1,
            title: `Slide ${i + 1}`,
            status: (i + 1 < slideProgressData.current_slide) ? "READY" : (i + 1 === slideProgressData.current_slide) ? "RENDERING" : "PREPARING"
          }))
        : []));

  return (
    <div className="pres-generating-body" aria-busy={!isFailed && !isReady}>
      {/* Terminal outcomes only; active progress belongs to the phase list. */}
      {(isFailed || isReady) && (
        <div className="generating-header-card" role="status" aria-live="polite">
        <div className="pipeline-spinner-badge" aria-hidden="true">
          {isFailed ? (
            <AlertTriangle size={26} />
          ) : isReady ? (
            <CheckCircle2 size={26} />
          ) : (
            <RotateCw size={26} className="spin-icon" />
          )}
        </div>

        <p className="generating-subtitle">
          {isFailed
            ? "HighView · Generation Stopped"
            : isReady
            ? "HighView · Presentation Ready"
            : "HighView · Presentation Studio"}
        </p>

        <h4 className="generating-phase-title">
          {isFailed
            ? "Generation failed"
            : isReady
            ? "Presentation Certified & Ready"
            : `${currentStage?.label || "Preparing slides"}`}
        </h4>

        <p className="generating-detail-label">
          {isFailed
            ? "Your presentation wasn’t completed. Review the issue below, then return to setup or try again."
            : isReady
            ? "All slide checks, deterministic validation, and visual reviews are complete."
            : (stageDetail || currentStage?.desc || "Synthesizing executive presentation...")}
        </p>

        {/* Progress track */}
        {!isFailed && (
          <>
            <div
              className="pipeline-progress-track"
              role="progressbar"
              aria-valuenow={progress}
              aria-valuemin={0}
              aria-valuemax={100}
              aria-label="Presentation generation progress"
            >
              <div
                className="pipeline-progress-bar"
                style={{ width: `${progress}%` }}
              />
            </div>
            <span className="pipeline-progress-pct">{progress}% Complete</span>
          </>
        )}

        {isReady && onOpenInStudio && (
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
      )}

      {/* Manifest-Locked Stable Slides Rail */}
      {(manifestLocked || displaySlides.length > 0) && (
        <div
          className="manifest-locked-slides-section"
          role="region"
          aria-label="Locked slide sequence"
          style={{
            margin: "20px auto 28px",
            maxWidth: "880px",
            background: "var(--color-bg-surface)",
            border: "1px solid var(--color-border-subtle)",
            borderRadius: "12px",
            padding: "16px 20px",
            boxShadow: "var(--shadow-sm)"
          }}
        >
          <div
            style={{
              display: "flex",
              alignItems: "center",
              justifyContent: "space-between",
              marginBottom: "12px",
              paddingBottom: "8px",
              borderBottom: "1px solid var(--color-border-subtle)"
            }}
          >
            <div style={{ display: "flex", alignItems: "center", gap: "8px" }}>
              <Lock size={14} style={{ color: "var(--color-brand-secondary)" }} />
              <span style={{ fontSize: "12px", fontWeight: "700", textTransform: "uppercase", letterSpacing: "0.05em", color: "var(--color-brand-secondary)" }}>
                Slide Structure Locked
              </span>
            </div>
            <span style={{ fontSize: "12px", color: "var(--color-text-secondary)" }}>
              {displaySlides.length} physical slide slots allocated
            </span>
          </div>

          <div
            style={{
              display: "grid",
              gridTemplateColumns: "repeat(auto-fill, minmax(180px, 1fr))",
              gap: "10px"
            }}
          >
            {displaySlides.map((s, sIdx) => {
              const slideId = s.physical_slide_id || s.id || `SLD-${sIdx + 1}`;
              const st = s.status || (isReady ? "READY" : "PREPARING");
              const isDone = st === "READY";
              const isWorking = st === "RENDERING" || st === "VALIDATING" || st === "VISUALLY_REVIEWING" || st === "REPAIRING";
              return (
                <div
                  key={slideId}
                  style={{
                    border: isDone
                      ? "1px solid var(--color-brand-secondary)"
                      : isWorking
                      ? "1px solid var(--color-brand-accent, #3b82f6)"
                      : "1px dashed var(--color-border-strong)",
                    borderRadius: "8px",
                    padding: "10px",
                    background: isDone ? "var(--color-bg-soft-teal, rgba(16, 185, 129, 0.05))" : "var(--color-bg-base)",
                    display: "flex",
                    flexDirection: "column",
                    gap: "6px"
                  }}
                >
                  <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
                    <span style={{ fontSize: "11px", fontWeight: "600", color: "var(--color-text-secondary)" }}>
                      Slide {s.slide_order || s.order || sIdx + 1}
                    </span>
                    <span
                      style={{
                        fontSize: "9px",
                        fontWeight: "700",
                        padding: "2px 6px",
                        borderRadius: "4px",
                        textTransform: "uppercase",
                        letterSpacing: "0.04em",
                        background: isDone
                          ? "rgba(16, 185, 129, 0.15)"
                          : isWorking
                          ? "rgba(59, 130, 246, 0.15)"
                          : "var(--color-bg-hover)",
                        color: isDone
                          ? "var(--color-brand-secondary)"
                          : isWorking
                          ? "var(--color-brand-accent, #3b82f6)"
                          : "var(--color-text-secondary)"
                      }}
                    >
                      {st}
                    </span>
                  </div>
                  <div
                    style={{
                      fontSize: "12px",
                      fontWeight: "600",
                      color: "var(--color-text-primary)",
                      whiteSpace: "nowrap",
                      overflow: "hidden",
                      textOverflow: "ellipsis"
                    }}
                    title={s.title}
                  >
                    {s.title || `Slide ${sIdx + 1}`}
                  </div>
                  <div style={{ fontSize: "10px", color: "var(--color-text-secondary)", textTransform: "capitalize" }}>
                    {s.visual_type?.replace(/_/g, " ") || s.category?.replace(/_/g, " ") || (s.layout === "chart_narrative" ? "Analysis" : s.layout?.replace(/_/g, " ")) || "Analysis"}
                  </div>
                </div>
              );
            })}
          </div>
        </div>
      )}

      {/* Sequential generation phases */}
      {!isFailed && (
        <div className="pipeline-stages-list" role="list" aria-label="Presentation generation phases">
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
                    {isCurrent && stageDetail ? stageDetail : (st.desc || st.label)}
                  </span>
                </div>

                {isCurrent && !isReady && (
                  <span className="stage-active-pulse" role="status" aria-live="polite">
                    Running · {progress}%
                  </span>
                )}
              </div>
            );
          })}
        </div>
      )}

      {/* Error Callout */}
      {isFailed && (
        <div className="pres-error-callout" role="alert" aria-live="assertive">
          <AlertTriangle size={20} />
          <div className="error-callout-content">
            <strong>Presentation could not be completed</strong>
            <p>{jobError || jobStageLabel || "Generation failed. Please try again."}</p>
          </div>
        </div>
      )}

      {/* Action Row - Navigation locked while generating */}
      <div className="generating-actions-row">
        <button
          type="button"
          className="btn-secondary"
          disabled={!isFailed}
          onClick={() => onGoBackToConfig()}
          title={!isFailed ? "Navigation locked while presentation is generating" : "Return to configuration setup"}
          aria-disabled={!isFailed}
        >
          Back to setup
        </button>

        {isFailed ? (
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
