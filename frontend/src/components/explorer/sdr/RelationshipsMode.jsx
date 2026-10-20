import React, { useState, useEffect } from "react";
import { getExplorerRelationships } from "../../../api/client";
import {
  GitMerge,
  ShieldCheck,
  ShieldAlert,
  AlertTriangle,
  ArrowRight,
  Filter,
  CheckCircle2,
  XCircle,
  HelpCircle,
  Layers,
  Zap,
  AlertCircle,
} from "lucide-react";

export default function RelationshipsMode({
  datasetId,
  themeTokens,
  isDark = false,
}) {
  const [relData, setRelData] = useState(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);
  const [statusFilter, setStatusFilter] = useState("ALL"); // "ALL", "VALIDATED", "REJECTED"
  const [safetyFilter, setSafetyFilter] = useState("ALL"); // "ALL", "SAFE", "SAFE_WITH_PREAGGREGATION", "UNSAFE"
  const [selectedRel, setSelectedRel] = useState(null);

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
          if (res?.relationships?.length > 0) {
            setSelectedRel(res.relationships[0]);
          }
        }
      } catch (err) {
        if (!isCancelled) {
          setError(err.message || "Failed to load relationship intelligence");
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

  const bgCard = isDark ? "#1e293b" : "#ffffff";
  const borderCol = isDark ? "#334155" : "#e2e8f0";
  const textPrimary = isDark ? "#f8fafc" : "#0f172a";
  const textSecondary = isDark ? "#94a3b8" : "#64748b";
  const bgSubtle = isDark ? "#0f172a" : "#f8fafc";

  const allRelationships = relData?.relationships || [];

  const filteredRelationships = allRelationships.filter((rel) => {
    if (statusFilter !== "ALL") {
      const isVal = rel.status_raw === "VALIDATED";
      if (statusFilter === "VALIDATED" && !isVal) return false;
      if (statusFilter === "REJECTED" && isVal) return false;
    }
    if (safetyFilter !== "ALL") {
      if (rel.safety_status_raw !== safetyFilter) return false;
    }
    return true;
  });

  const getSafetyBadgeStyle = (status) => {
    switch (status) {
      case "SAFE":
        return { bg: "rgba(16, 185, 129, 0.12)", border: "rgba(16, 185, 129, 0.3)", text: "#10b981", label: "Safe to join" };
      case "SAFE_WITH_PREAGGREGATION":
        return { bg: "rgba(37, 99, 235, 0.12)", border: "rgba(37, 99, 235, 0.3)", text: "#2563eb", label: "Safe after aggregation" };
      case "UNSAFE":
        return { bg: "rgba(239, 68, 68, 0.12)", border: "rgba(239, 68, 68, 0.3)", text: "#ef4444", label: "Unsafe to join" };
      default:
        return { bg: "rgba(245, 158, 11, 0.12)", border: "rgba(245, 158, 11, 0.3)", text: "#f59e0b", label: "Needs review" };
    }
  };

  return (
    <div className="sdr-relationships-mode-container" style={{ display: "flex", flexDirection: "column", gap: "16px" }}>
      {/* Header */}
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
            <GitMerge size={18} color="#2563eb" />
            <h2 style={{ margin: 0, fontSize: "1.1rem", fontWeight: 700, color: textPrimary }}>
              Governed Relationships & Join Safety (SDR-5)
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
              Zero Ungoverned Joins
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
              Cartesian Multipliers Blocked
            </span>
          </div>
        </div>
        <p style={{ margin: 0, fontSize: "0.82rem", color: textSecondary }}>
          Inspect validated relationship edges, referential coverage, fanout prevention rules, and plain-English join safety assessments.
        </p>

        {/* Filter Controls */}
        <div style={{ display: "flex", alignItems: "center", gap: "12px", flexWrap: "wrap", paddingTop: "4px" }}>
          <div style={{ display: "flex", alignItems: "center", gap: "6px" }}>
            <span style={{ fontSize: "0.75rem", color: textSecondary, fontWeight: 600 }}>Status:</span>
            {["ALL", "VALIDATED", "REJECTED"].map((st) => (
              <button
                key={st}
                type="button"
                onClick={() => setStatusFilter(st)}
                style={{
                  padding: "4px 10px",
                  fontSize: "0.75rem",
                  fontWeight: statusFilter === st ? 700 : 500,
                  borderRadius: "6px",
                  border: statusFilter === st ? "1px solid #2563eb" : `1px solid ${borderCol}`,
                  background: statusFilter === st ? (isDark ? "rgba(37, 99, 235, 0.2)" : "rgba(37, 99, 235, 0.08)") : "transparent",
                  color: statusFilter === st ? "#2563eb" : textSecondary,
                  cursor: "pointer",
                }}
              >
                {st === "ALL" ? "All Statuses" : st.toLowerCase()}
              </button>
            ))}
          </div>

          <div style={{ display: "flex", alignItems: "center", gap: "6px" }}>
            <span style={{ fontSize: "0.75rem", color: textSecondary, fontWeight: 600 }}>Safety:</span>
            {[
              { id: "ALL", label: "All" },
              { id: "SAFE", label: "Safe" },
              { id: "SAFE_WITH_PREAGGREGATION", label: "After Aggregation" },
              { id: "UNSAFE", label: "Unsafe" },
            ].map((sf) => (
              <button
                key={sf.id}
                type="button"
                onClick={() => setSafetyFilter(sf.id)}
                style={{
                  padding: "4px 10px",
                  fontSize: "0.75rem",
                  fontWeight: safetyFilter === sf.id ? 700 : 500,
                  borderRadius: "6px",
                  border: safetyFilter === sf.id ? "1px solid #2563eb" : `1px solid ${borderCol}`,
                  background: safetyFilter === sf.id ? (isDark ? "rgba(37, 99, 235, 0.2)" : "rgba(37, 99, 235, 0.08)") : "transparent",
                  color: safetyFilter === sf.id ? "#2563eb" : textSecondary,
                  cursor: "pointer",
                }}
              >
                {sf.label}
              </button>
            ))}
          </div>
        </div>
      </div>

      {loading ? (
        <div style={{ padding: "40px", textAlign: "center", color: textSecondary, fontSize: "0.9rem" }}>
          Loading relationship topology…
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
      ) : allRelationships.length === 0 ? (
        <section
          className="explorer-empty-state explorer-empty-state--compact"
          style={{
            background: bgCard,
            border: `1px solid ${borderCol}`,
            borderRadius: "10px",
            padding: "36px 20px",
            textAlign: "center",
          }}
        >
          <div
            style={{
              display: "inline-flex",
              padding: "12px",
              borderRadius: "50%",
              background: isDark ? "rgba(37, 99, 235, 0.15)" : "rgba(37, 99, 235, 0.08)",
              marginBottom: "12px",
            }}
          >
            <GitMerge size={28} color="#2563eb" />
          </div>
          <h3 style={{ fontSize: "1.05rem", fontWeight: 700, color: textPrimary, margin: "0 0 6px 0" }}>
            No Governed Cross-Sheet Relationships
          </h3>
          <p style={{ fontSize: "0.85rem", color: textSecondary, maxWidth: "480px", margin: "0 auto", lineHeight: 1.5 }}>
            This dataset either has a single table or contains no validated cross-sheet join candidates. Relationships require strict key identity validation under SDR-5.
          </p>
        </section>
      ) : (
        <div style={{ display: "grid", gridTemplateColumns: "1.2fr 1fr", gap: "16px" }}>
          {/* Relationships List / Graph */}
          <div style={{ display: "flex", flexDirection: "column", gap: "10px" }}>
            {filteredRelationships.length === 0 ? (
              <div style={{ background: bgCard, border: `1px solid ${borderCol}`, borderRadius: "10px", padding: "30px", textAlign: "center", color: textSecondary, fontSize: "0.85rem" }}>
                No relationships matched the selected filters.
              </div>
            ) : (
              filteredRelationships.map((rel, idx) => {
                const isSelected = selectedRel && (selectedRel.relationship_id === rel.relationship_id || (selectedRel.left_sheet === rel.left_sheet && selectedRel.right_sheet === rel.right_sheet));
                const badge = getSafetyBadgeStyle(rel.safety_status_raw);
                return (
                  <div
                    key={rel.relationship_id || idx}
                    onClick={() => setSelectedRel(rel)}
                    style={{
                      background: bgCard,
                      border: isSelected ? "2px solid #2563eb" : `1px solid ${borderCol}`,
                      borderRadius: "10px",
                      padding: "14px 16px",
                      cursor: "pointer",
                      display: "flex",
                      flexDirection: "column",
                      gap: "10px",
                      transition: "all 0.15s ease",
                      boxShadow: isSelected ? "0 4px 12px rgba(37,99,235,0.12)" : "none",
                    }}
                  >
                    <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
                      <div style={{ display: "flex", alignItems: "center", gap: "8px" }}>
                        <span style={{ fontSize: "0.95rem", fontWeight: 700, color: textPrimary }}>
                          {rel.left_sheet}
                        </span>
                        <ArrowRight size={14} color={textSecondary} />
                        <span style={{ fontSize: "0.95rem", fontWeight: 700, color: textPrimary }}>
                          {rel.right_sheet}
                        </span>
                      </div>
                      <span
                        style={{
                          fontSize: "0.72rem",
                          fontWeight: 700,
                          padding: "2px 8px",
                          borderRadius: "6px",
                          background: badge.bg,
                          border: `1px solid ${badge.border}`,
                          color: badge.text,
                        }}
                      >
                        {rel.safety_status}
                      </span>
                    </div>

                    <div style={{ display: "flex", alignItems: "center", gap: "12px", fontSize: "0.78rem", color: textSecondary }}>
                      <span>Keys: <code>{rel.left_columns.join(", ")}</code> = <code>{rel.right_columns.join(", ")}</code></span>
                      <span>·</span>
                      <span>{rel.cardinality}</span>
                      <span>·</span>
                      <span>{rel.coverage_summary}</span>
                    </div>

                    {/* Preagg or Unsafe explanation snippet */}
                    {rel.preaggregation_explanation && (
                      <div style={{ fontSize: "0.75rem", color: "#2563eb", background: "rgba(37, 99, 235, 0.06)", padding: "6px 10px", borderRadius: "6px" }}>
                        💡 {rel.preaggregation_explanation}
                      </div>
                    )}
                    {rel.unsafe_explanation && (
                      <div style={{ fontSize: "0.75rem", color: "#ef4444", background: "rgba(239, 68, 68, 0.06)", padding: "6px 10px", borderRadius: "6px" }}>
                        ⚠️ {rel.unsafe_explanation}
                      </div>
                    )}
                  </div>
                );
              })
            )}
          </div>

          {/* Selected Relationship Deep Dive Panel */}
          {selectedRel ? (
            <div
              style={{
                background: bgCard,
                border: `1px solid ${borderCol}`,
                borderRadius: "10px",
                padding: "16px",
                display: "flex",
                flexDirection: "column",
                gap: "16px",
                position: "sticky",
                top: "16px",
                height: "fit-content",
              }}
            >
              <div style={{ borderBottom: `1px solid ${borderCol}`, paddingBottom: "12px" }}>
                <div style={{ fontSize: "0.75rem", color: textSecondary, textTransform: "uppercase", fontWeight: 700 }}>
                  Relationship Governance Specification
                </div>
                <div style={{ fontSize: "1.1rem", fontWeight: 700, color: textPrimary, marginTop: "4px" }}>
                  {selectedRel.left_sheet} ➔ {selectedRel.right_sheet}
                </div>
                <div style={{ fontSize: "0.78rem", color: textSecondary, marginTop: "2px" }}>
                  JoinPlan ID: <code>{selectedRel.join_plan_id || "Unplanned"}</code>
                </div>
              </div>

              {/* Safety Evaluation Card */}
              {(() => {
                const badge = getSafetyBadgeStyle(selectedRel.safety_status_raw);
                return (
                  <div style={{ background: badge.bg, border: `1px solid ${badge.border}`, borderRadius: "8px", padding: "12px" }}>
                    <div style={{ display: "flex", alignItems: "center", gap: "6px", color: badge.text, fontWeight: 700, fontSize: "0.85rem" }}>
                      {selectedRel.safety_status_raw === "SAFE" ? (
                        <CheckCircle2 size={16} />
                      ) : selectedRel.safety_status_raw === "UNSAFE" ? (
                        <ShieldAlert size={16} />
                      ) : (
                        <Zap size={16} />
                      )}
                      <span>Join Safety: {selectedRel.safety_status}</span>
                    </div>

                    {selectedRel.preaggregation_explanation && (
                      <div style={{ fontSize: "0.78rem", color: textPrimary, marginTop: "8px", lineHeight: "1.4" }}>
                        <strong>Governance Requirement:</strong> {selectedRel.preaggregation_explanation}
                      </div>
                    )}

                    {selectedRel.unsafe_explanation && (
                      <div style={{ fontSize: "0.78rem", color: "#ef4444", marginTop: "8px", lineHeight: "1.4" }}>
                        <strong>Safety Risk:</strong> {selectedRel.unsafe_explanation}
                      </div>
                    )}
                  </div>
                );
              })()}

              {/* Referential Metrics */}
              <div>
                <h4 style={{ margin: "0 0 8px 0", fontSize: "0.8rem", color: textSecondary, textTransform: "uppercase" }}>
                  Referential & Grain Evidence
                </h4>
                <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: "8px" }}>
                  <div style={{ padding: "8px", background: bgSubtle, borderRadius: "6px", border: `1px solid ${borderCol}` }}>
                    <div style={{ fontSize: "0.7rem", color: textSecondary }}>Left Coverage</div>
                    <div style={{ fontSize: "0.85rem", fontWeight: 700, color: textPrimary }}>{selectedRel.coverage_left_pct}%</div>
                  </div>
                  <div style={{ padding: "8px", background: bgSubtle, borderRadius: "6px", border: `1px solid ${borderCol}` }}>
                    <div style={{ fontSize: "0.7rem", color: textSecondary }}>Right Coverage</div>
                    <div style={{ fontSize: "0.85rem", fontWeight: 700, color: textPrimary }}>{selectedRel.coverage_right_pct}%</div>
                  </div>
                  <div style={{ padding: "8px", background: bgSubtle, borderRadius: "6px", border: `1px solid ${borderCol}` }}>
                    <div style={{ fontSize: "0.7rem", color: textSecondary }}>Cardinality</div>
                    <div style={{ fontSize: "0.85rem", fontWeight: 700, color: textPrimary }}>{selectedRel.cardinality}</div>
                  </div>
                  <div style={{ padding: "8px", background: bgSubtle, borderRadius: "6px", border: `1px solid ${borderCol}` }}>
                    <div style={{ fontSize: "0.7rem", color: textSecondary }}>Result Grain</div>
                    <div style={{ fontSize: "0.85rem", fontWeight: 700, color: textPrimary }}>{selectedRel.result_grain}</div>
                  </div>
                </div>
              </div>

              {/* Risk Flags if any */}
              {selectedRel.risk_flags && selectedRel.risk_flags.length > 0 && (
                <div>
                  <h4 style={{ margin: "0 0 6px 0", fontSize: "0.8rem", color: textSecondary, textTransform: "uppercase" }}>
                    Detected Risk Flags
                  </h4>
                  <div style={{ display: "flex", flexWrap: "wrap", gap: "6px" }}>
                    {selectedRel.risk_flags.map((rf, i) => (
                      <span
                        key={i}
                        style={{
                          fontSize: "0.72rem",
                          fontWeight: 600,
                          padding: "2px 6px",
                          borderRadius: "4px",
                          background: "rgba(239, 68, 68, 0.1)",
                          color: "#ef4444",
                          border: "1px solid rgba(239, 68, 68, 0.3)",
                        }}
                      >
                        {rf}
                      </span>
                    ))}
                  </div>
                </div>
              )}
            </div>
          ) : (
            <div style={{ background: bgCard, border: `1px solid ${borderCol}`, borderRadius: "10px", padding: "30px", textAlign: "center", color: textSecondary, fontSize: "0.85rem" }}>
              Select a relationship on the left to inspect its join plan and safety proofs.
            </div>
          )}
        </div>
      )}
    </div>
  );
}
