import React, { useEffect } from "react";
import { X, GitCommit, Database, GitMerge, LayoutDashboard, Award } from "lucide-react";
import StatusBadge from "../common/StatusBadge";

/**
 * Calculation Lineage Drawer
 * Step-by-step reconstruction path for analytical facts and metrics.
 * 100% centralized theme tokens, zero hardcoded hex colors, zero architecture jargon.
 */
export default function LineageDrawer({
  fact,
  onClose,
  themeTokens,
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

  const bgSurface = themeTokens?.colors?.surface || "var(--color-bg-surface)";
  const bgSubtle = themeTokens?.colors?.surfaceHover || "var(--color-bg-subtle)";
  const borderCol = themeTokens?.colors?.borderSubtle || "var(--color-divider)";
  const borderStrong = themeTokens?.colors?.border || "var(--color-border)";
  const textPrimary = themeTokens?.colors?.textPrimary || "var(--color-text-primary)";
  const textSecondary = themeTokens?.colors?.textSecondary || "var(--color-text-secondary)";
  const textMuted = themeTokens?.colors?.textMuted || "var(--color-text-muted)";
  const brandPrimary = themeTokens?.colors?.brandPrimary || "var(--color-brand-primary)";
  const brandSoftBg = themeTokens?.colors?.softBlue || "var(--color-bg-soft-blue)";

  const lineageSteps = fact.lineage_path || [];

  const getStepIcon = (type) => {
    switch (type) {
      case "SOURCE":
        return <Database size={16} color={brandPrimary} />;
      case "JOIN_PLAN":
        return <GitMerge size={16} color={themeTokens?.colors?.statusSuccess || "var(--color-success)"} />;
      case "ANALYTICAL_VIEW":
        return <LayoutDashboard size={16} color={brandPrimary} />;
      case "FACT":
        return <Award size={16} color={themeTokens?.colors?.gold || "var(--color-gold)"} />;
      default:
        return <GitCommit size={16} color={textSecondary} />;
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
          backgroundColor: bgSurface,
          borderLeft: `1px solid ${borderStrong}`,
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
            <div style={{ marginBottom: "4px" }}>
              <StatusBadge status="Calculation Lineage" variant="info" size="xs" />
            </div>
            <h2 id="lineage-drawer-title" style={{ margin: 0, fontSize: "1.1rem", fontWeight: 700, color: textPrimary }}>
              {fact.metric_name || fact.metric} = {fact.formatted_value || String(fact.exact_value ?? fact.value ?? "")} {fact.unit || ""}
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
          {/* Fact Summary */}
          <div style={{ background: bgSubtle, padding: "12px 16px", borderRadius: "8px", border: `1px solid ${borderCol}` }}>
            <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: "10px" }}>
              <div>
                <div style={{ fontSize: "0.72rem", color: textSecondary }}>Result Grain</div>
                <div style={{ fontSize: "0.85rem", fontWeight: 700, color: textPrimary }}>{fact.grain || "RECORD"}</div>
              </div>
              <div>
                <div style={{ fontSize: "0.72rem", color: textSecondary }}>Source / Provenance</div>
                <div style={{ fontSize: "0.85rem", fontWeight: 700, color: brandPrimary }}>{fact.provenance || "Reconstructed"}</div>
              </div>
              {fact.denominator !== null && fact.denominator !== undefined && (
                <div>
                  <div style={{ fontSize: "0.72rem", color: textSecondary }}>Denominator</div>
                  <div style={{ fontSize: "0.85rem", fontWeight: 700, color: textPrimary }}>{fact.denominator}</div>
                </div>
              )}
              <div>
                <div style={{ fontSize: "0.72rem", color: textSecondary }}>Status</div>
                <div style={{ marginTop: "2px" }}>
                  <StatusBadge status={fact.status || "Verified"} size="xs" />
                </div>
              </div>
            </div>
          </div>

          {/* Step-by-Step Lineage Timeline */}
          <div>
            <h3 style={{ fontSize: "0.85rem", fontWeight: 700, textTransform: "uppercase", letterSpacing: "0.05em", color: textSecondary, marginBottom: "16px" }}>
              Step-by-Step Calculation Path
            </h3>

            <div style={{ display: "flex", flexDirection: "column", gap: "0" }}>
              {lineageSteps.length > 0 ? (
                lineageSteps.map((step, idx) => {
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
                              background: borderCol,
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
                })
              ) : (
                <div style={{ padding: "16px", background: bgSubtle, borderRadius: "8px", fontSize: "0.8rem", color: textSecondary }}>
                  Source record value computed directly from primary grain observations.
                </div>
              )}
            </div>
          </div>

          {/* Technical Details (Progressive Disclosure) */}
          <details style={{ borderTop: `1px solid ${borderCol}`, paddingTop: "14px" }}>
            <summary style={{ cursor: "pointer", fontSize: "0.78rem", color: textSecondary, fontWeight: 600 }}>
              Technical Details
            </summary>
            <div style={{ marginTop: "8px", padding: "10px", background: bgSubtle, borderRadius: "6px", fontSize: "0.75rem", fontFamily: "monospace", color: textSecondary }}>
              <div>Fact ID: {fact.fact_id}</div>
              <div>View ID: {fact.analytical_view_id}</div>
              <div>Exact Value: {String(fact.exact_value)}</div>
            </div>
          </details>
        </div>
      </div>
    </div>
  );
}
