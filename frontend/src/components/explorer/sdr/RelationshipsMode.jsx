import React, { useState, useEffect } from "react";
import { getExplorerRelationships } from "../../../api/client";
import StatusBadge from "../common/StatusBadge";
import {
  GitMerge,
  ShieldCheck,
  ShieldAlert,
  AlertTriangle,
  ArrowRight,
  Filter,
  CheckCircle2,
  XCircle,
  Layers,
  Zap,
  AlertCircle,
  Eye,
  Table,
  Network,
  X,
  Info,
} from "lucide-react";

/**
 * HighView Data Explorer — Relationships
 * "Cards summarize. Tables compare. Drawers explain."
 * Primary representation is a clean data table with an optional Graph toggle.
 * Clicking a row opens a drawer explaining how tables connect.
 */
export default function RelationshipsMode({
  datasetId,
  themeTokens,
  isDark = false,
}) {
  const [relData, setRelData] = useState(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);
  const [viewMode, setViewMode] = useState("table"); // 'table' | 'graph'
  const [selectedRel, setSelectedRel] = useState(null);
  const [safetyFilter, setSafetyFilter] = useState("ALL"); // 'ALL' | 'SAFE' | 'AGG' | 'UNSAFE'

  const bgSurface = themeTokens?.colors?.surface || "var(--color-bg-surface)";
  const bgSubtle = themeTokens?.colors?.surfaceHover || "var(--color-bg-subtle)";
  const borderCol = themeTokens?.colors?.borderSubtle || "var(--color-divider)";
  const borderStrong = themeTokens?.colors?.border || "var(--color-border)";
  const textPrimary = themeTokens?.colors?.textPrimary || "var(--color-text-primary)";
  const textSecondary = themeTokens?.colors?.textSecondary || "var(--color-text-secondary)";
  const textMuted = themeTokens?.colors?.textMuted || "var(--color-text-muted)";
  const brandPrimary = themeTokens?.colors?.brandPrimary || "var(--color-brand-primary)";
  const brandSoftBg = themeTokens?.colors?.softBlue || "var(--color-bg-soft-blue)";

  useEffect(() => {
    if (!datasetId) return;
    let isCancelled = false;

    async function loadRelationships() {
      setLoading(true);
      setError(null);
      try {
        const res = await getExplorerRelationships(datasetId);
        if (!isCancelled) {
          setRelData(res);
        }
      } catch (err) {
        if (!isCancelled) {
          setError(err.message || "Failed to load relationship model");
        }
      } finally {
        if (!isCancelled) {
          setLoading(false);
        }
      }
    }

    loadRelationships();
    return () => {
      isCancelled = true;
    };
  }, [datasetId]);

  const allRelationships = relData?.relationships || [];

  const filteredRelationships = allRelationships.filter((rel) => {
    if (safetyFilter === "ALL") return true;
    if (safetyFilter === "SAFE") return rel.safety_status_raw === "SAFE";
    if (safetyFilter === "AGG") return String(rel.safety_status_raw || "").includes("PREAGGREGATION");
    if (safetyFilter === "UNSAFE") return rel.safety_status_raw === "UNSAFE";
    return true;
  });

  const totalValidated = relData?.total_validated ?? allRelationships.filter(r => r.is_validated).length;

  return (
    <div className="sdr-relationships-mode-container" style={{ display: "flex", flexDirection: "column", gap: "16px" }}>
      {/* Header & Controls */}
      <div
        style={{
          background: bgSurface,
          border: `1px solid ${borderCol}`,
          borderRadius: "10px",
          padding: "16px",
          display: "flex",
          flexDirection: "column",
          gap: "12px",
        }}
      >
        <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", flexWrap: "wrap", gap: "10px" }}>
          <div style={{ display: "flex", alignItems: "center", gap: "8px" }}>
            <GitMerge size={18} color={brandPrimary} aria-hidden="true" />
            <h2 style={{ margin: 0, fontSize: "1.1rem", fontWeight: 700, color: textPrimary }}>
              Relationships
            </h2>
          </div>

          {/* View Mode Toggle: Table | Graph (Default Table) */}
          <div style={{ display: "flex", alignItems: "center", gap: "6px" }}>
            <div
              style={{
                display: "inline-flex",
                background: bgSubtle,
                border: `1px solid ${borderCol}`,
                borderRadius: "8px",
                padding: "2px",
              }}
            >
              <button
                type="button"
                onClick={() => setViewMode("table")}
                aria-pressed={viewMode === "table"}
                style={{
                  display: "inline-flex",
                  alignItems: "center",
                  gap: "5px",
                  padding: "5px 10px",
                  fontSize: "0.78rem",
                  fontWeight: viewMode === "table" ? 700 : 500,
                  borderRadius: "6px",
                  border: "none",
                  background: viewMode === "table" ? bgSurface : "transparent",
                  color: viewMode === "table" ? brandPrimary : textSecondary,
                  cursor: "pointer",
                  boxShadow: viewMode === "table" ? "0 1px 3px rgba(0,0,0,0.08)" : "none",
                }}
              >
                <Table size={13} />
                Table
              </button>
              <button
                type="button"
                onClick={() => setViewMode("graph")}
                aria-pressed={viewMode === "graph"}
                style={{
                  display: "inline-flex",
                  alignItems: "center",
                  gap: "5px",
                  padding: "5px 10px",
                  fontSize: "0.78rem",
                  fontWeight: viewMode === "graph" ? 700 : 500,
                  borderRadius: "6px",
                  border: "none",
                  background: viewMode === "graph" ? bgSurface : "transparent",
                  color: viewMode === "graph" ? brandPrimary : textSecondary,
                  cursor: "pointer",
                  boxShadow: viewMode === "graph" ? "0 1px 3px rgba(0,0,0,0.08)" : "none",
                }}
              >
                <Network size={13} />
                Graph
              </button>
            </div>
          </div>
        </div>

        <p style={{ margin: 0, fontSize: "0.82rem", color: textSecondary }}>
          Governed connections between sheets, verified key integrity, and safe aggregation rules.
        </p>

        {/* Safety Filter Tabs */}
        <div style={{ display: "flex", alignItems: "center", gap: "6px", overflowX: "auto", paddingTop: "4px" }}>
          {[
            { id: "ALL", label: `All Connections (${allRelationships.length})` },
            { id: "SAFE", label: "Safe to Join" },
            { id: "AGG", label: "Safe After Aggregation" },
            { id: "UNSAFE", label: "Unsafe / Review" },
          ].map((f) => {
            const isActive = safetyFilter === f.id;
            return (
              <button
                key={f.id}
                type="button"
                onClick={() => setSafetyFilter(f.id)}
                style={{
                  padding: "6px 12px",
                  fontSize: "0.8rem",
                  fontWeight: isActive ? 700 : 500,
                  borderRadius: "8px",
                  border: isActive ? `1px solid ${brandPrimary}` : `1px solid ${borderCol}`,
                  background: isActive ? brandSoftBg : "transparent",
                  color: isActive ? brandPrimary : textSecondary,
                  cursor: "pointer",
                  whiteSpace: "nowrap",
                  transition: "all 0.15s ease",
                }}
              >
                {f.label}
              </button>
            );
          })}
        </div>
      </div>

      {loading ? (
        <div style={{ padding: "40px", textAlign: "center", color: textSecondary, fontSize: "0.9rem" }}>
          Loading relationship intelligence…
        </div>
      ) : error ? (
        <div
          style={{
            padding: "16px",
            background: themeTokens?.colors?.softError || "var(--color-bg-soft-error)",
            border: `1px solid ${themeTokens?.colors?.statusError || "var(--color-error)"}`,
            borderRadius: "8px",
            color: themeTokens?.colors?.statusError || "var(--color-error)",
            display: "flex",
            alignItems: "center",
            gap: "8px",
            fontSize: "0.85rem",
          }}
        >
          <AlertCircle size={16} />
          <span>{error}</span>
        </div>
      ) : allRelationships.length === 0 ? (
        <section
          style={{
            background: bgSurface,
            border: `1px solid ${borderCol}`,
            borderRadius: "10px",
            padding: "48px 24px",
            textAlign: "center",
          }}
        >
          <div style={{ width: "48px", height: "48px", borderRadius: "24px", background: brandSoftBg, display: "flex", alignItems: "center", justifyContent: "center", margin: "0 auto 16px" }}>
            <GitMerge size={24} color={brandPrimary} />
          </div>
          <h3 style={{ margin: "0 0 8px", fontSize: "1.1rem", fontWeight: 700, color: textPrimary }}>
            No validated relationships were found
          </h3>
          <p style={{ fontSize: "0.85rem", color: textSecondary, maxWidth: "480px", margin: "0 auto", lineHeight: 1.5 }}>
            This dataset either has a single sheet or contains no cross-sheet keys matching verified uniqueness constraints.
          </p>
        </section>
      ) : viewMode === "graph" ? (
        /* OPTIONAL TOPOLOGY GRAPH VIEW */
        <div style={{ background: bgSurface, border: `1px solid ${borderCol}`, borderRadius: "10px", padding: "20px" }}>
          <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: "16px" }}>
            <h3 style={{ margin: 0, fontSize: "0.9rem", fontWeight: 700, color: textPrimary }}>
              Sheet Topology Graph
            </h3>
            <span style={{ fontSize: "0.75rem", color: textSecondary }}>
              Visual map of cross-sheet connections
            </span>
          </div>
          <div style={{ display: "flex", flexWrap: "wrap", gap: "16px", alignItems: "center", justifyContent: "center", minHeight: "220px", padding: "20px" }}>
            {relData?.graph?.nodes?.map((node) => (
              <div
                key={node.id}
                style={{
                  padding: "12px 18px",
                  borderRadius: "8px",
                  border: `1px solid ${borderStrong}`,
                  background: bgSubtle,
                  color: textPrimary,
                  fontWeight: 700,
                  fontSize: "0.85rem",
                  boxShadow: "0 2px 4px rgba(0,0,0,0.05)",
                }}
              >
                <Layers size={14} style={{ marginRight: "6px", display: "inline" }} />
                {node.name}
              </div>
            ))}
          </div>
        </div>
      ) : (
        /* PRIMARY DATA TABLE VIEW */
        <div style={{ background: bgSurface, border: `1px solid ${borderCol}`, borderRadius: "10px", overflow: "hidden" }}>
          <div style={{ padding: "12px 16px", borderBottom: `1px solid ${borderCol}`, display: "flex", justifyContent: "space-between", alignItems: "center" }}>
            <h3 style={{ margin: 0, fontSize: "0.9rem", fontWeight: 700, color: textPrimary, display: "flex", alignItems: "center", gap: "6px" }}>
              <Table size={15} color={brandPrimary} />
              Validated Relationships Table ({filteredRelationships.length})
            </h3>
            <span style={{ fontSize: "0.75rem", color: textSecondary }}>
              Click any row or "Details" to examine join methods and key mappings
            </span>
          </div>
          <div style={{ overflowX: "auto" }}>
            <table style={{ width: "100%", borderCollapse: "collapse", fontSize: "0.82rem", textAlign: "left" }}>
              <thead>
                <tr style={{ background: bgSubtle, borderBottom: `2px solid ${borderCol}` }}>
                  <th style={{ padding: "10px 12px", color: textPrimary, fontWeight: 700 }}>From Sheet</th>
                  <th style={{ padding: "10px 12px", color: textPrimary, fontWeight: 700 }}>From Key</th>
                  <th style={{ padding: "10px 12px", color: textPrimary, fontWeight: 700 }}>To Sheet</th>
                  <th style={{ padding: "10px 12px", color: textPrimary, fontWeight: 700 }}>To Key</th>
                  <th style={{ padding: "10px 12px", color: textPrimary, fontWeight: 700 }}>Cardinality</th>
                  <th style={{ padding: "10px 12px", color: textPrimary, fontWeight: 700 }}>Coverage</th>
                  <th style={{ padding: "10px 12px", color: textPrimary, fontWeight: 700 }}>Safety</th>
                  <th style={{ padding: "10px 12px", color: textSecondary, fontWeight: 700, textAlign: "right" }}>Action</th>
                </tr>
              </thead>
              <tbody>
                {filteredRelationships.length > 0 ? (
                  filteredRelationships.map((rel, idx) => (
                    <tr
                      key={rel.relationship_id || idx}
                      onClick={() => setSelectedRel(rel)}
                      style={{
                        borderBottom: `1px solid ${borderCol}`,
                        background: idx % 2 === 1 ? bgSubtle : "transparent",
                        cursor: "pointer",
                      }}
                    >
                      <td style={{ padding: "10px 12px", fontWeight: 700, color: textPrimary }}>
                        {rel.left_sheet}
                      </td>
                      <td style={{ padding: "10px 12px", color: textSecondary, fontFamily: "monospace" }}>
                        {rel.left_columns?.join(", ")}
                      </td>
                      <td style={{ padding: "10px 12px", fontWeight: 700, color: textPrimary }}>
                        {rel.right_sheet}
                      </td>
                      <td style={{ padding: "10px 12px", color: textSecondary, fontFamily: "monospace" }}>
                        {rel.right_columns?.join(", ")}
                      </td>
                      <td style={{ padding: "10px 12px", color: textSecondary }}>
                        {rel.cardinality}
                      </td>
                      <td style={{ padding: "10px 12px", color: textSecondary }}>
                        {rel.coverage_summary || `${rel.coverage_left_pct}%`}
                      </td>
                      <td style={{ padding: "10px 12px" }}>
                        <StatusBadge status={rel.safety_status} />
                      </td>
                      <td style={{ padding: "10px 12px", textAlign: "right" }}>
                        <button
                          type="button"
                          className="btn-secondary"
                          onClick={(e) => {
                            e.stopPropagation();
                            setSelectedRel(rel);
                          }}
                          style={{
                            padding: "4px 8px",
                            fontSize: "0.74rem",
                            fontWeight: 600,
                            borderRadius: "6px",
                            cursor: "pointer",
                            display: "inline-flex",
                            alignItems: "center",
                            gap: "4px",
                            minHeight: "unset",
                            lineHeight: 1.25,
                          }}
                        >
                          <Eye size={12} />
                          Details
                        </button>
                      </td>
                    </tr>
                  ))
                ) : (
                  <tr>
                    <td colSpan={8} style={{ padding: "20px", textAlign: "center", color: textSecondary }}>
                      No relationships match the selected filter.
                    </td>
                  </tr>
                )}
              </tbody>
            </table>
          </div>
        </div>
      )}

      {/* Connection Details Drawer (Progressive Disclosure) */}
      {selectedRel && (
        <div
          role="dialog"
          aria-modal="true"
          aria-label="Relationship Details"
          style={{
            position: "fixed",
            top: 0,
            right: 0,
            bottom: 0,
            width: "min(480px, 92vw)",
            background: bgSurface,
            borderLeft: `1px solid ${borderStrong}`,
            boxShadow: "-4px 0 24px rgba(0,0,0,0.15)",
            zIndex: 1000,
            display: "flex",
            flexDirection: "column",
            animation: "slideInRight 0.2s ease",
          }}
        >
          {/* Drawer Header */}
          <div
            style={{
              padding: "16px 20px",
              borderBottom: `1px solid ${borderCol}`,
              display: "flex",
              justifyContent: "space-between",
              alignItems: "center",
            }}
          >
            <div>
              <div style={{ fontSize: "0.75rem", color: textSecondary, fontWeight: 700 }}>
                Connection Details
              </div>
              <h3 style={{ margin: "2px 0 0", fontSize: "1.05rem", fontWeight: 700, color: textPrimary }}>
                {selectedRel.left_sheet} ➔ {selectedRel.right_sheet}
              </h3>
            </div>
            <button
              type="button"
              onClick={() => setSelectedRel(null)}
              aria-label="Close drawer"
              style={{
                background: "transparent",
                border: "none",
                cursor: "pointer",
                color: textSecondary,
                padding: "4px",
              }}
            >
              <X size={18} />
            </button>
          </div>

          {/* Drawer Body */}
          <div style={{ padding: "20px", overflowY: "auto", display: "flex", flexDirection: "column", gap: "16px", flex: 1 }}>
            {/* Join Safety Status */}
            <div style={{ padding: "12px", borderRadius: "8px", background: bgSubtle, border: `1px solid ${borderCol}` }}>
              <div style={{ fontSize: "0.75rem", color: textSecondary, fontWeight: 600 }}>Safety Assessment</div>
              <div style={{ marginTop: "4px" }}>
                <StatusBadge status={selectedRel.safety_status} size="sm" />
              </div>
              <p style={{ margin: "8px 0 0", fontSize: "0.8rem", color: textSecondary, lineHeight: 1.4 }}>
                {selectedRel.safety_status_raw === "SAFE"
                  ? "This join preserves unique row grain and introduces zero fan-out risk."
                  : selectedRel.preaggregation_explanation
                  ? selectedRel.preaggregation_explanation
                  : "Aggregation must be performed before joining to avoid duplicate metric counts."}
              </p>
            </div>

            {/* Key Alignment Table */}
            <div>
              <div style={{ fontSize: "0.8rem", fontWeight: 700, color: textPrimary, marginBottom: "8px" }}>
                Key Mapping
              </div>
              <div style={{ border: `1px solid ${borderCol}`, borderRadius: "8px", overflow: "hidden" }}>
                <table style={{ width: "100%", fontSize: "0.8rem", borderCollapse: "collapse" }}>
                  <tbody>
                    <tr style={{ borderBottom: `1px solid ${borderCol}` }}>
                      <td style={{ padding: "8px 12px", color: textSecondary, width: "35%" }}>Left Sheet</td>
                      <td style={{ padding: "8px 12px", fontWeight: 600, color: textPrimary }}>{selectedRel.left_sheet}</td>
                    </tr>
                    <tr style={{ borderBottom: `1px solid ${borderCol}` }}>
                      <td style={{ padding: "8px 12px", color: textSecondary }}>Left Keys</td>
                      <td style={{ padding: "8px 12px", fontFamily: "monospace", color: textPrimary }}>{selectedRel.left_columns?.join(", ")}</td>
                    </tr>
                    <tr style={{ borderBottom: `1px solid ${borderCol}` }}>
                      <td style={{ padding: "8px 12px", color: textSecondary }}>Right Sheet</td>
                      <td style={{ padding: "8px 12px", fontWeight: 600, color: textPrimary }}>{selectedRel.right_sheet}</td>
                    </tr>
                    <tr style={{ borderBottom: `1px solid ${borderCol}` }}>
                      <td style={{ padding: "8px 12px", color: textSecondary }}>Right Keys</td>
                      <td style={{ padding: "8px 12px", fontFamily: "monospace", color: textPrimary }}>{selectedRel.right_columns?.join(", ")}</td>
                    </tr>
                    <tr style={{ borderBottom: `1px solid ${borderCol}` }}>
                      <td style={{ padding: "8px 12px", color: textSecondary }}>Cardinality</td>
                      <td style={{ padding: "8px 12px", color: textPrimary }}>{selectedRel.cardinality}</td>
                    </tr>
                    <tr>
                      <td style={{ padding: "8px 12px", color: textSecondary }}>Coverage</td>
                      <td style={{ padding: "8px 12px", color: textPrimary }}>{selectedRel.coverage_summary || `${selectedRel.coverage_left_pct}%`}</td>
                    </tr>
                  </tbody>
                </table>
              </div>
            </div>

            {/* Technical Details (Progressive Disclosure) */}
            <details style={{ marginTop: "8px" }}>
              <summary style={{ cursor: "pointer", fontSize: "0.78rem", color: textSecondary, fontWeight: 600 }}>
                Technical Details
              </summary>
              <div style={{ marginTop: "8px", padding: "10px", background: bgSubtle, borderRadius: "6px", fontSize: "0.75rem", fontFamily: "monospace", color: textSecondary, overflowX: "auto" }}>
                <div>Relationship ID: {selectedRel.relationship_id}</div>
                <div>Join Method: {selectedRel.join_plan_id || "Direct"}</div>
                <div>Target Grain: {selectedRel.result_grain || "PRESERVED"}</div>
              </div>
            </details>
          </div>
        </div>
      )}
    </div>
  );
}
