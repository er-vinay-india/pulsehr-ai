import React, { useEffect, useState } from "react";
import { UploadCloud, FileSpreadsheet } from "lucide-react";
import { uploadDatasetFile, listDatasets, deleteDataset } from "../api/client";
import UploadProgressCard from "../components/ingestion/UploadProgressCard";
import UploadResultCard from "../components/ingestion/UploadResultCard";
import DatasetListCard from "../components/ingestion/DatasetListCard";
import DeleteConsentModal from "../components/ingestion/DeleteConsentModal";

export default function IngestionPage() {
  const [datasets, setDatasets] = useState([]);
  const [uploading, setUploading] = useState(false);
  const [uploadingFile, setUploadingFile] = useState(null);
  const [uploadElapsed, setUploadElapsed] = useState(0);
  const [uploadStep, setUploadStep] = useState(1);
  const [isDragging, setIsDragging] = useState(false);
  const [uploadResult, setUploadResult] = useState(null);
  const [error, setError] = useState(null);

  // Consent modal state
  const [datasetToDelete, setDatasetToDelete] = useState(null);
  const [deleteConsent, setDeleteConsent] = useState(false);
  const [deleting, setDeleting] = useState(false);

  const loadData = () => {
    listDatasets()
      .then(res => setDatasets(res.datasets || []))
      .catch(err => console.error(err));
  };

  useEffect(() => {
    loadData();
  }, []);

  // Timer and progress steps for large file uploads
  useEffect(() => {
    let timer;
    if (uploading) {
      setUploadElapsed(0);
      setUploadStep(1);
      timer = setInterval(() => {
        setUploadElapsed(prev => {
          const next = prev + 1;
          if (next >= 22) setUploadStep(6);
          else if (next >= 16) setUploadStep(5);
          else if (next >= 11) setUploadStep(4);
          else if (next >= 6) setUploadStep(3);
          else if (next >= 2) setUploadStep(2);
          return next;
        });
      }, 1000);
    }
    return () => {
      if (timer) clearInterval(timer);
    };
  }, [uploading]);

  useEffect(() => {
    const handleKeyDown = (e) => {
      if (e.key === "Escape" && datasetToDelete && !deleting) {
        setDatasetToDelete(null);
        setDeleteConsent(false);
      }
    };
    window.addEventListener("keydown", handleKeyDown);
    return () => window.removeEventListener("keydown", handleKeyDown);
  }, [datasetToDelete, deleting]);

  const formatFileSize = (bytes) => {
    if (!bytes && bytes !== 0) return "";
    if (bytes < 1024) return `${bytes} B`;
    if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
    return `${(bytes / (1024 * 1024)).toFixed(2)} MB`;
  };

  const processFile = async (file) => {
    if (!file || uploading) return;

    setUploading(true);
    setUploadingFile({ name: file.name, size: formatFileSize(file.size) });
    setError(null);
    setUploadResult(null);

    try {
      const res = await uploadDatasetFile(file);
      setUploadStep(5);
      setUploadResult(res);
      loadData();
    } catch (err) {
      setError(err.message);
    } finally {
      setUploading(false);
      setUploadingFile(null);
    }
  };

  const handleFileInputChange = (e) => {
    const file = e.target.files?.[0];
    if (file) {
      processFile(file);
    }
    e.target.value = "";
  };

  const handleDragOver = (e) => {
    e.preventDefault();
    e.stopPropagation();
    if (!uploading) {
      setIsDragging(true);
    }
  };

  const handleDragLeave = (e) => {
    e.preventDefault();
    e.stopPropagation();
    setIsDragging(false);
  };

  const handleDrop = (e) => {
    e.preventDefault();
    e.stopPropagation();
    setIsDragging(false);
    if (uploading) return;
    const file = e.dataTransfer.files?.[0];
    if (file) {
      processFile(file);
    }
  };

  const promptDelete = (dataset) => {
    setDatasetToDelete(dataset);
    setDeleteConsent(false);
  };

  const handleConfirmDelete = async () => {
    if (!datasetToDelete || !deleteConsent || deleting) return;
    setDeleting(true);
    try {
      await deleteDataset(datasetToDelete.id);
      setDatasetToDelete(null);
      setDeleteConsent(false);
      loadData();
    } catch (err) {
      alert("Failed to delete dataset: " + err.message);
    } finally {
      setDeleting(false);
    }
  };

  return (
    <div className="ingestion-page">
      {/* Header Banner */}
      <div className="ingestion-hero">
        <div className="hero-content">
          <div className="banner-tag">
            <UploadCloud size={15} />
            <span>Your data workspace</span>
          </div>
          <h2>Upload your sheets</h2>
          <p>
            Add a CSV or Excel workbook. Analyse every sheet, discover shared keys, and connect related records in one workspace.
          </p>
        </div>
      </div>

      {/* Upload Drop Zone / Progress Container */}
      <div
        className={`upload-dropzone ${uploading ? "is-disabled" : ""} ${isDragging ? "is-dragging" : ""}`}
        onDragOver={handleDragOver}
        onDragLeave={handleDragLeave}
        onDrop={handleDrop}
      >
        <input
          type="file"
          id="file-upload-input"
          accept=".xlsx, .xls, .csv"
          onChange={handleFileInputChange}
          disabled={uploading}
        />

        {uploading ? (
          <UploadProgressCard
            uploadingFile={uploadingFile}
            uploadElapsed={uploadElapsed}
            uploadStep={uploadStep}
          />
        ) : (
          <label htmlFor="file-upload-input" className="dropzone-label">
            <div className="dropzone-icon">
              <FileSpreadsheet size={36} color="var(--brand-500)" />
            </div>
            <h3>{isDragging ? "Release File to Upload" : "Add a spreadsheet"}</h3>
            <p className="dropzone-hint">
              Supports .xlsx, .xls, and .csv formats · All sheets and rows retained · 20 MB, 20,000 rows, 200 columns per file
            </p>
            <div className="btn-primary" style={{ marginTop: "1rem" }}>
              <UploadCloud size={16} />
              <span>Browse Files</span>
            </div>
          </label>
        )}
      </div>

      {/* Success / Error Message */}
      <UploadResultCard uploadResult={uploadResult} />

      {error && (
        <div className="alert-box alert-error">
          <div>
            <strong>Upload Error:</strong>
            <p style={{ marginTop: "4px" }}>{error}</p>
          </div>
        </div>
      )}

      {/* Uploaded Datasets Registry */}
      <div className="card-panel" style={{ marginTop: "2rem" }}>
        <div className="panel-header">
          <div>
            <h3>Your datasets</h3>
            <p className="panel-sub">Uploaded files, ready to explore and ask questions about</p>
          </div>
        </div>

        <div className="dataset-list">
          {datasets.map(ds => (
            <DatasetListCard
              key={ds.id}
              dataset={ds}
              onPromptDelete={promptDelete}
            />
          ))}
        </div>
      </div>

      {/* Consent Check Modal */}
      <DeleteConsentModal
        datasetToDelete={datasetToDelete}
        deleteConsent={deleteConsent}
        setDeleteConsent={setDeleteConsent}
        deleting={deleting}
        onClose={() => setDatasetToDelete(null)}
        onConfirmDelete={handleConfirmDelete}
      />
    </div>
  );
}
