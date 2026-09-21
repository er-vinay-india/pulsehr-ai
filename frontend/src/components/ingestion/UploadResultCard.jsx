import React from "react";
import { CheckCircle2, Download, Link2, Table } from "lucide-react";
import { getDatasetDownloadUrl } from "../../api/client";

export default function UploadResultCard({ uploadResult }) {
  if (!uploadResult) return null;

  return (
    <div className="alert-box alert-success" style={{ flexDirection: "column" }}>
      <div style={{ display: "flex", gap: "0.85rem", alignItems: "flex-start" }}>
        <CheckCircle2 size={24} color="var(--emerald-tier)" style={{ flexShrink: 0, marginTop: "2px" }} />
        <div>
          <div style={{ display: "flex", alignItems: "center", gap: "8px", flexWrap: "wrap" }}>
            <strong style={{ fontSize: "1.1rem", color: "var(--brand-400)" }}>
              {uploadResult.display_name || uploadResult.filename}
            </strong>
            {uploadResult.domain && (
              <span className="filetype-badge" style={{ background: "rgba(224, 86, 36, 0.15)", color: "var(--brand-400)", borderColor: "rgba(224, 86, 36, 0.3)" }}>
                {uploadResult.domain}
              </span>
            )}
          </div>
          <p style={{ marginTop: "4px", fontSize: "0.85rem", color: "var(--fg-secondary)" }}>
            {uploadResult.description || uploadResult.message}
          </p>
          <div className="upload-meta-pills" style={{ marginTop: "8px" }}>
            <span><strong>Original File:</strong> {uploadResult.filename}</span>
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

      {/* Optional Collapsible Sample Preview */}
      {uploadResult.sample_preview && uploadResult.sample_preview.length > 0 && (() => {
        const MAX_COLS = 8;
        const allCols = uploadResult.columns || [];
        const displayCols = allCols.length > MAX_COLS ? allCols.slice(0, MAX_COLS) : allCols;
        const remainingCount = allCols.length - displayCols.length;

        return (
          <details
            style={{
              marginTop: "1.25rem",
              width: "100%",
              background: "rgba(0,0,0,0.25)",
              border: "1px solid var(--border-subtle)",
              borderRadius: "8px",
              padding: "0.75rem 1rem",
              fontSize: "0.8rem"
            }}
          >
            <summary
              style={{
                cursor: "pointer",
                display: "flex",
                alignItems: "center",
                gap: "8px",
                fontWeight: 600,
                color: "var(--fg-secondary)",
                userSelect: "none"
              }}
            >
              <Table size={14} color="var(--brand-400)" />
              <span>
                Optional Raw Data Preview (First {uploadResult.sample_preview.length} rows · {allCols.length} columns)
              </span>
              <span style={{ fontSize: "0.75rem", color: "var(--fg-muted)", marginLeft: "auto" }}>
                Click to expand
              </span>
            </summary>

            <div style={{ marginTop: "0.85rem" }}>
              {remainingCount > 0 && (
                <div style={{ fontSize: "0.75rem", color: "var(--fg-muted)", marginBottom: "8px" }}>
                  Showing first {MAX_COLS} of {allCols.length} columns to keep preview readable. All {allCols.length} columns are fully parsed & indexed.
                </div>
              )}
              <div style={{ overflowX: "auto", borderRadius: "6px", border: "1px solid var(--border-subtle)" }}>
                <table style={{ width: "100%", borderCollapse: "collapse", fontSize: "0.78rem" }}>
                  <thead>
                    <tr style={{ background: "#15110f", borderBottom: "1px solid var(--border)" }}>
                      {displayCols.map((col, idx) => (
                        <th key={idx} style={{ padding: "8px 12px", textAlign: "left", color: "var(--brand-400)", fontWeight: 700, whiteSpace: "nowrap" }}>
                          {col}
                        </th>
                      ))}
                      {remainingCount > 0 && (
                        <th style={{ padding: "8px 12px", textAlign: "left", color: "var(--fg-muted)", fontStyle: "italic", whiteSpace: "nowrap" }}>
                          +{remainingCount} more columns...
                        </th>
                      )}
                    </tr>
                  </thead>
                  <tbody>
                    {uploadResult.sample_preview.map((row, rIdx) => (
                      <tr key={rIdx} style={{ borderBottom: "1px solid var(--border-subtle)" }}>
                        {displayCols.map((col, cIdx) => (
                          <td key={cIdx} style={{ padding: "8px 12px", color: "var(--fg-primary)", whiteSpace: "nowrap" }}>
                            {String(row[col] !== undefined && row[col] !== null ? row[col] : "—")}
                          </td>
                        ))}
                        {remainingCount > 0 && (
                          <td style={{ padding: "8px 12px", color: "var(--fg-muted)", fontStyle: "italic" }}>
                            ...
                          </td>
                        )}
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </div>
          </details>
        );
      })()}
    </div>
  );
}
