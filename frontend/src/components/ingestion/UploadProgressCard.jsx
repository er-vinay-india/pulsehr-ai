import React from "react";
import { FileSpreadsheet, CheckCircle2, Loader2, Clock, ShieldCheck } from "lucide-react";

export default function UploadProgressCard({ uploadingFile, uploadElapsed, uploadStep }) {
  return (
    <div className="ingestion-progress-card">
      <div className="progress-card-header">
        <div className="progress-spinner-wrap">
          <Loader2 size={32} className="spin-animation" color="var(--brand-400)" />
        </div>
        <div className="progress-title-block">
          <h3>Ingesting & Vectorizing Spreadsheet</h3>
          <p className="progress-file-info">
            <FileSpreadsheet size={16} color="var(--accent-500)" />
            <strong>{uploadingFile?.name || "Processing spreadsheet"}</strong>
            {uploadingFile?.size && <span className="file-size-badge">{uploadingFile.size}</span>}
          </p>
        </div>
        <div className="progress-timer-badge">
          <Clock size={14} />
          <span>{uploadElapsed}s elapsed</span>
        </div>
      </div>

      {/* Visual Animated Progress Bar */}
      <div className="progress-bar-container">
        <div className="progress-bar-fill animated-gradient-bar" />
      </div>

      {/* Pipeline Stage Checklist */}
      <div className="pipeline-steps-list">
        {[
          {
            step: 1,
            title: "1. Raw Ingestion & Schema Extraction",
            sub: "Validating file format (.csv, .xlsx, .xls), byte boundaries, and capturing raw immutable records",
          },
          {
            step: 2,
            title: "2. AI Sheet Naming & Semantic Structural Profiling",
            sub: "Decontaminating filenames, removing noise/hashes, classifying business domain, and inferring column roles",
          },
          {
            step: 3,
            title: "3. Data Cleansing & Syntactic Sanitization",
            sub: "Normalizing whitespace, stripping invisible control characters, and standardizing sentinel nulls (NaN, N/A, -)",
          },
          {
            step: 4,
            title: "4. Metric & Unit Normalization",
            sub: "Parsing money ($/€/£), temperatures (°C/°F), areas (sqft/m²), percentages (%), and time intervals",
          },
          {
            step: 5,
            title: "5. Missing Value Diagnostics & Smart Imputation",
            sub: "Computing distribution-aware targets (median for skewed metrics, mode for categories) while preserving raw flags",
          },
          {
            step: 6,
            title: "6. Statistical Exploratory Data Analysis (EDA) & Outlier Profiling",
            sub: "Running Tukey IQR fences & Z-score diagnostics, generating column profiles, and computing 0–100 Data Health Score",
          },
          {
            step: 7,
            title: "7. Multi-Sheet Key Discovery & Cross-Correlation Matrix (N-Sheet EDA)",
            sub: "Discovering entity linkages across sheets, synthesizing derived tables, and mining empirical Pearson/Spearman matrix",
          },
          {
            step: 8,
            title: "8. Semantic Vectorization & BM25 Hybrid Retrieval Indexing",
            sub: "Batching normalized tokens through local embedding model and building inverted index for hybrid RAG search",
          },
          {
            step: 9,
            title: "9. Analytical Evidence Catalog & Dashboard Readiness",
            sub: "Materializing Post-EDA curated views, linking cross-sheet intelligence, and routing into projection pipelines",
          },
        ].map(({ step, title, sub }) => {
          const isCompleted = uploadStep > step;
          const isActive = uploadStep === step;
          const statusClass = isCompleted ? "completed" : isActive ? "active" : "pending";

          return (
            <div key={step} className={`pipeline-step ${statusClass}`}>
              <div className="step-icon">
                {isCompleted ? (
                  <CheckCircle2 size={16} color="var(--emerald-tier)" />
                ) : isActive ? (
                  <Loader2 size={16} className="spin-animation" color="var(--brand-400)" />
                ) : (
                  <div className="step-bullet" />
                )}
              </div>
              <div className="step-text">
                <span className="step-title">{title}</span>
                <span className="step-sub">{sub}</span>
              </div>
            </div>
          );
        })}
      </div>

      <div className="progress-safety-footer">
        <ShieldCheck size={16} color="var(--accent-500)" style={{ flexShrink: 0 }} />
        <span>Large spreadsheets with thousands of rows take 15–40s for full vector embedding. Duplicate uploads are blocked while this job runs.</span>
      </div>
    </div>
  );
}
