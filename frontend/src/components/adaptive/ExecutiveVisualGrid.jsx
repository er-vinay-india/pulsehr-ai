import React from "react";

/**
 * 12-Column CSS Grid Container for Executive Decision Stories.
 * Strictly layout-only without DOM reordering.
 */
export default function ExecutiveVisualGrid({
  children,
  className = "",
  "data-testid": testId,
  ...props
}) {
  return (
    <div
      className={`executive-visual-grid ${className}`.trim()}
      data-testid={testId}
      {...props}
    >
      {children}
    </div>
  );
}
