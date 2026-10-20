import React from "react";
import { FileSpreadsheet, CheckCircle2, Loader2, Clock, ShieldCheck, AlertCircle } from "lucide-react";

export const INGESTION_STAGES = [
  {
    step: 1,
    title: "1. Raw Ingestion & Source Preservation",
    sub: "Validating file format (.csv, .xlsx, .xls), byte boundaries, and capturing raw immutable records without loss",
  },
  {
    step: 2,
    title: "2. Structure & Data Quality Profiling",
    sub: "Decontaminating sheet names, detecting structure, checking nulls/uniqueness, and assessing data quality",
  },
  {
    step: 3,
    title: "3. Semantic Column Understanding",
    sub: "Inferring semantic data types, business roles, formats, units, and currencies while preserving raw values",
  },
  {
    step: 4,
    title: "4. Entity & Grain Discovery",
    sub: "Identifying table business entities, observations, grain definitions, and row-level semantics",
  },
  {
    step: 5,
    title: "5. Key Intelligence",
    sub: "Discovering candidate primary keys, surrogate identifiers, natural keys, and uniqueness integrity",
  },
  {
    step: 6,
    title: "6. Controlled Enrichment & Reference Resolution",
    sub: "Resolving reference concepts, taxonomic groupings, derived feature definitions, and controlled lookups",
  },
  {
    step: 7,
    title: "7. Relationship Validation & Join Governance",
    sub: "Validating foreign keys, cross-sheet associations, cardinality (1:1, 1:N, N:M), and join safety",
  },
  {
    step: 8,
    title: "8. Analytical Modeling & Evidence",
    sub: "Synthesizing analytical perspectives, rollup aggregates, governed metrics, and fact ledgers",
  },
  {
    step: 9,
    title: "9. Search & Retrieval Preparation",
    sub: "Building lexical index and retrieval metadata for semantic discovery and contextual Q&A",
  },
  {
    step: 10,
    title: "10. Dataset Finalization & Intelligence Readiness",
    sub: "Finalizing governed dataset catalog, verifying invariants, and activating workspace intelligence",
  },
];

export default function UploadProgressCard({
  uploadingFile,
  uploadElapsed,
  uploadStep = 1,
  currentStageMessage = "",
  progressPercentage = 10,
  stepStatus = {}, // Optional per-step status override: 'complete' | 'in_progress' | 'needs_review' | 'blocked' | 'pending'
}) {
  // Deterministic stage-derived progress (Stage N of 10 = N * 10%)
  const effectivePct = Math.max(10, Math.min(100, Math.round(uploadStep * 10)));

  return (
    <div className="ingestion-progress-card">
      <div className="progress-card-header">
        <div className="progress-spinner-wrap">
          {uploadStep >= 10 && progressPercentage >= 100 ? (
            <CheckCircle2 size={32} color="#10b981" />
          ) : (
            <Loader2 size={32} className="spin-animation" color="var(--brand-400)" />
          )}
        </div>
        <div className="progress-title-block">
          <h3>Governed Dataset Ingestion & Profiling</h3>
          <p className="progress-file-info">
            <FileSpreadsheet size={16} color="var(--accent-500)" />
            <strong>{uploadingFile?.name || "Processing spreadsheet"}</strong>
            {uploadingFile?.size && <span className="file-size-badge">{uploadingFile.size}</span>}
          </p>
        </div>
        <div className="progress-timer-badge">
          <Clock size={14} />
          <span>{uploadElapsed}s elapsed · Stage {Math.min(uploadStep, 10)} of 10 ({effectivePct}%)</span>
        </div>
      </div>

      {/* Visual Animated Dynamic Progress Bar */}
      <div className="progress-bar-container">
        <div
          className="progress-bar-fill animated-gradient-bar"
          style={{ width: `${effectivePct}%`, transition: "width 0.4s ease-in-out" }}
        />
      </div>

      {/* Pipeline Stage Checklist */}
      <div className="pipeline-steps-list">
        {INGESTION_STAGES.map(({ step, title, sub }) => {
          const customStatus = stepStatus[step];
          const isCompleted = customStatus ? customStatus === "complete" : uploadStep > step;
          const isActive = customStatus ? customStatus === "in_progress" : uploadStep === step;
          const isReview = customStatus === "needs_review";
          const isBlocked = customStatus === "blocked";
          const statusClass = isBlocked
            ? "blocked"
            : isReview
            ? "needs_review"
            : isCompleted
            ? "completed"
            : isActive
            ? "active"
            : "pending";

          return (
            <div key={step} className={`pipeline-step ${statusClass}`}>
              <div className="step-icon">
                {isCompleted ? (
                  <CheckCircle2 size={16} color="var(--emerald-tier, #10b981)" />
                ) : isReview ? (
                  <AlertCircle size={16} color="#f59e0b" />
                ) : isBlocked ? (
                  <AlertCircle size={16} color="#ef4444" />
                ) : isActive ? (
                  <Loader2 size={16} className="spin-animation" color="var(--brand-400, #2563eb)" />
                ) : (
                  <div className="step-bullet" />
                )}
              </div>
              <div className="step-text">
                <span className="step-title">{title}</span>
                <span className="step-sub">
                  {isActive && currentStageMessage ? currentStageMessage : sub}
                </span>
              </div>
            </div>
          );
        })}
      </div>

      <div className="progress-safety-footer">
        <ShieldCheck size={16} color="var(--accent-500)" style={{ flexShrink: 0 }} />
        <span>Non-blocking background ingestion with live stage telemetry. You can minimize this modal at any time without interrupting execution.</span>
      </div>
    </div>
  );
}
