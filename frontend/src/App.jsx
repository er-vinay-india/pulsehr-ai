import React, { useState, useEffect } from "react";
import Header from "./components/Header.jsx";
import Footer from "./components/Footer.jsx";
import EmployeeDrawer from "./components/EmployeeDrawer.jsx";
import GlobalCopilotWidget from "./components/GlobalCopilotWidget.jsx";
import AdaptiveDashboardPage from "./pages/AdaptiveDashboardPage.jsx";
import DataExplorerPage from "./pages/DataExplorerPage.jsx";
import PresentationPage from "./pages/PresentationPage.jsx";
import UploadModal from "./components/ingestion/UploadModal.jsx";
import { CheckCircle2, X, Table } from "lucide-react";

function parseHash() {
  const hash = window.location.hash.replace("#", "").trim();
  const valid = ["adaptive", "explorer", "presentation"];
  if (valid.includes(hash)) return hash;
  if (hash === "presentations") return "presentation";
  if (hash === "ingestion" || hash === "upload") return "explorer";
  if (hash === "report" || hash === "overview" || hash === "reference") {
    try {
      window.location.hash = "adaptive";
    } catch {}
    return "adaptive";
  }
  return "adaptive";
}

export default function App() {
  const [activeTab, setActiveTab] = useState(parseHash);
  const [selectedEmployeeId, setSelectedEmployeeId] = useState(null);
  const [copilotOpen, setCopilotOpen] = useState(() => window.location.hash.replace("#", "").trim() === "copilot");
  const [uploadModalOpen, setUploadModalOpen] = useState(() => {
    const raw = window.location.hash.replace("#", "").trim();
    return raw === "upload" || raw === "ingestion";
  });

  // Background Ingestion State & Notification Toast
  const [isUploadingBackground, setIsUploadingBackground] = useState(false);
  const [bgNotification, setBgNotification] = useState(null);

  // Presentation Pipeline Job & Deck State
  const [activePresentationJob, setActivePresentationJob] = useState(null);
  const [activeDeck, setActiveDeck] = useState(null);
  const [activeScope, setActiveScope] = useState({ datasetId: null, sheetId: null, snapshotId: null });

  // Key to force refresh DataExplorerPage when an upload finishes
  const [explorerRefreshKey, setExplorerRefreshKey] = useState(0);

  useEffect(() => {
    const handleHashChange = () => {
      const h = window.location.hash.replace("#", "").trim();
      if (h === "copilot") {
        setCopilotOpen(true);
        setActiveTab("adaptive");
      } else if (h === "upload" || h === "ingestion") {
        setUploadModalOpen(true);
        setActiveTab("explorer");
      } else {
        setActiveTab(parseHash());
      }
    };
    window.addEventListener("hashchange", handleHashChange);
    return () => window.removeEventListener("hashchange", handleHashChange);
  }, []);

  useEffect(() => { window.scrollTo(0, 0); }, [activeTab]);

  // Auto-dismiss notification after 8 seconds
  useEffect(() => {
    if (!bgNotification) return;
    const t = setTimeout(() => setBgNotification(null), 8000);
    return () => clearTimeout(t);
  }, [bgNotification]);

  const handleSelectTab = tab => {
    if (tab === "copilot") {
      setCopilotOpen(true);
      return;
    }
    if (tab === "upload" || tab === "ingestion") {
      setUploadModalOpen(true);
      return;
    }
    window.location.hash = tab;
    setActiveTab(tab);
  };

  const handleUploadStart = () => {
    // If modal is closed or gets closed during upload, Header can show progress
    setIsUploadingBackground(true);
  };

  const handleUploadEnd = () => {
    setIsUploadingBackground(false);
  };

  const handleUploadSuccess = (res, meta = {}) => {
    setExplorerRefreshKey(prev => prev + 1);
    if (meta.wasBackground) {
      setBgNotification({
        fileName: res.display_name || res.filename || "Spreadsheet",
        sheetsCount: res.sheets?.length || 1,
        totalRows: res.total_rows || 0
      });
    }
  };

  return (
    <div className="app">
      <a className="skip-link" href="#main-content" onClick={e => { e.preventDefault(); document.getElementById("main-content")?.focus(); }}>Skip to content</a>
      <Header
        activeTab={activeTab}
        onSelectTab={handleSelectTab}
        onOpenUploadModal={() => setUploadModalOpen(true)}
        activeJob={activePresentationJob}
        isUploadingBackground={isUploadingBackground}
      />

      {/* Floating Background Notification Toast */}
      {bgNotification && (
        <div
          className="bg-notification-toast"
          role="status"
          aria-live="polite"
          style={{
            position: "fixed",
            top: "80px",
            right: "24px",
            zIndex: 1100,
            display: "flex",
            alignItems: "center",
            gap: "12px",
            padding: "12px 18px",
            background: "#1c1815",
            border: "1px solid rgba(46, 213, 115, 0.4)",
            borderRadius: "12px",
            boxShadow: "0 8px 32px rgba(0, 0, 0, 0.5), 0 0 12px rgba(46, 213, 115, 0.15)",
            color: "#fff9f2",
            fontSize: "0.88rem",
            animation: "slideInRight 0.3s cubic-bezier(0.16, 1, 0.3, 1)"
          }}
        >
          <CheckCircle2 size={20} color="#2ed573" style={{ flexShrink: 0 }} />
          <div style={{ marginRight: "6px" }}>
            <strong style={{ color: "#2ed573" }}>Ingestion Complete:</strong>{" "}
            <span>{bgNotification.fileName} ({bgNotification.sheetsCount} sheets, {bgNotification.totalRows} rows)</span>
          </div>

          <button
            type="button"
            className="btn-primary"
            onClick={() => {
              setActiveTab("explorer");
              window.location.hash = "explorer";
              setBgNotification(null);
            }}
            style={{
              padding: "5px 12px",
              fontSize: "0.78rem",
              minHeight: "30px",
              display: "inline-flex",
              alignItems: "center",
              gap: "5px"
            }}
          >
            <Table size={13} />
            <span>View</span>
          </button>

          <button
            type="button"
            onClick={() => setBgNotification(null)}
            style={{
              background: "none",
              border: "none",
              color: "var(--fg-muted)",
              cursor: "pointer",
              padding: "4px",
              display: "flex",
              alignItems: "center"
            }}
            aria-label="Dismiss notification"
          >
            <X size={16} />
          </button>
        </div>
      )}

      <main id="main-content" className="app-main" tabIndex={-1}>
        {activeTab === "adaptive" && <AdaptiveDashboardPage onNavigateTab={handleSelectTab} />}
        {activeTab === "explorer" && (
          <DataExplorerPage
            key={explorerRefreshKey}
            onSelectEmployee={setSelectedEmployeeId}
          />
        )}
        {activeTab === "presentation" && (
          <PresentationPage
            activeJobId={activePresentationJob?.job_id || activePresentationJob?.id}
            initialDeck={activeDeck}
            initialScopeType="workspace"
            onJobUpdate={job => {
              setActivePresentationJob(job);
              if (!job || job.status === "in_progress" || !job.deck) {
                setActiveDeck(null);
              } else if (job.deck) {
                setActiveDeck(job.deck);
              }
            }}
          />
        )}
      </main>

      <Footer />

      {/* Multi-Step Spreadsheet Ingestion Modal */}
      <UploadModal
        isOpen={uploadModalOpen}
        onClose={() => setUploadModalOpen(false)}
        onUploadStart={handleUploadStart}
        onUploadEnd={handleUploadEnd}
        onUploadSuccess={handleUploadSuccess}
      />

      {/* Global Right-Side Floating Copilot Widget */}
      <GlobalCopilotWidget
        isOpen={copilotOpen}
        onToggle={setCopilotOpen}
        onClose={() => setCopilotOpen(false)}
        onSelectEmployee={setSelectedEmployeeId}
        activePage={activeTab}
        activeDatasetId={activeScope.datasetId}
        activeSheetId={activeScope.sheetId}
        activeSnapshotId={activeScope.snapshotId}
      />

      {selectedEmployeeId !== null && (
        <EmployeeDrawer
          employeeId={selectedEmployeeId}
          onClose={() => setSelectedEmployeeId(null)}
        />
      )}
    </div>
  );
}
