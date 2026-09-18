import React, { useEffect, useState } from "react";
import { UploadCloud, FileSpreadsheet, CheckCircle2, RefreshCw, Database, Layers, ArrowUpRight } from "lucide-react";
import { uploadDatasetFile, listDatasets, reseedKaggle } from "../api/client";

export default function IngestionPage() {
  const [datasets, setDatasets] = useState([]);
  const [uploading, setUploading] = useState(false);
  const [uploadResult, setUploadResult] = useState(null);
  const [reseedLoading, setReseedLoading] = useState(false);
  const [error, setError] = useState(null);

  const loadData = () => {
    listDatasets()
      .then(res => setDatasets(res.datasets || []))
      .catch(err => console.error(err));
  };

  useEffect(() => {
    loadData();
  }, []);

  const handleFileUpload = async (e) => {
    const file = e.target.files?.[0];
    if (!file) return;

    setUploading(true);
    setError(null);
    setUploadResult(null);

    try {
      const res = await uploadDatasetFile(file);
      setUploadResult(res);
      loadData();
    } catch (err) {
      setError(err.message);
    } finally {
      setUploading(false);
      e.target.value = "";
    }
  };

  const handleReseed = async () => {
    if (!window.confirm("Re-sync Kaggle attendance & ratings dataset? This will refresh all 100 employee records and alerts.")) return;
    setReseedLoading(true);
    try {
      await reseedKaggle();
      alert("Kaggle dataset re-seeded successfully!");
      loadData();
    } catch (err) {
      alert("Failed to re-seed: " + err.message);
    } finally {
      setReseedLoading(false);
    }
  };

  return (
    <div className="ingestion-page">
      {/* Header Banner */}
      <div className="ingestion-hero">
        <div className="hero-content">
          <div className="banner-tag">
            <UploadCloud size={15} />
            <span>Universal Tabular RAG Ingestion Pipeline</span>
          </div>
          <h2>Excel & CSV Tabular Ingestion Studio</h2>
          <p>
            Upload any workforce spreadsheet or roster. PulseHR AI automatically extracts sheets, infers column schemas, generates semantic row descriptions, and indexes vectors into SQLite with zero manual mapping.
          </p>
        </div>
        <div className="hero-cta-group">
          <button
            type="button"
            className="btn-secondary"
            onClick={handleReseed}
            disabled={reseedLoading}
          >
            <RefreshCw size={15} className={reseedLoading ? "spin" : ""} />
            <span>{reseedLoading ? "Re-syncing..." : "Re-sync Kaggle Demo"}</span>
          </button>
        </div>
      </div>

      {/* Upload Drop Zone */}
      <div className="upload-dropzone">
        <input
          type="file"
          id="file-upload-input"
          accept=".xlsx, .xls, .csv"
          onChange={handleFileUpload}
          disabled={uploading}
        />
        <label htmlFor="file-upload-input" className="dropzone-label">
          <div className="dropzone-icon">
            <FileSpreadsheet size={36} color="var(--brand-500)" />
          </div>
          <h3>{uploading ? "Parsing & Vectorizing Spreadsheet..." : "Drop Excel or CSV File Here"}</h3>
          <p className="dropzone-hint">
            Supports .xlsx, .xls, and .csv formats · Auto-chunks and embeds rows for AI inference
          </p>
          <div className="btn-primary" style={{ marginTop: "1rem" }}>
            <UploadCloud size={16} />
            <span>Browse Files</span>
          </div>
        </label>
      </div>

      {/* Success / Error Message */}
      {uploadResult && (
        <div className="alert-box alert-success">
          <CheckCircle2 size={20} />
          <div>
            <strong>Upload & Vectorization Complete!</strong>
            <p>{uploadResult.message}</p>
            <div className="upload-meta-pills">
              <span><strong>File:</strong> {uploadResult.filename}</span>
              <span><strong>Sheets:</strong> {uploadResult.sheets.join(", ")}</span>
              <span><strong>Total Rows:</strong> {uploadResult.total_rows}</span>
              <span><strong>Vector Chunks:</strong> {uploadResult.indexed_chunks}</span>
            </div>
          </div>
        </div>
      )}

      {error && (
        <div className="alert-box alert-error">
          <strong>Upload Error:</strong> {error}
        </div>
      )}

      {/* Uploaded Datasets Registry */}
      <div className="card-panel" style={{ marginTop: "2rem" }}>
        <div className="panel-header">
          <div>
            <h3>Active Ingested Datasets</h3>
            <p className="panel-sub">Spreadsheets indexed in SQLite and available for vector RAG querying</p>
          </div>
        </div>

        <div className="dataset-list">
          {datasets.map(ds => (
            <div key={ds.id} className="dataset-card">
              <div className="dataset-icon">
                <FileSpreadsheet size={24} color="var(--accent-500)" />
              </div>
              <div className="dataset-details">
                <div className="dataset-title-row">
                  <h4>{ds.original_name}</h4>
                  <span className="filetype-badge">{ds.file_type.toUpperCase()}</span>
                </div>
                <p className="dataset-summary">{ds.summary_insights}</p>
                <div className="dataset-stats">
                  <span><strong>{ds.row_count}</strong> Rows</span> · 
                  <span><strong>{ds.col_count}</strong> Columns</span> · 
                  <span><strong>{ds.sheet_count}</strong> Sheet(s)</span> · 
                  <span>Ingested {new Date(ds.uploaded_at).toLocaleDateString()}</span>
                </div>
              </div>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}
