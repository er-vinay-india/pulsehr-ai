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
  RefreshCw,
} from "lucide-react";
import Button from "../design-system/components/Button";
import ErrorBoundary from "../components/common/ErrorBoundary";
import Select from "../components/common/Select";
import ExecutiveBriefingCard from "../components/adaptive/ExecutiveBriefingCard";
import InvestigationDrawer from "../components/InvestigationDrawer";
import EmployeeDrawer from "../components/EmployeeDrawer";
import UnifiedExecutiveInsightsGrid from "../components/adaptive/UnifiedExecutiveInsightsGrid";
import SectionHeader from "../components/adaptive/SectionHeader";
import QuickInspectDialog from "../components/adaptive/QuickInspectDialog";
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

function getEmptyStateExplanation(data, activeDataset, sourcesCount = 0) {
  if (sourcesCount === 0 || (!data && !activeDataset)) {
    return {
      title: "No Workbooks Ingested",
      reason: "No datasets or spreadsheets have been uploaded to HighView yet.",
      action: "Upload an Excel (.xlsx, .xls) or CSV file to start automated executive intelligence."
    };
  }

  if (!data) {
    return {
      title: "No Data Available",
      reason: "Unable to retrieve analytical records for this workbook.",
      action: "Select an uploaded workbook or upload a new spreadsheet."
    };
  }

  if (data.total_rows === 0) {
    return {
      title: "Empty Spreadsheet",
      reason: `The selected workbook "${activeDataset?.display_name || data?.dataset_name || "Workbook"}" contains 0 data records after table reconstruction.`,
      action: "Upload a spreadsheet containing valid data rows."
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

function getDatasetIdFromUrl() {
  try {
    const searchP = new URLSearchParams(window.location.search);
    const searchVal = searchP.get("dataset_id") || searchP.get("sheet_id");
    if (searchVal) return searchVal;
    const hash = window.location.hash || "";
    if (hash.includes("?")) {
      const hashP = new URLSearchParams(hash.substring(hash.indexOf("?")));
      const hashVal = hashP.get("dataset_id") || hashP.get("sheet_id");
      if (hashVal) return hashVal;
    }
  } catch {}
  return "";
}

export default function AdaptiveDashboardPage({ onNavigateTab }) {
  const { isDark } = useTheme();
  const themeTokens = getThemeTokens(isDark);

  // Source / Dataset State — normalized strictly to dataset_id (WP-9.6)
  const [sources, setSources] = useState([]);
  const [sourcesLoading, setSourcesLoading] = useState(true);
  const [sourcesError, setSourcesError] = useState(null);
  const [selectedDatasetId, setSelectedDatasetId] = useState(getDatasetIdFromUrl);

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
        const urlDatasetId = getDatasetIdFromUrl();
        const p = new URLSearchParams(window.location.search);
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

  useEffect(() => {
    const handleUrlChange = () => {
      const idFromUrl = getDatasetIdFromUrl();
      if (idFromUrl && idFromUrl !== selectedDatasetId) {
        setSelectedDatasetId(idFromUrl);
      }
    };
    window.addEventListener("popstate", handleUrlChange);
    window.addEventListener("hashchange", handleUrlChange);
    return () => {
      window.removeEventListener("popstate", handleUrlChange);
      window.removeEventListener("hashchange", handleUrlChange);
    };
  }, [selectedDatasetId]);

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
    setSelectedCandidate(cand || (target === "briefing" ? briefingElement : null));
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
    } else {
      period = period.replace(/\s*\([^)]*\)/g, "").trim();
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
        </div>

        {/* Compact Dataset Context & Command Bar */}
        <div className="adaptive-scope-bar page-command-bar" aria-label="Dataset Command Bar">
          <div className="dataset-selector-and-context">
            <div className="scope-control-group">
              <Select
                id="dataset-selector"
                value={selectedDatasetId}
                onChange={(e) => handleSourceSelect(e.target.value)}
                disabled={sourcesLoading || sources.length === 0}
                aria-label="Selected dataset workbook"
                placeholder={sourcesLoading ? "Loading datasets…" : sources.length === 0 ? "No datasets uploaded" : "Select dataset…"}
                options={
                  sources.length > 0
                    ? sources.map((d) => ({
                        value: String(d.id),
                        label: d.display_name || d.original_name || `Dataset ${d.id}`,
                      }))
                    : selectedDatasetId
                    ? [
                        {
                          value: String(selectedDatasetId),
                          label: data?.dataset_name || activeDataset?.display_name || activeDataset?.original_name || "Dataset",
                        },
                      ]
                    : []
                }
              />
            </div>

            {scopeLine && (
              <div className="dataset-context-meta" aria-label="Dataset context">
                <span className="dataset-context-meta__item dataset-context-meta__period">
                  {scopeLine.period}
                </span>
                <span className="dataset-context-meta__sep">·</span>
                <span className="dataset-context-meta__item dataset-context-meta__sheets">
                  {scopeLine.sheet}
                </span>
                <span className="dataset-context-meta__sep">·</span>
                <span className="dataset-context-meta__item dataset-context-meta__verified">
                  <span className="scope-live-dot" aria-hidden="true" />
                  <span>Live verified</span>
                </span>
              </div>
            )}
          </div>

          <div style={{ display: "flex", alignItems: "center", gap: "8px" }}>
            {sources.length === 0 && !sourcesLoading && (
              <Button
                variant="PRIMARY"
                size="sm"
                icon={UploadCloud}
                onClick={() => {
                  if (typeof onNavigateTab === "function") {
                    onNavigateTab("upload");
                  } else {
                    window.location.hash = "upload";
                  }
                }}
                ariaLabel="Upload new spreadsheet"
                title="Upload new spreadsheet"
              >
                Upload Data
              </Button>
            )}
            <Button
              variant="GHOST"
              size="sm"
              icon={RefreshCw}
              className="scope-refresh-btn"
              onClick={() => setRevision((r) => r + 1)}
              disabled={calculating || !selectedDatasetId || sources.length === 0}
              ariaLabel="Refresh analysis for selected workbook"
              title="Refresh analysis for selected workbook"
            >
              Refresh
            </Button>
          </div>
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
            {/* Governed Executive Briefing Audio/Text (if available at dataset level) */}
            {!calcError && briefingElement && (
              <section
                className="dashboard-section dashboard-section--summary"
                aria-labelledby="section-summary-heading"
                style={{ marginBottom: "24px" }}
              >
                <SectionHeader
                  id="section-summary-heading"
                  title="Executive Summary"
                />
                <ExecutiveBriefingCard
                  briefing={briefingElement}
                  sheetId={selectedDatasetId}
                  onOpenInspect={() => handleOpenInspect("briefing", briefingElement)}
                  snapshot={data?.snapshot}
                  domain={data?.contract?.domain}
                />
              </section>
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
                  layoutPlan={data?.layout_plan || null}
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
                const isNoSources = sources.length === 0 || (!data && !activeDataset);
                const explanation = getEmptyStateExplanation(data, activeDataset, sources.length);
                return (
                  <section className="adaptive-empty-state" aria-labelledby="adaptive-empty-title">
                    <div className="adaptive-empty-icon" aria-hidden="true">
                      <FileSpreadsheet size={36} />
                    </div>
                    <h2 id="adaptive-empty-title" className="adaptive-empty-heading">
                      {explanation.title}
                    </h2>
                    <p className="adaptive-empty-text">
                      {explanation.reason}
                    </p>
                    <div className="adaptive-empty-hint">
                      {explanation.action}
                    </div>

                    {isNoSources && (
                      <div className="adaptive-empty-features" aria-label="HighView Capabilities">
                        <div className="adaptive-empty-feature-card">
                          <div className="feature-icon-wrap" aria-hidden="true"><Layers size={20} /></div>
                          <strong>Adaptive Ingestion</strong>
                          <span>Auto-reconstructs messy multi-row headers, merged cells, and wrapped records into clean tabular datasets.</span>
                        </div>
                        <div className="adaptive-empty-feature-card">
                          <div className="feature-icon-wrap" aria-hidden="true"><TrendingUp size={20} /></div>
                          <strong>Deterministic Truth</strong>
                          <span>Uncovers statistical variance, outlier clusters, and business KPIs with zero LLM math or hallucinated numbers.</span>
                        </div>
                        <div className="adaptive-empty-feature-card">
                          <div className="feature-icon-wrap" aria-hidden="true"><Presentation size={20} /></div>
                          <strong>Executive Studio</strong>
                          <span>Transforms verified findings into 16:9 board-ready presentations with 100% native editable PowerPoint charts.</span>
                        </div>
                      </div>
                    )}

                    <div className="adaptive-empty-actions">
                      <button
                        type="button"
                        className="btn-primary"
                        onClick={() => {
                          if (typeof onNavigateTab === "function") {
                            onNavigateTab("upload");
                          } else {
                            window.location.hash = "upload";
                          }
                        }}
                      >
                        <UploadCloud size={18} />
                        <span>Upload Spreadsheet</span>
                      </button>
                      <button
                        type="button"
                        className="btn-secondary"
                        onClick={() => {
                          if (typeof onNavigateTab === "function") {
                            onNavigateTab("explorer");
                          } else {
                            window.location.hash = "explorer";
                          }
                        }}
                      >
                        <Table size={16} />
                        <span>Open Data Explorer</span>
                      </button>
                    </div>
                  </section>
                );
              })()
            )}

            {/* Level 2: Compact Contextual Evidence & Governance Handoff Strip */}
            {!calcError && data && (data.evidence_count > 0 || (data.selected_dashboard_insights && data.selected_dashboard_insights.length > 0)) && (
              <aside
                className="dashboard-section dashboard-section--evidence"
                aria-label="Evidence and governance"
                style={{ marginTop: "24px" }}
              >
                <div
                  className="adaptive-evidence-handoff-strip"
                  data-testid="adaptive-evidence-handoff-strip"
                  style={{
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
                    <ShieldCheck size={16} color={themeTokens.colors.brandBlue || "#2563eb"} aria-hidden="true" />
                    <span>
                      <strong style={{ color: themeTokens.colors.textPrimary }}>
                        {data.evidence_count ?? data.story_plan?.claims?.length ?? 0} validated findings
                      </strong>
                      {" · "}
                      <span>
                        {data.relationship_count ?? 0} cross-source relationships
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
                      minHeight: "32px",
                      padding: "6px 10px",
                      borderRadius: "6px",
                    }}
                    aria-label="Explore evidence ledger and lineage in Data Explorer"
                  >
                    <span>Explore evidence ledger & lineage</span>
                    <ArrowRight size={14} aria-hidden="true" />
                  </a>
                </div>
              </aside>
            )}
          </div>
        </section>
      </SurfaceGuard>

      {/* Layer 3: Accessible Quick Inspect Dialog Rendered Through Portal */}
      <QuickInspectDialog
        isOpen={inspectModalOpen}
        onClose={handleCloseInspect}
        inspectTarget={inspectTarget}
        selectedCandidate={selectedCandidate}
        data={data}
        activeDataset={activeDataset}
        selectedDatasetId={selectedDatasetId}
        themeTokens={themeTokens}
        isDark={isDark}
      />

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
