import React, { useState, useEffect } from "react";
import Header from "./components/Header.jsx";
import Footer from "./components/Footer.jsx";
import EmployeeDrawer from "./components/EmployeeDrawer.jsx";
import GlobalCopilotWidget from "./components/GlobalCopilotWidget.jsx";
import OverviewPage from "./pages/OverviewPage.jsx";
import DataExplorerPage from "./pages/DataExplorerPage.jsx";
import PresentationsPage from "./pages/PresentationsPage.jsx";
import IngestionPage from "./pages/IngestionPage.jsx";

function parseHash() {
  const hash = window.location.hash.replace("#", "").trim();
  const valid = ["overview", "explorer", "presentations", "ingestion"];
  return valid.includes(hash) ? hash : "overview";
}

export default function App() {
  const [activeTab, setActiveTab] = useState(parseHash);
  const [selectedEmployeeId, setSelectedEmployeeId] = useState(null);
  const [copilotOpen, setCopilotOpen] = useState(() => window.location.hash.replace("#", "").trim() === "copilot");

  useEffect(() => {
    const handleHashChange = () => {
      const h = window.location.hash.replace("#", "").trim();
      if (h === "copilot") {
        setCopilotOpen(true);
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
    window.location.hash = tab;
    setActiveTab(tab);
  };

  return (
    <div className="app">
      <a className="skip-link" href="#main-content" onClick={e => { e.preventDefault(); document.getElementById("main-content")?.focus(); }}>Skip to content</a>
      <Header activeTab={activeTab} onSelectTab={handleSelectTab} />

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
        {activeTab === "presentations" && (
          <PresentationsPage />
        )}
        {activeTab === "ingestion" && (
          <IngestionPage />
        )}
      </main>

      <Footer />

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
