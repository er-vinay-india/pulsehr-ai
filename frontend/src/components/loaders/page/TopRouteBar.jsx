import React, { useEffect, useState } from "react";
import "../loaders.scss";

/**
 * TopRouteBar
 * Ultra-thin (3px) glowing navigation progress bar at the top of the viewport.
 * Simulates rapid initial trickle to 85% and snaps to 100% on route completion.
 */
export default function TopRouteBar({
  isAnimating = false,
  color = "var(--color-brand-primary, #183B56)",
}) {
  const [progress, setProgress] = useState(0);
  const [visible, setVisible] = useState(false);

  useEffect(() => {
    let timer;
    if (isAnimating) {
      setVisible(true);
      setProgress(25);

      timer = setInterval(() => {
        setProgress((prev) => {
          if (prev >= 85) {
            clearInterval(timer);
            return 85;
          }
          return prev + Math.floor(Math.random() * 12) + 5;
        });
      }, 150);
    } else {
      if (visible) {
        setProgress(100);
        const hideTimer = setTimeout(() => {
          setVisible(false);
          setProgress(0);
        }, 320);
        return () => clearTimeout(hideTimer);
      }
    }

    return () => clearInterval(timer);
  }, [isAnimating]);

  if (!visible) return null;

  return (
    <div
      role="progressbar"
      aria-label="Route navigation progress"
      aria-valuenow={progress}
      aria-valuemin={0}
      aria-valuemax={100}
      style={{
        position: "fixed",
        top: 0,
        left: 0,
        width: "100vw",
        height: "3px",
        zIndex: 99999,
        pointerEvents: "none",
        backgroundColor: "transparent",
      }}
    >
      <div
        style={{
          height: "100%",
          width: `${progress}%`,
          backgroundColor: color,
          boxShadow: `0 0 10px ${color}, 0 0 4px ${color}`,
          transition: progress === 100 ? "width 0.2s ease-out, opacity 0.3s ease-out" : "width 0.3s ease-in-out",
          opacity: progress === 100 ? 0 : 1,
        }}
      />
    </div>
  );
}
