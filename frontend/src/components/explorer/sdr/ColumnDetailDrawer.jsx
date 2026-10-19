import React, { useEffect } from "react";
import { X, Shield, Tag, Hash, FileCode, CheckCircle2, AlertTriangle, Layers, Info } from "lucide-react";

export default function ColumnDetailDrawer({
  column,
  onClose,
  isDark = false,
}) {
  useEffect(() => {
    const handleKeyDown = (e) => {
      if (e.key === "Escape") onClose();
    };
    window.addEventListener("keydown", handleKeyDown);
    return () => window.removeEventListener("keydown", handleKeyDown);
  }, [onClose]);

  if (!column) return null;

  const bgCard = isDark ? "#1e293b" : "#ffffff";
  const borderCol = isDark ? "#334155" : "#e2e8f0";
  const textPrimary = isDark ? "#f8fafc" : "#0f172a";
  const textSecondary = isDark ? "#94a3b8" : "#64748b";
  const bgSubtle = isDark ? "#0f172a" : "#f8fafc";

  const isEnriched = column.provenance_type === "DERIVED_ENRICHMENT" || column.provenance_type === "DERIVED_RELATIONAL";

  return (
    <div
      style={{
        position: "fixed",
        top: 0,
        left: 0,
        width: "100vw",
        height: "100vh",
        backgroundColor: "rgba(0, 0, 0, 0.45)",
        zIndex: 9999,
        display: "flex",
        justifyContent: "flex-end",
        backdropFilter: "blur(2px)",
      }}
      onClick={onClose}
    >
      <div
        role="dialog"
        aria-modal="true"
        aria-labelledby="drawer-title"
        onClick={(e) => e.stopPropagation()}
        style={{
          width: "480px",
          maxWidth: "90vw",
          height: "100%",
          backgroundColor: bgCard,
          borderLeft: `1px solid ${borderCol}`,
          boxShadow: "-8px 0 24px rgba(0,0,0,0.2)",
          display: "flex",
          flexDirection: "column",
          overflowY: "auto",
        }}
      >
        {/* Drawer Header */}
        <div
          style={{
            padding: "20px",
            borderBottom: `1px solid ${borderCol}`,
            display: "flex",
            alignItems: "center",
            justifyContent: "space-between",
          }}
        >
          <div style={{ display: "flex", alignItems: "center", gap: "10px" }}>
            <span
              style={{
                display: "inline-flex",
                padding: "4px 8px",
                borderRadius: "6px",
                fontSize: "0.72rem",
                fontWeight: 700,
                background: isEnriched ? "rgba(168, 85, 247, 0.15)" : "rgba(37, 99, 235, 0.15)",
                color: isEnriched ? "#a855f7" : "#2563eb",
                border: isEnriched ? "1px solid rgba(168, 85, 247, 0.3)" : "1px solid rgba(37, 99, 235, 0.3)",
              }}
            >
              {isEnriched ? "Derived / Enriched" : "Source / Observed"}
            </span>
            <h2 id="drawer-title" style={{ margin: 0, fontSize: "1.1rem", fontWeight: 700, color: textPrimary }}>
              {column.display_name || column.column_id}
            </h2>
          </div>
          <button
            type="button"
            onClick={onClose}
            aria-label="Close drawer"
            style={{
              background: "transparent",
              border: "none",
              color: textSecondary,
              cursor: "pointer",
              padding: "4px",
              display: "flex",
              alignItems: "center",
              borderRadius: "4px",
            }}
          >
            <X size={18} />
          </button>
        </div>

        {/* Content Body */}
        <div style={{ padding: "20px", display: "flex", flexDirection: "column", gap: "20px" }}>
          {/* Identity & Sheet Context */}
          <div style={{ background: bgSubtle, padding: "12px 16px", borderRadius: "8px", border: `1px solid ${borderCol}` }}>
            <div style={{ fontSize: "0.75rem", color: textSecondary, marginBottom: "4px" }}>Table / Sheet Context</div>
            <div style={{ fontSize: "0.9rem", fontWeight: 600, color: textPrimary }}>
              Sheet: <span style={{ color: "#2563eb" }}>{column.sheet_id}</span> · Column ID: <code>{column.column_id}</code>
            </div>
          </div>

          {/* Core Semantic Profile Section */}
          <div>
            <h3 style={{ fontSize: "0.85rem", fontWeight: 700, textTransform: "uppercase", letterSpacing: "0.05em", color: textSecondary, marginBottom: "12px" }}>
              Semantic Classification
            </h3>
            <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: "12px" }}>
              <div style={{ padding: "10px", background: bgSubtle, borderRadius: "6px", border: `1px solid ${borderCol}` }}>
                <div style={{ fontSize: "0.72rem", color: textSecondary }}>Semantic Role</div>
                <div style={{ fontSize: "0.85rem", fontWeight: 600, color: textPrimary, marginTop: "2px" }}>
                  {column.role}
                </div>
              </div>
              <div style={{ padding: "10px", background: bgSubtle, borderRadius: "6px", border: `1px solid ${borderCol}` }}>
                <div style={{ fontSize: "0.72rem", color: textSecondary }}>Logical Data Type</div>
                <div style={{ fontSize: "0.85rem", fontWeight: 600, color: textPrimary, marginTop: "2px" }}>
                  {column.data_type}
                </div>
              </div>
              <div style={{ padding: "10px", background: bgSubtle, borderRadius: "6px", border: `1px solid ${borderCol}` }}>
                <div style={{ fontSize: "0.72rem", color: textSecondary }}>Semantic Concept</div>
                <div style={{ fontSize: "0.85rem", fontWeight: 600, color: textPrimary, marginTop: "2px" }}>
                  {column.concept}
                </div>
              </div>
              <div style={{ padding: "10px", background: bgSubtle, borderRadius: "6px", border: `1px solid ${borderCol}` }}>
                <div style={{ fontSize: "0.72rem", color: textSecondary }}>Entity Type</div>
                <div style={{ fontSize: "0.85rem", fontWeight: 600, color: textPrimary, marginTop: "2px" }}>
                  {column.entity}
                </div>
              </div>
              <div style={{ padding: "10px", background: bgSubtle, borderRadius: "6px", border: `1px solid ${borderCol}` }}>
                <div style={{ fontSize: "0.72rem", color: textSecondary }}>Measure Class</div>
                <div style={{ fontSize: "0.85rem", fontWeight: 600, color: textPrimary, marginTop: "2px" }}>
                  {column.measure_class || "None"}
                </div>
              </div>
              <div style={{ padding: "10px", background: bgSubtle, borderRadius: "6px", border: `1px solid ${borderCol}` }}>
                <div style={{ fontSize: "0.72rem", color: textSecondary }}>Privacy Governance</div>
                <div style={{ fontSize: "0.85rem", fontWeight: 600, color: column.privacy_raw === "DIRECT_IDENTIFIER" || column.privacy_raw === "SENSITIVE_ATTRIBUTE" ? "#f59e0b" : textPrimary, marginTop: "2px" }}>
                  {column.privacy}
                </div>
              </div>
            </div>
          </div>

          {/* Epistemic Confidence & Ambiguity */}
          <div>
            <h3 style={{ fontSize: "0.85rem", fontWeight: 700, textTransform: "uppercase", letterSpacing: "0.05em", color: textSecondary, marginBottom: "12px" }}>
              Confidence & Ambiguity Evidence
            </h3>
            <div style={{ background: bgSubtle, padding: "12px 16px", borderRadius: "8px", border: `1px solid ${borderCol}`, display: "flex", flexDirection: "column", gap: "10px" }}>
              <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
                <span style={{ fontSize: "0.8rem", color: textSecondary }}>Confidence Level:</span>
                <span style={{ fontSize: "0.85rem", fontWeight: 700, color: column.confidence === "High" ? "#10b981" : "#f59e0b" }}>
                  {column.confidence} ({Math.round(column.confidence_score * 100)}%)
                </span>
              </div>
              <div style={{ width: "100%", height: "6px", background: isDark ? "#334155" : "#e2e8f0", borderRadius: "3px", overflow: "hidden" }}>
                <div
                  style={{
                    width: `${Math.round(column.confidence_score * 100)}%`,
                    height: "100%",
                    background: column.confidence === "High" ? "#10b981" : "#f59e0b",
                    borderRadius: "3px",
                  }}
                />
              </div>

              <div style={{ display: "flex", alignItems: "center", gap: "6px", marginTop: "4px" }}>
                {column.is_ambiguous ? (
                  <AlertTriangle size={15} color="#f59e0b" />
                ) : (
                  <CheckCircle2 size={15} color="#10b981" />
                )}
                <span style={{ fontSize: "0.8rem", fontWeight: 600, color: column.is_ambiguous ? "#f59e0b" : textPrimary }}>
                  Ambiguity State: {column.ambiguity}
                </span>
              </div>
            </div>
          </div>

          {/* Value Distribution Observations */}
          <div>
            <h3 style={{ fontSize: "0.85rem", fontWeight: 700, textTransform: "uppercase", letterSpacing: "0.05em", color: textSecondary, marginBottom: "12px" }}>
              Observed Value Distribution
            </h3>
            <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: "10px" }}>
              <div style={{ padding: "8px 12px", background: bgSubtle, borderRadius: "6px", border: `1px solid ${borderCol}` }}>
                <div style={{ fontSize: "0.72rem", color: textSecondary }}>Total Rows</div>
                <div style={{ fontSize: "0.88rem", fontWeight: 700, color: textPrimary }}>{column.row_count}</div>
              </div>
              <div style={{ padding: "8px 12px", background: bgSubtle, borderRadius: "6px", border: `1px solid ${borderCol}` }}>
                <div style={{ fontSize: "0.72rem", color: textSecondary }}>Distinct Count</div>
                <div style={{ fontSize: "0.88rem", fontWeight: 700, color: textPrimary }}>
                  {column.distinct_count} ({column.distinct_ratio_pct}%)
                </div>
              </div>
              <div style={{ padding: "8px 12px", background: bgSubtle, borderRadius: "6px", border: `1px solid ${borderCol}` }}>
                <div style={{ fontSize: "0.72rem", color: textSecondary }}>Null Count</div>
                <div style={{ fontSize: "0.88rem", fontWeight: 700, color: textPrimary }}>
                  {column.null_count} ({column.null_ratio_pct}%)
                </div>
              </div>
              <div style={{ padding: "8px 12px", background: bgSubtle, borderRadius: "6px", border: `1px solid ${borderCol}` }}>
                <div style={{ fontSize: "0.72rem", color: textSecondary }}>Physical Storage</div>
                <div style={{ fontSize: "0.88rem", fontWeight: 700, color: textPrimary }}>{column.physical_dtype || "string"}</div>
              </div>
            </div>

            {column.sample_values && column.sample_values.length > 0 && (
              <div style={{ marginTop: "12px" }}>
                <div style={{ fontSize: "0.75rem", color: textSecondary, marginBottom: "6px" }}>Sample Values:</div>
                <div style={{ display: "flex", flexWrap: "wrap", gap: "6px" }}>
                  {column.sample_values.map((v, i) => (
                    <span
                      key={i}
                      style={{
                        padding: "3px 8px",
                        fontSize: "0.75rem",
                        fontFamily: "monospace",
                        background: bgSubtle,
                        border: `1px solid ${borderCol}`,
                        borderRadius: "4px",
                        color: textPrimary,
                      }}
                    >
                      {String(v)}
                    </span>
                  ))}
                </div>
              </div>
            )}
          </div>

          {/* Lineage & Fingerprint */}
          <div style={{ borderTop: `1px solid ${borderCol}`, paddingTop: "16px" }}>
            <div style={{ fontSize: "0.75rem", color: textSecondary }}>
              Artifact Fingerprint: <code style={{ fontSize: "0.72rem" }}>{column.artifact_fingerprint || "governed_deterministic"}</code>
            </div>
            <div style={{ fontSize: "0.75rem", color: textSecondary, marginTop: "4px" }}>
              Lineage: {column.lineage?.source_file_hash ? `File Hash ${column.lineage.source_file_hash.slice(0, 12)}…` : "Local upload"}
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
