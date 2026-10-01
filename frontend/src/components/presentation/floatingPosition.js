// Anchor and popup bounds are viewport coordinates, including scaled slide canvases.
export function floatingPosition(anchor, popup, viewport, preferred = "top") {
  const margin = 12;
  const gap = 8;
  const leftEdge = viewport.left || 0;
  const topEdge = viewport.top || 0;
  const rightEdge = leftEdge + viewport.width;
  const bottomEdge = topEdge + viewport.height;
  const above = Math.max(0, anchor.top - topEdge - margin - gap);
  const below = Math.max(0, bottomEdge - anchor.bottom - margin - gap);
  const useTop = preferred === "top"
    ? popup.height <= above || (popup.height > below && above > below)
    : popup.height > below && above > below;
  const maxHeight = Math.max(1, useTop ? above : below);
  const height = Math.min(popup.height, maxHeight);
  const width = Math.min(popup.width, Math.max(1, viewport.width - margin * 2));
  return {
    left: Math.max(leftEdge + margin, Math.min(anchor.left + anchor.width / 2 - width / 2, rightEdge - margin - width)),
    top: Math.max(topEdge + margin, Math.min(useTop ? anchor.top - gap - height : anchor.bottom + gap, bottomEdge - margin - height)),
    maxHeight,
    maxWidth: Math.max(1, viewport.width - margin * 2),
  };
}
