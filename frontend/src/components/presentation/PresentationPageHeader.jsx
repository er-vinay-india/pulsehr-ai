import React from "react";
import {
  Presentation,
  Download,
  Sparkles,
  RefreshCw,
  Plus
} from "lucide-react";

export default function PresentationPageHeader({
  viewMode = "config",
  deckSpec = null,
  currentTheme = null,
  isRegeneratingSlide = false,
  isExportingPptx = false,
  onResetAndStartGeneration = () => {},
  onGoBackToConfig = () => {},
  onExportHtml = () => {},
  onOpenRegenerateModal = () => {},
  onExportPptx = () => {},
  onReturnToDeck = () => {}
}) {
  const getTitle = () => {
    switch (viewMode) {
      case "generating":
        return "Generating Presentation Deck";
      case "studio":
        return deckSpec?.metadata?.title || "Presentation Studio";
      case "config":
      default:
        return "Presentation Studio";
    }
  };

  const getDescription = () => {
    switch (viewMode) {
      case "generating":
        return "HRIDAY is building your deck. The current phase appears below.";
      case "studio": {
        const slideCount = deckSpec?.slides?.length || 0;
        const themeLabel = currentTheme?.name || "Theme";
        return `${slideCount} slide${slideCount !== 1 ? "s" : ""} · ${themeLabel} · Frontend Slides 16:9 Stage`;
      }
      case "config":
      default:
        return "";
    }
  };

  const description = getDescription();

  return (
    <header className="page-top-header presentation-page-header">
      <div className="page-title-row">
        <div className="page-title-group">
          <h1 className="page-heading">{getTitle()}</h1>
          {description ? <p className="page-description">{description}</p> : null}
        </div>

        <div className="header-actions-row">
          {viewMode === "studio" && (
            <>
              <button
                type="button"
                className="btn-secondary btn-sm"
                disabled={isRegeneratingSlide}
                onClick={onResetAndStartGeneration}
                title="Regenerate presentation deck with fresh AI intelligence"
              >
                <RefreshCw size={14} />
                <span>Generate Again</span>
              </button>

              <button
                type="button"
                className="btn-secondary btn-sm"
                disabled={isRegeneratingSlide}
                onClick={onGoBackToConfig}
                title="Configure and generate a new presentation"
              >
                <Plus size={14} />
                <span>New Deck</span>
              </button>

              <button
                type="button"
                className="btn-secondary btn-sm"
                onClick={onExportHtml}
                title="Download Standalone Zero-Dependency HTML Presentation (Offline Presenter)"
              >
                <Download size={14} />
                <span>Download HTML</span>
              </button>

              <button
                type="button"
                className="btn-secondary btn-sm"
                disabled={isRegeneratingSlide}
                onClick={onOpenRegenerateModal}
                title="Regenerate current slide with AI prompt"
              >
                <Sparkles size={14} />
                <span>Regenerate Slide</span>
              </button>

              <button
                type="button"
                className="btn-primary btn-sm"
                onClick={onExportPptx}
                disabled={isExportingPptx}
                title="Export native editable PowerPoint with charts and notes"
              >
                <Download size={14} />
                <span>{isExportingPptx ? "Preparing .PPTX..." : "Download .PPTX"}</span>
              </button>
            </>
          )}

          {viewMode === "config" && deckSpec && (
            <button
              type="button"
              className="btn-secondary btn-sm"
              onClick={onReturnToDeck}
              title="Return to the currently loaded presentation deck"
            >
              <Presentation size={14} />
              <span>Return to Deck</span>
            </button>
          )}
        </div>
      </div>
    </header>
  );
}
