import React from "react";
import Spinner from "../primitives/Spinner";
import "../loaders.scss";

/**
 * BlockingOverlayLoader
 * Frosted-glass container guard strictly scoped to a form or drawer container.
 * Prevents user interactions while critical mutations are in flight.
 */
export default function BlockingOverlayLoader({
  active = false,
  label = "Processing updates…",
  blur = "3px",
  style = {},
}) {
  if (!active) return null;

  return (
    <div
      role="status"
      aria-live="polite"
      className="highview-blocking-overlay"
      style={{
        position: "absolute",
        inset: 0,
        backgroundColor: "rgba(255, 255, 255, 0.72)",
        backdropFilter: `blur(${blur})`,
        WebkitBackdropFilter: `blur(${blur})`,
        display: "flex",
        flexDirection: "column",
        alignItems: "center",
        justifyContent: "center",
        gap: "10px",
        zIndex: 50,
        borderRadius: "inherit",
        pointerEvents: "auto",
        ...style,
      }}
    >
      <Spinner size={28} strokeWidth={3} color="var(--color-brand-primary, #183B56)" />
      {label && (
        <span
          style={{
            fontSize: "0.82rem",
            fontWeight: 600,
            color: "var(--color-text-primary, #172B3A)",
          }}
        >
          {label}
        </span>
      )}
    </div>
  );
}
