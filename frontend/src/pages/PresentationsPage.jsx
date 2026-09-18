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
    {
      num: 1,
      title: "Title & Executive Cover",
      desc: "Workforce Attendance & Performance Review · Widescreen 16:9 executive dark theme layout with dataset provenance.",
      badge: "Cover Slide"
    },
    {
      num: 2,
      title: "Executive Workforce Health & KPIs",
      desc: "4 High-impact stat cards: Total Headcount (100), Attendance (92.4%), Performance (3.8/5.0), Overtime (8.4h) + AI summary.",
      badge: "Dashboard"
    },
    {
      num: 3,
      title: "Department Benchmarking Matrix",
      desc: "Comprehensive structured comparison table across Engineering, Product, Sales, Marketing, HR, Finance, Operations.",
      badge: "Analysis"
    },
    {
      num: 4,
      title: "Talent Risk & Burnout Anomaly Alerts",
      desc: "3 Targeted risk pillars highlighting high-overtime contributors, attendance disconnects, and PIP recommendations.",
      badge: "Risk Alerts"
    },
    {
      num: 5,
      title: "Strategic HR Retention Roadmap",
      desc: "4 Actionable pillars: Workload Rebalancing, Remote Harmonization, Retention Grants, and Coaching Programs.",
      badge: "Action Plan"
    }
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
            Export dynamic PowerPoint presentations (.pptx) formatted with executive color palettes, high-contrast typography, and data-grounded AI recommendations.
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
            <p className="subtitle">5 Widescreen 16:9 Slides compiled autonomously using python-pptx</p>
          </div>
        </div>

        <div className="slides-grid">
          {slides.map(s => (
            <div key={s.num} className="slide-preview-card">
              <div className="slide-top">
                <span className="slide-badge">{s.badge}</span>
                <span className="slide-num">Slide 0{s.num}</span>
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
