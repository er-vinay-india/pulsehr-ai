import React from "react";
import { CheckCircle2, AlertCircle, Clock } from "lucide-react";
import Spinner from "../primitives/Spinner";
import "../loaders.scss";

/**
 * PhaseStepperLoader
 * Multi-stage sequential pipeline progress indicator.
 * Used for Ingestion (10 stages), Presentation generation, and complex Q&A pipelines.
 */
export default function PhaseStepperLoader({
  phases = [],
  currentPhaseIndex = 0,
  errorPhaseIndex = -1,
  elapsedSeconds = 0,
  orientation = "vertical", // 'vertical' | 'horizontal'
  className = "",
  style = {},
}) {
  return (
    <div
      role="region"
      aria-label="Process stages"
      className={`highview-phase-stepper ${className}`}
      style={{
        display: "flex",
        flexDirection: orientation === "horizontal" ? "row" : "column",
        gap: orientation === "horizontal" ? "16px" : "10px",
        width: "100%",
        ...style,
      }}
    >
      {phases.map((phase, idx) => {
        const isCompleted = idx < currentPhaseIndex;
        const isActive = idx === currentPhaseIndex && errorPhaseIndex !== idx;
        const isError = idx === errorPhaseIndex;
        const isPending = idx > currentPhaseIndex;

        return (
          <div
            key={phase.id || idx}
            style={{
              display: "flex",
              alignItems: "flex-start",
              gap: "12px",
              padding: "8px 12px",
              borderRadius: "8px",
              background: isActive
                ? "var(--color-bg-soft-blue, #EAF0F5)"
                : isError
                ? "var(--color-bg-soft-error, #FAEAEE)"
                : "transparent",
              transition: "all 0.2s ease",
              opacity: isPending ? 0.55 : 1,
            }}
          >
            {/* Status Icon Indicator */}
            <div
              style={{
                width: "24px",
                height: "24px",
                display: "flex",
                alignItems: "center",
                justifyContent: "center",
                flexShrink: 0,
                marginTop: "1px",
              }}
            >
              {isCompleted ? (
                <CheckCircle2 size={18} color="var(--color-success, #075443)" />
              ) : isActive ? (
                <Spinner size={18} strokeWidth={3.5} color="var(--color-brand-primary, #183B56)" />
              ) : isError ? (
                <AlertCircle size={18} color="var(--color-error, #8E1938)" />
              ) : (
                <div
                  style={{
                    width: "10px",
                    height: "10px",
                    borderRadius: "50%",
                    background: "var(--color-border, #D4DDD6)",
                  }}
                />
              )}
            </div>

            {/* Stage Title and Description */}
            <div style={{ flex: 1, minWidth: 0 }}>
              <div
                style={{
                  fontSize: "0.82rem",
                  fontWeight: isActive ? 700 : 600,
                  color: isError
                    ? "var(--color-error, #8E1938)"
                    : isActive
                    ? "var(--color-brand-primary, #183B56)"
                    : "var(--color-text-primary, #172B3A)",
                  display: "flex",
                  alignItems: "center",
                  justifyContent: "space-between",
                  gap: "8px",
                }}
              >
                <span>{phase.label || phase.title}</span>
                {isActive && elapsedSeconds > 0 && (
                  <span
                    style={{
                      fontSize: "0.72rem",
                      fontWeight: 500,
                      color: "var(--color-text-secondary, #475569)",
                      display: "flex",
                      alignItems: "center",
                      gap: "3px",
                    }}
                  >
                    <Clock size={11} />
                    {elapsedSeconds}s
                  </span>
                )}
              </div>
              {(phase.description || phase.sub) && (
                <p
                  style={{
                    margin: "2px 0 0 0",
                    fontSize: "0.74rem",
                    color: "var(--color-text-secondary, #475569)",
                    lineHeight: 1.35,
                  }}
                >
                  {phase.description || phase.sub}
                </p>
              )}
            </div>
          </div>
        );
      })}
    </div>
  );
}
