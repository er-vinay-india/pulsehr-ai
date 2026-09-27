import React from "react";
import {
  LayoutDashboard,
  Table,
  BrainCircuit,
  UploadCloud,
  Loader2,
  Presentation
} from "lucide-react";

import highviewLogo from "../assets/highview-logo.png";

export default function Header({ activeTab, onSelectTab, onOpenUploadModal, activeJob, isUploadingBackground }) {
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
            <img src={highviewLogo} alt="HighView Logo" className="brand-logo-img" />
          </div>
          <div className="brand-text-block">
            <h1 className="brand-title">HighView</h1>
            <p className="subtitle">Clarity From Every Sheet.</p>
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
            className={`btn-header-upload ${isUploadingBackground ? "is-processing" : ""}`}
            onClick={onOpenUploadModal}
            title={isUploadingBackground ? "Spreadsheet ingestion running in background - click to view" : "Upload and ingest a new spreadsheet"}
            aria-label="Upload spreadsheet"
          >
            {isUploadingBackground ? (
              <>
                <Loader2 size={16} className="spin-icon" />
                <span>Ingesting...</span>
              </>
            ) : (
              <>
                <UploadCloud size={16} />
                <span>Upload Data</span>
              </>
            )}
          </button>
        </div>
      </div>
    </header>
  );
}
