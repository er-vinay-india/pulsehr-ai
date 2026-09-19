import React, { useEffect, useState } from "react";
import { UploadCloud, FileSpreadsheet, CheckCircle2, RefreshCw, Database, Layers, ArrowUpRight, Link2, Trash2, Download, Table, AlertTriangle, X, ShieldAlert } from "lucide-react";
import { uploadDatasetFile, listDatasets, deleteDataset, getDatasetDownloadUrl, getSheetDownloadUrl } from "../api/client";

export default function IngestionPage() {
  const [datasets, setDatasets] = useState([]);
  const [uploading, setUploading] = useState(false);
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
              <div style={{ marginTop: "10px", display: "flex", gap: "0.5rem", flexWrap: "wrap" }}>
                <a
                  href={getDatasetDownloadUrl(uploadResult.dataset_id)}
                  download={uploadResult.filename}
                  className="btn-secondary"
                  style={{
                    display: "inline-flex",
                    alignItems: "center",
                    gap: "6px",
                    textDecoration: "none",
                    fontSize: "0.8rem",
                    padding: "0.35rem 0.75rem",
                    color: "var(--accent-500)",
                    borderColor: "rgba(126, 231, 217, 0.3)"
                  }}
                >
                  <Download size={14} />
                  <span>Download Ingested File</span>
                </a>
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

                {ds.sheets && ds.sheets.length > 0 && (
                  <div style={{ marginTop: "0.85rem" }}>
                    <div style={{ fontSize: "0.72rem", fontWeight: 700, color: "var(--fg-secondary)", textTransform: "uppercase", letterSpacing: "0.05em", marginBottom: "0.4rem" }}>
                      Uploaded {ds.sheets.length > 1 ? `Sheets (${ds.sheets.length})` : "Sheet"}:
                    </div>
                    <div style={{ display: "flex", flexWrap: "wrap", gap: "0.5rem" }}>
                      {ds.sheets.map(sheet => (
                        <div
                          key={sheet.id}
                          style={{
                            display: "inline-flex",
                            alignItems: "center",
                            gap: "8px",
                            background: "rgba(255, 255, 255, 0.04)",
                            border: "1px solid var(--border-subtle)",
                            borderRadius: "6px",
                            padding: "0.35rem 0.65rem",
                            fontSize: "0.8rem"
                          }}
                        >
                          <Layers size={13} color="var(--accent-500)" />
                          <span style={{ fontWeight: 600, color: "var(--fg-primary)" }}>{sheet.name}</span>
                          <span style={{ color: "var(--fg-secondary)", fontSize: "0.75rem" }}>({sheet.row_count} rows)</span>

                          {/* If workbook has multiple sheets, allow downloading individual sheet */}
                          {ds.sheets.length > 1 && (
                            <a
                              href={getSheetDownloadUrl(sheet.id, "csv")}
                              download={`${sheet.name}.csv`}
                              style={{
                                display: "inline-flex",
                                alignItems: "center",
                                gap: "4px",
                                marginLeft: "4px",
                                padding: "0.2rem 0.5rem",
                                borderRadius: "4px",
                                background: "rgba(126, 231, 217, 0.12)",
                                border: "1px solid rgba(126, 231, 217, 0.3)",
                                color: "var(--accent-500)",
                                textDecoration: "none",
                                fontSize: "0.725rem",
                                fontWeight: 600,
                                cursor: "pointer",
                                transition: "all 0.15s ease"
                              }}
                              title={`Download '${sheet.name}' as CSV`}
                            >
                              <Download size={12} />
                              <span>Download</span>
                            </a>
                          )}
                        </div>
                      ))}
                    </div>
                  </div>
                )}
              </div>

              <div style={{ display: "flex", flexDirection: "column", gap: "0.6rem", alignItems: "flex-end", flexShrink: 0 }}>
                <a
                  href={getDatasetDownloadUrl(ds.id)}
                  download={ds.original_name}
                  style={{
                    display: "inline-flex",
                    alignItems: "center",
                    gap: "6px",
                    background: "rgba(126, 231, 217, 0.1)",
                    border: "1px solid rgba(126, 231, 217, 0.3)",
                    borderRadius: "6px",
                    padding: "0.45rem 0.8rem",
                    color: "var(--accent-500)",
                    textDecoration: "none",
                    fontSize: "0.8rem",
                    fontWeight: 600,
                    cursor: "pointer",
                    whiteSpace: "nowrap",
                    transition: "all 0.15s ease"
                  }}
                  title={`Download ${ds.original_name}`}
                >
                  <Download size={14} />
                  <span>{ds.sheets && ds.sheets.length > 1 ? "Download Workbook" : "Download Sheet"}</span>
                </a>

                <button
                  type="button"
                  onClick={() => promptDelete(ds)}
                  style={{
                    display: "inline-flex",
                    alignItems: "center",
                    gap: "5px",
                    color: "var(--rose-tier)",
                    background: "rgba(255, 180, 190, 0.08)",
                    border: "1px solid rgba(255, 180, 190, 0.2)",
                    borderRadius: "6px",
                    padding: "0.4rem 0.65rem",
                    cursor: "pointer",
                    fontSize: "0.775rem",
                    transition: "all 0.15s ease"
                  }}
                  title={`Delete ${ds.original_name}`}
                >
                  <Trash2 size={14} color="var(--rose-tier)" />
                  <span>Delete</span>
                </button>
              </div>
            </div>
          ))}
        </div>
      </div>

      {/* Consent Check Modal */}
      {datasetToDelete && (
        <div
          className="modal-overlay"
          onClick={() => !deleting && setDatasetToDelete(null)}
          role="dialog"
          aria-modal="true"
          aria-labelledby="modal-title"
        >
          <div className="modal-dialog" onClick={(e) => e.stopPropagation()}>
            <div className="modal-header">
              <div className="modal-title-group">
                <div className="modal-icon-badge">
                  <AlertTriangle size={20} />
                </div>
                <div>
                  <h3 id="modal-title">Confirm Dataset Deletion</h3>
                  <p>Explicit consent required before permanent removal</p>
                </div>
              </div>
              <button
                type="button"
                className="modal-close-btn"
                onClick={() => !deleting && setDatasetToDelete(null)}
                disabled={deleting}
                title="Cancel and close"
              >
                <X size={18} />
              </button>
            </div>

            <div className="modal-body">
              <div className="modal-target-box">
                <FileSpreadsheet size={24} color="var(--accent-500)" style={{ flexShrink: 0 }} />
                <div style={{ flex: 1, minWidth: 0 }}>
                  <div className="target-name">{datasetToDelete.original_name}</div>
                  <div className="target-meta">
                    <span>{datasetToDelete.file_type.toUpperCase()}</span> · <span>{datasetToDelete.row_count} rows</span> · <span>{datasetToDelete.sheet_count} sheet(s)</span>
                  </div>
                </div>
              </div>

              <div className="modal-warning-box">
                <div className="warning-title">
                  <AlertTriangle size={15} />
                  <span>Permanent Irreversible Action</span>
                </div>
                <ul>
                  <li>Permanently erases all <strong>{datasetToDelete.row_count} indexed rows</strong> and cell values.</li>
                  <li>Cleanses associated <strong>vector chunks & BM25 search indices</strong>.</li>
                  <li>Unlinks all <strong>exact-key joins</strong> and relationships connected to this sheet.</li>
                  <li>Removes stored file from local server storage.</li>
                </ul>
              </div>

              <label className="modal-consent-checkbox">
                <input
                  type="checkbox"
                  checked={deleteConsent}
                  onChange={(e) => setDeleteConsent(e.target.checked)}
                  disabled={deleting}
                />
                <span>
                  I understand that this action is permanent, cannot be undone, and will immediately remove these rows from all analytics and Copilot searches.
                </span>
              </label>
            </div>

            <div className="modal-footer">
              <button
                type="button"
                className="btn-cancel"
                onClick={() => setDatasetToDelete(null)}
                disabled={deleting}
              >
                Cancel
              </button>
              <button
                type="button"
                className="btn-danger-confirm"
                onClick={handleConfirmDelete}
                disabled={!deleteConsent || deleting}
              >
                <Trash2 size={14} />
                <span>{deleting ? "Deleting..." : "Permanently Delete"}</span>
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
