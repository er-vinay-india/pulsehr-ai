import React from "react";
import { FileSpreadsheet, Layers, TrendingUp, Presentation, UploadCloud, Table } from "lucide-react";
import Button from "../../design-system/components/Button";
import { NAVIGATION_INTENTS, dispatchNavigationIntent } from "../../contracts/NavigationIntentRegistry";

/**
 * EmptyDashboardState
 *
 * First-class zero-data product state for the Executive Dashboard.
 * Strictly adheres to:
 * - Layer 1 (Governed Truth): Zero synthetic numbers, zero fake counts, zero phantom relationships.
 * - Layer 2 (Design System): Uses only canonical <Button> and semantic icons. Zero raw <button>.
 * - Layer 3 (Accessibility / Contrast): 100% WCAG AAA >= 7:1 tokens for primary actions and text.
 * - Layer 4 (Routing): Dispatches intents via NavigationIntentRegistry. Zero direct window.location mutation.
 */
export default function EmptyDashboardState({ onNavigateTab, onOpenUpload }) {
  const handleUpload = () => {
    dispatchNavigationIntent(NAVIGATION_INTENTS.OPEN_UPLOAD, {}, { onNavigateTab, onOpenUpload });
  };

  const handleOpenExplorer = () => {
    dispatchNavigationIntent(NAVIGATION_INTENTS.OPEN_EXPLORER, {}, { onNavigateTab });
  };

  return (
    <section className="adaptive-empty-state" aria-labelledby="adaptive-empty-title">
      <div className="adaptive-empty-icon" aria-hidden="true">
        <FileSpreadsheet size={40} />
      </div>
      <h2 id="adaptive-empty-title" className="adaptive-empty-heading">
        No Workbooks Ingested
      </h2>
      <p className="adaptive-empty-text">
        No datasets or spreadsheets have been uploaded to HighView yet.
      </p>
      <div className="adaptive-empty-hint">
        Upload an Excel (.xlsx, .xls) or CSV file to start automated executive intelligence.
      </div>

      <div className="adaptive-empty-features" aria-label="HighView Capabilities">
        <div className="adaptive-empty-feature-card">
          <div className="feature-icon-wrap" aria-hidden="true">
            <Layers size={20} />
          </div>
          <strong>Adaptive Ingestion</strong>
          <span>Auto-reconstructs messy multi-row headers, merged cells, and wrapped records into clean tabular datasets.</span>
        </div>
        <div className="adaptive-empty-feature-card">
          <div className="feature-icon-wrap" aria-hidden="true">
            <TrendingUp size={20} />
          </div>
          <strong>Deterministic Truth</strong>
          <span>Uncovers statistical variance, outlier clusters, and business KPIs with zero LLM math or hallucinated numbers.</span>
        </div>
        <div className="adaptive-empty-feature-card">
          <div className="feature-icon-wrap" aria-hidden="true">
            <Presentation size={20} />
          </div>
          <strong>Executive Studio</strong>
          <span>Transforms verified findings into 16:9 board-ready presentations with 100% native editable PowerPoint charts.</span>
        </div>
      </div>

      <div className="adaptive-empty-actions">
        <Button
          variant="PRIMARY"
          size="md"
          icon={UploadCloud}
          onClick={handleUpload}
          ariaLabel="Upload new spreadsheet"
        >
          Upload Spreadsheet
        </Button>
        <Button
          variant="SECONDARY"
          size="md"
          icon={Table}
          onClick={handleOpenExplorer}
          ariaLabel="Open Data Explorer"
        >
          Open Data Explorer
        </Button>
      </div>
    </section>
  );
}
