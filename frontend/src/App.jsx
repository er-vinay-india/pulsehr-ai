import React, { useState, useEffect } from "react";
import Header from "./components/Header.jsx";
import Footer from "./components/Footer.jsx";
import EmployeeDrawer from "./components/EmployeeDrawer.jsx";
import GlobalCopilotWidget from "./components/GlobalCopilotWidget.jsx";
import AdaptiveDashboardPage from "./pages/AdaptiveDashboardPage.jsx";
import DataExplorerPage from "./pages/DataExplorerPage.jsx";
import PresentationPage from "./pages/PresentationPage.jsx";
import UploadModal from "./components/ingestion/UploadModal.jsx";

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

  // Presentation Pipeline Job & Deck State
  const [activePresentationJob, setActivePresentationJob] = useState(null);
  const [activeDeck, setActiveDeck] = useState(null);
  const [activeScope, setActiveScope] = useState({ datasetId: null, sheetId: null, snapshotId: null });

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

  return (
    <div className="app">
      <a className="skip-link" href="#main-content" onClick={e => { e.preventDefault(); document.getElementById("main-content")?.focus(); }}>Skip to content</a>
      <Header
        activeTab={activeTab}
        onSelectTab={handleSelectTab}
        onOpenUploadModal={() => setUploadModalOpen(true)}
        activeJob={activePresentationJob}
      />

      <main id="main-content" className="app-main" tabIndex={-1}>
        {activeTab === "adaptive" && <AdaptiveDashboardPage onNavigateTab={handleSelectTab} />}
        {activeTab === "explorer" && (
          <DataExplorerPage
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
        onUploadSuccess={() => {
          // If on explorer or adaptive, components reload seamlessly
        }}
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
