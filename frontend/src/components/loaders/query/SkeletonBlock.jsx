import React from "react";
import Shimmer from "../primitives/Shimmer";

/**
 * Dimension-Accurate Composable Skeleton Block
 * Supports multiple variants to prevent layout shifts.
 */
export default function SkeletonBlock({
  variant = "rect", // 'text' | 'rect' | 'circle' | 'card' | 'table-row'
  count = 1,
  width,
  height,
  borderRadius,
  className = "",
  style = {},
  columns = 6, // for table-row variant
}) {
  const items = Array.from({ length: Math.max(1, count) });

  if (variant === "text") {
    return (
      <div
        className={`highview-skeleton-group ${className}`}
        style={{ display: "flex", flexDirection: "column", gap: "8px", width: width || "100%", ...style }}
      >
        {items.map((_, i) => (
          <Shimmer
            key={i}
            width={i === items.length - 1 && items.length > 1 ? "70%" : "100%"}
            height={height || "14px"}
            borderRadius={borderRadius || "4px"}
          />
        ))}
      </div>
    );
  }

  if (variant === "circle") {
    const size = width || height || "40px";
    return (
      <div className={className} style={{ display: "flex", gap: "10px", alignItems: "center", ...style }}>
        {items.map((_, i) => (
          <Shimmer key={i} width={size} height={size} borderRadius="50%" />
        ))}
      </div>
    );
  }

  if (variant === "card") {
    return (
      <div
        className={`highview-skeleton-cards ${className}`}
        style={{
          display: "grid",
          gridTemplateColumns: "repeat(auto-fit, minmax(200px, 1fr))",
          gap: "12px",
          width: "100%",
          ...style,
        }}
      >
        {items.map((_, i) => (
          <div
            key={i}
            style={{
              padding: "16px",
              borderRadius: "10px",
              background: "var(--color-bg-surface, #ffffff)",
              border: "1px solid var(--color-border-subtle, rgba(0,0,0,0.08))",
              display: "flex",
              flexDirection: "column",
              gap: "10px",
            }}
          >
            <div style={{ display: "flex", alignItems: "center", gap: "10px" }}>
              <Shimmer width="36px" height="36px" borderRadius="8px" />
              <div style={{ flex: 1, display: "flex", flexDirection: "column", gap: "6px" }}>
                <Shimmer width="40%" height="20px" borderRadius="4px" />
                <Shimmer width="75%" height="12px" borderRadius="3px" />
              </div>
            </div>
          </div>
        ))}
      </div>
    );
  }

  if (variant === "table-row") {
    return (
      <div
        className={`highview-skeleton-table-rows ${className}`}
        style={{ display: "flex", flexDirection: "column", gap: "1px", width: "100%", ...style }}
      >
        {items.map((_, rowIdx) => (
          <div
            key={rowIdx}
            style={{
              display: "grid",
              gridTemplateColumns: `repeat(${columns}, 1fr)`,
              gap: "12px",
              padding: "12px 14px",
              background: rowIdx % 2 === 0 ? "var(--color-bg-surface, #ffffff)" : "var(--color-bg-subtle, rgba(0,0,0,0.02))",
              borderBottom: "1px solid var(--color-border-subtle, rgba(0,0,0,0.06))",
              alignItems: "center",
            }}
          >
            {Array.from({ length: columns }).map((_, colIdx) => {
              // Vary cell width naturally to mimic real text distribution
              const cellWidths = ["85%", "60%", "75%", "90%", "50%", "70%"];
              const cellWidth = cellWidths[colIdx % cellWidths.length];
              return (
                <Shimmer
                  key={colIdx}
                  width={cellWidth}
                  height={height || "14px"}
                  borderRadius={borderRadius || "4px"}
                />
              );
            })}
          </div>
        ))}
      </div>
    );
  }

  // Default 'rect'
  return (
    <div
      className={`highview-skeleton-rects ${className}`}
      style={{ display: "flex", flexDirection: "column", gap: "8px", width: width || "100%", ...style }}
    >
      {items.map((_, i) => (
        <Shimmer
          key={i}
          width="100%"
          height={height || "38px"}
          borderRadius={borderRadius || "8px"}
        />
      ))}
    </div>
  );
}
