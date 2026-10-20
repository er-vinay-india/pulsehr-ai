import React from "react";
import "../loaders.scss";

/**
 * Theme-Adaptive Shimmer Primitive
 * Base placeholder block that adapts cleanly across light and dark modes.
 */
export default function Shimmer({
  width = "100%",
  height = "16px",
  borderRadius = "6px",
  className = "",
  style = {},
  ariaHidden = true,
}) {
  return (
    <div
      aria-hidden={ariaHidden}
      className={`highview-shimmer ${className}`}
      style={{
        width,
        height,
        borderRadius,
        display: "block",
        ...style,
      }}
    />
  );
}
