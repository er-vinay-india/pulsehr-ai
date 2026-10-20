import React, { useState, useEffect } from "react";
import { CheckCircle2, Download, Link2, Table } from "lucide-react";
import { getDatasetDownloadUrl } from "../../api/client";
import AnalysisBriefCard from "./AnalysisBriefCard";
import ContextReviewCard from "./ContextReviewCard";
import EnrichmentReviewCard from "./EnrichmentReviewCard";
import DataTable from "../DataTable";

export default function UploadResultCard({ uploadResult }) {
  if (!uploadResult) return null;

  const [activeContext, setActiveContext] = useState(uploadResult.workspace_context || null);

  useEffect(() => {
    if (uploadResult.workspace_context) {
      setActiveContext(uploadResult.workspace_context);
    }
  }, [uploadResult]);

  return (
    <div className="alert-box alert-success" style={{ flexDirection: "column" }}>
      <div style={{ display: "flex", gap: "0.85rem", alignItems: "flex-start" }}>
        <CheckCircle2 size={24} color="var(--emerald-tier)" style={{ flexShrink: 0, marginTop: "2px" }} />
        <div style={{ flex: 1 }}>
          <div style={{ display: "flex", alignItems: "center", gap: "8px", flexWrap: "wrap" }}>
            <strong style={{ fontSize: "1.1rem", color: "var(--brand-400)" }}>
              {uploadResult.display_name || uploadResult.filename}
            </strong>
            {(activeContext?.context_summary?.domain || uploadResult.domain) && (
              <span className="filetype-badge" style={{ background: "rgba(224, 86, 36, 0.15)", color: "var(--brand-400)", borderColor: "rgba(224, 86, 36, 0.3)" }}>
                {activeContext?.context_summary?.domain || uploadResult.domain}
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
            {uploadResult.enrichment?.derived_features_count > 0 && (
              <span style={{ color: "var(--brand-400)", borderColor: "rgba(224, 86, 36, 0.3)" }}>
                <strong>Enriched:</strong> +{uploadResult.enrichment.derived_features_count} Scientific Features
              </span>
            )}
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

      {/* Lightweight User Context Review & Override (Section 7, 8, 9) */}
      {activeContext && (
        <ContextReviewCard
          workspaceContext={activeContext}
          workspaceId={String(uploadResult.dataset_id)}
          onContextUpdated={(updated) => setActiveContext(updated)}
        />
      )}

      {/* Controlled Semantic Enrichment & Scientific Discovery (Stages 1-11) */}
      {uploadResult.enrichment && (
        <EnrichmentReviewCard enrichment={uploadResult.enrichment} />
      )}

      {/* Analysis Brief & Business Intent Section */}
      <AnalysisBriefCard uploadResult={uploadResult} />

      {/* Optional Collapsible Sample Preview */}
      {uploadResult.sample_preview && uploadResult.sample_preview.length > 0 && (() => {
        const allCols = uploadResult.columns || Object.keys(uploadResult.sample_preview[0] || {});
        const previewCols = allCols.map((c) => ({
          key: c,
          label: c,
          type: "text",
          sortable: true,
          defaultVisible: true,
          render: (val) => <span>{val !== undefined && val !== null ? String(val) : "—"}</span>,
        }));

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
              <DataTable
                columns={previewCols}
                rows={uploadResult.sample_preview}
                totalRows={uploadResult.sample_preview.length}
                pageSize={10}
                pageSizeOptions={[10, 25, 50]}
                searchable={true}
                searchPlaceholder="Search sample preview..."
                columnVisibilityEnabled={true}
                emptyMessage="No sample records available."
                tableAriaLabel="Uploaded sample preview table"
              />
            </div>
          </details>
        );
      })()}
    </div>
  );
}
