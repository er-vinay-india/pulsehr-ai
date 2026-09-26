import React, { useEffect, useState } from "react";
import {
  UploadCloud,
  FileSpreadsheet,
  Sparkles,
  X,
  ArrowRight,
  ArrowLeft,
  CheckCircle2,
  Table,
  LayoutDashboard,
  RotateCcw
} from "lucide-react";
import { uploadDatasetFile } from "../../api/client";
import UploadProgressCard from "./UploadProgressCard";
import UploadResultCard from "./UploadResultCard";

export default function UploadModal({ isOpen, onClose, onUploadSuccess }) {
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

  // Reset state when modal opens or closes
  useEffect(() => {
    if (!isOpen) {
      setStep(1);
      setSelectedFile(null);
      setUserIntent("");
      setUploading(false);
      setUploadingFile(null);
      setUploadElapsed(0);
      setUploadResult(null);
      setError(null);
    }
  }, [isOpen]);

  // Handle ESC key to dismiss if not currently uploading
  useEffect(() => {
    if (!isOpen) return;
    const handleKeyDown = (e) => {
      if (e.key === "Escape" && !uploading) {
        onClose();
      }
    };
    window.addEventListener("keydown", handleKeyDown);
    return () => window.removeEventListener("keydown", handleKeyDown);
  }, [isOpen, uploading, onClose]);

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

  if (!isOpen) return null;

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
    setUploadingFile({
      name: selectedFile.name,
      size: formatFileSize(selectedFile.size),
    });
    setError(null);
    setUploadResult(null);

    try {
      const res = await uploadDatasetFile(selectedFile, intentToUse);
      setUploadStep(9);
      setUploadResult(res);
      if (onUploadSuccess) {
        onUploadSuccess(res);
      }
    } catch (err) {
      setError(err.message || "Failed to process spreadsheet");
    } finally {
      setUploading(false);
      setUploadingFile(null);
    }
  };

  const handleReset = () => {
    setStep(1);
    setSelectedFile(null);
    setUserIntent("");
    setUploadResult(null);
    setError(null);
  };

  return (
    <div
      className="upload-modal-overlay"
      onClick={() => {
        if (!uploading) onClose();
      }}
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
          {!uploading && (
            <button
              type="button"
              className="upload-modal-close-btn"
              onClick={onClose}
              aria-label="Close upload modal"
            >
              <X size={20} />
            </button>
          )}
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
              {/* Selected File Summary Banner */}
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

              {/* Business Intent Question Prompt */}
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

              {/* Action Buttons */}
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

          {/* STEP 3: Progress & Ingestion Results */}
          {step === 3 && (
            <div className="upload-step-pane upload-step-progress">
              {uploading && (
                <UploadProgressCard
                  uploadingFile={uploadingFile}
                  uploadElapsed={uploadElapsed}
                  uploadStep={uploadStep}
                />
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

              {uploadResult && (
                <div className="upload-success-container">
                  <UploadResultCard uploadResult={uploadResult} />

                  <div className="upload-success-actions">
                    <button
                      type="button"
                      className="btn-primary"
                      onClick={() => {
                        onClose();
                        window.location.hash = "explorer";
                      }}
                    >
                      <Table size={15} />
                      <span>Explore in Data Explorer</span>
                    </button>

                    <button
                      type="button"
                      className="btn-secondary"
                      onClick={() => {
                        onClose();
                        window.location.hash = "adaptive";
                      }}
                    >
                      <LayoutDashboard size={15} />
                      <span>View Executive Dashboard</span>
                    </button>

                    <button
                      type="button"
                      className="btn-secondary"
                      onClick={handleReset}
                    >
                      <UploadCloud size={15} />
                      <span>Upload Another</span>
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
