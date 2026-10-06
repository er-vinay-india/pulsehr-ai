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

import { getSlideTheme } from "../theme/slideTokens.js";
import { buildSlideHtml } from "./exporter/slideHtmlBuilder";
import { generateFullPresentationHtml } from "./exporter/exportTemplate";
import { buildResolvedSlideHtml } from "./exporter/resolvedSlideHtml.js";

/**
 * Exports a full presentation deck as a self-contained single HTML file.
 */
export async function exportStandaloneHtmlPresentation(deck, selectedTheme = "bold_signal", printPdf = false) {
  if (!deck || !deck.slides || deck.slides.length === 0) {
    alert("No slides found in the presentation to export.");
    return;
  }

  const title = deck.metadata?.title || deck.title || "Executive Presentation";
  const slides = deck.slides;
  const currentTheme = getSlideTheme(deck.theme?.id || deck.metadata?.theme_id || selectedTheme);

  let slidesHtml;
  let exportedSlideCount = slides.length;
  if (currentTheme.background_asset) {
    const imageResponse = await fetch(`/api/presentations/theme-assets/${encodeURIComponent(currentTheme.id)}/background`);
    if (!imageResponse.ok) throw new Error('The presentation theme artwork could not be loaded.');
    const blob = await imageResponse.blob();
    const background = await new Promise((resolve, reject) => {
      const reader = new FileReader();
      reader.onload = () => resolve(reader.result);
      reader.onerror = () => reject(new Error('The presentation theme artwork could not be embedded.'));
      reader.readAsDataURL(blob);
    });
    if (currentTheme.font_asset) {
      const fontResponse = await fetch(`/api/presentations/theme-assets/${encodeURIComponent(currentTheme.id)}/font`);
      if (!fontResponse.ok) throw new Error('The presentation title font could not be loaded.');
      const fontBlob = await fontResponse.blob();
      currentTheme.font_data_uri = await new Promise((resolve, reject) => {
        const reader = new FileReader();
        reader.onload = () => resolve(reader.result);
        reader.onerror = () => reject(new Error('The presentation title font could not be embedded.'));
        reader.readAsDataURL(fontBlob);
      });
    }
    const pages = [];
    for (const [idx, slide] of slides.entries()) {
      const response = await fetch(`/api/presentations/layout-preview?theme_id=${encodeURIComponent(currentTheme.id)}`, {
        method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(slide),
      });
      const { plan, detail } = await response.json();
      if (!response.ok || !plan) throw new Error(detail || 'This slide needs a supported layout for Amber Brush HTML export.');
      for (let part = 0; part < plan.pages.length; part++) {
        pages.push(buildResolvedSlideHtml({ ...slide, order: idx+1 }, pages.length, slides.length, currentTheme, plan, part, background));
      }
    }
    slidesHtml = pages.join('\n');
    exportedSlideCount = pages.length;
  } else {
    slidesHtml = slides.map((s, idx) => buildSlideHtml(s, idx, slides.length, currentTheme)).join("\n");
  }
  const fullHtml = generateFullPresentationHtml(title, slidesHtml, exportedSlideCount, currentTheme);

  if (printPdf) {
    const printWindow = window.open("", "_blank");
    if (!printWindow) { alert("Allow the presentation print window to save the deck as PDF."); return; }
    printWindow.document.open();
    printWindow.document.write(fullHtml);
    printWindow.document.close();
    printWindow.addEventListener("load", () => { printWindow.focus(); printWindow.print(); }, { once: true });
    return;
  }

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
