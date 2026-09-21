/**
 * Standalone HTML Presentation Exporter
 * Based on the zarazhangrui/frontend-slides architecture.
 *
 * Generates a zero-dependency, self-contained single HTML file with:
 * - Fixed 16:9 1920x1080 Stage with mathematical scaling
 * - Curated typography and theme CSS variables
 * - Embedded SVG charts and structured slide layouts
 * - Pure JavaScript SlidePresentation navigation controller
 * - Full print/PDF support (@media print)
 * - Offline capability: opens and presents anywhere with zero server or npm dependencies!
 */

import { EXPORT_THEMES } from "./exporter/exportThemes";
import { buildSlideHtml } from "./exporter/slideHtmlBuilder";
import { generateFullPresentationHtml } from "./exporter/exportTemplate";

/**
 * Exports a full presentation deck as a self-contained single HTML file.
 */
export function exportStandaloneHtmlPresentation(deck, selectedTheme = "bold_signal") {
  if (!deck || !deck.slides || deck.slides.length === 0) {
    alert("No slides found in the presentation to export.");
    return;
  }

  const title = deck.title || "Executive Presentation";
  const slides = deck.slides;
  const currentTheme = EXPORT_THEMES[selectedTheme] || EXPORT_THEMES.bold_signal;

  const slidesHtml = slides.map((s, idx) => buildSlideHtml(s, idx, slides.length, currentTheme)).join("\n");
  const fullHtml = generateFullPresentationHtml(title, slidesHtml, slides.length, currentTheme);

  // Trigger file download
  const blob = new Blob([fullHtml], { type: "text/html;charset=utf-8" });
  const url = URL.createObjectURL(blob);
  const now = new Date();
  const pad = (n) => String(n).padStart(2, "0");
  const ts = `${now.getFullYear()}${pad(now.getMonth() + 1)}${pad(now.getDate())}_${pad(now.getHours())}${pad(now.getMinutes())}${pad(now.getSeconds())}`;
  const sanitizedTitle = (deck.title || "presentation").toLowerCase().replace(/[^a-z0-9_-]+/g, "_").slice(0, 40).replace(/^_+|_+$/g, "") || "presentation";
  const a = document.createElement("a");
  a.href = url;
  a.download = `${sanitizedTitle}_${ts}.html`;
  document.body.appendChild(a);
  a.click();
  document.body.removeChild(a);
  URL.revokeObjectURL(url);
}
