import React from "react";
import SkeletonBlock from "../query/SkeletonBlock";
import Shimmer from "../primitives/Shimmer";

/**
 * Structural Full-Page Wireframe Skeleton
 * Matches HighView layout frames to prevent layout flash during route / tab switches.
 */
export default function PageShellSkeleton({ layout = "explorer" }) {
  return (
    <div
      role="status"
      aria-label="Loading page structure"
      style={{
        padding: "24px 32px",
        display: "flex",
        flexDirection: "column",
        gap: "20px",
        width: "100%",
        maxWidth: "1440px",
        margin: "0 auto",
      }}
    >
      {/* Top Header Placeholder */}
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", gap: "16px" }}>
        <div style={{ display: "flex", flexDirection: "column", gap: "6px", width: "280px" }}>
          <Shimmer width="180px" height="28px" borderRadius="6px" />
          <Shimmer width="260px" height="14px" borderRadius="4px" />
        </div>
        <div style={{ display: "flex", gap: "10px" }}>
          <Shimmer width="120px" height="36px" borderRadius="8px" />
          <Shimmer width="100px" height="36px" borderRadius="8px" />
        </div>
      </div>

      {/* Scope Selector Bar Placeholder */}
      <div
        style={{
          padding: "14px 16px",
          borderRadius: "10px",
          background: "var(--color-bg-surface, #ffffff)",
          border: "1px solid var(--color-border-subtle, rgba(0,0,0,0.08))",
          display: "flex",
          justifyContent: "space-between",
          alignItems: "center",
        }}
      >
        <Shimmer width="260px" height="32px" borderRadius="6px" />
        <div style={{ display: "flex", gap: "8px" }}>
          <Shimmer width="90px" height="32px" borderRadius="6px" />
          <Shimmer width="90px" height="32px" borderRadius="6px" />
        </div>
      </div>

      {/* 4 Summary KPI Cards */}
      <SkeletonBlock variant="card" count={4} />

      {/* Main Table Structure Placeholder */}
      <div
        style={{
          padding: "16px",
          borderRadius: "10px",
          background: "var(--color-bg-surface, #ffffff)",
          border: "1px solid var(--color-border-subtle, rgba(0,0,0,0.08))",
          display: "flex",
          flexDirection: "column",
          gap: "14px",
        }}
      >
        <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
          <Shimmer width="200px" height="20px" borderRadius="4px" />
          <Shimmer width="140px" height="30px" borderRadius="6px" />
        </div>
        <SkeletonBlock variant="table-row" count={8} columns={layout === "dashboard" ? 4 : 7} />
      </div>
    </div>
  );
}
