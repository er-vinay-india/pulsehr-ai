import React from "react";
import {
  Info,
  Table,
  Sparkles,
  GitMerge,
  LayoutDashboard,
  FileText,
  ChevronDown,
} from "lucide-react";

/**
 * HighView Data Explorer Navigation
 * Unified 6-tab Information Architecture:
 * Overview -> Data -> Semantic Model -> Relationships -> Analysis -> Evidence / Lineage
 * Derives 100% of styling from centralized HighView theme tokens.
 */
export const EXPLORER_TABS = [
  { id: "overview", label: "Overview", icon: Info, desc: "High-level metrics, entities, and workbook catalog" },
  { id: "data", label: "Data", icon: Table, desc: "Exact raw observed records without derived columns" },
  { id: "semantics", label: "Semantic Model", icon: Sparkles, desc: "Entities, semantic column profiles, candidate keys, and enrichments" },
  { id: "relationships", label: "Relationships", icon: GitMerge, desc: "Governed connections, join safety, and preaggregation rules" },
  { id: "analysis", label: "Analysis", icon: LayoutDashboard, desc: "Reconstructed analytical views, verified metrics, and facts" },
  { id: "evidence", label: "Evidence / Lineage", icon: FileText, desc: "Calculations, audit trails, and source verification" },
];

export default function DataExplorerNavigation({
  activeTab = "overview",
  onSelectTab,
  themeTokens,
  isDark = false,
}) {
  const activeColor = themeTokens?.colors?.brandPrimary || "var(--color-brand-primary)";
  const inactiveColor = themeTokens?.colors?.textSecondary || "var(--color-text-secondary)";
  const activeBg = themeTokens?.colors?.softBlue || "var(--color-bg-soft-blue)";
  const borderColor = themeTokens?.colors?.borderSubtle || "var(--color-divider)";

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
      {/* 1. DESKTOP TAB BAR */}
      <div
        className="explorer-desktop-tab-bar"
        role="tablist"
        style={{
          display: "flex",
          alignItems: "center",
          gap: "4px",
          borderBottom: `1px solid ${borderColor}`,
          paddingBottom: "4px",
          overflowX: "auto",
          flex: 1,
          minWidth: 0,
        }}
      >
        {EXPLORER_TABS.map((tab) => {
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
              title={tab.desc}
              style={{
                display: "inline-flex",
                alignItems: "center",
                gap: "6px",
                padding: "8px 14px",
                fontSize: "0.82rem",
                fontWeight: isActive ? 700 : 500,
                color: isActive ? activeColor : inactiveColor,
                backgroundColor: isActive ? activeBg : "transparent",
                border: "none",
                borderBottom: isActive
                  ? `2px solid ${activeColor}`
                  : "2px solid transparent",
                borderRadius: "6px 6px 0 0",
                cursor: "pointer",
                whiteSpace: "nowrap",
                transition: "all 0.15s ease",
              }}
            >
              <Icon size={14} aria-hidden="true" />
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
              backgroundColor: themeTokens?.colors?.surface || "var(--color-bg-surface)",
              color: themeTokens?.colors?.textPrimary || "var(--color-text-primary)",
              border: `1px solid ${borderColor}`,
              appearance: "none",
            }}
          >
            {EXPLORER_TABS.map((tab) => (
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
            <ChevronDown size={14} color={inactiveColor} aria-hidden="true" />
          </div>
        </div>
      </div>
    </nav>
  );
}
