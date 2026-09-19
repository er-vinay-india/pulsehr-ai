import React, { useState } from "react";
import { Presentation, Download, FileText, CheckCircle2, Layers, Sparkles, ExternalLink } from "lucide-react";
import { triggerPresentationGeneration, openExecutivePrintReport } from "../api/client";

export default function PresentationsPage() {
  const [downloading, setDownloading] = useState(false);

  const handleDownloadPptx = async () => {
    setDownloading(true);
    try {
      await triggerPresentationGeneration();
    } catch (err) {
      alert("Failed to generate PPTX: " + err.message);
    } finally {
      setDownloading(false);
    }
  };

  const slides = [
    { num: 1, title: "Uploaded data overview", desc: "Dataset, sheet and row counts based on active uploads.", badge: "Overview" },
    { num: 2, title: "Sheet metrics", desc: "Editable tables show numeric means and missing values for each uploaded sheet.", badge: "Comparison" },
    { num: 3, title: "Source notes", desc: "Source, population and calculation definitions explain what the figures represent.", badge: "Source notes" }
  ];

  return (
    <div className="presentations-page">
      {/* Top Banner */}
      <div className="presentation-hero">
        <div className="hero-content">
          <div className="banner-tag">
            <Presentation size={15} />
            <span>Automated 1-Click Executive Artifacts</span>
          </div>
          <h2>Executive Presentation & Report Generator</h2>
          <p>
            Export dynamic PowerPoint presentations (.pptx) formatted with executive color palettes, high-contrast typography, and calculated values and source notes. Create custom calculations and export them from the Copilot page.
          </p>
        </div>
        <div className="hero-cta-group">
          <button
            type="button"
            className="btn-primary btn-large"
            onClick={handleDownloadPptx}
            disabled={downloading}
          >
            <Download size={18} />
            <span>{downloading ? "Generating Deck..." : "Download .PPTX Deck"}</span>
          </button>
          <button
            type="button"
            className="btn-secondary btn-large"
            onClick={openExecutivePrintReport}
          >
            <FileText size={18} />
            <span>Printable PDF Report</span>
          </button>
        </div>
      </div>

      {/* Slide Deck Previews */}
      <div className="deck-preview-section">
        <div className="section-header">
          <Layers size={20} color="var(--brand-400)" />
          <div>
            <h3>Generated Slide Deck Architecture</h3>
            <p className="subtitle">Widescreen slides generated from the current uploaded sheets</p>
          </div>
        </div>

        <div className="slides-grid">
          {slides.map(s => (
            <div key={s.num} className="slide-preview-card">
              <div className="slide-top">
                <span className="slide-badge">{s.badge}</span>
                <span className="slide-num">Section {s.num}</span>
              </div>
              <div className="slide-mockup">
                <div className="mockup-header-bar" />
                <div className="mockup-content">
                  <div className="mockup-title">{s.title}</div>
                  <div className="mockup-line" style={{ width: "80%" }} />
                  <div className="mockup-line" style={{ width: "55%" }} />
                  <div className="mockup-boxes">
                    <div className="mockup-box" />
                    <div className="mockup-box" />
                  </div>
                </div>
              </div>
              <div className="slide-desc">{s.desc}</div>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}
