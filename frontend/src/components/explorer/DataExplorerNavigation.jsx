import React from "react";
import {
  LayoutDashboard,
  Award,
  TrendingUp,
  GitMerge,
  BarChart2,
  FileText,
  Table,
  Sparkles,
  Info,
  ChevronDown,
} from "lucide-react";

export const EXPLORER_TABS = [
  { id: "source", label: "Source Data", icon: Table, desc: "Exact raw records (no derived columns)" },
  { id: "semantics", label: "Semantic Models", icon: Sparkles, desc: "Roles, entities, grain, keys, and enrichments" },
  { id: "relationships", label: "Relationships & Joins", icon: GitMerge, desc: "Governed relationships, join safety, and preaggregation" },
  { id: "analytical-views", label: "Analytical Views & Facts", icon: LayoutDashboard, desc: "Reconstructed Gold metrics, facts, and lineage" },
  { id: "overview", label: "Overview", icon: Info, desc: "About your data" },
  { id: "technical", label: "Data table", icon: Table, desc: "Browse and search rows" },
  { id: "added-columns", label: "Added columns", icon: Sparkles, desc: "Review columns created from your data" },
  { id: "rankings", label: "Rankings", icon: Award, desc: "Compare highest and lowest values" },
  { id: "trends", label: "Trends", icon: TrendingUp, desc: "Changes over time" },
  { id: "distributions", label: "Value ranges", icon: BarChart2, desc: "Typical values and unusual results" },
  { id: "evidence", label: "Sources & calculations", icon: FileText, desc: "Check how findings were produced" },
];

export default function DataExplorerNavigation({
  activeTab = "overview",
  onSelectTab,
  themeTokens,
  isDark = false,
}) {
  return (
    <nav
      className="data-explorer-nav-container"
      aria-label="Data Explorer Subpages"
      style={{
        display: "flex",
        flexDirection: "row",
        alignItems: "center",
        gap: "10px",
        marginBottom: "16px",
      }}
    >
      {/* 1. DESKTOP SECONDARY TAB BAR */}
      <div
        className="explorer-desktop-tab-bar"
        role="tablist"
        style={{
          display: "flex",
          alignItems: "center",
          gap: "4px",
          borderBottom: `1px solid ${themeTokens?.colors?.borderSubtle || "#e2e8f0"}`,
          paddingBottom: "4px",
          overflowX: "auto",
          flex: 1,
          minWidth: 0,
        }}
      >
        {EXPLORER_TABS.filter((tab) => tab.id !== "evidence").map((tab) => {
          const Icon = tab.icon;
          const isActive = activeTab === tab.id;
          return (
            <button
              key={tab.id}
              type="button"
              role="tab"
              aria-selected={isActive}
              aria-controls={`explorer-panel-${tab.id}`}
              id={`explorer-tab-${tab.id}`}
              onClick={() => onSelectTab(tab.id)}
              style={{
                display: "inline-flex",
                alignItems: "center",
                gap: "6px",
                padding: "8px 14px",
                fontSize: "0.82rem",
                fontWeight: isActive ? 700 : 500,
                color: isActive
                  ? (themeTokens?.colors?.brandBlue || "#2563eb")
                  : (themeTokens?.colors?.textSecondary || "#64748b"),
                backgroundColor: isActive
                  ? (isDark ? "rgba(37, 99, 235, 0.12)" : "rgba(37, 99, 235, 0.08)")
                  : "transparent",
                border: "none",
                borderBottom: isActive
                  ? `2px solid ${themeTokens?.colors?.brandBlue || "#2563eb"}`
                  : "2px solid transparent",
                borderRadius: "6px 6px 0 0",
                cursor: "pointer",
                whiteSpace: "nowrap",
                transition: "all 0.15s ease",
              }}
            >
              <Icon size={14} />
              <span>{tab.label}</span>
            </button>
          );
        })}
      </div>

      {/* 2. MOBILE COMPACT DROPDOWN SELECTOR (Hidden on Desktop, displayed on mobile <= 640px) */}
      <div
        className="explorer-mobile-tab-dropdown"
        style={{
          flex: 1,
          minWidth: 0,
        }}
      >
        <div style={{ position: "relative", width: "100%" }}>
          <select
            value={activeTab}
            onChange={(e) => onSelectTab(e.target.value)}
            aria-label="Select Data Explorer Subpage"
            style={{
              width: "100%",
              padding: "8px 12px",
              fontSize: "0.86rem",
              fontWeight: 600,
              borderRadius: "8px",
              backgroundColor: themeTokens?.colors?.surface,
              color: themeTokens?.colors?.textPrimary,
              border: `1px solid ${themeTokens?.colors?.borderSubtle || "#cbd5e1"}`,
              appearance: "none",
            }}
          >
            {EXPLORER_TABS.filter((tab) => tab.id !== "evidence" || activeTab === "evidence").map((tab) => (
              <option key={tab.id} value={tab.id}>
                {tab.label}
              </option>
            ))}
          </select>
          <div
            style={{
              position: "absolute",
              right: "12px",
              top: "50%",
              transform: "translateY(-50%)",
              pointerEvents: "none",
            }}
          >
            <ChevronDown size={14} color={themeTokens?.colors?.textSecondary} />
          </div>
        </div>
      </div>
      <button
        type="button"
        id="explorer-tab-evidence"
        className="btn-secondary"
        aria-label="Details: sources and calculations"
        aria-pressed={activeTab === "evidence"}
        aria-controls="explorer-panel-evidence"
        title="Check sources and calculations behind the findings"
        onClick={() => onSelectTab("evidence")}
        style={{ display: "inline-flex", alignItems: "center", gap: "6px", flexShrink: 0 }}
      >
        <Info size={14} />
        <span>Details</span>
      </button>
    </nav>
  );
}
