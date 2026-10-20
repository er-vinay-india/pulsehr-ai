import React from "react";
import RefetchBadge from "./RefetchBadge";
import { AlertCircle, RefreshCw } from "lucide-react";

/**
 * Smart Query Boundary Orchestrator
 * Separates hard initial load (`isLoading`) from soft background sync (`isFetching`).
 */
export default function QueryBoundary({
  isLoading = false,
  isFetching = false,
  error = null,
  onRetry = null,
  skeleton = null,
  refetchLabel = "Updating results…",
  children,
}) {
  // 1. Error State
  if (error) {
    return (
      <div
        role="alert"
        style={{
          padding: "16px 20px",
          borderRadius: "8px",
          background: "var(--color-bg-soft-error, #FAEAEE)",
          border: "1px solid var(--color-error, #8E1938)",
          color: "var(--color-error, #8E1938)",
          display: "flex",
          alignItems: "center",
          justifyContent: "space-between",
          gap: "12px",
          fontSize: "0.85rem",
        }}
      >
        <div style={{ display: "flex", alignItems: "center", gap: "8px" }}>
          <AlertCircle size={18} style={{ flexShrink: 0 }} />
          <span>{typeof error === "string" ? error : error?.message || "Failed to load data"}</span>
        </div>
        {onRetry && (
          <button
            type="button"
            onClick={onRetry}
            style={{
              display: "inline-flex",
              alignItems: "center",
              gap: "4px",
              padding: "4px 10px",
              borderRadius: "6px",
              background: "var(--color-bg-surface, #ffffff)",
              border: "1px solid var(--color-error, #8E1938)",
              color: "var(--color-error, #8E1938)",
              fontSize: "0.78rem",
              fontWeight: 600,
              cursor: "pointer",
            }}
          >
            <RefreshCw size={12} />
            Retry
          </button>
        )}
      </div>
    );
  }

  // 2. Hard Load State (no existing data on screen)
  if (isLoading) {
    return skeleton || null;
  }

  // 3. Render Children with optional soft background refetch badge & subtle opacity
  return (
    <div style={{ position: "relative", width: "100%" }}>
      {isFetching && (
        <div
          style={{
            position: "absolute",
            top: "8px",
            right: "8px",
            zIndex: 15,
          }}
        >
          <RefetchBadge active={true} label={refetchLabel} />
        </div>
      )}
      <div
        style={{
          transition: "opacity 0.2s ease",
          opacity: isFetching ? 0.75 : 1,
          pointerEvents: isFetching ? "none" : "auto",
        }}
      >
        {children}
      </div>
    </div>
  );
}
