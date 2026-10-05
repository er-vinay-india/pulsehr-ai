import React, { useState } from "react";
import { Sparkles, ShieldCheck, Database, CheckCircle2, ChevronDown, ChevronUp, ExternalLink, ArrowRight } from "lucide-react";
import { SurfaceGuard } from "../guard";

const CAUSAL_COLORS = {
  OBSERVED: { bg: "rgba(16, 185, 129, 0.12)", text: "#10b981", border: "rgba(16, 185, 129, 0.3)" },
  ASSOCIATED: { bg: "rgba(6, 182, 212, 0.12)", text: "#06b6d4", border: "rgba(6, 182, 212, 0.3)" },
  INFERRED: { bg: "rgba(99, 102, 241, 0.12)", text: "#6366f1", border: "rgba(99, 102, 241, 0.3)" },
  HYPOTHESIS: { bg: "rgba(245, 158, 11, 0.12)", text: "#f59e0b", border: "rgba(245, 158, 11, 0.3)" },
};

export default function EvidenceStoryCard({ storyPlan, evidenceGraph, snapshot }) {
  const [selectedEvidId, setSelectedEvidId] = useState(null);
  const [showAllNodes, setShowAllNodes] = useState(false);

  if (!storyPlan || !evidenceGraph) return null;

  const nodes = evidenceGraph.nodes || [];
  const selectedNode = nodes.find((n) => n.evidence_id === selectedEvidId);

  return (
    <SurfaceGuard.Card
      className="adaptive-element-card evidence-story-card"
      style={{
        marginTop: "1.5rem",
        padding: "1.5rem",
        background: "var(--card-bg, #1e293b)",
        borderRadius: "12px",
        border: "1px solid var(--border-color, #334155)",
      }}
    >
      {/* Header */}
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start", flexWrap: "wrap", gap: "1rem", marginBottom: "1rem" }}>
        <div style={{ display: "flex", alignItems: "center", gap: "12px" }}>
          <div style={{ background: "rgba(99, 102, 241, 0.15)", color: "#818cf8", padding: "10px", borderRadius: "10px" }}>
            <Sparkles size={22} />
          </div>
          <div>
            <div style={{ display: "flex", alignItems: "center", gap: "8px" }}>
              <h3 style={{ margin: 0, fontSize: "1.15rem", fontWeight: 700, color: "var(--fg-primary, #f8fafc)" }}>
                {storyPlan.narrative_angle || "Governed Decision Storyboard"}
              </h3>
              <span
                style={{
                  fontSize: "0.7rem",
                  fontWeight: 600,
                  padding: "2px 8px",
                  borderRadius: "12px",
                  background: "rgba(16, 185, 129, 0.15)",
                  color: "#34d399",
                  border: "1px solid rgba(16, 185, 129, 0.3)",
                  display: "inline-flex",
                  alignItems: "center",
                  gap: "4px",
                }}
              >
                <ShieldCheck size={12} /> Zero-Hallucination Evidence Graph
              </span>
            </div>
            <p style={{ margin: "4px 0 0 0", fontSize: "0.85rem", color: "var(--fg-muted, #94a3b8)" }}>
              {storyPlan.executive_summary}
            </p>
          </div>
        </div>

        {snapshot && (
          <div style={{ fontSize: "0.72rem", color: "var(--fg-subtle, #64748b)", fontFamily: "monospace" }}>
            Snapshot: {snapshot.slice(0, 10)}
          </div>
        )}
      </div>

      {/* Grounded Claims List */}
      <div style={{ display: "flex", flexDirection: "column", gap: "0.85rem", marginTop: "1.25rem" }}>
        {storyPlan.claims?.map((claim) => {
          const causalStyle = CAUSAL_COLORS[claim.causal_type] || CAUSAL_COLORS.OBSERVED;
          return (
            <div
              key={claim.claim_id}
              style={{
                background: "rgba(15, 23, 42, 0.6)",
                border: "1px solid var(--border-color, #334155)",
                borderRadius: "8px",
                padding: "1rem",
              }}
            >
              <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: "6px" }}>
                <div style={{ display: "flex", alignItems: "center", gap: "8px" }}>
                  <span style={{ fontSize: "0.75rem", fontWeight: 700, color: "#818cf8", fontFamily: "monospace" }}>
                    {claim.claim_id}
                  </span>
                  <span
                    style={{
                      fontSize: "0.68rem",
                      fontWeight: 700,
                      padding: "2px 6px",
                      borderRadius: "4px",
                      background: causalStyle.bg,
                      color: causalStyle.text,
                      border: `1px solid ${causalStyle.border}`,
                    }}
                  >
                    {claim.causal_type}
                  </span>
                </div>
                <div style={{ display: "flex", gap: "6px" }}>
                  {claim.evidence_ids?.map((evid) => (
                    <button
                      key={evid}
                      onClick={() => setSelectedEvidId(selectedEvidId === evid ? null : evid)}
                      style={{
                        background: selectedEvidId === evid ? "#4f46e5" : "rgba(79, 70, 229, 0.15)",
                        color: selectedEvidId === evid ? "#ffffff" : "#a5b4fc",
                        border: "1px solid rgba(79, 70, 229, 0.4)",
                        borderRadius: "4px",
                        fontSize: "0.72rem",
                        fontWeight: 600,
                        padding: "2px 8px",
                        cursor: "pointer",
                        display: "inline-flex",
                        alignItems: "center",
                        gap: "4px",
                      }}
                    >
                      <Database size={11} /> {evid}
                    </button>
                  ))}
                </div>
              </div>

              <div style={{ fontSize: "0.92rem", color: "var(--fg-primary, #f1f5f9)", lineHeight: 1.45, fontWeight: 500 }}>
                {claim.rendered_text}
              </div>

              {claim.strategic_implication && (
                <div style={{ marginTop: "6px", fontSize: "0.8rem", color: "var(--fg-muted, #94a3b8)", display: "flex", alignItems: "center", gap: "6px" }}>
                  <span style={{ fontWeight: 600, color: "#cbd5e1" }}>Operational Implication:</span> {claim.strategic_implication}
                </div>
              )}

              {claim.recommended_action && (
                <div style={{ marginTop: "4px", fontSize: "0.8rem", color: "#38bdf8", display: "flex", alignItems: "center", gap: "6px" }}>
                  <ArrowRight size={13} /> <span style={{ fontWeight: 600 }}>Action:</span> {claim.recommended_action}
                </div>
              )}
            </div>
          );
        })}
      </div>

      {/* Selected Evidence Node Inspection Callout */}
      {selectedNode && (
        <div
          style={{
            marginTop: "1rem",
            padding: "1rem",
            background: "rgba(30, 41, 59, 0.95)",
            border: "1px solid #4f46e5",
            borderRadius: "8px",
          }}
        >
          <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: "8px" }}>
            <span style={{ fontWeight: 700, color: "#a5b4fc", fontSize: "0.85rem", display: "flex", alignItems: "center", gap: "6px" }}>
              <Database size={14} /> Provenance for {selectedNode.evidence_id}: {selectedNode.subject}
            </span>
            <button
              onClick={() => setSelectedEvidId(null)}
              style={{ background: "transparent", border: "none", color: "#94a3b8", cursor: "pointer", fontSize: "0.8rem" }}
            >
              Close
            </button>
          </div>
          <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(200px, 1fr))", gap: "0.75rem", fontSize: "0.8rem" }}>
            <div>
              <span style={{ color: "#64748b" }}>Calculation:</span>
              <div style={{ color: "#f8fafc", fontFamily: "monospace", marginTop: "2px" }}>{selectedNode.calculation}</div>
            </div>
            <div>
              <span style={{ color: "#64748b" }}>Source Table:</span>
              <div style={{ color: "#f8fafc", marginTop: "2px" }}>{selectedNode.source_table}</div>
            </div>
            <div>
              <span style={{ color: "#64748b" }}>Sample Size:</span>
              <div style={{ color: "#f8fafc", marginTop: "2px" }}>{selectedNode.population} records</div>
            </div>
            <div>
              <span style={{ color: "#64748b" }}>Confidence:</span>
              <div style={{ color: selectedNode.confidence === "HIGH" ? "#34d399" : "#f59e0b", fontWeight: 600, marginTop: "2px" }}>
                {selectedNode.confidence}
              </div>
            </div>
          </div>
        </div>
      )}

      {/* Toggle View All Evidence Nodes */}
      {nodes.length > 0 && (
        <div style={{ marginTop: "1rem", paddingTop: "0.75rem", borderTop: "1px solid rgba(255, 255, 255, 0.08)" }}>
          <button
            onClick={() => setShowAllNodes(!showAllNodes)}
            style={{
              background: "transparent",
              border: "none",
              color: "#94a3b8",
              cursor: "pointer",
              fontSize: "0.78rem",
              display: "flex",
              alignItems: "center",
              gap: "4px",
              padding: 0,
            }}
          >
            {showAllNodes ? <ChevronUp size={14} /> : <ChevronDown size={14} />}
            {showAllNodes ? "Hide Governed Fact Nodes" : `View all ${nodes.length} verified evidence nodes`}
          </button>

          {showAllNodes && (
            <div style={{ marginTop: "0.75rem", display: "grid", gridTemplateColumns: "repeat(auto-fill, minmax(220px, 1fr))", gap: "0.5rem" }}>
              {nodes.map((n) => (
                <div
                  key={n.evidence_id}
                  onClick={() => setSelectedEvidId(n.evidence_id)}
                  style={{
                    padding: "6px 10px",
                    background: selectedEvidId === n.evidence_id ? "rgba(79, 70, 229, 0.25)" : "rgba(15, 23, 42, 0.5)",
                    border: `1px solid ${selectedEvidId === n.evidence_id ? "#6366f1" : "rgba(255, 255, 255, 0.08)"}`,
                    borderRadius: "6px",
                    cursor: "pointer",
                    fontSize: "0.75rem",
                  }}
                >
                  <div style={{ display: "flex", justifyContent: "space-between" }}>
                    <span style={{ fontWeight: 700, color: "#818cf8" }}>{n.evidence_id}</span>
                    <span style={{ color: "#34d399", fontWeight: 600 }}>{n.formatted_value}</span>
                  </div>
                  <div style={{ color: "var(--fg-muted, #94a3b8)", whiteSpace: "nowrap", overflow: "hidden", textOverflow: "ellipsis", marginTop: "2px" }}>
                    {n.subject}
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>
      )}
    </SurfaceGuard.Card>
  );
}
