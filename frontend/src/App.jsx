import React, { useState, useEffect } from "react";
import Header from "./components/Header.jsx";
import Footer from "./components/Footer.jsx";
import EmployeeDrawer from "./components/EmployeeDrawer.jsx";
import GlobalCopilotWidget from "./components/GlobalCopilotWidget.jsx";
import OverviewPage from "./pages/OverviewPage.jsx";
import DataExplorerPage from "./pages/DataExplorerPage.jsx";
import IngestionPage from "./pages/IngestionPage.jsx";
import CreatePresentationModal from "./components/CreatePresentationModal.jsx";

function parseHash() {
  const hash = window.location.hash.replace("#", "").trim();
  const valid = ["overview", "explorer", "ingestion"];
  return valid.includes(hash) ? hash : "overview";
}

export default function App() {
  const [activeTab, setActiveTab] = useState(parseHash);
  const [selectedEmployeeId, setSelectedEmployeeId] = useState(null);
  const [copilotOpen, setCopilotOpen] = useState(() => window.location.hash.replace("#", "").trim() === "copilot");

  // Presentation Pipeline Modal & Job State
  const [presentationModalOpen, setPresentationModalOpen] = useState(false);
  const [activePresentationJob, setActivePresentationJob] = useState(null);
  const [activeDeck, setActiveDeck] = useState(null);

  useEffect(() => {
    const handleHashChange = () => {
      const h = window.location.hash.replace("#", "").trim();
      if (h === "copilot") {
        setCopilotOpen(true);
        setActiveTab("overview");
      } else if (h === "presentation" || h === "presentations") {
        setPresentationModalOpen(true);
        setActiveTab("overview");
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
    if (tab === "presentation" || tab === "presentations") {
      setPresentationModalOpen(true);
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
        onOpenPresentationModal={() => setPresentationModalOpen(true)}
        activeJob={activePresentationJob}
      />

      <main id="main-content" className="app-main" tabIndex={-1}>
        {activeTab === "overview" && (
          <OverviewPage
            onSelectEmployee={setSelectedEmployeeId}
            onNavigateTab={handleSelectTab}
          />
        )}
        {activeTab === "explorer" && (
          <DataExplorerPage
            onSelectEmployee={setSelectedEmployeeId}
          />
        )}
        {activeTab === "ingestion" && (
          <IngestionPage />
        )}
      </main>

      <Footer />

      {/* AI Presentation Pipeline & Studio Modal */}
      <CreatePresentationModal
        isOpen={presentationModalOpen}
        onClose={() => setPresentationModalOpen(false)}
        activeJobId={activePresentationJob?.job_id || activePresentationJob?.id}
        initialDeck={activeDeck}
        initialScopeType={activeTab === "overview" ? "workspace" : "workspace"}
        onJobUpdate={job => {
          setActivePresentationJob(job);
          if (job?.deck) {
            setActiveDeck(job.deck);
          }
        }}
      />

      {/* Global Right-Side Floating Copilot Widget */}
      <GlobalCopilotWidget
        isOpen={copilotOpen}
        onToggle={setCopilotOpen}
        onClose={() => setCopilotOpen(false)}
        onSelectEmployee={setSelectedEmployeeId}
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
