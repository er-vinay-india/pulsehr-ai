import React from "react";
import { resolvePresentationLabel } from "../registries/PresentationLabelResolver";

/**
 * Standardized Metadata Eyebrow Badge.
 * Replaces heading-like styling on section badges and status pills.
 */
export default function Badge({
  children,
  variant = "neutral", // "neutral" | "success" | "warning" | "brand"
  size = "sm",         // "xs" | "sm"
  className = "",
  style = {},
}) {
  const label = typeof children === "string" ? resolvePresentationLabel(children) : children;

  const variantStyles = {
    neutral: {
      backgroundColor: "var(--color-bg-subtle, #EEEFE9)",
      color: "var(--color-text-secondary, #334B57)",
      border: "1px solid var(--color-border, #D4DDD6)",
    },
    success: {
      backgroundColor: "var(--color-bg-soft-teal, #E7F3ED)",
      color: "var(--color-success, #075443)",
      border: "1px solid var(--color-border-strong, #78877F)",
    },
    warning: {
      backgroundColor: "var(--color-bg-soft-gold, #F6EDDA)",
      color: "var(--color-warning, #65470C)",
      border: "1px solid var(--color-gold, #65470C)",
    },
    brand: {
      backgroundColor: "var(--color-bg-soft-blue, #EAF0F5)",
      color: "var(--color-brand-blue, #234E70)",
      border: "1px solid var(--color-brand-blue, #234E70)",
    },
  }[variant] || {
    backgroundColor: "var(--color-bg-subtle, #EEEFE9)",
    color: "var(--color-text-secondary, #334B57)",
    border: "1px solid var(--color-border, #D4DDD6)",
  };

  return (
    <span
      className={`hv-badge hv-badge--${variant} ${className}`.trim()}
      style={{
        display: "inline-flex",
        alignItems: "center",
        justifyContent: "center",
        fontSize: size === "xs" ? "0.625rem" : "0.6875rem",
        fontWeight: 700,
        textTransform: "uppercase",
        letterSpacing: "0.06em",
        padding: size === "xs" ? "1px 5px" : "2px 8px",
        borderRadius: "4px",
        lineHeight: 1.2,
        whiteSpace: "nowrap",
        ...variantStyles,
        ...style,
      }}
    >
      {label}
    </span>
  );
}
