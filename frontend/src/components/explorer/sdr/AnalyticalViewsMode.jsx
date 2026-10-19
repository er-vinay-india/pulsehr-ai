import React, { useState, useEffect } from "react";
import { getExplorerAnalyticalViews } from "../../../api/client";
import LineageDrawer from "./LineageDrawer";
import {
  LayoutDashboard,
  ShieldCheck,
  AlertTriangle,
  Award,
  GitBranch,
  Layers,
  CheckCircle2,
  Lock,
  Clock,
  ArrowRight,
  Eye,
  AlertCircle,
} from "lucide-react";

export default function AnalyticalViewsMode({
  datasetId,
  themeTokens,
  isDark = false,
}) {
  const [viewsData, setViewsData] = useState(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);
  const [selectedViewId, setSelectedViewId] = useState(null);
  const [selectedFact, setSelectedFact] = useState(null);

  useEffect(() => {
    if (!datasetId) return;
    let isCancelled = false;

    async function loadViews() {
      setLoading(true);
      setError(null);
      try {
        const res = await getExplorerAnalyticalViews(datasetId);
        if (!isCancelled) {
          setViewsData(res);
          if (res?.views?.length > 0) {
            setSelectedViewId(res.views[0].view_id);
          }
        }
      } catch (err) {
        if (!isCancelled) {
          setError(err.message || "Failed to load analytical views");
        }
      } finally {
        if (!isCancelled) {
          setLoading(false);
        }
      }
    }

    loadViews();
    return () => {
      isCancelled = true;
    };
  }, [datasetId]);

  const bgCard = isDark ? "#1e293b" : "#ffffff";
  const borderCol = isDark ? "#334155" : "#e2e8f0";
  const textPrimary = isDark ? "#f8fafc" : "#0f172a";
  const textSecondary = isDark ? "#94a3b8" : "#64748b";
  const bgSubtle = isDark ? "#0f172a" : "#f8fafc";

  const allViews = viewsData?.views || [];
  const allFacts = viewsData?.facts || [];

  const activeView = allViews.find((v) => v.view_id === selectedViewId) || allViews[0];
  const filteredFacts = allFacts.filter((f) => !selectedViewId || f.analytical_view_id === selectedViewId);

  return (
    <div className="sdr-analytical-views-mode-container" style={{ display: "flex", flexDirection: "column", gap: "16px" }}>
      {/* Header & Governance Banner */}
      <div
        style={{
          background: isDark ? "rgba(30, 41, 59, 0.7)" : "#ffffff",
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
            <LayoutDashboard size={18} color="#2563eb" />
            <h2 style={{ margin: 0, fontSize: "1.1rem", fontWeight: 700, color: textPrimary }}>
              Governed Analytical Views & Gold Facts (SDR-6)
            </h2>
          </div>
          <div style={{ display: "flex", alignItems: "center", gap: "8px", flexWrap: "wrap" }}>
            <span
              style={{
                fontSize: "0.75rem",
                fontWeight: 600,
                padding: "3px 8px",
                borderRadius: "6px",
                background: "rgba(16, 185, 129, 0.12)",
                color: "#10b981",
                border: "1px solid rgba(16, 185, 129, 0.3)",
              }}
            >
              Default Virtual Materialization
            </span>
            <span
              style={{
                fontSize: "0.75rem",
                fontWeight: 600,
                padding: "3px 8px",
                borderRadius: "6px",
                background: "rgba(239, 68, 68, 0.12)",
                color: "#ef4444",
                border: "1px solid rgba(239, 68, 68, 0.3)",
              }}
            >
              Stale Views Blocked from Serving
            </span>
          </div>
        </div>
        <p style={{ margin: 0, fontSize: "0.82rem", color: textSecondary }}>
          Inspect reconstructed multi-table analytical views, freshness statuses, exact Gold metric facts, and complete provenance lineage paths.
        </p>

        {/* View Selection Tabs */}
        <div style={{ display: "flex", alignItems: "center", gap: "6px", overflowX: "auto", paddingTop: "4px" }}>
          {allViews.map((v) => {
            const isSelected = v.view_id === selectedViewId;
            return (
              <button
                key={v.view_id}
                type="button"
                onClick={() => setSelectedViewId(v.view_id)}
                style={{
                  padding: "6px 12px",
                  fontSize: "0.8rem",
                  fontWeight: isSelected ? 700 : 500,
                  borderRadius: "8px",
                  border: isSelected ? "1px solid #2563eb" : `1px solid ${borderCol}`,
                  background: isSelected ? (isDark ? "rgba(37, 99, 235, 0.2)" : "rgba(37, 99, 235, 0.08)") : "transparent",
                  color: isSelected ? "#2563eb" : textSecondary,
                  cursor: "pointer",
                  whiteSpace: "nowrap",
                  display: "inline-flex",
                  alignItems: "center",
                  gap: "6px",
                }}
              >
                {v.is_stale && <AlertTriangle size={12} color="#ef4444" />}
                <span>{v.name}</span>
              </button>
            );
          })}
        </div>
      </div>

      {loading ? (
        <div style={{ padding: "40px", textAlign: "center", color: textSecondary, fontSize: "0.9rem" }}>
          Loading analytical views…
        </div>
      ) : error ? (
        <div
          style={{
            padding: "16px",
            background: "rgba(239, 68, 68, 0.1)",
            border: "1px solid rgba(239, 68, 68, 0.3)",
            borderRadius: "8px",
            color: "#ef4444",
            display: "flex",
            alignItems: "center",
            gap: "8px",
            fontSize: "0.85rem",
          }}
        >
          <AlertCircle size={16} />
          <span>{error}</span>
        </div>
      ) : activeView ? (
        <>
          {/* Active View Specification Card */}
          <div
            style={{
              background: bgCard,
              border: `1px solid ${borderCol}`,
              borderRadius: "10px",
              padding: "16px",
              display: "flex",
              flexDirection: "column",
              gap: "12px",
            }}
          >
            {/* Stale Warning Banner if stale */}
            {activeView.is_stale && (
              <div
                style={{
                  background: "rgba(239, 68, 68, 0.12)",
                  border: "1px solid rgba(239, 68, 68, 0.35)",
                  borderRadius: "8px",
                  padding: "12px 14px",
                  color: "#ef4444",
                  display: "flex",
                  alignItems: "flex-start",
                  gap: "10px",
                }}
              >
                <AlertTriangle size={18} style={{ flexShrink: 0, marginTop: "2px" }} />
                <div>
                  <div style={{ fontWeight: 700, fontSize: "0.88rem" }}>
                    STALE ANALYTICAL VIEW BLOCKED FROM SERVING
                  </div>
                  <div style={{ fontSize: "0.8rem", marginTop: "2px", opacity: 0.9 }}>
                    {activeView.rejection_reason || "Upstream dependency drift detected. This view cannot be served as current truth until re-verified."}
                  </div>
                </div>
              </div>
            )}

            <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start", flexWrap: "wrap", gap: "10px" }}>
              <div>
                <div style={{ fontSize: "1.1rem", fontWeight: 700, color: textPrimary }}>
                  {activeView.name}
                </div>
                <div style={{ fontSize: "0.78rem", color: textSecondary, marginTop: "2px" }}>
                  View ID: <code>{activeView.view_id}</code> · Result Grain: <strong>{activeView.result_grain}</strong>
                </div>
              </div>
              <div style={{ display: "flex", alignItems: "center", gap: "8px" }}>
                <span
                  style={{
                    fontSize: "0.75rem",
                    fontWeight: 700,
                    padding: "3px 8px",
                    borderRadius: "6px",
                    background: activeView.is_stale ? "rgba(239, 68, 68, 0.12)" : "rgba(16, 185, 129, 0.12)",
                    color: activeView.is_stale ? "#ef4444" : "#10b981",
                    border: activeView.is_stale ? "1px solid rgba(239, 68, 68, 0.3)" : "1px solid rgba(16, 185, 129, 0.3)",
                  }}
                >
                  Status: {activeView.status}
                </span>
                <span
                  style={{
                    fontSize: "0.75rem",
                    fontWeight: 600,
                    padding: "3px 8px",
                    borderRadius: "6px",
                    background: bgSubtle,
                    color: textSecondary,
                    border: `1px solid ${borderCol}`,
                  }}
                >
                  {activeView.materialization_mode}
                </span>
              </div>
            </div>

            {/* View Architecture Metadata Grid */}
            <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(200px, 1fr))", gap: "10px" }}>
              <div style={{ padding: "8px 12px", background: bgSubtle, borderRadius: "6px", border: `1px solid ${borderCol}` }}>
                <div style={{ fontSize: "0.7rem", color: textSecondary }}>Source Sheets</div>
                <div style={{ fontSize: "0.85rem", fontWeight: 600, color: textPrimary, marginTop: "2px" }}>
                  {activeView.source_sheets.join(", ")}
                </div>
              </div>
              <div style={{ padding: "8px 12px", background: bgSubtle, borderRadius: "6px", border: `1px solid ${borderCol}` }}>
                <div style={{ fontSize: "0.7rem", color: textSecondary }}>JoinPlans Used</div>
                <div style={{ fontSize: "0.85rem", fontWeight: 600, color: textPrimary, marginTop: "2px" }}>
                  {activeView.join_plan_ids.length > 0 ? activeView.join_plan_ids.join(", ") : "Single-sheet (0 JoinPlans)"}
                </div>
              </div>
              <div style={{ padding: "8px 12px", background: bgSubtle, borderRadius: "6px", border: `1px solid ${borderCol}` }}>
                <div style={{ fontSize: "0.7rem", color: textSecondary }}>Dimensions</div>
                <div style={{ fontSize: "0.85rem", fontWeight: 600, color: textPrimary, marginTop: "2px" }}>
                  {activeView.dimension_columns.join(", ") || "None"}
                </div>
              </div>
              <div style={{ padding: "8px 12px", background: bgSubtle, borderRadius: "6px", border: `1px solid ${borderCol}` }}>
                <div style={{ fontSize: "0.7rem", color: textSecondary }}>Measures</div>
                <div style={{ fontSize: "0.85rem", fontWeight: 600, color: textPrimary, marginTop: "2px" }}>
                  {activeView.measure_columns.join(", ") || "None"}
                </div>
              </div>
            </div>

            {/* Derived Measures / Formulas */}
            {activeView.derived_measures && activeView.derived_measures.length > 0 && (
              <div style={{ borderTop: `1px solid ${borderCol}`, paddingTop: "10px" }}>
                <div style={{ fontSize: "0.75rem", color: textSecondary, fontWeight: 700, marginBottom: "6px" }}>
                  DERIVED MEASURE FORMULAS
                </div>
                <div style={{ display: "flex", flexWrap: "wrap", gap: "8px" }}>
                  {activeView.derived_measures.map((dm, i) => (
                    <div
                      key={i}
                      style={{
                        padding: "6px 12px",
                        borderRadius: "6px",
                        background: bgSubtle,
                        border: `1px solid ${borderCol}`,
                        fontSize: "0.8rem",
                      }}
                    >
                      <strong style={{ color: "#2563eb" }}>{dm.measure_name}</strong> = <code>{dm.formula_repr}</code> {dm.unit && <span style={{ color: textSecondary }}>[{dm.unit}]</span>}
                    </div>
                  ))}
                </div>
              </div>
            )}
          </div>

          {/* Analytical Facts Table */}
          <div style={{ background: bgCard, border: `1px solid ${borderCol}`, borderRadius: "10px", overflow: "hidden" }}>
            <div style={{ padding: "14px 16px", borderBottom: `1px solid ${borderCol}`, display: "flex", justifyContent: "space-between", alignItems: "center" }}>
              <div style={{ display: "flex", alignItems: "center", gap: "8px" }}>
                <Award size={16} color="#f59e0b" />
                <h3 style={{ margin: 0, fontSize: "0.95rem", fontWeight: 700, color: textPrimary }}>
                  Governed Gold Metric Facts ({filteredFacts.length} facts)
                </h3>
              </div>
              <span style={{ fontSize: "0.75rem", color: textSecondary }}>
                Click "Lineage" to view complete reconstruction steps
              </span>
            </div>

            {filteredFacts.length === 0 ? (
              <div style={{ padding: "30px", textAlign: "center", color: textSecondary, fontSize: "0.85rem" }}>
                No facts materialized for this view.
              </div>
            ) : (
              <div style={{ overflowX: "auto" }}>
                <table style={{ width: "100%", borderCollapse: "collapse", fontSize: "0.82rem", textAlign: "left" }}>
                  <thead>
                    <tr style={{ background: isDark ? "#0f172a" : "#f8fafc", borderBottom: `2px solid ${borderCol}` }}>
                      <th style={{ padding: "10px 12px", color: textPrimary, fontWeight: 700 }}>Metric</th>
                      <th style={{ padding: "10px 12px", color: textPrimary, fontWeight: 700 }}>Exact Value</th>
                      <th style={{ padding: "10px 12px", color: textPrimary, fontWeight: 700 }}>Unit</th>
                      <th style={{ padding: "10px 12px", color: textPrimary, fontWeight: 700 }}>Result Grain</th>
                      <th style={{ padding: "10px 12px", color: textPrimary, fontWeight: 700 }}>Provenance Authority</th>
                      <th style={{ padding: "10px 12px", color: textSecondary, fontWeight: 700, textAlign: "right" }}>Lineage</th>
                    </tr>
                  </thead>
                  <tbody>
                    {filteredFacts.map((fact, idx) => (
                      <tr
                        key={fact.fact_id || idx}
                        style={{
                          borderBottom: `1px solid ${borderCol}`,
                          background: idx % 2 === 1 ? (isDark ? "rgba(255,255,255,0.02)" : "rgba(0,0,0,0.015)") : "transparent",
                        }}
                      >
                        <td style={{ padding: "10px 12px", fontWeight: 600, color: textPrimary }}>
                          {fact.metric}
                        </td>
                        <td style={{ padding: "10px 12px", fontFamily: "monospace", fontSize: "0.88rem", fontWeight: 700, color: textPrimary }}>
                          {fact.formatted_value || fact.value}
                        </td>
                        <td style={{ padding: "10px 12px", color: textSecondary }}>
                          {fact.unit || "—"}
                        </td>
                        <td style={{ padding: "10px 12px", color: textSecondary }}>
                          {fact.grain}
                        </td>
                        <td style={{ padding: "10px 12px" }}>
                          <span
                            style={{
                              padding: "2px 6px",
                              borderRadius: "4px",
                              fontSize: "0.72rem",
                              fontWeight: 600,
                              background: "rgba(37, 99, 235, 0.1)",
                              color: "#2563eb",
                            }}
                          >
                            {fact.provenance}
                          </span>
                        </td>
                        <td style={{ padding: "10px 12px", textAlign: "right" }}>
                          <button
                            type="button"
                            onClick={() => setSelectedFact(fact)}
                            style={{
                              padding: "4px 8px",
                              fontSize: "0.75rem",
                              fontWeight: 600,
                              borderRadius: "6px",
                              border: `1px solid ${borderCol}`,
                              background: bgSubtle,
                              color: "#2563eb",
                              cursor: "pointer",
                              display: "inline-flex",
                              alignItems: "center",
                              gap: "4px",
                            }}
                          >
                            <GitBranch size={12} />
                            Lineage Path
                          </button>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          </div>
        </>
      ) : null}

      {/* Step-by-Step Fact Lineage Drawer */}
      {selectedFact && (
        <LineageDrawer
          fact={selectedFact}
          onClose={() => setSelectedFact(null)}
          isDark={isDark}
        />
      )}
    </div>
  );
}
