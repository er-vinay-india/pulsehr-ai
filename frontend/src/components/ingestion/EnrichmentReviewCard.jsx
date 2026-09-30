import React, { useState } from "react";
import { Sparkles, Layers, Atom, Table, ChevronDown, ChevronRight, Zap, CheckCircle2 } from "lucide-react";

export default function EnrichmentReviewCard({ enrichment }) {
  if (!enrichment) return null;

  const [activeTab, setActiveTab] = useState("features");
  const [expandedTable, setExpandedTable] = useState(null);

  const derivedCount = enrichment.derived_features_count || enrichment.derived_features?.length || 0;
  const groups = enrichment.semantic_groups || [];
  const tables = enrichment.analytical_tables || [];
  const budget = enrichment.budget_summary || {};

  return (
    <div
      style={{
        marginTop: "1.25rem",
        background: "rgba(224, 86, 36, 0.04)",
        border: "1px solid rgba(224, 86, 36, 0.25)",
        borderRadius: "10px",
        padding: "1rem 1.25rem",
        fontSize: "0.85rem"
      }}
    >
      {/* Header */}
      <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", flexWrap: "wrap", gap: "0.5rem" }}>
        <div style={{ display: "flex", alignItems: "center", gap: "8px" }}>
          <Sparkles size={18} color="var(--brand-400)" />
          <strong style={{ fontSize: "0.98rem", color: "var(--brand-400)" }}>
            Controlled Semantic Enrichment & Scientific Discovery
          </strong>
          <span
            style={{
              fontSize: "0.75rem",
              background: "rgba(16, 185, 129, 0.15)",
              color: "var(--emerald-tier)",
              padding: "2px 8px",
              borderRadius: "12px",
              border: "1px solid rgba(16, 185, 129, 0.3)",
              display: "inline-flex",
              alignItems: "center",
              gap: "4px"
            }}
          >
            <CheckCircle2 size={12} /> Bounded & Audited
          </span>
        </div>

        {/* Resource Budget Metrics */}
        <div style={{ display: "flex", gap: "6px", flexWrap: "wrap", fontSize: "0.75rem" }}>
          <span className="filetype-badge" style={{ background: "rgba(255,255,255,0.06)", color: "var(--fg-secondary)" }}>
            <strong>Derived Columns:</strong> +{derivedCount} / {budget.max_derived_columns || 1000}
          </span>
          <span className="filetype-badge" style={{ background: "rgba(255,255,255,0.06)", color: "var(--fg-secondary)" }}>
            <strong>Tables:</strong> {tables.length} / {budget.max_generated_tables || 100}
          </span>
          <span className="filetype-badge" style={{ background: "rgba(255,255,255,0.06)", color: "var(--fg-secondary)" }}>
            <strong>Execution:</strong> {budget.elapsed_seconds || 0.2}s
          </span>
        </div>
      </div>

      <p style={{ marginTop: "6px", fontSize: "0.82rem", color: "var(--fg-secondary)" }}>
        Autonomous multi-role semantic profiling, isolated group clustering, SI unit standardizations,
        scientific formulas, and multi-dimensional analytical table synthesis.
      </p>

      {/* Navigation Tabs */}
      <div style={{ display: "flex", gap: "8px", marginTop: "1rem", borderBottom: "1px solid var(--border-subtle)", paddingBottom: "6px" }}>
        <button
          onClick={() => setActiveTab("features")}
          className="btn-secondary"
          style={{
            fontSize: "0.78rem",
            padding: "4px 10px",
            border: activeTab === "features" ? "1px solid var(--brand-400)" : "1px solid var(--border-subtle)",
            background: activeTab === "features" ? "rgba(224, 86, 36, 0.15)" : "transparent",
            color: activeTab === "features" ? "var(--brand-400)" : "var(--fg-secondary)",
            display: "inline-flex",
            alignItems: "center",
            gap: "5px"
          }}
        >
          <Zap size={13} />
          Derived Features ({derivedCount})
        </button>

        <button
          onClick={() => setActiveTab("groups")}
          className="btn-secondary"
          style={{
            fontSize: "0.78rem",
            padding: "4px 10px",
            border: activeTab === "groups" ? "1px solid var(--brand-400)" : "1px solid var(--border-subtle)",
            background: activeTab === "groups" ? "rgba(224, 86, 36, 0.15)" : "transparent",
            color: activeTab === "groups" ? "var(--brand-400)" : "var(--fg-secondary)",
            display: "inline-flex",
            alignItems: "center",
            gap: "5px"
          }}
        >
          <Layers size={13} />
          Semantic Groups ({groups.length})
        </button>

        <button
          onClick={() => setActiveTab("tables")}
          className="btn-secondary"
          style={{
            fontSize: "0.78rem",
            padding: "4px 10px",
            border: activeTab === "tables" ? "1px solid var(--brand-400)" : "1px solid var(--border-subtle)",
            background: activeTab === "tables" ? "rgba(224, 86, 36, 0.15)" : "transparent",
            color: activeTab === "tables" ? "var(--brand-400)" : "var(--fg-secondary)",
            display: "inline-flex",
            alignItems: "center",
            gap: "5px"
          }}
        >
          <Table size={13} />
          Analytical Tables ({tables.length})
        </button>
      </div>

      {/* Tab 1: Derived Features */}
      {activeTab === "features" && (
        <div style={{ marginTop: "0.75rem", maxHeight: "280px", overflowY: "auto" }}>
          {enrichment.derived_features && enrichment.derived_features.length > 0 ? (
            <table style={{ width: "100%", borderCollapse: "collapse", fontSize: "0.78rem" }}>
              <thead>
                <tr style={{ borderBottom: "1px solid var(--border)", color: "var(--fg-muted)", textAlign: "left" }}>
                  <th style={{ padding: "6px 8px" }}>Feature Name</th>
                  <th style={{ padding: "6px 8px" }}>Derivation Type</th>
                  <th style={{ padding: "6px 8px" }}>Expression</th>
                  <th style={{ padding: "6px 8px" }}>Unit</th>
                  <th style={{ padding: "6px 8px", textAlign: "right" }}>Utility</th>
                </tr>
              </thead>
              <tbody>
                {enrichment.derived_features.map((feat, idx) => (
                  <tr key={idx} style={{ borderBottom: "1px solid rgba(255,255,255,0.05)" }}>
                    <td style={{ padding: "6px 8px", color: "var(--brand-400)", fontWeight: 600 }}>
                      {feat.name}
                    </td>
                    <td style={{ padding: "6px 8px" }}>
                      <span className="filetype-badge" style={{ fontSize: "0.7rem", padding: "1px 6px" }}>
                        {feat.derivation_type}
                      </span>
                    </td>
                    <td style={{ padding: "6px 8px", color: "var(--accent-500)", fontFamily: "monospace" }}>
                      {feat.expression}
                    </td>
                    <td style={{ padding: "6px 8px", color: "var(--fg-secondary)" }}>
                      {feat.unit || "—"}
                    </td>
                    <td style={{ padding: "6px 8px", textAlign: "right", color: "var(--emerald-tier)" }}>
                      {(feat.utility_score * 100).toFixed(0)}%
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          ) : (
            <p style={{ color: "var(--fg-muted)", fontStyle: "italic", padding: "8px 0" }}>
              No derived features were required for this dataset.
            </p>
          )}
        </div>
      )}

      {/* Tab 2: Semantic Groups G1...Gf */}
      {activeTab === "groups" && (
        <div style={{ marginTop: "0.75rem", display: "grid", gridTemplateColumns: "repeat(auto-fill, minmax(260px, 1fr))", gap: "10px" }}>
          {groups.map((grp, idx) => (
            <div
              key={idx}
              style={{
                background: "rgba(0,0,0,0.3)",
                border: "1px solid var(--border-subtle)",
                borderRadius: "8px",
                padding: "10px"
              }}
            >
              <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
                <span style={{ fontWeight: 700, color: "var(--brand-400)", fontSize: "0.85rem" }}>
                  {grp.group_id}: {grp.group_name}
                </span>
                <span style={{ fontSize: "0.72rem", color: "var(--fg-muted)" }}>
                  Cohesion: {(grp.cohesion_score * 100).toFixed(0)}%
                </span>
              </div>
              <p style={{ fontSize: "0.76rem", color: "var(--fg-secondary)", marginTop: "4px" }}>
                {grp.domain_interpretation}
              </p>
              <div style={{ display: "flex", flexWrap: "wrap", gap: "4px", marginTop: "6px" }}>
                {grp.columns.map((c, cIdx) => (
                  <span
                    key={cIdx}
                    style={{
                      fontSize: "0.7rem",
                      background: "rgba(255,255,255,0.06)",
                      padding: "2px 6px",
                      borderRadius: "4px",
                      color: "var(--fg-primary)"
                    }}
                  >
                    {c}
                  </span>
                ))}
              </div>
            </div>
          ))}
        </div>
      )}

      {/* Tab 3: Synthesized Analytical Tables */}
      {activeTab === "tables" && (
        <div style={{ marginTop: "0.75rem", display: "flex", flexDirection: "column", gap: "10px" }}>
          {tables.map((tbl, idx) => {
            const isExp = expandedTable === tbl.table_id;
            return (
              <div
                key={idx}
                style={{
                  background: "rgba(0,0,0,0.3)",
                  border: "1px solid var(--border-subtle)",
                  borderRadius: "8px",
                  padding: "10px"
                }}
              >
                <div
                  onClick={() => setExpandedTable(isExp ? null : tbl.table_id)}
                  style={{ display: "flex", justifyContent: "space-between", alignItems: "center", cursor: "pointer" }}
                >
                  <div style={{ display: "flex", alignItems: "center", gap: "8px" }}>
                    {isExp ? <ChevronDown size={14} color="var(--brand-400)" /> : <ChevronRight size={14} color="var(--brand-400)" />}
                    <strong style={{ color: "var(--brand-400)", fontSize: "0.85rem" }}>{tbl.title}</strong>
                    <span className="filetype-badge" style={{ fontSize: "0.7rem" }}>
                      {tbl.row_count} rows × {tbl.col_count} cols
                    </span>
                  </div>
                  <span style={{ fontSize: "0.74rem", color: "var(--emerald-tier)" }}>
                    Utility: {(tbl.utility_score * 100).toFixed(0)}%
                  </span>
                </div>

                <p style={{ fontSize: "0.78rem", color: "var(--fg-secondary)", marginTop: "4px", marginLeft: "22px" }}>
                  {tbl.description}
                </p>

                {isExp && tbl.data_preview && tbl.data_preview.length > 0 && (
                  <div style={{ marginTop: "10px", overflowX: "auto", borderRadius: "6px", border: "1px solid var(--border-subtle)" }}>
                    <table style={{ width: "100%", borderCollapse: "collapse", fontSize: "0.75rem" }}>
                      <thead>
                        <tr style={{ background: "#15110f", borderBottom: "1px solid var(--border)" }}>
                          {tbl.columns.map((c, colIdx) => (
                            <th key={colIdx} style={{ padding: "6px 10px", textAlign: "left", color: "var(--brand-400)" }}>
                              {c}
                            </th>
                          ))}
                        </tr>
                      </thead>
                      <tbody>
                        {tbl.data_preview.map((row, rIdx) => (
                          <tr key={rIdx} style={{ borderBottom: "1px solid rgba(255,255,255,0.05)" }}>
                            {tbl.columns.map((c, colIdx) => (
                              <td key={colIdx} style={{ padding: "6px 10px", color: "var(--fg-primary)" }}>
                                {String(row[c] !== undefined ? row[c] : "—")}
                              </td>
                            ))}
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                )}
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
}
