import React from "react";
import {
  CheckCircle2,
  ShieldCheck,
  AlertTriangle,
  XCircle,
  Info,
  Sparkles,
  Database,
  Lock,
  Layers,
  Key,
} from "lucide-react";

/**
 * Standardized Accessible Status Badge for Data Explorer.
 * Derives colors entirely from centralized HighView theme tokens.
 * Complies with WCAG AAA & color-vision independence:
 * meaning is always conveyed through text + icon, never color alone.
 */
export default function StatusBadge({
  status,
  variant = null, // "success" | "warning" | "danger" | "info" | "neutral"
  icon: CustomIcon = null,
  size = "sm",
  className = "",
  style = {},
}) {
  // Automatic semantic variant mapping if not explicitly provided
  const resolvedVariant = variant || (() => {
    const s = String(status || "").toLowerCase();
    if (s.includes("safe to join") || s.includes("safe after aggregation") || s.includes("safe") || s.includes("current") || s.includes("verified") || s.includes("high") || s.includes("identified") || s.includes("exact") || s.includes("valid") || s.includes("resolved") || s.includes("clear")) {
      return "success";
    }
    if (s.includes("needs review") || s.includes("needs refresh") || s.includes("aggregation") || s.includes("candidate") || s.includes("medium") || s.includes("clarification") || s.includes("ambiguous") || s.includes("warning")) {
      return "warning";
    }
    if (s.includes("unsafe") || s.includes("stale") || s.includes("blocked") || s.includes("error") || s.includes("fail") || s.includes("low") || s.includes("danger")) {
      return "danger";
    }
    if (s.includes("derived") || s.includes("virtual") || s.includes("enriched") || s.includes("canonical") || s.includes("materialized")) {
      return "info";
    }
    if (s.includes("source") || s.includes("observed")) {
      return "neutral";
    }
    return "neutral";
  })();

  const DefaultIcon = (() => {
    switch (resolvedVariant) {
      case "success":
        return CheckCircle2;
      case "warning":
        return AlertTriangle;
      case "danger":
        return XCircle;
      case "info":
        return Sparkles;
      default:
        return Database;
    }
  })();

  const IconComponent = CustomIcon || DefaultIcon;

  const variantStyles = {
    success: {
      backgroundColor: "var(--hv-status-success-bg, var(--color-bg-soft-teal, #E7F3ED))",
      color: "var(--hv-status-success, var(--color-success, #075443))",
      borderColor: "var(--hv-status-success-border, var(--color-border-strong, #78877F))",
    },
    warning: {
      backgroundColor: "var(--color-bg-soft-gold, #F6EDDA)",
      color: "var(--hv-status-warning, var(--color-warning, #65470C))",
      borderColor: "var(--color-border, #D4DDD6)",
    },
    danger: {
      backgroundColor: "var(--color-bg-soft-error, #FAEAEE)",
      color: "var(--hv-status-error, var(--color-error, #8E1938))",
      borderColor: "var(--color-border, #D4DDD6)",
    },
    info: {
      backgroundColor: "var(--hv-info-bg, var(--color-bg-soft-blue, #EAF0F5))",
      color: "var(--hv-info, var(--color-brand-blue, #234E70))",
      borderColor: "var(--color-border, #D4DDD6)",
    },
    neutral: {
      backgroundColor: "var(--color-bg-subtle, #EEEFE9)",
      color: "var(--color-text-secondary, #334B57)",
      borderColor: "var(--color-border, #D4DDD6)",
    },
  }[resolvedVariant];

  const iconSize = size === "xs" ? 11 : 13;

  return (
    <span
      className={`hv-status-badge hv-status-badge--${resolvedVariant} ${className}`.trim()}
      style={{
        display: "inline-flex",
        alignItems: "center",
        gap: "4px",
        fontSize: size === "xs" ? "0.7rem" : "0.75rem",
        fontWeight: 600,
        padding: size === "xs" ? "2px 6px" : "3px 8px",
        borderRadius: "6px",
        border: "1px solid",
        lineHeight: 1.25,
        whiteSpace: "nowrap",
        ...variantStyles,
        ...style,
      }}
    >
      <IconComponent size={iconSize} aria-hidden="true" style={{ flexShrink: 0 }} />
      <span>{status}</span>
    </span>
  );
}
