import React, { useEffect, useState, useRef } from "react";
import {
  UploadCloud,
  FileSpreadsheet,
  Sparkles,
  X,
  ArrowRight,
  ArrowLeft,
  CheckCircle2,
  Table,
  RotateCcw,
  Minimize2
} from "lucide-react";
import { uploadDatasetFile } from "../../api/client";
import UploadProgressCard from "./UploadProgressCard";

export default function UploadModal({
  isOpen,
  onClose,
  onUploadSuccess,
  onUploadStart,
  onUploadEnd
}) {
  const [step, setStep] = useState(1); // 1: Select file, 2: Expectation intent, 3: Ingestion & results
  const [selectedFile, setSelectedFile] = useState(null);
  const [userIntent, setUserIntent] = useState("");
  const [uploading, setUploading] = useState(false);
  const [uploadingFile, setUploadingFile] = useState(null);
  const [uploadElapsed, setUploadElapsed] = useState(0);
  const [uploadStep, setUploadStep] = useState(1);
  const [isDragging, setIsDragging] = useState(false);
  const [uploadResult, setUploadResult] = useState(null);
  const [error, setError] = useState(null);

  // Track if upload was minimized to background
  const isBackgroundRef = useRef(false);

  // Reset state when modal is closed AND not uploading
  useEffect(() => {
    if (!isOpen && !uploading) {
      setStep(1);
      setSelectedFile(null);
      setUserIntent("");
      setUploadElapsed(0);
      setUploadResult(null);
      setError(null);
      isBackgroundRef.current = false;
    }
  }, [isOpen, uploading]);

  // Handle ESC key to dismiss (even while uploading, minimizes to background)
  useEffect(() => {
    if (!isOpen) return;
    const handleKeyDown = (e) => {
      if (e.key === "Escape") {
        handleDismiss();
      }
    };
    window.addEventListener("keydown", handleKeyDown);
    return () => window.removeEventListener("keydown", handleKeyDown);
  }, [isOpen, uploading]);

  // Upload timer & step progression
  useEffect(() => {
    let timer;
    if (uploading) {
      setUploadElapsed(0);
      setUploadStep(1);
      timer = setInterval(() => {
        setUploadElapsed((prev) => {
          const next = prev + 1;
          if (next >= 26) setUploadStep(9);
          else if (next >= 22) setUploadStep(8);
          else if (next >= 18) setUploadStep(7);
          else if (next >= 14) setUploadStep(6);
          else if (next >= 10) setUploadStep(5);
          else if (next >= 7) setUploadStep(4);
          else if (next >= 4) setUploadStep(3);
          else if (next >= 2) setUploadStep(2);
          return next;
        });
      }, 1000);
    }
    return () => {
      if (timer) clearInterval(timer);
    };
  }, [uploading]);

  const formatFileSize = (bytes) => {
    if (!bytes && bytes !== 0) return "";
    if (bytes < 1024) return `${bytes} B`;
    if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
    return `${(bytes / (1024 * 1024)).toFixed(2)} MB`;
  };

  const handleFileChosen = (file) => {
    if (!file) return;
    setSelectedFile(file);
    setError(null);
    setStep(2); // Automatically advance to Step 2: What do you expect from this sheet?
  };

  const handleDrop = (e) => {
    e.preventDefault();
    setIsDragging(false);
    if (e.dataTransfer.files && e.dataTransfer.files.length > 0) {
      handleFileChosen(e.dataTransfer.files[0]);
    }
  };

  const handleDragOver = (e) => {
    e.preventDefault();
    setIsDragging(true);
  };

  const handleDragLeave = (e) => {
    e.preventDefault();
    setIsDragging(false);
  };

  const handleFileInputChange = (e) => {
    if (e.target.files && e.target.files.length > 0) {
      handleFileChosen(e.target.files[0]);
    }
  };

  const executeUpload = async (intentToUse) => {
    if (!selectedFile || uploading) return;

    setStep(3);
    setUploading(true);
    const fileInfo = {
      name: selectedFile.name,
      size: formatFileSize(selectedFile.size)
    };
    setUploadingFile(fileInfo);
    setError(null);
    setUploadResult(null);

    if (onUploadStart) {
      onUploadStart(fileInfo);
    }

    try {
      const res = await uploadDatasetFile(selectedFile, intentToUse);
      setUploadStep(9);
      setUploadResult(res);

      if (onUploadSuccess) {
        onUploadSuccess(res, { wasBackground: isBackgroundRef.current });
      }
    } catch (err) {
      setError(err.message || "Failed to process spreadsheet");
    } finally {
      setUploading(false);
      setUploadingFile(null);
      if (onUploadEnd) {
        onUploadEnd();
      }
    }
  };

  const handleDismiss = () => {
    if (uploading) {
      isBackgroundRef.current = true;
    }
    onClose();
  };

  const handleReset = () => {
    setStep(1);
    setSelectedFile(null);
    setUserIntent("");
    setUploadResult(null);
    setError(null);
    isBackgroundRef.current = false;
  };

  // If closed and not uploading, do not render overlay
  if (!isOpen) return null;

  return (
    <div
      className="upload-modal-overlay"
      onClick={handleDismiss}
      role="dialog"
      aria-modal="true"
      aria-labelledby="upload-modal-title"
    >
      <div
        className="upload-modal-panel"
        onClick={(e) => e.stopPropagation()}
      >
        {/* Modal Header */}
        <div className="upload-modal-header">
          <div className="upload-modal-title-group">
            <div className="upload-modal-icon-badge">
              <UploadCloud size={20} />
            </div>
            <div>
              <h2 id="upload-modal-title">Upload Spreadsheet</h2>
              <div className="upload-modal-steps-indicator">
                <span className={`step-badge ${step >= 1 ? "active" : ""}`}>
                  1. Select File
                </span>
                <span className="step-arrow">&rarr;</span>
                <span className={`step-badge ${step >= 2 ? "active" : ""}`}>
                  2. Analysis Expectations
                </span>
                <span className="step-arrow">&rarr;</span>
                <span className={`step-badge ${step >= 3 ? "active" : ""}`}>
                  3. Ingest & Profile
                </span>
              </div>
            </div>
          </div>

          <button
            type="button"
            className="upload-modal-close-btn"
            onClick={handleDismiss}
            aria-label={uploading ? "Run in background" : "Close modal"}
            title={uploading ? "Minimize & run in background" : "Close"}
          >
            <X size={20} />
          </button>
        </div>

        {/* Modal Body */}
        <div className="upload-modal-body">
          {/* STEP 1: Select File Dropzone */}
          {step === 1 && (
            <div className="upload-step-pane">
              <div
                className={`upload-dropzone ${isDragging ? "is-dragging" : ""}`}
                onDragOver={handleDragOver}
                onDragLeave={handleDragLeave}
                onDrop={handleDrop}
              >
                <input
                  type="file"
                  id="modal-file-upload-input"
                  accept=".xlsx, .xls, .csv"
                  onChange={handleFileInputChange}
                />
                <label htmlFor="modal-file-upload-input" className="dropzone-label">
                  <div className="dropzone-icon">
                    <FileSpreadsheet size={42} color="var(--brand-500)" />
                  </div>
                  <h3>{isDragging ? "Release File to Upload" : "Choose a spreadsheet"}</h3>
                  <p className="dropzone-hint">
                    Supports <strong>.xlsx</strong>, <strong>.xls</strong>, and <strong>.csv</strong> workbooks
                    <br />
                    All sheets, tabs, and columns are automatically preserved
                  </p>
                  <div className="btn-primary" style={{ marginTop: "1rem" }}>
                    <UploadCloud size={16} />
                    <span>Browse Files</span>
                  </div>
                </label>
              </div>
            </div>
          )}

          {/* STEP 2: Expectations from the Sheet (Mandatory Step, Optional to Fill with Skip Option) */}
          {step === 2 && (
            <div className="upload-step-pane upload-step-expectations">
              <div className="selected-file-banner">
                <div className="selected-file-info">
                  <FileSpreadsheet size={18} color="var(--brand-400)" />
                  <div>
                    <strong>{selectedFile?.name}</strong>
                    <span className="file-size-sub">
                      {" "}· {formatFileSize(selectedFile?.size)}
                    </span>
                  </div>
                </div>
                <button
                  type="button"
                  className="btn-link-sm"
                  onClick={() => setStep(1)}
                  title="Choose another file"
                >
                  Change File
                </button>
              </div>

              <div className="expectations-prompt-card">
                <div className="expectations-header">
                  <div className="expectations-title-wrap">
                    <Sparkles size={18} color="var(--brand-400)" />
                    <h3>What do you expect from this sheet?</h3>
                  </div>
                  <span className="optional-tag">Optional</span>
                </div>
                <p className="expectations-description">
                  Specify what you want this analysis to answer, corporate targets, policy rules, or key questions.
                  PulseHR AI will prioritize your intent across autonomous findings.
                  If you prefer automatic exploratory discovery, simply choose <strong>Skip & Ingest</strong>.
                </p>

                <textarea
                  rows={4}
                  value={userIntent}
                  onChange={(e) => setUserIntent(e.target.value)}
                  placeholder="e.g. Employees must work from office at least 3 days per week. Compare department compliance, identify outlier teams, and audit attendance vs leave ledgers."
                  className="expectations-textarea"
                />

                {userIntent.trim() && (
                  <div className="intent-confirmed-badge">
                    <span>✓ PulseHR AI will prioritize this intent during analytical reasoning.</span>
                  </div>
                )}
              </div>

              <div className="upload-step-actions">
                <button
                  type="button"
                  className="btn-secondary"
                  onClick={() => setStep(1)}
                >
                  <ArrowLeft size={14} />
                  <span>Back</span>
                </button>

                <div className="action-right-group">
                  <button
                    type="button"
                    className="btn-ghost-skip"
                    onClick={() => executeUpload("")}
                    title="Skip custom expectations and use automatic discovery"
                  >
                    <span>Skip & Ingest</span>
                  </button>

                  <button
                    type="button"
                    className="btn-primary"
                    onClick={() => executeUpload(userIntent)}
                  >
                    <span>Submit & Ingest</span>
                    <ArrowRight size={14} />
                  </button>
                </div>
              </div>
            </div>
          )}

          {/* STEP 3: Progress & Pure Minimal Success Message */}
          {step === 3 && (
            <div className="upload-step-pane upload-step-progress">
              {uploading && (
                <div>
                  <UploadProgressCard
                    uploadingFile={uploadingFile}
                    uploadElapsed={uploadElapsed}
                    uploadStep={uploadStep}
                  />

                  {/* Option to run in background */}
                  <div style={{ marginTop: "1rem", textAlign: "center" }}>
                    <button
                      type="button"
                      className="btn-secondary"
                      onClick={handleDismiss}
                      style={{
                        display: "inline-flex",
                        alignItems: "center",
                        gap: "6px",
                        fontSize: "0.82rem",
                        padding: "0.45rem 1rem",
                        borderRadius: "8px"
                      }}
                      title="Continue work while spreadsheet processes in the background"
                    >
                      <Minimize2 size={14} />
                      <span>Run in Background</span>
                    </button>
                  </div>
                </div>
              )}

              {error && (
                <div className="alert-box alert-error">
                  <div>
                    <strong>Upload Error:</strong>
                    <p style={{ marginTop: "4px" }}>{error}</p>
                    <div style={{ marginTop: "12px" }}>
                      <button
                        type="button"
                        className="btn-secondary btn-sm"
                        onClick={handleReset}
                      >
                        <RotateCcw size={14} />
                        <span>Try Again</span>
                      </button>
                    </div>
                  </div>
                </div>
              )}

              {/* Minimal Success Card: Pure Confirmation without technical noise */}
              {uploadResult && (
                <div
                  className="upload-minimal-success"
                  style={{
                    display: "flex",
                    flexDirection: "column",
                    alignItems: "center",
                    textAlign: "center",
                    padding: "2.5rem 1.5rem",
                    background: "rgba(46, 213, 115, 0.04)",
                    border: "1px solid rgba(46, 213, 115, 0.25)",
                    borderRadius: "14px"
                  }}
                >
                  <div
                    style={{
                      width: "60px",
                      height: "60px",
                      borderRadius: "50%",
                      background: "rgba(46, 213, 115, 0.15)",
                      display: "flex",
                      alignItems: "center",
                      justifyContent: "center",
                      marginBottom: "1rem",
                      border: "1px solid rgba(46, 213, 115, 0.4)"
                    }}
                  >
                    <CheckCircle2 size={32} color="#2ed573" />
                  </div>

                  <h3 style={{ fontSize: "1.3rem", color: "#fff9f2", marginBottom: "0.4rem" }}>
                    Spreadsheet Ingested Successfully
                  </h3>

                  <p style={{ fontSize: "0.92rem", color: "var(--fg-secondary)", maxWidth: "420px", marginBottom: "0.25rem" }}>
                    <strong>{uploadResult.display_name || uploadResult.filename}</strong> is fully processed.
                  </p>

                  <p style={{ fontSize: "0.82rem", color: "var(--fg-muted)", maxWidth: "420px", marginBottom: "1.75rem" }}>
                    {uploadResult.sheets?.length || 1} sheet(s) · {uploadResult.total_rows || 0} rows indexed and normalized for exploratory analytics.
                  </p>

                  <div style={{ display: "flex", gap: "0.75rem", flexWrap: "wrap", justifyContent: "center" }}>
                    <button
                      type="button"
                      className="btn-primary"
                      onClick={() => {
                        onClose();
                        window.location.hash = "explorer";
                      }}
                      style={{ display: "inline-flex", alignItems: "center", gap: "8px", padding: "0.6rem 1.25rem" }}
                    >
                      <Table size={16} />
                      <span>Explore in Data Explorer</span>
                    </button>

                    <button
                      type="button"
                      className="btn-secondary"
                      onClick={onClose}
                      style={{ padding: "0.6rem 1.25rem" }}
                    >
                      <span>Done</span>
                    </button>
                  </div>
                </div>
              )}
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
