import React from "react";
import Spinner from "../primitives/Spinner";
import "../loaders.scss";

/**
 * AppSplashLoader
 * Fullscreen branded boot screen for initial startup, authentication checks, or tenant boot.
 */
export default function AppSplashLoader({
  message = "Initializing HighView Intelligence…",
  subMessage = "Governed Dataset Fabric & Invariant Verification",
  isExiting = false,
}) {
  return (
    <div
      role="status"
      aria-live="polite"
      style={{
        position: "fixed",
        inset: 0,
        width: "100vw",
        height: "100vh",
        backgroundColor: "var(--color-bg-page, #F6F5F0)",
        display: "flex",
        flexDirection: "column",
        alignItems: "center",
        justifyContent: "center",
        zIndex: 99999,
        transition: "opacity 0.3s ease-out",
        opacity: isExiting ? 0 : 1,
        pointerEvents: isExiting ? "none" : "auto",
      }}
    >
      <div
        style={{
          display: "flex",
          flexDirection: "column",
          alignItems: "center",
          gap: "16px",
          maxWidth: "400px",
          textAlign: "center",
          padding: "24px",
        }}
      >
        {/* Animated Brand Pulse */}
        <div
          style={{
            width: "56px",
            height: "56px",
            borderRadius: "14px",
            background: "var(--color-bg-soft-blue, #EAF0F5)",
            border: "1px solid var(--color-border-subtle, rgba(0,0,0,0.08))",
            display: "flex",
            alignItems: "center",
            justifyContent: "center",
            animation: "pulse-glow 2s infinite ease-in-out",
          }}
        >
          <Spinner size={28} strokeWidth={3} color="var(--color-brand-primary, #183B56)" />
        </div>

        <div>
          <h2
            style={{
              margin: 0,
              fontSize: "1.1rem",
              fontWeight: 700,
              color: "var(--color-text-primary, #172B3A)",
              letterSpacing: "-0.01em",
            }}
          >
            {message}
          </h2>
          {subMessage && (
            <p
              style={{
                margin: "6px 0 0 0",
                fontSize: "0.8rem",
                color: "var(--color-text-secondary, #475569)",
              }}
            >
              {subMessage}
            </p>
          )}
        </div>
      </div>
    </div>
  );
}
