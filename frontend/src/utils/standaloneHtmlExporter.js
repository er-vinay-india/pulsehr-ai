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
import { getPresentationThemeAssetUrl, getPresentationLayoutPreview } from "../api/client";

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

  const deckId = deck.id || deck.metadata?.deck_id;

  // 1. PRIMARY DELIVERY PATH: Fetch the certified, server-rendered standalone presentation HTML
  if (deckId) {
    try {
      const resp = await fetch(`/api/presentations/decks/${deckId}/html`);
      if (resp.ok) {
        const fullHtml = await resp.text();
        if (fullHtml && fullHtml.includes("<!DOCTYPE html>")) {
          if (printPdf) {
            const printWindow = window.open("", "_blank");
            if (!printWindow) { alert("Allow the presentation print window to save the deck as PDF."); return; }
            printWindow.document.open();
            printWindow.document.write(fullHtml);
            printWindow.document.close();
            printWindow.addEventListener("load", () => { printWindow.focus(); printWindow.print(); }, { once: true });
            return;
          }

          // Trigger direct attachment download of certified standalone presentation HTML
          const sanitizedTitle = (deck.title || "presentation").toLowerCase().replace(/[^a-z0-9_-]+/g, "_").slice(0, 40).replace(/^_+|_+$/g, "") || "presentation";
          const a = document.createElement("a");
          a.href = `/api/presentations/download/${deckId}/html?download=true`;
          a.download = `${sanitizedTitle}.html`;
          document.body.appendChild(a);
          a.click();
          setTimeout(() => {
            if (a.parentNode) a.parentNode.removeChild(a);
          }, 1000);
          return;
        }
      }
    } catch (err) {
      console.warn("Could not fetch server-rendered HTML presentation, falling back to client compiler:", err);
    }
  }

  // 2. FALLBACK DELIVERY PATH: Client-side standalone HTML compilation (100% semantic DOM, zero raster image hacks)
  let slidesHtml;
  let exportedSlideCount = slides.length;

  if (currentTheme.background_asset) {
    const imageResponse = await fetch(getPresentationThemeAssetUrl(currentTheme.id, 'background'));
    if (!imageResponse.ok) throw new Error('The presentation theme artwork could not be loaded.');
    const blob = await imageResponse.blob();
    const background = await new Promise((resolve, reject) => {
      const reader = new FileReader();
      reader.onload = () => resolve(reader.result);
      reader.onerror = () => reject(new Error('The presentation theme artwork could not be embedded.'));
      reader.readAsDataURL(blob);
    });
    if (currentTheme.font_asset) {
      const fontResponse = await fetch(getPresentationThemeAssetUrl(currentTheme.id, 'font'));
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
      const plan = await getPresentationLayoutPreview(currentTheme.id, slide).catch(() => null);
      if (plan && plan.pages && Array.isArray(plan.pages)) {
        for (let part = 0; part < plan.pages.length; part++) {
          pages.push(buildResolvedSlideHtml({ ...slide, order: idx+1 }, pages.length, slides.length, currentTheme, plan, part, background));
        }
      } else {
        pages.push(buildSlideHtml(slide, idx, slides.length, currentTheme));
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
