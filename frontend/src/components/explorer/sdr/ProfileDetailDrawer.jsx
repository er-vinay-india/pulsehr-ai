import React, { useState, useEffect } from "react";
import {
  X,
  Activity,
  BarChart2,
  CheckCircle2,
  AlertTriangle,
  Layers,
  Copy,
  Check,
  Percent,
  Hash,
  Info,
} from "lucide-react";
import StatusBadge from "../common/StatusBadge";

/**
 * Profile Detail Drawer
 * Deep inspection of deterministic column quality, descriptive statistics,
 * missingness, quartiles, and Tukey IQR 1.5 potential outliers.
 */
export default function ProfileDetailDrawer({
  column,
  onClose,
  themeTokens,
  isDark = false,
}) {
  const [copiedValue, setCopiedValue] = useState(null);

  useEffect(() => {
    const handleKeyDown = (e) => {
      if (e.key === "Escape") onClose();
    };
    window.addEventListener("keydown", handleKeyDown);
    return () => window.removeEventListener("keydown", handleKeyDown);
  }, [onClose]);

  if (!column) return null;

  const bgSurface = themeTokens?.colors?.surface || "var(--color-bg-surface)";
  const bgSubtle = themeTokens?.colors?.surfaceHover || "var(--color-bg-subtle)";
  const borderCol = themeTokens?.colors?.borderSubtle || "var(--color-divider)";
  const textPrimary = themeTokens?.colors?.textPrimary || "var(--color-text-primary)";
  const textSecondary = themeTokens?.colors?.textSecondary || "var(--color-text-secondary)";
  const textMuted = themeTokens?.colors?.textMuted || "var(--color-text-muted)";
  const brandPrimary = themeTokens?.colors?.brandPrimary || "var(--color-brand-primary)";
  const brandSoftBg = themeTokens?.colors?.softBlue || "var(--color-bg-soft-blue)";

  const rowCount = column.row_count ?? 0;
  const nullCount = column.null_count ?? 0;
  const populatedCount = Math.max(0, rowCount - nullCount);
  const nullPct = column.null_percentage ?? 0;
  const populatedPct = column.populated_pct ?? Math.max(0, 100 - nullPct);
  const distinctCount = column.distinct_count ?? 0;
  const distinctPct = column.distinct_pct ?? (rowCount > 0 ? Math.round((distinctCount / rowCount) * 1000) / 10 : 0);

  const isNumeric = Boolean(column.is_numeric);
  const hasOutliers = (column.outlier_count ?? 0) > 0;
  const bins = column.bins || [];
  const maxBinCount = bins.length > 0 ? Math.max(...bins.map((b) => b.count || 0), 1) : 1;

  const handleCopy = (val) => {
    try {
      navigator.clipboard.writeText(String(val));
      setCopiedValue(String(val));
      setTimeout(() => setCopiedValue(null), 1800);
    } catch {
      // Fallback
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
        aria-labelledby="drawer-title"
        style={{
          width: "100%",
          maxWidth: "520px",
          height: "100%",
          backgroundColor: bgSurface,
          borderLeft: `1px solid ${borderCol}`,
          boxShadow: "-8px 0 24px rgba(0, 0, 0, 0.15)",
          display: "flex",
          flexDirection: "column",
          overflow: "hidden",
        }}
        onClick={(e) => e.stopPropagation()}
      >
        {/* Drawer Header */}
        <div
          style={{
            padding: "20px",
            borderBottom: `1px solid ${borderCol}`,
            display: "flex",
            justifyContent: "space-between",
            alignItems: "flex-start",
            gap: "12px",
          }}
        >
          <div style={{ flex: 1, minWidth: 0 }}>
            <div style={{ display: "flex", alignItems: "center", gap: "8px", marginBottom: "6px", flexWrap: "wrap" }}>
              <span
                style={{
                  fontSize: "0.72rem",
                  fontWeight: 700,
                  textTransform: "uppercase",
                  padding: "2px 8px",
                  borderRadius: "4px",
                  background: brandSoftBg,
                  color: brandPrimary,
                }}
              >
                {column.data_type || "Column"}
              </span>
              <span
                style={{
                  fontSize: "0.72rem",
                  fontWeight: 600,
                  padding: "2px 8px",
                  borderRadius: "4px",
                  background: bgSubtle,
                  border: `1px solid ${borderCol}`,
                  color: textSecondary,
                }}
              >
                {column.sheet_name || "Sheet"}
              </span>
              <StatusBadge status={column.status} />
            </div>

            <div style={{ display: "flex", alignItems: "center", gap: "8px" }}>
              <h2
                id="drawer-title"
                style={{
                  margin: 0,
                  fontSize: "1.1rem",
                  fontWeight: 700,
                  color: textPrimary,
                  wordBreak: "break-word",
                }}
              >
                {column.column}
              </h2>
              <button
                type="button"
                onClick={() => handleCopy(column.column)}
                title="Copy column name"
                aria-label="Copy column name"
                style={{
                  background: "transparent",
                  border: "none",
                  cursor: "pointer",
                  color: textMuted,
                  display: "flex",
                  alignItems: "center",
                  padding: "4px",
                  borderRadius: "4px",
                }}
              >
                {copiedValue === column.column ? (
                  <Check size={14} color="var(--color-success, #075443)" />
                ) : (
                  <Copy size={14} />
                )}
              </button>
            </div>
          </div>

          <button
            type="button"
            onClick={onClose}
            aria-label="Close drawer"
            style={{
              background: "transparent",
              border: "none",
              cursor: "pointer",
              color: textSecondary,
              padding: "6px",
              borderRadius: "6px",
              display: "flex",
              alignItems: "center",
              justifyContent: "center",
            }}
          >
            <X size={18} />
          </button>
        </div>

        {/* Drawer Body */}
        <div
          style={{
            flex: 1,
            overflowY: "auto",
            padding: "20px",
            display: "flex",
            flexDirection: "column",
            gap: "20px",
          }}
        >
          {/* Section 1: Completeness & Quality Summary */}
          <div
            style={{
              padding: "16px",
              borderRadius: "8px",
              background: bgSubtle,
              border: `1px solid ${borderCol}`,
            }}
          >
            <div style={{ display: "flex", alignItems: "center", gap: "6px", marginBottom: "12px" }}>
              <Percent size={14} color={brandPrimary} />
              <h3 style={{ margin: 0, fontSize: "0.86rem", fontWeight: 700, color: textPrimary }}>
                Completeness & Missingness
              </h3>
            </div>

            <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: "10px", marginBottom: "12px" }}>
              <div>
                <div style={{ fontSize: "0.72rem", color: textMuted }}>Populated Values</div>
                <div style={{ fontSize: "1rem", fontWeight: 700, color: textPrimary }}>
                  {populatedCount.toLocaleString()} <span style={{ fontSize: "0.76rem", fontWeight: 500, color: textSecondary }}>({populatedPct}%)</span>
                </div>
              </div>
              <div>
                <div style={{ fontSize: "0.72rem", color: textMuted }}>Missing / Null Values</div>
                <div style={{ fontSize: "1rem", fontWeight: 700, color: nullCount > 0 ? "var(--color-warning, #D97706)" : textPrimary }}>
                  {nullCount.toLocaleString()} <span style={{ fontSize: "0.76rem", fontWeight: 500, color: textSecondary }}>({nullPct}%)</span>
                </div>
              </div>
            </div>

            {/* Micro completeness bar */}
            <div
              style={{
                width: "100%",
                height: "8px",
                borderRadius: "4px",
                backgroundColor: nullCount > 0 ? "var(--color-bg-soft-warning, #FEF3C7)" : "var(--color-bg-soft-teal, #E7F3ED)",
                overflow: "hidden",
                display: "flex",
                marginBottom: "10px",
              }}
            >
              <div
                style={{
                  width: `${populatedPct}%`,
                  height: "100%",
                  backgroundColor: brandPrimary,
                }}
              />
            </div>

            <p style={{ margin: 0, fontSize: "0.74rem", color: textSecondary, fontStyle: "italic" }}>
              Note: Missing data is preserved as missing and not coerced to zero or altered.
            </p>
          </div>

          {/* Section 2: Cardinality & Uniqueness */}
          <div
            style={{
              padding: "16px",
              borderRadius: "8px",
              background: bgSubtle,
              border: `1px solid ${borderCol}`,
            }}
          >
            <div style={{ display: "flex", alignItems: "center", gap: "6px", marginBottom: "12px" }}>
              <Hash size={14} color={brandPrimary} />
              <h3 style={{ margin: 0, fontSize: "0.86rem", fontWeight: 700, color: textPrimary }}>
                Cardinality & Distinctness
              </h3>
            </div>

            <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: "10px" }}>
              <div>
                <div style={{ fontSize: "0.72rem", color: textMuted }}>Distinct Values</div>
                <div style={{ fontSize: "1rem", fontWeight: 700, color: textPrimary }}>
                  {distinctCount.toLocaleString()}
                </div>
              </div>
              <div>
                <div style={{ fontSize: "0.72rem", color: textMuted }}>Uniqueness Ratio</div>
                <div style={{ fontSize: "1rem", fontWeight: 700, color: textPrimary }}>
                  {distinctPct}%
                </div>
              </div>
            </div>
          </div>

          {/* Section 3: Descriptive Statistics (Numeric Only) */}
          {isNumeric && (
            <div
              style={{
                padding: "16px",
                borderRadius: "8px",
                background: bgSubtle,
                border: `1px solid ${borderCol}`,
              }}
            >
              <div style={{ display: "flex", alignItems: "center", gap: "6px", marginBottom: "12px" }}>
                <Activity size={14} color={brandPrimary} />
                <h3 style={{ margin: 0, fontSize: "0.86rem", fontWeight: 700, color: textPrimary }}>
                  Descriptive Statistics
                </h3>
              </div>

              <div style={{ display: "grid", gridTemplateColumns: "repeat(3, 1fr)", gap: "10px" }}>
                <div>
                  <div style={{ fontSize: "0.72rem", color: textMuted }}>Min</div>
                  <div style={{ fontSize: "0.92rem", fontWeight: 700, color: textPrimary }}>
                    {column.min != null ? column.min.toLocaleString() : "—"}
                  </div>
                </div>
                <div>
                  <div style={{ fontSize: "0.72rem", color: textMuted }}>Max</div>
                  <div style={{ fontSize: "0.92rem", fontWeight: 700, color: textPrimary }}>
                    {column.max != null ? column.max.toLocaleString() : "—"}
                  </div>
                </div>
                <div>
                  <div style={{ fontSize: "0.72rem", color: textMuted }}>Range</div>
                  <div style={{ fontSize: "0.92rem", fontWeight: 700, color: textPrimary }}>
                    {column.min != null && column.max != null ? (column.max - column.min).toLocaleString() : "—"}
                  </div>
                </div>
                <div>
                  <div style={{ fontSize: "0.72rem", color: textMuted }}>Mean</div>
                  <div style={{ fontSize: "0.92rem", fontWeight: 700, color: textPrimary }}>
                    {column.mean != null ? column.mean.toLocaleString() : "—"}
                  </div>
                </div>
                <div>
                  <div style={{ fontSize: "0.72rem", color: textMuted }}>Median</div>
                  <div style={{ fontSize: "0.92rem", fontWeight: 700, color: textPrimary }}>
                    {column.median != null ? column.median.toLocaleString() : "—"}
                  </div>
                </div>
                <div>
                  <div style={{ fontSize: "0.72rem", color: textMuted }}>Std Dev</div>
                  <div style={{ fontSize: "0.92rem", fontWeight: 700, color: textPrimary }}>
                    {column.std != null ? column.std.toLocaleString() : "—"}
                  </div>
                </div>
              </div>
            </div>
          )}

          {/* Section 4: Quartiles & Outlier Analysis */}
          {isNumeric && (
            <div
              style={{
                padding: "16px",
                borderRadius: "8px",
                background: bgSubtle,
                border: `1px solid ${borderCol}`,
              }}
            >
              <div style={{ display: "flex", alignItems: "center", gap: "6px", marginBottom: "12px" }}>
                <AlertTriangle size={14} color={hasOutliers ? "var(--color-warning, #D97706)" : brandPrimary} />
                <h3 style={{ margin: 0, fontSize: "0.86rem", fontWeight: 700, color: textPrimary }}>
                  Tukey IQR 1.5 Outlier Analysis
                </h3>
              </div>

              <div style={{ display: "grid", gridTemplateColumns: "repeat(2, 1fr)", gap: "10px", marginBottom: "12px" }}>
                <div>
                  <div style={{ fontSize: "0.72rem", color: textMuted }}>Potential Outliers</div>
                  <div style={{ fontSize: "1rem", fontWeight: 700, color: hasOutliers ? "var(--color-warning, #D97706)" : textPrimary }}>
                    {column.outlier_count || 0}
                  </div>
                </div>
                <div>
                  <div style={{ fontSize: "0.72rem", color: textMuted }}>IQR (Q3 - Q1)</div>
                  <div style={{ fontSize: "1rem", fontWeight: 700, color: textPrimary }}>
                    {column.iqr != null ? column.iqr.toLocaleString() : "—"}
                  </div>
                </div>
                <div>
                  <div style={{ fontSize: "0.72rem", color: textMuted }}>Lower Bound [Q1 - 1.5×IQR]</div>
                  <div style={{ fontSize: "0.88rem", fontWeight: 600, color: textSecondary }}>
                    {column.outlier_low != null ? column.outlier_low.toLocaleString() : "—"}
                  </div>
                </div>
                <div>
                  <div style={{ fontSize: "0.72rem", color: textMuted }}>Upper Bound [Q3 + 1.5×IQR]</div>
                  <div style={{ fontSize: "0.88rem", fontWeight: 600, color: textSecondary }}>
                    {column.outlier_high != null ? column.outlier_high.toLocaleString() : "—"}
                  </div>
                </div>
              </div>

              {column.outliers && column.outliers.length > 0 && (
                <div style={{ marginTop: "10px", paddingTop: "10px", borderTop: `1px solid ${borderCol}` }}>
                  <div style={{ fontSize: "0.72rem", color: textMuted, marginBottom: "6px" }}>Sample Outlier Values:</div>
                  <div style={{ display: "flex", gap: "6px", flexWrap: "wrap" }}>
                    {column.outliers.slice(0, 8).map((outVal, idx) => (
                      <span
                        key={idx}
                        style={{
                          padding: "2px 8px",
                          borderRadius: "4px",
                          fontSize: "0.75rem",
                          fontWeight: 600,
                          backgroundColor: "var(--color-bg-soft-warning, #FEF3C7)",
                          color: "var(--color-warning, #D97706)",
                        }}
                      >
                        {String(outVal)}
                      </span>
                    ))}
                    {column.outliers.length > 8 && (
                      <span style={{ fontSize: "0.72rem", color: textMuted, alignSelf: "center" }}>
                        +{column.outliers.length - 8} more
                      </span>
                    )}
                  </div>
                </div>
              )}

              <p style={{ margin: "10px 0 0 0", fontSize: "0.72rem", color: textMuted, lineHeight: 1.4 }}>
                Calculated via Tukey&apos;s IQR rule: values outside [Q1 - 1.5×IQR, Q3 + 1.5×IQR]. Outliers represent unusual observations, not errors.
              </p>
            </div>
          )}

          {/* Section 5: Distribution Bins (if numeric and bins exist) */}
          {bins.length > 0 && (
            <div
              style={{
                padding: "16px",
                borderRadius: "8px",
                background: bgSubtle,
                border: `1px solid ${borderCol}`,
              }}
            >
              <div style={{ display: "flex", alignItems: "center", gap: "6px", marginBottom: "12px" }}>
                <BarChart2 size={14} color={brandPrimary} />
                <h3 style={{ margin: 0, fontSize: "0.86rem", fontWeight: 700, color: textPrimary }}>
                  Distribution Frequency
                </h3>
              </div>

              <div style={{ display: "flex", flexDirection: "column", gap: "6px" }}>
                {bins.map((bin, idx) => {
                  const bCount = bin.count || 0;
                  const bPct = Math.round((bCount / maxBinCount) * 100);
                  const bLabel = bin.label || `${bin.bin_start} - ${bin.bin_end}`;
                  return (
                    <div key={idx} style={{ display: "flex", alignItems: "center", gap: "8px", fontSize: "0.75rem" }}>
                      <span style={{ width: "110px", color: textSecondary, overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }} title={bLabel}>
                        {bLabel}
                      </span>
                      <div
                        style={{
                          flex: 1,
                          height: "12px",
                          backgroundColor: "rgba(0, 0, 0, 0.05)",
                          borderRadius: "3px",
                          overflow: "hidden",
                        }}
                      >
                        <div
                          style={{
                            width: `${bPct}%`,
                            height: "100%",
                            backgroundColor: brandPrimary,
                          }}
                        />
                      </div>
                      <span style={{ width: "35px", textAlign: "right", fontWeight: 600, color: textPrimary }}>
                        {bCount}
                      </span>
                    </div>
                  );
                })}
              </div>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
