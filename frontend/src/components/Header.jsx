import React from "react";
import {
  LayoutDashboard,
  Table,
  BrainCircuit,
  UploadCloud,
  FileText,
  Sparkles,
  RotateCw,
  Presentation,
  Activity
} from "lucide-react";
import { openExecutivePrintReport } from "../api/client";

export default function Header({ activeTab, onSelectTab, onOpenUploadModal, activeJob }) {
  const tabs = [
    { id: "adaptive", label: "Executive Dashboard", short: "Dashboard", icon: LayoutDashboard },
    { id: "explorer", label: "Data Explorer", short: "Explorer", icon: Table },
    { id: "presentation", label: "Presentation Studio", short: "Presentation", icon: Presentation }
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
          {tabs.map(({ id, label, short, icon: Icon }) => (
            <button
              key={id}
              type="button"
              className={`nav-segment ${activeTab === id ? "active" : ""}`}
              onClick={() => onSelectTab(id)}
              aria-label={label}
              aria-current={activeTab === id ? "page" : undefined}
            >
              <Icon size={16} />
              <span className="nav-label-long" aria-hidden="true">{label}</span>
              <span className="nav-label-short" aria-hidden="true">{short}</span>
            </button>
          ))}
        </nav>

        <div className="header-actions">
          <button
            type="button"
            className="btn-secondary"
            onClick={openExecutivePrintReport}
            title="Open Printable Executive Report"
            aria-label="Open printable report"
          >
            <FileText size={15} />
            <span>PDF Report</span>
          </button>

          <button
            type="button"
            className="btn-primary"
            onClick={onOpenUploadModal}
            title="Upload and ingest a new spreadsheet"
            aria-label="Upload spreadsheet"
          >
            <UploadCloud size={15} />
            <span>Upload Data</span>
          </button>
        </div>
      </div>
    </header>
  );
}
