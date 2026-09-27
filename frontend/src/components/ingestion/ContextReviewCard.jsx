import React, { useState } from "react";
import {
  Sparkles,
  CheckCircle2,
  AlertTriangle,
  AlertCircle,
  HelpCircle,
  Edit3,
  Calendar,
  Layers,
  Database,
  BarChart3,
  ShieldAlert,
  ArrowRight,
  Check,
  X
} from "lucide-react";
import ContextOverrideModal from "./ContextOverrideModal";

export default function ContextReviewCard({
  workspaceContext,
  workspaceId,
  onContextUpdated,
}) {
  const [modalOpen, setModalOpen] = useState(false);

  if (!workspaceContext) return null;

  const summary = workspaceContext.context_summary || {};
  const userReq = workspaceContext.user_request || {};
  const readiness = workspaceContext.readiness || {};
  const timeIntel = workspaceContext.time_intelligence || {};
  const quality = workspaceContext.quality || {};
  const questions = workspaceContext.question_mappings || [];
  const relationships = workspaceContext.relationships || [];
  const datasets = workspaceContext.datasets || [];

  // Confidence level calculation
  const conf = userReq.confidence ?? 0.85;
  const isHighConfidence = conf >= 0.8 && readiness.status === "READY";
  const isMediumConfidence = conf >= 0.6 && !isHighConfidence;
  const isLowConfidence = conf < 0.6 || readiness.status === "NEEDS_MAPPING" || readiness.status === "INSUFFICIENT_DATA";

  // Sensitive columns detection across datasets
  const sensitiveColumns = [];
  datasets.forEach((ds) => {
    (ds.columns || []).forEach((c) => {
      if (c.is_sensitive) {
        sensitiveColumns.push({
          name: c.name,
          dataset: ds.name,
          unit: c.semantic_unit || "currency",
          role: c.semantic_role || "METRIC"
        });
      }
    });
  });

  // Actionable quality issues
  const actionableIssues = [];
  if (quality.issues) {
    quality.issues.forEach((iss) => {
      if (iss.severity === "ERROR" || iss.severity === "WARNING") {
        actionableIssues.push(iss.description);
      }
    });
  }

  // Unsafe join warning
  const unsafeJoins = relationships.filter((r) => !r.is_safe || r.cardinality === "MANY_TO_MANY");

  // Readiness badge color
  const getReadinessBadge = (status) => {
    switch (status) {
      case "READY":
        return {
          bg: "rgba(16, 185, 129, 0.15)",
          color: "var(--emerald-tier, #10B981)",
          border: "rgba(16, 185, 129, 0.3)",
          label: "Ready"
        };
      case "READY_WITH_WARNINGS":
        return {
          bg: "rgba(245, 158, 11, 0.15)",
          color: "var(--amber-tier, #F59E0B)",
          border: "rgba(245, 158, 11, 0.3)",
          label: "Ready with Warnings"
        };
      case "NEEDS_MAPPING":
        return {
          bg: "rgba(239, 68, 68, 0.15)",
          color: "var(--rose-tier, #EF4444)",
          border: "rgba(239, 68, 68, 0.3)",
          label: "Needs Mapping"
        };
      default:
        return {
          bg: "rgba(239, 68, 68, 0.15)",
          color: "var(--rose-tier, #EF4444)",
          border: "rgba(239, 68, 68, 0.3)",
          label: status || "Insufficient Data"
        };
    }
  };

  const badge = getReadinessBadge(readiness.status);

  return (
    <div
      className="context-review-container"
      style={{
        marginTop: "1rem",
        padding: "1rem 1.25rem",
        background: "var(--surface-primary, rgba(15, 23, 42, 0.6))",
        border: isLowConfidence ? "1px solid rgba(239, 68, 68, 0.4)" : "1px solid var(--border-subtle, rgba(255,255,255,0.08))",
        borderRadius: "10px",
        boxShadow: "0 4px 12px rgba(0, 0, 0, 0.15)"
      }}
    >
      {/* Header bar */}
      <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", flexWrap: "wrap", gap: "0.5rem" }}>
        <div style={{ display: "flex", alignItems: "center", gap: "8px" }}>
          <Sparkles size={18} color="var(--brand-accent, #155EEF)" />
          <h4 style={{ margin: 0, fontSize: "0.95rem", fontWeight: 600, color: "var(--fg-primary, #F8FAFC)" }}>
            Understanding your data
          </h4>
          <span
            style={{
              fontSize: "0.75rem",
              padding: "2px 8px",
              borderRadius: "12px",
              background: badge.bg,
              color: badge.color,
              border: `1px solid ${badge.border}`,
              fontWeight: 600
            }}
          >
            {badge.label}
          </span>
          {isLowConfidence && (
            <span
              style={{
                fontSize: "0.7rem",
                padding: "2px 6px",
                borderRadius: "4px",
                background: "rgba(239, 68, 68, 0.2)",
                color: "#EF4444",
                fontWeight: 600
              }}
            >
              Review Recommended
            </span>
          )}
        </div>

        <button
          type="button"
          onClick={() => setModalOpen(true)}
          className="btn-secondary"
          style={{
            display: "inline-flex",
            alignItems: "center",
            gap: "5px",
            fontSize: "0.75rem",
            padding: "4px 10px",
            color: "var(--brand-400, #E05624)",
            borderColor: "rgba(224, 86, 36, 0.3)"
          }}
        >
          <Edit3 size={12} />
          <span>{isLowConfidence ? "Correct Context" : "Edit / Review Context"}</span>
        </button>
      </div>

      {/* Primary Key Grid */}
      <div
        style={{
          display: "grid",
          gridTemplateColumns: "repeat(auto-fit, minmax(180px, 1fr))",
          gap: "0.75rem",
          marginTop: "0.85rem"
        }}
      >
        {/* Domain */}
        <div style={{ padding: "0.5rem 0.75rem", background: "rgba(255,255,255,0.03)", borderRadius: "6px" }}>
          <div style={{ fontSize: "0.7rem", color: "var(--fg-muted, #94A3B8)", textTransform: "uppercase", letterSpacing: "0.5px" }}>
            Domain
          </div>
          <div style={{ fontSize: "0.85rem", fontWeight: 600, color: "var(--fg-primary, #F8FAFC)", marginTop: "2px" }}>
            {summary.domain || "Generic Analytics"}
          </div>
        </div>

        {/* Reporting Period */}
        <div style={{ padding: "0.5rem 0.75rem", background: "rgba(255,255,255,0.03)", borderRadius: "6px" }}>
          <div style={{ fontSize: "0.7rem", color: "var(--fg-muted, #94A3B8)", textTransform: "uppercase", letterSpacing: "0.5px" }}>
            Reporting Period
          </div>
          <div style={{ fontSize: "0.85rem", fontWeight: 600, color: "var(--fg-primary, #F8FAFC)", marginTop: "2px" }}>
            {summary.reporting_period || timeIntel.reporting_period || "Current Period"}
            {timeIntel.is_partial_year && (
              <span style={{ fontSize: "0.7rem", color: "var(--amber-tier, #F59E0B)", marginLeft: "4px" }}>
                (Partial Year)
              </span>
            )}
          </div>
        </div>

        {/* Primary Dataset */}
        <div style={{ padding: "0.5rem 0.75rem", background: "rgba(255,255,255,0.03)", borderRadius: "6px" }}>
          <div style={{ fontSize: "0.7rem", color: "var(--fg-muted, #94A3B8)", textTransform: "uppercase", letterSpacing: "0.5px" }}>
            Primary Dataset
          </div>
          <div style={{ fontSize: "0.85rem", fontWeight: 600, color: "var(--fg-primary, #F8FAFC)", marginTop: "2px" }}>
            {summary.primary_dataset || "Main Table"}
          </div>
        </div>

        {/* Key Metrics */}
        <div style={{ padding: "0.5rem 0.75rem", background: "rgba(255,255,255,0.03)", borderRadius: "6px" }}>
          <div style={{ fontSize: "0.7rem", color: "var(--fg-muted, #94A3B8)", textTransform: "uppercase", letterSpacing: "0.5px" }}>
            Key Metrics
          </div>
          <div style={{ display: "flex", gap: "4px", flexWrap: "wrap", marginTop: "3px" }}>
            {(summary.key_metrics || []).slice(0, 4).map((m, idx) => (
              <span
                key={idx}
                style={{
                  fontSize: "0.7rem",
                  padding: "1px 6px",
                  borderRadius: "4px",
                  background: "rgba(37, 99, 235, 0.15)",
                  color: "#60A5FA",
                  fontWeight: 500
                }}
              >
                {m}
              </span>
            ))}
          </div>
        </div>

        {/* Key Dimensions */}
        <div style={{ padding: "0.5rem 0.75rem", background: "rgba(255,255,255,0.03)", borderRadius: "6px" }}>
          <div style={{ fontSize: "0.7rem", color: "var(--fg-muted, #94A3B8)", textTransform: "uppercase", letterSpacing: "0.5px" }}>
            Key Dimensions
          </div>
          <div style={{ display: "flex", gap: "4px", flexWrap: "wrap", marginTop: "3px" }}>
            {(summary.key_dimensions || []).slice(0, 4).map((d, idx) => (
              <span
                key={idx}
                style={{
                  fontSize: "0.7rem",
                  padding: "1px 6px",
                  borderRadius: "4px",
                  background: "rgba(168, 85, 247, 0.15)",
                  color: "#C084FC",
                  fontWeight: 500
                }}
              >
                {d}
              </span>
            ))}
          </div>
        </div>
      </div>

      {/* User Goal / Objective Section */}
      <div style={{ marginTop: "0.75rem", padding: "0.5rem 0.75rem", background: "rgba(255,255,255,0.02)", borderRadius: "6px" }}>
        <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between" }}>
          <span style={{ fontSize: "0.75rem", fontWeight: 600, color: "var(--fg-secondary, #CBD5E1)" }}>
            User Goal:
          </span>
          <span style={{ fontSize: "0.7rem", color: "var(--fg-muted, #94A3B8)" }}>
            Intent: {userReq.intent_status || "UNSPECIFIED"}
          </span>
        </div>
        <p style={{ margin: "2px 0 0 0", fontSize: "0.8rem", color: "var(--fg-primary, #F8FAFC)" }}>
          {summary.user_goal || userReq.normalized_objective || "General analytical discovery across dataset."}
        </p>
      </div>

      {/* Explicit Questions Support Status (Section 13) */}
      {questions.length > 0 && (
        <div style={{ marginTop: "0.75rem" }}>
          <div style={{ fontSize: "0.75rem", fontWeight: 600, color: "var(--fg-secondary, #CBD5E1)", marginBottom: "4px" }}>
            Analytical Questions & Data Support:
          </div>
          <div style={{ display: "flex", flexDirection: "column", gap: "4px" }}>
            {questions.map((qm, qIdx) => {
              const isSup = qm.alignment_status === "SUPPORTED";
              const isPart = qm.alignment_status === "PARTIALLY_SUPPORTED";
              return (
                <div
                  key={qIdx}
                  style={{
                    display: "flex",
                    alignItems: "center",
                    gap: "8px",
                    fontSize: "0.75rem",
                    padding: "3px 8px",
                    borderRadius: "4px",
                    background: isSup
                      ? "rgba(16, 185, 129, 0.08)"
                      : isPart
                      ? "rgba(245, 158, 11, 0.08)"
                      : "rgba(239, 68, 68, 0.08)"
                  }}
                >
                  {isSup ? (
                    <CheckCircle2 size={13} color="var(--emerald-tier, #10B981)" style={{ flexShrink: 0 }} />
                  ) : isPart ? (
                    <AlertTriangle size={13} color="var(--amber-tier, #F59E0B)" style={{ flexShrink: 0 }} />
                  ) : (
                    <X size={13} color="var(--rose-tier, #EF4444)" style={{ flexShrink: 0 }} />
                  )}
                  <span style={{ flex: 1, color: "var(--fg-primary, #F8FAFC)" }}>
                    "{qm.question}"
                  </span>
                  <span
                    style={{
                      fontSize: "0.7rem",
                      fontWeight: 500,
                      color: isSup
                        ? "var(--emerald-tier, #10B981)"
                        : isPart
                        ? "var(--amber-tier, #F59E0B)"
                        : "var(--rose-tier, #EF4444)"
                    }}
                  >
                    {isSup
                      ? "Supported"
                      : isPart
                      ? "Partially supported"
                      : (qm.explanation || "Required data not available")}
                  </span>
                </div>
              );
            })}
          </div>
        </div>
      )}

      {/* Sensitive Fields Protection (Section 16) */}
      {sensitiveColumns.length > 0 && (
        <div style={{ marginTop: "0.6rem", display: "flex", alignItems: "center", gap: "6px", flexWrap: "wrap" }}>
          <ShieldAlert size={14} color="var(--amber-tier, #F59E0B)" />
          <span style={{ fontSize: "0.75rem", color: "var(--fg-muted, #94A3B8)" }}>
            Sensitive columns protected (PII/Salary sample values redacted):
          </span>
          {sensitiveColumns.map((sc, scIdx) => (
            <span
              key={scIdx}
              style={{
                fontSize: "0.7rem",
                padding: "1px 6px",
                borderRadius: "4px",
                background: "rgba(245, 158, 11, 0.15)",
                color: "var(--amber-tier, #F59E0B)",
                fontWeight: 600
              }}
            >
              {sc.name} (Sensitive: Yes)
            </span>
          ))}
        </div>
      )}

      {/* Unsafe Joins & Actionable Warnings */}
      {(unsafeJoins.length > 0 || actionableIssues.length > 0) && (
        <div style={{ marginTop: "0.6rem" }}>
          {unsafeJoins.map((uj, uIdx) => (
            <div
              key={uIdx}
              style={{
                fontSize: "0.72rem",
                color: "var(--amber-tier, #F59E0B)",
                background: "rgba(245, 158, 11, 0.1)",
                padding: "3px 8px",
                borderRadius: "4px",
                marginTop: "3px"
              }}
            >
              <AlertTriangle size={12} style={{ display: "inline", verticalAlign: "middle", marginRight: "4px" }} />
              Automatic join disabled for {uj.left_column} ↔ {uj.right_column}: both sides contain repeated keys (Many-to-Many).
            </div>
          ))}
          {actionableIssues.slice(0, 2).map((iss, iIdx) => (
            <div
              key={iIdx}
              style={{
                fontSize: "0.72rem",
                color: "var(--fg-muted, #94A3B8)",
                padding: "2px 8px"
              }}
            >
              • {iss}
            </div>
          ))}
        </div>
      )}

      {/* Override Modal */}
      {modalOpen && (
        <ContextOverrideModal
          workspaceId={workspaceId}
          workspaceContext={workspaceContext}
          onClose={() => setModalOpen(false)}
          onSuccess={(updatedCtx) => {
            setModalOpen(false);
            if (onContextUpdated) onContextUpdated(updatedCtx);
          }}
        />
      )}
    </div>
  );
}
