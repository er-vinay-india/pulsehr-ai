import React, { useEffect, useRef } from "react";
import "../loaders.scss";

/**
 * ViewportSentinelLoader
 * Compact intersection sentinel placed at the bottom of long feeds, virtualized tables, or tree nodes.
 * Automatically fires `onLoadMore` when scrolled into view.
 */
export default function ViewportSentinelLoader({
  hasMore = false,
  isLoadingMore = false,
  onLoadMore = () => {},
  loadingLabel = "Loading additional records…",
  rootMargin = "100px",
}) {
  const sentinelRef = useRef(null);

  useEffect(() => {
    if (!hasMore || isLoadingMore) return;

    const observer = new IntersectionObserver(
      (entries) => {
        if (entries[0].isIntersecting) {
          onLoadMore();
        }
      },
      { rootMargin }
    );

    const currentEl = sentinelRef.current;
    if (currentEl) observer.observe(currentEl);

    return () => {
      if (currentEl) observer.unobserve(currentEl);
    };
  }, [hasMore, isLoadingMore, onLoadMore, rootMargin]);

  if (!hasMore && !isLoadingMore) return null;

  return (
    <div
      ref={sentinelRef}
      role="status"
      aria-live="polite"
      style={{
        display: "flex",
        alignItems: "center",
        justifyContent: "center",
        gap: "8px",
        padding: "16px",
        width: "100%",
      }}
    >
      {isLoadingMore ? (
        <div style={{ display: "flex", alignItems: "center", gap: "6px" }}>
          {/* Animated 3-dot wave */}
          <div style={{ display: "flex", gap: "4px" }}>
            {[0, 1, 2].map((i) => (
              <div
                key={i}
                style={{
                  width: "6px",
                  height: "6px",
                  borderRadius: "50%",
                  backgroundColor: "var(--color-brand-primary, #183B56)",
                  animation: `wave-dot 1.2s infinite ease-in-out ${i * 0.16}s`,
                }}
              />
            ))}
          </div>
          <span style={{ fontSize: "0.76rem", color: "var(--color-text-secondary, #475569)", fontWeight: 500 }}>
            {loadingLabel}
          </span>
        </div>
      ) : (
        <div style={{ height: "1px", width: "100%" }} />
      )}
    </div>
  );
}
