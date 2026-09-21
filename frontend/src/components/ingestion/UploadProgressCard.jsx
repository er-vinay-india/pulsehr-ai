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
        <div className={`pipeline-step ${uploadStep >= 1 ? (uploadStep > 1 ? "completed" : "active") : "pending"}`}>
          <div className="step-icon">
            {uploadStep > 1 ? <CheckCircle2 size={16} color="var(--emerald-tier)" /> : (uploadStep === 1 ? <Loader2 size={16} className="spin-animation" color="var(--brand-400)" /> : <div className="step-bullet" />)}
          </div>
          <div className="step-text">
            <span className="step-title">1. Uploading file & inspecting spreadsheet structure</span>
            <span className="step-sub">Validating file format (.csv, .xlsx, .xls) and extracting raw tabular frames</span>
          </div>
        </div>

        <div className={`pipeline-step ${uploadStep >= 2 ? (uploadStep > 2 ? "completed" : "active") : "pending"}`}>
          <div className="step-icon">
            {uploadStep > 2 ? <CheckCircle2 size={16} color="var(--emerald-tier)" /> : (uploadStep === 2 ? <Loader2 size={16} className="spin-animation" color="var(--brand-400)" /> : <div className="step-bullet" />)}
          </div>
          <div className="step-text">
            <span className="step-title">2. AI Sheet Naming & Semantic Classification</span>
            <span className="step-sub">Cleansing filenames, filtering noise/hashes, analyzing column architecture, and synthesizing executive title</span>
          </div>
        </div>

        <div className={`pipeline-step ${uploadStep >= 3 ? (uploadStep > 3 ? "completed" : "active") : "pending"}`}>
          <div className="step-icon">
            {uploadStep > 3 ? <CheckCircle2 size={16} color="var(--emerald-tier)" /> : (uploadStep === 3 ? <Loader2 size={16} className="spin-animation" color="var(--brand-400)" /> : <div className="step-bullet" />)}
          </div>
          <div className="step-text">
            <span className="step-title">3. Extracting worksheets & normalizing rows</span>
            <span className="step-sub">Sanitizing empty cells, detecting data types, and retaining 100% of source records</span>
          </div>
        </div>

        <div className={`pipeline-step ${uploadStep >= 4 ? (uploadStep > 4 ? "completed" : "active") : "pending"}`}>
          <div className="step-icon">
            {uploadStep > 4 ? <CheckCircle2 size={16} color="var(--emerald-tier)" /> : (uploadStep === 4 ? <Loader2 size={16} className="spin-animation" color="var(--brand-400)" /> : <div className="step-bullet" />)}
          </div>
          <div className="step-text">
            <span className="step-title">4. Profiling columns & statistical summaries</span>
            <span className="step-sub">Computing min/max/mean metrics and detecting unique identifiers</span>
          </div>
        </div>

        <div className={`pipeline-step ${uploadStep >= 5 ? (uploadStep > 5 ? "completed" : "active") : "pending"}`}>
          <div className="step-icon">
            {uploadStep > 5 ? <CheckCircle2 size={16} color="var(--emerald-tier)" /> : (uploadStep === 5 ? <Loader2 size={16} className="spin-animation" color="var(--brand-400)" /> : <div className="step-bullet" />)}
          </div>
          <div className="step-text">
            <span className="step-title">5. Generating vector embeddings & BM25 search indices</span>
            <span className="step-sub">Batching rows through local embedding model for high-precision retrieval</span>
          </div>
        </div>

        <div className={`pipeline-step ${uploadStep >= 6 ? "active" : "pending"}`}>
          <div className="step-icon">
            {uploadStep >= 6 ? <Loader2 size={16} className="spin-animation" color="var(--brand-400)" /> : <div className="step-bullet" />}
          </div>
          <div className="step-text">
            <span className="step-title">6. Discovering cross-sheet key joins & updating catalog</span>
            <span className="step-sub">Connecting foreign keys and updating the real-time overview</span>
          </div>
        </div>
      </div>

      <div className="progress-safety-footer">
        <ShieldCheck size={16} color="var(--accent-500)" style={{ flexShrink: 0 }} />
        <span>Large spreadsheets with thousands of rows take 15–40s for full vector embedding. Duplicate uploads are blocked while this job runs.</span>
      </div>
    </div>
  );
}
