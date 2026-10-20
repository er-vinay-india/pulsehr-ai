import React from "react";
import "../loaders.scss";

/**
 * Universal Linear Progress Bar
 * Supports determinate (0-100%) and indeterminate modes.
 */
export default function ProgressBar({
  value, // number 0-100 or null/undefined for indeterminate
  height = "4px",
  color = "var(--color-brand-primary, #183B56)",
  trackColor = "var(--color-border-subtle, rgba(0, 0, 0, 0.08))",
  borderRadius = "2px",
  className = "",
  style = {},
  ariaLabel = "Progress indicator",
}) {
  const isDeterminate = typeof value === "number" && !isNaN(value);
  const clampedValue = isDeterminate ? Math.max(0, Math.min(100, value)) : null;

  return (
    <div
      role="progressbar"
      aria-label={ariaLabel}
      aria-valuenow={isDeterminate ? clampedValue : undefined}
      aria-valuemin={0}
      aria-valuemax={100}
      className={`highview-progress-bar ${className}`}
      style={{
        width: "100%",
        height,
        backgroundColor: trackColor,
        borderRadius,
        overflow: "hidden",
        position: "relative",
        ...style,
      }}
    >
      <div
        style={{
          height: "100%",
          backgroundColor: color,
          borderRadius,
          transition: isDeterminate ? "width 0.3s ease" : "none",
          width: isDeterminate ? `${clampedValue}%` : "35%",
          ...(isDeterminate
            ? {}
            : {
                position: "absolute",
                animation: "subtle-shimmer 1.5s infinite linear",
              }),
        }}
      />
    </div>
  );
}
