import React from "react";
import { LayoutDashboard, Table, BrainCircuit, Presentation, UploadCloud, Download, FileText } from "lucide-react";
import { triggerPresentationGeneration, openExecutivePrintReport } from "../api/client";

export default function Header({ activeTab, onSelectTab }) {
  const tabs = [
    { id: "overview", label: "Executive Overview", icon: LayoutDashboard },
    { id: "explorer", label: "Data Explorer", icon: Table },
    { id: "copilot", label: "AI HR Copilot", icon: BrainCircuit },
    { id: "presentations", label: "Presentations", icon: Presentation },
    { id: "ingestion", label: "Ingestion Studio", icon: UploadCloud }
  ];

  return (
    <header className="app-header">
      <div className="header-inner">
        <div className="brand-group">
          <div className="brand-logo-wrap">
            <BrainCircuit size={24} />
          </div>
          <div>
            <h1>PulseHR AI</h1>
            <p className="subtitle">Tabular Workforce & Attendance Intelligence</p>
          </div>
        </div>

        <nav className="tabs-nav-segmented" aria-label="Primary Navigation">
          {tabs.map(({ id, label, icon: Icon }) => (
            <button
              key={id}
              type="button"
              className={`nav-segment ${activeTab === id ? "active" : ""}`}
              onClick={() => onSelectTab(id)}
            >
              <Icon size={16} />
              <span>{label}</span>
            </button>
          ))}
        </nav>

        <div className="header-actions">
          <button
            type="button"
            className="btn-secondary"
            onClick={openExecutivePrintReport}
            title="Open Printable Executive Report"
          >
            <FileText size={15} />
            <span>PDF Report</span>
          </button>
          <button
            type="button"
            className="btn-primary"
            onClick={triggerPresentationGeneration}
            title="Export PowerPoint (.pptx) Presentation"
          >
            <Download size={15} />
            <span>Export .PPTX</span>
          </button>
        </div>
      </div>
    </header>
  );
}
