import React, { useLayoutEffect, useRef, useState } from "react";
import { createPortal } from "react-dom";
import { floatingPosition } from "./floatingPosition.js";
import "../../styles/deck-floating.scss";

export default function DeckFloatingLayer({ anchorRef, children, onClose, role = "tooltip", placement = "top", className = "", ...props }) {
  const layerRef = useRef(null);
  const closeRef = useRef(onClose);
  closeRef.current = onClose;
  const [position, setPosition] = useState(null);
  const interactive = role !== "tooltip";

  useLayoutEffect(() => {
    const layer = layerRef.current;
    const anchor = anchorRef.current;
    if (!layer || !anchor) return;
    // The browser's top layer escapes overflow, transformed canvases and fullscreen.
    if (typeof layer.showPopover === "function") layer.showPopover();
    const positionLayer = () => {
      const viewport = window.visualViewport;
      const bounds = { width: viewport?.width || window.innerWidth, height: viewport?.height || window.innerHeight,
        left: viewport?.offsetLeft || 0, top: viewport?.offsetTop || 0 };
      const anchorBounds = anchor.getBoundingClientRect();
      if (anchorBounds.bottom < bounds.top || anchorBounds.top > bounds.top + bounds.height) {
        closeRef.current?.();
        return;
      }
      const popup = { width: layer.offsetWidth, height: layer.scrollHeight + layer.offsetHeight - layer.clientHeight };
      setPosition(floatingPosition(anchorBounds, popup, bounds, placement));
    };
    positionLayer();
    const focusable = () => Array.from(layer.querySelectorAll('button:not(:disabled), a[href], input, select, textarea, [tabindex="0"]'));
    const dismiss = (restoreFocus = false) => {
      closeRef.current?.();
      if (restoreFocus && interactive) anchor.focus({ preventScroll: true });
    };
    const keydown = event => {
      if (event.key === "Escape") {
        event.preventDefault();
        event.stopPropagation();
        dismiss(true);
      } else if (interactive && event.key === "Tab") {
        const items = focusable();
        const first = items[0], last = items[items.length - 1];
        if (event.shiftKey && document.activeElement === first) { event.preventDefault(); last?.focus(); }
        else if (!event.shiftKey && document.activeElement === last) { event.preventDefault(); first?.focus(); }
      }
    };
    const outside = event => {
      if (interactive && !layer.contains(event.target) && !anchor.contains(event.target)) dismiss();
    };
    const fullscreen = () => dismiss();
    const observer = typeof ResizeObserver !== "undefined" ? new ResizeObserver(positionLayer) : null;
    observer?.observe(anchor);
    observer?.observe(layer);
    window.addEventListener("resize", positionLayer);
    window.addEventListener("scroll", positionLayer, true);
    window.visualViewport?.addEventListener("resize", positionLayer);
    window.visualViewport?.addEventListener("scroll", positionLayer);
    document.addEventListener("keydown", keydown, true);
    document.addEventListener("pointerdown", outside, true);
    document.addEventListener("fullscreenchange", fullscreen);
    return () => {
      observer?.disconnect();
      window.removeEventListener("resize", positionLayer);
      window.removeEventListener("scroll", positionLayer, true);
      window.visualViewport?.removeEventListener("resize", positionLayer);
      window.visualViewport?.removeEventListener("scroll", positionLayer);
      document.removeEventListener("keydown", keydown, true);
      document.removeEventListener("pointerdown", outside, true);
      document.removeEventListener("fullscreenchange", fullscreen);
      if (typeof layer.hidePopover === "function" && layer.matches(":popover-open")) layer.hidePopover();
    };
  }, [anchorRef, interactive, placement]);

  const positioned = Boolean(position);
  useLayoutEffect(() => {
    if (interactive && positioned) {
      layerRef.current?.querySelector('button:not(:disabled), a[href], input, select, textarea, [tabindex="0"]')?.focus({ preventScroll: true });
    }
  }, [interactive, positioned]);

  return createPortal(
    <div {...props} ref={layerRef} role={role} popover="manual"
      className={`deck-floating-layer ${interactive ? "deck-floating-popover" : "deck-floating-tooltip"} ${className}`}
      onWheel={event => event.stopPropagation()}
      onTouchStart={event => event.stopPropagation()}
      onTouchEnd={event => event.stopPropagation()}
      style={{ ...position, visibility: position ? "visible" : "hidden" }}>
      {children}
    </div>,
    document.fullscreenElement || document.body
  );
}
