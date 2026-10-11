import React from "react";
import { ArrowRight } from "lucide-react";

/**
 * Standardized Level-1 Card Action Controller.
 * Provides a clean, two-tier action hierarchy:
 * - Primary Action: "Inspect" button to open the Quick Inspect drawer.
 * - Secondary Action: Contextual deep-link into the Data Explorer.
 */
export default function CardActions({
  primary,
  secondary,
  themeTokens,
  isDark = false,
  className = "",
}) {
  return (
    <div
      className={`card-actions-group ${className}`.trim()}
      style={{
        display: "flex",
        alignItems: "center",
        gap: "6px",
        flexShrink: 0,
      }}
    >
      {secondary && secondary.href && (
        <a
          href={secondary.href}
          onClick={(e) => {
            if (secondary.onClick) {
              secondary.onClick(e);
            } else {
              e.preventDefault();
              window.location.href = secondary.href;
            }
          }}
          className="card-btn-deep-dive"
          style={{
            textDecoration: "none",
            border: `1px solid ${themeTokens?.colors?.brandBlue || "#2563eb"}`,
            borderRadius: "6px",
            color: themeTokens?.colors?.brandBlue || "#2563eb",
            fontSize: "0.70rem",
            fontWeight: 600,
            padding: "2px 7px",
            display: "inline-flex",
            alignItems: "center",
            gap: "3px",
            backgroundColor: isDark ? "rgba(37, 99, 235, 0.12)" : "rgba(37, 99, 235, 0.06)",
            cursor: "pointer",
            transition: "all 0.15s ease",
          }}
          aria-label={secondary.ariaLabel || `${secondary.label} in Data Explorer`}
        >
          <span>{secondary.label}</span>
          <ArrowRight size={10} aria-hidden="true" />
        </a>
      )}

      {primary && (
        <button
          type="button"
          className="card-btn-inspect"
          onClick={primary.onClick}
          style={{
            background: "transparent",
            border: `1px solid ${themeTokens?.colors?.borderSubtle || "rgba(0, 0, 0, 0.12)"}`,
            borderRadius: "6px",
            color: themeTokens?.colors?.textSecondary || "#64748b",
            fontSize: "0.70rem",
            fontWeight: 600,
            padding: "2px 8px",
            cursor: "pointer",
            display: "inline-flex",
            alignItems: "center",
            gap: "3px",
            transition: "all 0.15s ease",
          }}
          aria-label={primary.ariaLabel || `Inspect ${primary.label}`}
        >
          <span>{primary.label}</span>
        </button>
      )}
    </div>
  );
}
