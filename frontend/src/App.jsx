import React, { useState, useEffect } from "react";
import Header from "./components/Header.jsx";
import Footer from "./components/Footer.jsx";
import EmployeeDrawer from "./components/EmployeeDrawer.jsx";
import OverviewPage from "./pages/OverviewPage.jsx";
import DataExplorerPage from "./pages/DataExplorerPage.jsx";
import CopilotPage from "./pages/CopilotPage.jsx";
import PresentationsPage from "./pages/PresentationsPage.jsx";
import IngestionPage from "./pages/IngestionPage.jsx";

function parseHash() {
  const hash = window.location.hash.replace("#", "").trim();
  const valid = ["overview", "explorer", "copilot", "presentations", "ingestion"];
  return valid.includes(hash) ? hash : "overview";
}

export default function App() {
  const [activeTab, setActiveTab] = useState(parseHash);
  const [selectedEmployeeId, setSelectedEmployeeId] = useState(null);

  useEffect(() => {
    const handleHashChange = () => {
      setActiveTab(parseHash());
    };
    window.addEventListener("hashchange", handleHashChange);
    return () => window.removeEventListener("hashchange", handleHashChange);
  }, []);

  const handleSelectTab = tab => {
    window.location.hash = tab;
    setActiveTab(tab);
  };

  return (
    <div className="app">
      <Header activeTab={activeTab} onSelectTab={handleSelectTab} />

      <main className="app-main">
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
        {activeTab === "copilot" && (
          <CopilotPage
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

      {selectedEmployeeId !== null && (
        <EmployeeDrawer
          employeeId={selectedEmployeeId}
          onClose={() => setSelectedEmployeeId(null)}
        />
      )}
    </div>
  );
}
