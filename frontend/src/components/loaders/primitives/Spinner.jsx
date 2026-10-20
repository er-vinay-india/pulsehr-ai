import React from "react";
import "../loaders.scss";

/**
 * Scalable SVG Ring Spinner
 * Renders smooth stroke-dasharray SVG animation. Zero dependencies.
 */
export default function Spinner({
  size = "md", // 'xs' (12px) | 'sm' (16px) | 'md' (24px) | 'lg' (36px) | 'xl' (48px) | number
  color = "var(--color-brand-primary, #183B56)",
  trackColor = "var(--color-divider, rgba(0, 0, 0, 0.1))",
  strokeWidth = 3,
  className = "",
  style = {},
  ariaLabel = "Loading",
}) {
  const sizeMap = {
    xs: 12,
    sm: 16,
    md: 24,
    lg: 36,
    xl: 48,
  };

  const dimension = typeof size === "number" ? size : sizeMap[size] || 24;

  return (
    <svg
      role="status"
      aria-label={ariaLabel}
      className={`highview-spinner ${className}`}
      width={dimension}
      height={dimension}
      viewBox="0 0 50 50"
      style={{
        display: "inline-block",
        verticalAlign: "middle",
        flexShrink: 0,
        ...style,
      }}
    >
      <circle
        cx="25"
        cy="25"
        r="20"
        fill="none"
        stroke={trackColor}
        strokeWidth={strokeWidth}
      />
      <circle
        cx="25"
        cy="25"
        r="20"
        fill="none"
        stroke={color}
        strokeWidth={strokeWidth}
        strokeDasharray="80"
        strokeDashoffset="60"
        strokeLinecap="round"
        style={{
          transformOrigin: "center",
          animation: "dash-spin 1.4s ease-in-out infinite",
        }}
      />
    </svg>
  );
}
