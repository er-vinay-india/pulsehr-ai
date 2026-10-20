import React from "react";
import "../loaders.scss";

/**
 * DeterminatePhaseBar
 * Segmented progress bar showing progression through discrete phases with dynamic ticker text.
 */
export default function DeterminatePhaseBar({
  totalPhases = 10,
  activePhase = 1,
  phaseLabel = "",
  subLabel = "",
  percent,
  className = "",
  style = {},
}) {
  const calculatedPercent =
    typeof percent === "number"
      ? percent
      : Math.min(100, Math.round((activePhase / totalPhases) * 100));

  return (
    <div
      role="progressbar"
      aria-label="Phase progress"
      aria-valuenow={calculatedPercent}
      aria-valuemin={0}
      aria-valuemax={100}
      className={`highview-determinate-phase-bar ${className}`}
      style={{ display: "flex", flexDirection: "column", gap: "8px", width: "100%", ...style }}
    >
      {/* Segmented Bar Track */}
      <div
        style={{
          display: "grid",
          gridTemplateColumns: `repeat(${totalPhases}, 1fr)`,
          gap: "4px",
          width: "100%",
          height: "6px",
        }}
      >
        {Array.from({ length: totalPhases }).map((_, i) => {
          const stepNumber = i + 1;
          const isDone = stepNumber < activePhase;
          const isCurrent = stepNumber === activePhase;

          return (
            <div
              key={i}
              style={{
                height: "100%",
                borderRadius: "3px",
                backgroundColor: isDone
                  ? "var(--color-success, #075443)"
                  : isCurrent
                  ? "var(--color-brand-primary, #183B56)"
                  : "var(--color-border, #D4DDD6)",
                transition: "background-color 0.3s ease",
              }}
            />
          );
        })}
      </div>

      {/* Dynamic Status Ticker */}
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", fontSize: "0.76rem" }}>
        <span style={{ fontWeight: 600, color: "var(--color-text-primary, #172B3A)" }}>
          {phaseLabel || `Phase ${activePhase} of ${totalPhases}`}
        </span>
        <span style={{ color: "var(--color-text-secondary, #475569)" }}>
          {subLabel || `${calculatedPercent}% Complete`}
        </span>
      </div>
    </div>
  );
}
