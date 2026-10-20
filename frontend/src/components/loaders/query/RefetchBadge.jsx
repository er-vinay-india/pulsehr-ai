import React from "react";
import Spinner from "../primitives/Spinner";

/**
 * Non-Blocking Background Refetch Indicator
 * Shows users that data is syncing without blocking interaction or flashing white.
 */
export default function RefetchBadge({
  active = false,
  label = "Updating results…",
  className = "",
  style = {},
}) {
  if (!active) return null;

  return (
    <div
      role="status"
      aria-live="polite"
      className={`highview-refetch-badge ${className}`}
      style={{
        display: "inline-flex",
        alignItems: "center",
        gap: "6px",
        padding: "3px 8px",
        borderRadius: "12px",
        background: "var(--color-bg-surface, #ffffff)",
        border: "1px solid var(--color-border, #D4DDD6)",
        boxShadow: "0 2px 6px rgba(0, 0, 0, 0.08)",
        fontSize: "0.72rem",
        fontWeight: 600,
        color: "var(--color-brand-primary, #183B56)",
        pointerEvents: "none",
        zIndex: 20,
        ...style,
      }}
    >
      <Spinner size={12} strokeWidth={3.5} color="var(--color-brand-primary, #183B56)" />
      <span>{label}</span>
    </div>
  );
}
