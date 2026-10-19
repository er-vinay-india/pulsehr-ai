import React, { useEffect } from "react";
import { X, GitCommit, Database, GitMerge, LayoutDashboard, Award, ArrowDown } from "lucide-react";

export default function LineageDrawer({
  fact,
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

  if (!fact) return null;

  const bgCard = isDark ? "#1e293b" : "#ffffff";
  const borderCol = isDark ? "#334155" : "#e2e8f0";
  const textPrimary = isDark ? "#f8fafc" : "#0f172a";
  const textSecondary = isDark ? "#94a3b8" : "#64748b";
  const bgSubtle = isDark ? "#0f172a" : "#f8fafc";

  const lineageSteps = fact.lineage_path || [];

  const getStepIcon = (type) => {
    switch (type) {
      case "SOURCE":
        return <Database size={16} color="#2563eb" />;
      case "JOIN_PLAN":
        return <GitMerge size={16} color="#10b981" />;
      case "ANALYTICAL_VIEW":
        return <LayoutDashboard size={16} color="#a855f7" />;
      case "FACT":
        return <Award size={16} color="#f59e0b" />;
      default:
        return <GitCommit size={16} color="#64748b" />;
    }
  };

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
        aria-labelledby="lineage-drawer-title"
        onClick={(e) => e.stopPropagation()}
        style={{
          width: "500px",
          maxWidth: "92vw",
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
          <div>
            <span
              style={{
                display: "inline-block",
                padding: "2px 6px",
                borderRadius: "4px",
                fontSize: "0.72rem",
                fontWeight: 700,
                background: "rgba(245, 158, 11, 0.15)",
                color: "#f59e0b",
                border: "1px solid rgba(245, 158, 11, 0.3)",
                marginBottom: "4px",
              }}
            >
              Gold Fact Lineage Path
            </span>
            <h2 id="lineage-drawer-title" style={{ margin: 0, fontSize: "1.1rem", fontWeight: 700, color: textPrimary }}>
              {fact.metric} = {fact.formatted_value || fact.value} {fact.unit || ""}
            </h2>
          </div>
          <button
            type="button"
            onClick={onClose}
            aria-label="Close lineage drawer"
            style={{
              background: "transparent",
              border: "none",
              color: textSecondary,
              cursor: "pointer",
              padding: "4px",
              display: "flex",
              alignItems: "center",
            }}
          >
            <X size={18} />
          </button>
        </div>

        {/* Content Body */}
        <div style={{ padding: "20px", display: "flex", flexDirection: "column", gap: "20px" }}>
          {/* Fact Summary Banner */}
          <div style={{ background: bgSubtle, padding: "12px 16px", borderRadius: "8px", border: `1px solid ${borderCol}` }}>
            <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: "10px" }}>
              <div>
                <div style={{ fontSize: "0.72rem", color: textSecondary }}>Result Grain</div>
                <div style={{ fontSize: "0.85rem", fontWeight: 700, color: textPrimary }}>{fact.grain}</div>
              </div>
              <div>
                <div style={{ fontSize: "0.72rem", color: textSecondary }}>Provenance Type</div>
                <div style={{ fontSize: "0.85rem", fontWeight: 700, color: "#2563eb" }}>{fact.provenance}</div>
              </div>
              {fact.denominator_value !== null && fact.denominator_value !== undefined && (
                <div>
                  <div style={{ fontSize: "0.72rem", color: textSecondary }}>Denominator Value</div>
                  <div style={{ fontSize: "0.85rem", fontWeight: 700, color: textPrimary }}>{fact.denominator_value}</div>
                </div>
              )}
              <div>
                <div style={{ fontSize: "0.72rem", color: textSecondary }}>Fact ID</div>
                <code style={{ fontSize: "0.75rem", color: textPrimary }}>{fact.fact_id}</code>
              </div>
            </div>
          </div>

          {/* Step-by-Step Lineage Timeline */}
          <div>
            <h3 style={{ fontSize: "0.85rem", fontWeight: 700, textTransform: "uppercase", letterSpacing: "0.05em", color: textSecondary, marginBottom: "16px" }}>
              Step-by-Step Reconstruction Path
            </h3>

            <div style={{ display: "flex", flexDirection: "column", gap: "0" }}>
              {lineageSteps.map((step, idx) => {
                const isLast = idx === lineageSteps.length - 1;
                return (
                  <div key={idx} style={{ display: "flex", gap: "14px", position: "relative" }}>
                    {/* Step Icon and Vertical Line */}
                    <div style={{ display: "flex", flexDirection: "column", alignItems: "center" }}>
                      <div
                        style={{
                          width: "32px",
                          height: "32px",
                          borderRadius: "50%",
                          background: bgSubtle,
                          border: `2px solid ${borderCol}`,
                          display: "flex",
                          alignItems: "center",
                          justifyContent: "center",
                          zIndex: 2,
                        }}
                      >
                        {getStepIcon(step.type)}
                      </div>
                      {!isLast && (
                        <div
                          style={{
                            width: "2px",
                            flex: 1,
                            minHeight: "40px",
                            background: isDark ? "#334155" : "#e2e8f0",
                            margin: "4px 0",
                          }}
                        />
                      )}
                    </div>

                    {/* Step Details */}
                    <div style={{ paddingBottom: isLast ? "0" : "24px", flex: 1 }}>
                      <div style={{ fontSize: "0.72rem", fontWeight: 700, color: textSecondary, textTransform: "uppercase" }}>
                        Step {step.step}: {step.type}
                      </div>
                      <div style={{ fontSize: "0.9rem", fontWeight: 600, color: textPrimary, marginTop: "2px" }}>
                        {step.label}
                      </div>
                      <div style={{ fontSize: "0.78rem", color: textSecondary, marginTop: "4px", lineHeight: "1.4" }}>
                        {step.detail}
                      </div>
                    </div>
                  </div>
                );
              })}
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
