import React, { useState } from "react";
import { FileSpreadsheet, Layers, Download, Trash2, Sparkles, ChevronDown, ChevronUp } from "lucide-react";
import { getDatasetDownloadUrl, getSheetDownloadUrl } from "../../api/client";
import AnalysisBriefCard from "./AnalysisBriefCard";

export default function DatasetListCard({ dataset, onPromptDelete }) {
  const ds = dataset;
  const [showBriefEditor, setShowBriefEditor] = useState(false);

  return (
    <div className="dataset-card" style={{ flexDirection: "column" }}>
      <div style={{ display: "flex", width: "100%", alignItems: "flex-start", gap: "1rem" }}>
        <div className="dataset-icon">
          <FileSpreadsheet size={24} color="var(--accent-500)" />
        </div>
        <div className="dataset-details" style={{ flex: 1 }}>
          <div className="dataset-title-row">
            <h4>{ds.display_name || ds.original_name}</h4>
            <span className="filetype-badge">{ds.file_type.toUpperCase()}</span>
            {ds.analysis_context?.mode === "USER_DIRECTED" && (
              <span
                style={{
                  fontSize: "0.7rem",
                  padding: "2px 8px",
                  borderRadius: "12px",
                  background: "rgba(46, 213, 115, 0.15)",
                  color: "var(--emerald-tier)",
                  border: "1px solid rgba(46, 213, 115, 0.3)"
                }}
              >
                Brief Applied
              </span>
            )}
          </div>
          {ds.display_name && ds.original_name && ds.display_name !== ds.original_name && (
            <div style={{ fontSize: "0.74rem", color: "var(--fg-muted)", marginTop: "2px", marginBottom: "4px" }}>
              Source file: <span style={{ fontFamily: "monospace" }}>{ds.original_name}</span>
            </div>
          )}
          <p className="dataset-summary">{ds.summary_insights}</p>
          <div className="dataset-stats">
            <span><strong>{ds.row_count}</strong> Rows</span> · 
            <span><strong>{ds.col_count}</strong> Columns</span> · 
            <span><strong>{ds.sheet_count}</strong> Sheet(s)</span> · 
            <span>Ingested {new Date(ds.uploaded_at).toLocaleDateString()}</span>
          </div>

          {ds.analysis_context?.user_objective && (
            <div style={{ marginTop: "6px", fontSize: "0.78rem", color: "var(--brand-400)", background: "rgba(224, 86, 36, 0.08)", padding: "4px 8px", borderRadius: "4px", border: "1px solid rgba(224, 86, 36, 0.2)" }}>
              <strong>Active Brief:</strong> &ldquo;{ds.analysis_context.user_objective}&rdquo;
            </div>
          )}

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
                  <span style={{ fontWeight: 600, color: "var(--fg-primary)" }}>{sheet.display_name || sheet.name}</span>
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
          onClick={() => setShowBriefEditor(!showBriefEditor)}
          style={{
            display: "inline-flex",
            alignItems: "center",
            gap: "5px",
            color: "var(--brand-400)",
            background: "rgba(224, 86, 36, 0.08)",
            border: "1px solid rgba(224, 86, 36, 0.25)",
            borderRadius: "6px",
            padding: "0.4rem 0.65rem",
            cursor: "pointer",
            fontSize: "0.775rem",
            transition: "all 0.15s ease"
          }}
          title="Set or view Analysis Brief"
        >
          <Sparkles size={13} color="var(--brand-400)" />
          <span>{ds.analysis_context?.mode === "USER_DIRECTED" ? "Edit Brief" : "Add Brief"}</span>
        </button>

        <button
          type="button"
          onClick={() => onPromptDelete(ds)}
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

      {showBriefEditor && (
        <div style={{ width: "100%" }}>
          <AnalysisBriefCard
            uploadResult={{
              dataset_id: ds.id,
              columns: ds.columns || [],
              display_name: ds.display_name || ds.original_name,
              filename: ds.original_name
            }}
          />
        </div>
      )}
    </div>
  );
}
