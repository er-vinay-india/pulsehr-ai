import React from "react";
import { ArrowRight } from "lucide-react";
import Button from "../../design-system/components/Button";

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
      {secondary && (
        <Button
          variant="GHOST"
          size="sm"
          iconRight={ArrowRight}
          onClick={secondary.onClick}
          ariaLabel={secondary.ariaLabel || `${secondary.label} in Data Explorer`}
          style={{ fontSize: "0.70rem", padding: "2px 7px" }}
        >
          {secondary.label}
        </Button>
      )}

      {primary && (
        <Button
          variant="GHOST"
          size="sm"
          onClick={primary.onClick}
          ariaLabel={primary.ariaLabel || `Inspect ${primary.label}`}
          style={{ fontSize: "0.70rem", padding: "2px 8px" }}
        >
          {primary.label}
        </Button>
      )}
    </div>
  );
}
