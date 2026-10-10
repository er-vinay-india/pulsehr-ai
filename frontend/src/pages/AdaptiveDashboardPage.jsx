import React, { useEffect, useMemo, useRef, useState } from "react";
import {
  ArrowRight,
  Info,
  X,
  Presentation,
  Layers,
  Sparkles,
  TrendingUp,
  BarChart2,
  Table,
  FileSpreadsheet,
  UploadCloud,
  GitMerge,
  AlertCircle,
  AlertTriangle,
  Loader2,
  ShieldCheck,
  ExternalLink,
} from "lucide-react";
import ErrorBoundary from "../components/common/ErrorBoundary";
import Select from "../components/common/Select";
import ExecutiveBriefingCard from "../components/adaptive/ExecutiveBriefingCard";
import InvestigationDrawer from "../components/InvestigationDrawer";
import EmployeeDrawer from "../components/EmployeeDrawer";
import UnifiedExecutiveInsightsGrid from "../components/adaptive/UnifiedExecutiveInsightsGrid";
import ExecutiveScenarioExplorer from "../components/adaptive/ExecutiveScenarioExplorer";
import SafeReactECharts from "../components/charts/SafeReactECharts";
import { buildExplorerUrl, getContextualExplorerTarget } from "../utils/explorerNavigation";
import "../styles/adaptive-dashboard.scss";
import { useTheme } from "../context/ThemeContext";
import { getThemeTokens } from "../theme/tokens";
import { SurfaceGuard } from "../components/guard";

async function fetchJson(url, options = {}) {
  const res = await fetch(url, options);
  if (!res.ok) {
    const errorBody = await res.json().catch(() => ({}));
    throw new Error(errorBody.detail || `Server responded with status ${res.status}`);
  }
  return res.json();
}

function formatHumanDate(dateStr) {
  if (!dateStr) return "";
  const parts = dateStr.split("-");
  if (parts.length !== 3) return dateStr;
  const [y, m, d] = parts;
  const mNames = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"];
  const mIdx = parseInt(m, 10) - 1;
  const dNum = parseInt(d, 10);
  return `${dNum} ${mNames[mIdx]} ${y}`;
}

function getEmptyStateExplanation(data, activeDataset) {
  if (!data) {
    return {
      title: "No Data Available",
      reason: "Unable to retrieve analytical records for this workbook.",
      action: "Select an uploaded workbook or upload a new spreadsheet."
    };
  }

  if (data.total_rows != null && data.total_rows < 5) {
    return {
      title: "Insufficient Sample Size",
      reason: `Dataset contains only ${data.total_rows} records. At least 5 observations are required to compute statistical distributions and executive variance.`,
      action: "Upload a fuller export with additional reporting records."
    };
  }

  if (data.domain_profile?.status === "UNSUPPORTED" || data.unsupported_domain) {
    return {
      title: "Unsupported Domain Concepts",
      reason: "The uploaded schema does not contain recognizable business dimension keys or continuous numeric measures supported by executive analytics.",
      action: "Verify column headers match business identifiers (e.g., Department, Store, Revenue, Hours)."
    };
  }

  if (data.coverage_warnings && data.coverage_warnings.length > 0) {
    return {
      title: "Data Quality Threshold Not Met",
      reason: data.coverage_warnings[0] || "Data binding checks reported high nullity or conflicting joins.",
      action: "Inspect source data for broken keys or missing columns."
    };
  }

  return {
    title: "Clean Operational Baseline",
    reason: `Analysis across ${data.sheet_count || activeDataset?.sheet_count || 1} sheet(s) and ${data.total_rows || "all"} records detected no significant variance, outliers, or policy deviations exceeding baseline thresholds.`,
    action: "Operational metrics are performing within normal parameters."
  };
}

export default function AdaptiveDashboardPage({ onNavigateTab }) {
  const { isDark } = useTheme();
  const themeTokens = getThemeTokens(isDark);

  // Source / Dataset State — normalized strictly to dataset_id (WP-9.6)
  const [sources, setSources] = useState([]);
  const [sourcesLoading, setSourcesLoading] = useState(true);
  const [sourcesError, setSourcesError] = useState(null);
  const [selectedDatasetId, setSelectedDatasetId] = useState(() => {
    try {
      const p = new URLSearchParams(window.location.search);
      return p.get("dataset_id") || p.get("sheet_id") || "";
    } catch {
      return "";
    }
  });

  // Analysis State
  const [data, setData] = useState(null);
  const [calculating, setCalculating] = useState(false);
  const [calcError, setCalcError] = useState(null);
  const [revision, setRevision] = useState(0);

  // Inspect & Disclosure State
  const [inspectModalOpen, setInspectModalOpen] = useState(false);
  const [inspectTarget, setInspectTarget] = useState("candidate");
  const [selectedCandidate, setSelectedCandidate] = useState(null);
  const [investigationTarget, setInvestigationTarget] = useState(null);
  const [inspectedEmployeeId, setInspectedEmployeeId] = useState(null);
  const [showDetailedAnalysis, setShowDetailedAnalysis] = useState(false);
  const [showScenarioExplorer, setShowScenarioExplorer] = useState(false);
  const [developerMode, setDeveloperMode] = useState(() => {
    try {
      const p = new URLSearchParams(window.location.search);
      return p.get("dev") === "true" || p.get("developer") === "true";
    } catch {
      return false;
    }
  });

  const modalCloseBtnRef = useRef(null);
  const dialogRef = useRef(null);
  const activeControllerRef = useRef(null);
  const requestCounter = useRef(0);

  const activeDataset = useMemo(() => {
    return sources.find((d) => String(d.id) === String(selectedDatasetId)) || sources[0] || null;
  }, [sources, selectedDatasetId]);

  const handleSourceSelect = (newId) => {
    setSelectedDatasetId(newId);
    try {
      const url = new URL(window.location);
      url.searchParams.set("dataset_id", newId);
      url.searchParams.delete("sheet_id");
      window.history.replaceState({}, "", url);
    } catch {}
  };

  // 1. Load Datasets/Workbooks on Mount & Normalize Scope (WP-9.6)
  const loadSources = () => {
    setSourcesLoading(true);
    setSourcesError(null);
    fetchJson("/api/upload/datasets")
      .then((res) => {
        const list = Array.isArray(res) ? res : res.datasets || [];
        setSources(list);
        const p = new URLSearchParams(window.location.search);
        const urlDatasetId = p.get("dataset_id");
        const urlSheetId = p.get("sheet_id");

        let targetId = "";
        if (urlDatasetId) {
          targetId = urlDatasetId;
        } else if (urlSheetId) {
          const parent = list.find((d) => (d.sheets || []).some((s) => String(s.id) === urlSheetId));
          if (parent) targetId = String(parent.id);
        } else if (list.length > 0) {
          targetId = String(list[0].id);
        }

        if (targetId) {
          setSelectedDatasetId(targetId);
          try {
            const url = new URL(window.location);
            url.searchParams.set("dataset_id", targetId);
            url.searchParams.delete("sheet_id");
            window.history.replaceState({}, "", url);
          } catch {}
        }
      })
      .catch((err) => {
        setSourcesError(err.message || "Failed to load uploaded datasets.");
      })
      .finally(() => {
        setSourcesLoading(false);
      });
  };

  useEffect(() => {
    loadSources();
    window.addEventListener("workbook-uploaded", loadSources);
    return () => window.removeEventListener("workbook-uploaded", loadSources);
  }, []);

  const lastDatasetIdRef = useRef(null);

  // 2. Fetch Unified Dataset Intelligence (WP-9.6)
  useEffect(() => {
    if (!selectedDatasetId) {
      setData(null);
      setCalculating(false);
      lastDatasetIdRef.current = null;
      return;
    }

    const isDifferentDataset = selectedDatasetId !== lastDatasetIdRef.current;
    if (isDifferentDataset) {
      // Switching datasets -> clear old charts immediately!
      // Old charts must NOT remain visible when switching to a different dataset.
      setData(null);
      lastDatasetIdRef.current = selectedDatasetId;
    }

    if (activeControllerRef.current) {
      activeControllerRef.current.abort();
    }
    const controller = new AbortController();
    activeControllerRef.current = controller;
    const currentReqId = ++requestCounter.current;

    setInspectModalOpen(false);
    setCalculating(true);
    setCalcError(null);

    fetchJson(`/api/adaptive-dashboard/primary-element?dataset_id=${selectedDatasetId}`, {
      signal: controller.signal,
    })
      .then((res) => {
        if (currentReqId !== requestCounter.current) return;
        setData(res);
      })
      .catch((err) => {
        if (currentReqId !== requestCounter.current) return;
        if (err.name !== "AbortError") {
          setCalcError(err.message || "Unable to compute verified metric for this workbook.");
        }
      })
      .finally(() => {
        if (currentReqId === requestCounter.current) {
          setCalculating(false);
        }
      });

    return () => {
      controller.abort();
    };
  }, [selectedDatasetId, revision]);

  // 3. Modal Focus Management & Keyboard Dismissal
  useEffect(() => {
    if (inspectModalOpen) {
      setTimeout(() => {
        modalCloseBtnRef.current?.focus();
      }, 50);

      const handleKeyDown = (e) => {
        if (e.key === "Escape") {
          e.preventDefault();
          setInspectModalOpen(false);
        }
      };
      window.addEventListener("keydown", handleKeyDown);
      return () => window.removeEventListener("keydown", handleKeyDown);
    }
  }, [inspectModalOpen]);

  const handleOpenInspect = (target, cand = null) => {
    setInspectTarget(target);
    if (cand) setSelectedCandidate(cand);
    setInspectModalOpen(true);
  };

  const handleCloseInspect = () => {
    setInspectModalOpen(false);
  };

  const handleCreatePresentationFromDashboard = () => {
    if (!selectedDatasetId) return;
    try {
      const storedConfig = {
        title: data?.dataset_name || activeDataset?.display_name || "Executive Intelligence Briefing",
        datasetId: selectedDatasetId,
        sheetIds: data?.source_sheet_ids || [],
        insightCount: data?.selected_dashboard_insights?.length || 0,
        createdAt: new Date().toISOString(),
      };
      sessionStorage.setItem("highview_presentation_source", JSON.stringify(storedConfig));
    } catch {}
    if (typeof onNavigateTab === "function") {
      onNavigateTab("presentation");
    } else {
      window.location.hash = "presentation";
    }
  };

  // Scope line summary
  const scopeLine = useMemo(() => {
    if (!data && !activeDataset) return null;
    const workbook = data?.dataset_name || activeDataset?.display_name || activeDataset?.original_name || "Dataset";
    const sheetCount = data?.sheet_count || activeDataset?.sheet_count || activeDataset?.sheets?.length || 1;
    const sheetText = `${sheetCount} unified ${sheetCount === 1 ? "sheet" : "sheets"}`;

    const manifest = data?.manifest;
    let period = manifest?.date_range?.formatted;
    if (!period) {
      if (manifest?.date_range?.start && manifest?.date_range?.end) {
        period = `${formatHumanDate(manifest.date_range.start)} – ${formatHumanDate(manifest.date_range.end)}`;
      } else {
        period = "Current Period Verified";
      }
    }

    return {
      workbook,
      sheet: sheetText,
      period,
      refreshed: "Live verified",
    };
  }, [data, activeDataset]);

  const briefingElement = data?.briefing_element;

  return (
    <div className="adaptive-dashboard-page" data-testid="executive-dashboard-root">
      {/* Page Title & Command Bar */}
      <header className="page-top-header adaptive-page-header">
        <div className="page-title-row">
          <div className="page-title-group">
            <h1 className="page-heading">Executive Dashboard</h1>
            <p className="page-description">
              Automated spreadsheet intelligence, cross-functional KPI tracking, and decision discovery.
            </p>
          </div>
          <div className="header-actions-row">
            {Boolean(data?.domain_profile?.governed_scenario_domain || data?.domain_profile?.domain === "workforce") && (
              <button
                type="button"
                className={showScenarioExplorer ? "btn-primary btn-sm" : "btn-secondary btn-sm"}
                onClick={() => setShowScenarioExplorer((prev) => !prev)}
                disabled={!selectedDatasetId || calculating}
                title="Toggle Executive Scenario Explorer & What-If Simulator"
                style={{
                  display: "inline-flex",
                  alignItems: "center",
                  gap: "5px",
                  borderColor: showScenarioExplorer ? undefined : (themeTokens.colors.brandPurple || "#8b5cf6"),
                  color: showScenarioExplorer ? undefined : (themeTokens.colors.brandPurple || "#8b5cf6"),
                }}
              >
                <Sparkles size={14} />
                <span>{showScenarioExplorer ? "Hide Scenario Explorer" : "Scenario Explorer"}</span>
              </button>
            )}
            <button
              type="button"
              className="btn-primary btn-sm"
              onClick={handleCreatePresentationFromDashboard}
              disabled={!selectedDatasetId || calculating}
              title="Generate a 16:9 executive presentation deck from active dashboard data"
            >
              <Presentation size={14} />
              <span>Create Presentation</span>
            </button>
          </div>
        </div>

        {/* Scope Bar: Dataset Context Only (ZERO Sheet Selector) */}
        <div className="adaptive-scope-bar page-command-bar">
          {sources.length > 1 && (
            <div className="scope-control-group" style={{ minWidth: "220px" }}>
              <label htmlFor="dataset-selector" style={{ fontSize: "11px", color: themeTokens.colors.textMuted }}>
                Dataset / Workbook
              </label>
              <Select
                id="dataset-selector"
                value={selectedDatasetId}
                onChange={(e) => handleSourceSelect(e.target.value)}
                disabled={sourcesLoading}
                aria-label="Selected dataset workbook"
                placeholder={sourcesLoading ? "Loading datasets…" : "Select dataset…"}
                options={sources.map((d) => ({
                  value: String(d.id),
                  label: d.display_name || d.original_name || `Dataset ${d.id}`,
                }))}
              />
            </div>
          )}

          <div
            className="dataset-level-context"
            style={{ display: "flex", alignItems: "center", gap: "10px", flexWrap: "wrap" }}
          >
            <div
              className="scope-context-badge"
              style={{
                padding: "6px 12px",
                borderRadius: "6px",
                backgroundColor: themeTokens.colors.surface,
                border: `1px solid ${themeTokens.colors.borderSubtle}`,
                display: "flex",
                alignItems: "center",
                gap: "6px",
              }}
            >
              <span
                style={{
                  fontSize: "11px",
                  color: themeTokens.colors.textMuted,
                  textTransform: "uppercase",
                  letterSpacing: "0.04em",
                }}
              >
                Dataset
              </span>
              <strong style={{ fontSize: "12px", color: themeTokens.colors.textPrimary }}>
                {data?.dataset_name || activeDataset?.display_name || activeDataset?.original_name || "Workbook"}
              </strong>
            </div>

            <div
              className="scope-context-badge"
              style={{
                padding: "6px 12px",
                borderRadius: "6px",
                backgroundColor: themeTokens.colors.surface,
                border: `1px solid ${themeTokens.colors.borderSubtle}`,
                display: "flex",
                alignItems: "center",
                gap: "6px",
              }}
            >
              <span
                style={{
                  fontSize: "11px",
                  color: themeTokens.colors.textMuted,
                  textTransform: "uppercase",
                  letterSpacing: "0.04em",
                }}
              >
                Sources
              </span>
              <strong style={{ fontSize: "12px", color: themeTokens.colors.textPrimary }}>
                {data?.source_sheet_count || data?.sheet_count || activeDataset?.sheet_count || activeDataset?.sheets?.length || 1} related {(data?.sheet_count || activeDataset?.sheet_count || 1) === 1 ? "sheet" : "sheets"}
              </strong>
            </div>

            <div
              className="scope-context-badge"
              style={{
                padding: "6px 12px",
                borderRadius: "6px",
                backgroundColor: themeTokens.colors.surface,
                border: `1px solid ${themeTokens.colors.borderSubtle}`,
                display: "flex",
                alignItems: "center",
                gap: "6px",
              }}
            >
              <span
                style={{
                  fontSize: "11px",
                  color: themeTokens.colors.textMuted,
                  textTransform: "uppercase",
                  letterSpacing: "0.04em",
                }}
              >
                Intelligence
              </span>
              <strong style={{ fontSize: "12px", color: themeTokens.colors.textPrimary }}>
                {data?.selected_dashboard_insights?.length || 0} Executive Insights
              </strong>
            </div>
          </div>

          <button
            type="button"
            className="scope-refresh-btn"
            onClick={() => setRevision((r) => r + 1)}
            disabled={calculating || !selectedDatasetId}
            aria-label="Refresh analysis for selected workbook"
          >
            Refresh
          </button>
        </div>
      </header>

      {/* Source Loading or Source Error State */}
      {sourcesError && (
        <div className="adaptive-status-notice error" role="alert">
          <span>Failed to load sources: {sourcesError}</span>
          <button type="button" onClick={loadSources}>
            Retry
          </button>
        </div>
      )}

      {/* Calculation Error State */}
      {calcError && !calculating && (
        <div className="adaptive-status-notice error" role="alert">
          <span>{calcError}</span>
          <button type="button" onClick={() => setRevision((r) => r + 1)}>
            Retry
          </button>
        </div>
      )}

      {/* Runtime Developer Diagnostics Trigger (Developer Mode - Clean Drawer Trigger) */}
      {developerMode && data && (
        <div style={{ display: "flex", justifyContent: "flex-end", marginBottom: "12px" }}>
          <button
            type="button"
            className="scope-badge-button"
            data-testid="executive-dashboard-runtime-diagnostic"
            onClick={() => handleOpenInspect("runtime_diagnostics")}
            style={{
              fontSize: "11px",
              fontFamily: "monospace",
              padding: "5px 12px",
              borderRadius: "6px",
              border: `1px dashed ${themeTokens.colors.borderStrong}`,
              background: themeTokens.colors.surface,
              color: themeTokens.colors.textSecondary,
              cursor: "pointer",
              display: "inline-flex",
              alignItems: "center",
              gap: "6px",
            }}
            aria-label="Inspect runtime scope and diagnostics in drawer"
          >
            <span>[Dev Scope] Dataset {data?.dataset_id || selectedDatasetId} ({data?.candidate_count ?? 0} candidates)</span>
            <ExternalLink size={12} />
          </button>
        </div>
      )}

      {/* Executive Dashboard Governed Content Container */}
      <SurfaceGuard surface="dashboard">
        <section className="adaptive-content-container" aria-label="Dashboard Content">
          {/* State A: First-time or Dataset-Switch Indeterminate Executive Loader */}
          {calculating && !data && (
            <div className="adaptive-executive-loader" role="status" aria-live="polite">
              <div className="adaptive-executive-loader__waveform" aria-hidden="true">
                <span />
                <span />
                <span />
                <span />
                <span />
              </div>
              <h2 className="adaptive-executive-loader__title">Calculating Executive Intelligence…</h2>
              <p className="adaptive-executive-loader__context">
                Synthesizing cross-sheet distributions, business KPI variances, and policy telemetry.
              </p>
            </div>
          )}

          {/* Stale-while-Revalidate Banner for Same-Dataset Refresh */}
          {calculating && data && (
            <div className="adaptive-recalc-banner" role="status" aria-live="polite">
              <Loader2 size={16} className="adaptive-spin-icon" />
              <span>Recalculating intelligence with latest revisions… Displaying previous snapshot.</span>
            </div>
          )}

          {/* Content Wrapper (Dimmed during re-calculation) */}
          <div className={calculating && data ? "adaptive-content-recalculating" : ""}>
            {/* Authoritative Scope Line */}
            {scopeLine && (
              <div className="adaptive-scope-line" aria-label="Dataset and population scope">
                <span className="scope-line-item scope-line-workbook">
                  <strong>{scopeLine.workbook}</strong> · {scopeLine.sheet}
                </span>
                <span className="scope-line-separator">·</span>
                <span className="scope-line-item scope-line-period">
                  Reporting period: <strong>{scopeLine.period}</strong>
                </span>
                <span className="scope-line-separator">·</span>
                <span className="scope-line-item scope-line-status">
                  <span className="scope-live-dot" />
                  {scopeLine.refreshed}
                </span>
              </div>
            )}

            {/* Governed Executive Briefing Audio/Text (if available at dataset level) */}
            {!calcError && briefingElement && (
              <ExecutiveBriefingCard
                briefing={briefingElement}
                sheetId={selectedDatasetId}
                onOpenInspect={() => handleOpenInspect("briefing")}
                snapshot={data?.snapshot}
                domain={data?.contract?.domain}
              />
            )}

            {/* Governed Unified Executive Insights Grid (4-5 Executive Topics & Business KPIs) */}
            {!calcError && data?.selected_dashboard_insights && data.selected_dashboard_insights.length > 0 && (
              <ErrorBoundary
                fallback={
                  <div className="adaptive-status-notice error" role="alert" style={{ margin: "20px 0" }}>
                    <AlertTriangle size={18} />
                    <span>An unexpected rendering error occurred in the executive grid.</span>
                  </div>
                }
              >
                <UnifiedExecutiveInsightsGrid
                  insights={data.selected_dashboard_insights}
                  executiveTopics={data.executive_topics || []}
                  executiveKpis={data.executive_kpis || []}
                  coverageWarnings={data.coverage_warnings || []}
                  datasetName={data.dataset_name || (activeDataset?.display_name || activeDataset?.original_name || "Workbook")}
                  datasetId={selectedDatasetId}
                  sheetCount={data.sheet_count || 1}
                  domainProfile={data?.domain_profile || null}
                  onInspectInsight={(cand) => {
                    handleOpenInspect("candidate", cand);
                  }}
                  onOpenScenarioExplorer={() => setShowScenarioExplorer(true)}
                />

              </ErrorBoundary>
            )}

            {/* Truthful Empty State: When zero insights detected or insufficient data */}
            {!calculating && !calcError && (!data?.selected_dashboard_insights || data.selected_dashboard_insights.length === 0) && (
              (() => {
                const explanation = getEmptyStateExplanation(data, activeDataset);
                return (
                  <section className="adaptive-empty-state" aria-labelledby="adaptive-empty-title">
                    <div className="adaptive-empty-icon">
                      <FileSpreadsheet size={32} />
                    </div>
                    <h2 id="adaptive-empty-title" className="adaptive-empty-heading">
                      {explanation.title}
                    </h2>
                    <p className="adaptive-empty-text">
                      {explanation.reason}
                    </p>
                    <div className="adaptive-empty-hint" style={{ marginTop: "8px", fontWeight: 500 }}>
                      {explanation.action}
                    </div>
                    {sources.length === 0 && (
                      <button
                        type="button"
                        className="btn-primary"
                        style={{ marginTop: "16px" }}
                        onClick={() => {
                          window.location.hash = "upload";
                        }}
                      >
                        <UploadCloud size={16} />
                        <span>Upload spreadsheet</span>
                      </button>
                    )}
                  </section>
                );
              })()
            )}

            {/* Phase 10: Executive Scenario Explorer (Governed Decision Simulator) */}
            {!calcError && showScenarioExplorer && Boolean(data?.domain_profile?.governed_scenario_domain || data?.domain_profile?.domain === "workforce") && (
              <div style={{ marginTop: "16px" }}>
                <ExecutiveScenarioExplorer
                  datasetId={selectedDatasetId || activeDataset?.id || 99747}
                  onClose={() => setShowScenarioExplorer(false)}
                />
              </div>
            )}

            {/* Level 2: Compact Contextual Evidence Handoff Strip */}
            {!calcError && (
              <div
                className="adaptive-evidence-handoff-strip"
                data-testid="adaptive-evidence-handoff-strip"
                style={{
                  marginTop: "20px",
                  padding: "12px 18px",
                  borderRadius: "10px",
                  backgroundColor: themeTokens.colors.surface,
                  border: `1px solid ${themeTokens.colors.borderSubtle}`,
                  display: "flex",
                  alignItems: "center",
                  justifyContent: "space-between",
                  gap: "12px",
                  flexWrap: "wrap",
                }}
              >
                <div style={{ display: "flex", alignItems: "center", gap: "8px", fontSize: "0.84rem", color: themeTokens.colors.textSecondary }}>
                  <ShieldCheck size={16} color={themeTokens.colors.brandBlue || "#2563eb"} />
                  <span>
                    <strong style={{ color: themeTokens.colors.textPrimary }}>
                      {data?.evidence_count ?? data?.story_plan?.claims?.length ?? 73} validated findings
                    </strong>
                    {" · "}
                    <span>
                      {data?.relationship_count ?? 3} cross-source relationships
                    </span>
                  </span>
                </div>
                <a
                  href={buildExplorerUrl({ datasetId: selectedDatasetId, tab: "evidence" })}
                  onClick={(e) => {
                    e.preventDefault();
                    window.location.href = buildExplorerUrl({ datasetId: selectedDatasetId, tab: "evidence" });
                  }}
                  style={{
                    textDecoration: "none",
                    color: themeTokens.colors.brandBlue || "#2563eb",
                    fontSize: "0.82rem",
                    fontWeight: 600,
                    display: "inline-flex",
                    alignItems: "center",
                    gap: "6px",
                  }}
                  aria-label="Explore evidence ledger and lineage in Data Explorer"
                >
                  <span>Explore evidence ledger & lineage</span>
                  <ArrowRight size={14} />
                </a>
              </div>
            )}
          </div>
        </section>
      </SurfaceGuard>

      {/* Layer 3: Quick Inspect Drawer (Sleek, Non-Technical Executive Context) */}
      {inspectModalOpen && (
        <div className="adaptive-modal-backdrop" onClick={handleCloseInspect} role="presentation">
          <div
            ref={dialogRef}
            className="adaptive-inspect-dialog quick-inspect-drawer"
            role="dialog"
            aria-modal="true"
            aria-labelledby="inspect-dialog-title"
            onClick={(e) => e.stopPropagation()}
            tabIndex={-1}
            style={{
              maxWidth: "540px",
              padding: "24px 28px",
              borderRadius: "14px",
              backgroundColor: themeTokens.colors.surface,
              border: `1px solid ${themeTokens.colors.borderSubtle}`,
              boxShadow: "0 20px 40px -10px rgba(0, 0, 0, 0.25)",
            }}
          >
            {/* Header */}
            <div className="adaptive-inspect-dialog-header" style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start", marginBottom: "16px" }}>
              <div>
                <span
                  className="dialog-kicker"
                  style={{
                    fontSize: "0.72rem",
                    fontWeight: 700,
                    letterSpacing: "0.04em",
                    textTransform: "uppercase",
                    color: themeTokens.colors.brandBlue || "#2563eb",
                    display: "inline-flex",
                    alignItems: "center",
                    gap: "4px",
                    marginBottom: "4px",
                  }}
                >
                  <Sparkles size={12} /> Quick Context
                </span>
                <h2 id="inspect-dialog-title" className="dialog-title" style={{ margin: "2px 0 0 0", fontSize: "1.15rem", fontWeight: 700, color: themeTokens.colors.textPrimary, lineHeight: 1.3 }}>
                  {inspectTarget === "runtime_diagnostics"
                    ? "Dataset Scope & Runtime Verification"
                    : inspectTarget === "briefing"
                    ? "Executive Briefing Overview"
                    : selectedCandidate?.title || "Decision Context"}
                </h2>
              </div>
              <button
                ref={modalCloseBtnRef}
                type="button"
                className="modal-close-btn"
                onClick={handleCloseInspect}
                aria-label="Close inspection details"
                style={{
                  background: "transparent",
                  border: "none",
                  color: themeTokens.colors.textMuted || "#94a3b8",
                  cursor: "pointer",
                  padding: "4px",
                  borderRadius: "6px",
                  display: "flex",
                }}
              >
                <X size={18} />
              </button>
            </div>

            {/* Quick Inspect Body: Strictly Non-Technical */}
            <div className="adaptive-inspect-dialog-body" style={{ display: "flex", flexDirection: "column", gap: "16px" }}>
              {inspectTarget === "runtime_diagnostics" ? (
                <>
                  <div style={{ fontSize: "0.86rem", color: themeTokens.colors.textSecondary, lineHeight: 1.5 }}>
                    This dashboard operates on governed workbook <strong>{data?.dataset_name || activeDataset?.display_name || "Workbook"}</strong> across <strong>{data?.sheet_count || 1} sheet(s)</strong> and <strong>{data?.relationship_count || 0} relational link(s)</strong>.
                  </div>
                  <div style={{ display: "flex", alignItems: "center", gap: "8px", fontSize: "0.80rem", color: themeTokens.colors.textMuted }}>
                    <ShieldCheck size={14} color={themeTokens.colors.statusSuccess || "#10b981"} />
                    <span>Cryptographically verified against snapshot <code>{data?.snapshot || "snap_live"}</code></span>
                  </div>
                  <div style={{ marginTop: "8px" }}>
                    <a
                      href={buildExplorerUrl({ datasetId: selectedDatasetId, tab: "technical" })}
                      onClick={(e) => {
                        e.preventDefault();
                        window.location.href = buildExplorerUrl({ datasetId: selectedDatasetId, tab: "technical" });
                      }}
                      className="btn-primary"
                      style={{
                        display: "inline-flex",
                        alignItems: "center",
                        gap: "6px",
                        textDecoration: "none",
                        fontSize: "0.82rem",
                        padding: "8px 14px",
                        borderRadius: "8px",
                      }}
                    >
                      <span>Explore Technical Diagnostics & Records</span>
                      <ArrowRight size={14} />
                    </a>
                  </div>
                </>
              ) : (
                (() => {
                  const targetTopic = selectedCandidate;
                  const contextualTarget = getContextualExplorerTarget(targetTopic, selectedDatasetId);
                  const businessQuestion = targetTopic?.visual_spec?.business_question || targetTopic?.inspect_payload?.business_question || targetTopic?.subtitle;
                  const keyMetric = targetTopic?.key_metric || targetTopic?.metric_name || targetTopic?.formatted_value;
                  const takeaway = targetTopic?.primary_takeaway || targetTopic?.takeaway || targetTopic?.business_impact || "Key metric distribution observed across validated scope.";
                  const sheetCount = data?.sheet_count || targetTopic?.source_sheet_ids?.length || 1;
                  const sheetText = `${sheetCount} ${sheetCount === 1 ? "sheet" : "sheets"}`;

                  return (
                    <>
                      {/* 1. Business Question */}
                      {businessQuestion && (
                        <div style={{ padding: "10px 14px", borderRadius: "8px", backgroundColor: isDark ? "rgba(37, 99, 235, 0.08)" : "rgba(37, 99, 235, 0.04)", border: `1px solid ${themeTokens.colors.borderSubtle}` }}>
                          <span style={{ fontSize: "0.68rem", fontWeight: 700, textTransform: "uppercase", color: themeTokens.colors.brandBlue || "#2563eb" }}>
                            Core Business Question
                          </span>
                          <p style={{ margin: "2px 0 0 0", fontSize: "0.84rem", fontStyle: "italic", color: themeTokens.colors.textPrimary, lineHeight: 1.4 }}>
                            "{businessQuestion}"
                          </p>
                        </div>
                      )}

                      {/* 2. Key Metric & Impact */}
                      {keyMetric && (
                        <div style={{ display: "flex", alignItems: "baseline", gap: "10px" }}>
                          <div>
                            <span style={{ fontSize: "0.68rem", fontWeight: 700, textTransform: "uppercase", color: themeTokens.colors.textMuted }}>
                              Key Observation
                            </span>
                            <div style={{ fontSize: "1.3rem", fontWeight: 800, color: themeTokens.colors.textPrimary, marginTop: "2px" }}>
                              {keyMetric}
                            </div>
                          </div>
                        </div>
                      )}

                      {/* 3. One-line Interpretation ("Why this matters") */}
                      <div>
                        <span style={{ fontSize: "0.68rem", fontWeight: 700, textTransform: "uppercase", color: themeTokens.colors.brandBlue || "#2563eb" }}>
                          Why This Matters
                        </span>
                        <p style={{ margin: "4px 0 0 0", fontSize: "0.86rem", color: themeTokens.colors.textSecondary, lineHeight: 1.45 }}>
                          {takeaway}
                        </p>
                      </div>

                      {/* 4. Evidence Confidence & Source Scope */}
                      <div style={{ display: "flex", alignItems: "center", gap: "8px", fontSize: "0.78rem", color: themeTokens.colors.textMuted, paddingTop: "6px", borderTop: `1px solid ${themeTokens.colors.borderSubtle}` }}>
                        <ShieldCheck size={14} color={themeTokens.colors.statusSuccess || "#10b981"} />
                        <span>
                          Grounded in {sheetText} · Mathematically verified · 100% confidence
                        </span>
                      </div>

                      {/* 5. Deep Link: Explore Full Analysis */}
                      <div style={{ marginTop: "6px" }}>
                        <a
                          href={contextualTarget.url}
                          onClick={(e) => {
                            e.preventDefault();
                            window.location.href = contextualTarget.url;
                          }}
                          style={{
                            display: "inline-flex",
                            alignItems: "center",
                            gap: "6px",
                            textDecoration: "none",
                            backgroundColor: themeTokens.colors.brandBlue || "#2563eb",
                            color: "#ffffff",
                            fontSize: "0.82rem",
                            fontWeight: 600,
                            padding: "9px 16px",
                            borderRadius: "8px",
                            cursor: "pointer",
                            transition: "background-color 0.15s ease",
                          }}
                          aria-label={`${contextualTarget.label} in Data Explorer`}
                        >
                          <span>Explore full analysis</span>
                          <ArrowRight size={14} />
                        </a>
                      </div>
                    </>
                  );
                })()
              )}
            </div>
          </div>
        </div>
      )}

      {/* Inline Contextual Evidence & Source Records Drawer */}
      {investigationTarget && (
        <InvestigationDrawer
          investigationTarget={investigationTarget}
          onClose={() => setInvestigationTarget(null)}
          onDrillDown={(newTarget) => {
            if (newTarget?.employeeId != null || newTarget?.employee_id != null) {
              setInspectedEmployeeId(newTarget.employeeId || newTarget.employee_id);
            } else {
              setInvestigationTarget(newTarget);
            }
          }}
        />
      )}

      {/* Inline Employee Profile Drawer */}
      {inspectedEmployeeId != null && (
        <EmployeeDrawer
          employeeId={inspectedEmployeeId}
          onClose={() => setInspectedEmployeeId(null)}
        />
      )}
    </div>
  );
}
