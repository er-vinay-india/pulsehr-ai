import React from "react";
import FrontendSlidesDeck from "./FrontendSlidesDeck.jsx";

/**
 * PresentationRevealDeck is now powered by the Frontend Slides 16:9 Fixed Stage Engine
 * (based on zarazhangrui/frontend-slides architecture).
 *
 * It provides:
 * - Mathematical 1920x1080 stage scaling matching widescreen PowerPoint geometry
 * - Full keyboard, touch/swipe, and debounced wheel navigation
 * - Curated themes (Bold Signal, Electric Studio, Dark Botanical, etc.)
 * - Inline editing with 'E' hotkey and auto-save
 * - Zero external Reveal.js library dependencies
 */
export default function PresentationRevealDeck(props) {
  return <FrontendSlidesDeck {...props} />;
}
