import React, { useEffect, useState } from "react";
import { UploadCloud, FileSpreadsheet, CheckCircle2, RefreshCw, Database, Layers, ArrowUpRight, Link2, Trash2 } from "lucide-react";
import { uploadDatasetFile, listDatasets, deleteDataset } from "../api/client";

export default function IngestionPage() {
  const [datasets, setDatasets] = useState([]);
  const [uploading, setUploading] = useState(false);
  const [uploadResult, setUploadResult] = useState(null);
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

  const handleDelete = async (datasetId, filename) => {
    if (!window.confirm(`Delete '${filename}' and remove its rows, metrics, search entries and relationships?`)) return;
    try {
      await deleteDataset(datasetId);
      loadData();
    } catch (err) {
      alert("Failed to delete dataset: " + err.message);
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
            Upload any workforce spreadsheet or roster. PulseHR AI automatically extracts sheets, sanitizes missing cells, infers column schemas, preserves every row, discovers shared keys across files, and updates your overview.
          </p>
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
          <h3>{uploading ? "Parsing, Sanitizing & Vectorizing Spreadsheet..." : "Drop Excel or CSV File Here"}</h3>
          <p className="dropzone-hint">
            Supports .xlsx, .xls, and .csv formats · All sheets and rows retained · 20 MB, 20,000 rows, 200 columns per file
          </p>
          <div className="btn-primary" style={{ marginTop: "1rem" }}>
            <UploadCloud size={16} />
            <span>Browse Files</span>
          </div>
        </label>
      </div>

      {/* Success / Error Message */}
      {uploadResult && (
        <div className="alert-box alert-success" style={{ flexDirection: "column" }}>
          <div style={{ display: "flex", gap: "0.85rem", alignItems: "flex-start" }}>
            <CheckCircle2 size={24} color="var(--emerald-tier)" style={{ flexShrink: 0, marginTop: "2px" }} />
            <div>
              <strong style={{ fontSize: "1.05rem" }}>Upload & Analysis Complete!</strong>
              <p style={{ marginTop: "4px" }}>{uploadResult.message}</p>
              <div className="upload-meta-pills" style={{ marginTop: "8px" }}>
                <span><strong>File:</strong> {uploadResult.filename}</span>
                <span><strong>Sheets:</strong> {uploadResult.sheets.join(", ")}</span>
                <span><strong>Total Rows:</strong> {uploadResult.total_rows}</span>
                <span><strong>Searchable rows:</strong> {uploadResult.indexed_chunks}</span>
                {uploadResult.linked_employees > 0 && (
                  <span style={{ color: "var(--accent-500)", borderColor: "rgba(126,231,217,0.3)" }}>
                    <Link2 size={13} style={{ display: "inline", verticalAlign: "middle", marginRight: "4px" }} />
                    <strong>Linked:</strong> {uploadResult.linked_employees} Employees
                  </span>
                )}
              </div>
            </div>
          </div>

          {/* Sample Preview Table */}
          {uploadResult.sample_preview && uploadResult.sample_preview.length > 0 && (
            <div style={{ marginTop: "1.25rem", width: "100%" }}>
              <div style={{ fontSize: "0.8rem", fontWeight: 700, color: "var(--brand-400)", marginBottom: "6px" }}>
                PARSED DATA PREVIEW (FIRST {uploadResult.sample_preview.length} ROWS)
              </div>
              <div style={{ overflowX: "auto", background: "rgba(0,0,0,0.3)", borderRadius: "8px", border: "1px solid var(--border-subtle)" }}>
                <table style={{ width: "100%", borderCollapse: "collapse", fontSize: "0.8rem" }}>
                  <thead>
                    <tr style={{ background: "#15110f", borderBottom: "1px solid var(--border)" }}>
                      {uploadResult.columns.map((col, idx) => (
                        <th key={idx} style={{ padding: "8px 12px", textAlign: "left", color: "var(--brand-400)", fontWeight: 700 }}>
                          {col}
                        </th>
                      ))}
                    </tr>
                  </thead>
                  <tbody>
                    {uploadResult.sample_preview.map((row, rIdx) => (
                      <tr key={rIdx} style={{ borderBottom: "1px solid var(--border-subtle)" }}>
                        {uploadResult.columns.map((col, cIdx) => (
                          <td key={cIdx} style={{ padding: "8px 12px", color: "var(--fg-primary)" }}>
                            {String(row[col] !== undefined && row[col] !== null ? row[col] : "—")}
                          </td>
                        ))}
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </div>
          )}
        </div>
      )}

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

              {(
                <button
                  type="button"
                  onClick={() => handleDelete(ds.id, ds.original_name)}
                  style={{
                    color: "var(--fg-secondary)",
                    background: "rgba(255, 180, 190, 0.08)",
                    border: "1px solid rgba(255, 180, 190, 0.2)",
                    borderRadius: "6px",
                    padding: "0.45rem",
                    cursor: "pointer",
                    transition: "all 0.15s ease"
                  }}
                  title={`Delete ${ds.original_name}`}
                >
                  <Trash2 size={16} color="var(--rose-tier)" />
                </button>
              )}
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}
