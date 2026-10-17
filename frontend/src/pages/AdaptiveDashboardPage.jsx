import React, { useEffect, useMemo, useRef, useState } from "react";
import {
  ArrowRight,
  Presentation,
  Layers,
  TrendingUp,
  Table,
  FileSpreadsheet,
  UploadCloud,
  AlertTriangle,
  Loader2,
  ShieldCheck,
  ExternalLink,
  RefreshCw,
  CheckCircle2,
  X,
} from "lucide-react";
import Button from "../design-system/components/Button";
import ActionIconButton from "../design-system/components/ActionIconButton";
import ErrorBoundary from "../components/common/ErrorBoundary";
import Select from "../components/common/Select";
import ExecutiveBriefingCard from "../components/adaptive/ExecutiveBriefingCard";
import InvestigationDrawer from "../components/InvestigationDrawer";
import EmployeeDrawer from "../components/EmployeeDrawer";
import UnifiedExecutiveInsightsGrid from "../components/adaptive/UnifiedExecutiveInsightsGrid";
import SectionHeader from "../components/adaptive/SectionHeader";
import QuickInspectDialog from "../components/adaptive/QuickInspectDialog";
import ExecutiveScenarioExplorer from "../components/adaptive/ExecutiveScenarioExplorer";
import EmptyDashboardBoundary from "../components/adaptive/EmptyDashboardBoundary";
import EmptyDashboardState from "../components/adaptive/EmptyDashboardState";
import {
  DASHBOARD_STATES,
  resolveDashboardState,
} from "../contracts/DashboardStateContract";
import { sanitizeError } from "../contracts/ProductErrorSanitizer";
import {
  extractDatasetIdFromUrl,
  validateAndResolveDataset,
  selfHealUrl,
} from "../contracts/DatasetReferenceIntegrity";
import {
  NAVIGATION_INTENTS,
  dispatchNavigationIntent,
} from "../contracts/NavigationIntentRegistry";
import { resolveGovernedCount } from "../contracts/DashboardTruthIntegrity";
import { STORAGE_KEYS } from "../constants/storageKeys";
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

export default function AdaptiveDashboardPage({ onNavigateTab, onOpenUpload }) {
  const { isDark } = useTheme();
  const themeTokens = getThemeTokens(isDark);

  // Source / Dataset State — normalized strictly to dataset_id (WP-9.6)
  const [sources, setSources] = useState([]);
  const [sourcesLoading, setSourcesLoading] = useState(true);
  const [sourcesError, setSourcesError] = useState(null);
  const [selectedDatasetId, setSelectedDatasetId] = useState(extractDatasetIdFromUrl);

  // Analysis State
  const [data, setData] = useState(null);
  const [calculating, setCalculating] = useState(false);
  const [calcError, setCalcError] = useState(null);
  const [revision, setRevision] = useState(0);
  const [burstCache, setBurstCache] = useState(false);
  const [refreshNotice, setRefreshNotice] = useState(null);
  const [lastRefreshedAt, setLastRefreshedAt] = useState(null);

  useEffect(() => {
    if (!refreshNotice) return;
    const timer = setTimeout(() => {
      setRefreshNotice(null);
    }, 4500);
    return () => clearTimeout(timer);
  }, [refreshNotice]);

  // Inspect & Disclosure State
  const [inspectModalOpen, setInspectModalOpen] = useState(false);
  const [inspectTarget, setInspectTarget] = useState("candidate");
  const [selectedCandidate, setSelectedCandidate] = useState(null);
  const [investigationTarget, setInvestigationTarget] = useState(null);
  const [inspectedEmployeeId, setInspectedEmployeeId] = useState(null);
  const [showScenarioExplorer, setShowScenarioExplorer] = useState(false);
  const [developerMode] = useState(() => {
    try {
      const p = new URLSearchParams(window.location.search);
      return p.get("dev") === "true" || p.get("developer") === "true";
    } catch {
      return false;
    }
  });

  const modalCloseBtnRef = useRef(null);
  const activeControllerRef = useRef(null);
  const requestCounter = useRef(0);

  // Formal HighView State Machine Resolution
  const dashboardState = useMemo(() => {
    return resolveDashboardState({
      sourcesLoading,
      sources,
      selectedDatasetId,
      data,
      calculating,
      calcError,
      sourcesError,
    });
  }, [sourcesLoading, sources, selectedDatasetId, data, calculating, calcError, sourcesError]);

  const activeDataset = useMemo(() => {
    return sources.find((d) => String(d.id) === String(selectedDatasetId)) || sources[0] || null;
  }, [sources, selectedDatasetId]);

  const handleSourceSelect = (newId) => {
    setSelectedDatasetId(newId);
    selfHealUrl(newId);
  };

  // 1. Load Datasets/Workbooks on Mount & Normalize Scope (WP-9.6)
  const loadSources = (forceBurst = false) => {
    setSourcesLoading(true);
    setSourcesError(null);
    const qs = forceBurst ? `?_ts=${Date.now()}` : "";
    const options = forceBurst
      ? {
          headers: {
            "Cache-Control": "no-cache, no-store, must-revalidate",
            "Pragma": "no-cache",
          },
        }
      : {};
    fetchJson(`/api/upload/datasets${qs}`, options)
      .then((res) => {
        const list = Array.isArray(res) ? res : res.datasets || [];
        setSources(list);

        const urlDatasetId = extractDatasetIdFromUrl();
        const resolution = validateAndResolveDataset(list, urlDatasetId);

        setSelectedDatasetId(resolution.resolvedId);
        if (resolution.status === "CATALOG_EMPTY") {
          setData(null);
          setCalcError(null);
        }
      })
      .catch((err) => {
        setSourcesError(sanitizeError(err));
      })
      .finally(() => {
        setSourcesLoading(false);
      });
  };

  const handleRefresh = () => {
    if (calculating || !selectedDatasetId) return;
    setBurstCache(true);
    setRevision((r) => r + 1);
    loadSources(true);
  };

  useEffect(() => {
    loadSources();
    window.addEventListener("workbook-uploaded", () => loadSources(true));
    return () => window.removeEventListener("workbook-uploaded", () => loadSources(true));
  }, []);

  useEffect(() => {
    const handleUrlChange = () => {
      const idFromUrl = extractDatasetIdFromUrl();
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

    const shouldBurst = burstCache || revision > 0;
    const burstQuery = shouldBurst
      ? `&force_refresh=true&burst_cache=true&_ts=${Date.now()}`
      : "";
    const fetchOptions = {
      signal: controller.signal,
      ...(shouldBurst
        ? {
            headers: {
              "Cache-Control": "no-cache, no-store, must-revalidate",
              "Pragma": "no-cache",
            },
          }
        : {}),
    };

    fetchJson(`/api/adaptive-dashboard/primary-element?dataset_id=${selectedDatasetId}${burstQuery}`, fetchOptions)
      .then((res) => {
        if (currentReqId !== requestCounter.current) return;
        setData(res);
        if (shouldBurst) {
          const now = new Date();
          const timeStr = now.toLocaleTimeString([], { hour: "2-digit", minute: "2-digit", second: "2-digit" });
          setLastRefreshedAt(timeStr);
          setRefreshNotice({
            type: "success",
            title: "Cache Burst & Refreshed",
            message: `Dashboard intelligence recalculated fresh at ${timeStr}. Stale cache was purged.`,
            timestamp: Date.now(),
          });
        }
      })
      .catch((err) => {
        if (currentReqId !== requestCounter.current) return;
        if (err.name !== "AbortError") {
          const rawMsg = err.message || "";
          if (rawMsg.includes("No uploaded sheet found") || rawMsg.includes("not found")) {
            // Stale or deleted dataset requested -> cleanly self-heal URL and clear state
            setData(null);
            setSelectedDatasetId("");
            setCalcError(null);
            selfHealUrl(null);
          } else {
            setCalcError(sanitizeError(err));
          }
          if (shouldBurst) {
            setRefreshNotice({
              type: "error",
              title: "Refresh Failed",
              message: err.message || "Failed to recalculate dashboard intelligence.",
              timestamp: Date.now(),
            });
          }
        }
      })
      .finally(() => {
        if (currentReqId === requestCounter.current) {
          setCalculating(false);
          setBurstCache(false);
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
      sessionStorage.setItem(STORAGE_KEYS.PRESENTATION_SOURCE, JSON.stringify(storedConfig));
      sessionStorage.setItem(STORAGE_KEYS.PRESENTATION_DASHBOARD_CONTEXT, JSON.stringify(storedConfig));
    } catch {}
    dispatchNavigationIntent(NAVIGATION_INTENTS.CREATE_PRESENTATION, {}, { onNavigateTab });
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
      {/* Floating Refresh / Cache Burst Notification Toast */}
      {refreshNotice && (
        <div
          className={`dashboard-refresh-toast ${refreshNotice.type === "error" ? "is-error" : "is-success"}`}
          role="status"
          aria-live="polite"
        >
          {refreshNotice.type === "error" ? (
            <AlertTriangle size={18} className="toast-icon-error" aria-hidden="true" />
          ) : (
            <CheckCircle2 size={18} className="toast-icon-success" aria-hidden="true" />
          )}
          <div className="toast-body">
            <span className="toast-title">{refreshNotice.title}</span>
            <span className="toast-msg">{refreshNotice.message}</span>
          </div>
          <ActionIconButton
            action="close"
            buttonSize={26}
            size={13}
            variant="ghost"
            onClick={() => setRefreshNotice(null)}
            ariaLabel="Dismiss notification"
          />
        </div>
      )}

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
            {sources.length > 0 && (
              <div className="scope-control-group">
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

            {scopeLine && sources.length > 0 && (
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
                  <span>{lastRefreshedAt ? `Refreshed ${lastRefreshedAt}` : "Live verified"}</span>
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
                onClick={() => dispatchNavigationIntent(NAVIGATION_INTENTS.OPEN_UPLOAD, {}, { onNavigateTab, onOpenUpload })}
                ariaLabel="Upload new spreadsheet"
                title="Upload new spreadsheet"
              >
                Upload Data
              </Button>
            )}
            {sources.length > 0 && (
              <Button
                variant="GHOST"
                size="sm"
                icon={RefreshCw}
                className={`scope-refresh-btn ${calculating && (burstCache || revision > 0) ? "is-refreshing" : ""}`}
                onClick={handleRefresh}
                disabled={calculating || !selectedDatasetId}
                ariaLabel="Refresh and burst cache for selected workbook"
                title="Refresh and burst cache for selected workbook"
              >
                {calculating && (burstCache || revision > 0) ? "Refreshing…" : "Refresh"}
              </Button>
            )}
          </div>
        </div>
      </header>

      {/* Source Loading or Source Error State */}
      {sourcesError && (
        <div className="adaptive-status-notice error" role="alert">
          <span>{sourcesError.message}</span>
          <Button
            variant="GHOST"
            size="sm"
            icon={RefreshCw}
            onClick={loadSources}
            ariaLabel="Retry loading sources"
          >
            Retry
          </Button>
        </div>
      )}

      {/* Calculation Error State */}
      {calcError && !calculating && (
        <div className="adaptive-status-notice error" role="alert">
          <span>{calcError.message}</span>
          <Button
            variant="GHOST"
            size="sm"
            icon={RefreshCw}
            onClick={() => setRevision((r) => r + 1)}
            ariaLabel="Retry calculating executive intelligence"
          >
            Retry
          </Button>
        </div>
      )}

      {/* Runtime Developer Diagnostics Trigger */}
      {developerMode && data && (
        <div style={{ display: "flex", justifyContent: "flex-end", marginBottom: "12px" }}>
          <Button
            variant="GHOST"
            size="sm"
            iconRight={ExternalLink}
            data-testid="executive-dashboard-runtime-diagnostic"
            onClick={() => handleOpenInspect("runtime_diagnostics")}
            ariaLabel="Inspect runtime scope and diagnostics in drawer"
          >
            [Dev Scope] Dataset {data?.dataset_id || selectedDatasetId} ({data?.candidate_count ?? 0} candidates)
          </Button>
        </div>
      )}

      {/* Executive Dashboard Governed Content Container Protected by Zero-Data Render Firewall */}
      <SurfaceGuard surface="dashboard">
        <EmptyDashboardBoundary
          dashboardState={dashboardState}
          error={calcError || sourcesError}
          onRetry={() => {
            if (sourcesError) loadSources();
            else setRevision((r) => r + 1);
          }}
          onNavigateTab={onNavigateTab}
          onOpenUpload={onOpenUpload}
        >
          <section className="adaptive-content-container" aria-label="Dashboard Content">
            {/* State A: Indeterminate Executive Loader */}
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
              {/* Governed Executive Briefing Audio/Text */}
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

              {/* Governed Unified Executive Insights Grid */}
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
                    sheetCount={data.sheet_count ?? null}
                    domainProfile={data?.domain_profile || null}
                    layoutPlan={data?.layout_plan || null}
                    onInspectInsight={(cand) => {
                      handleOpenInspect("candidate", cand);
                    }}
                    onOpenScenarioExplorer={() => setShowScenarioExplorer(true)}
                  />
                </ErrorBoundary>
              )}

              {/* Truthful Empty State for Dataset with Zero Insights */}
              {!calculating && !calcError && (!data?.selected_dashboard_insights || data.selected_dashboard_insights.length === 0) && (
                <EmptyDashboardState
                  onNavigateTab={onNavigateTab}
                  onOpenUpload={onOpenUpload}
                />
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
                      <ShieldCheck size={16} color="var(--brand-400, #075443)" aria-hidden="true" />
                      <span>
                        <strong style={{ color: themeTokens.colors.textPrimary }}>
                          {data.evidence_count != null ? `${data.evidence_count} validated findings` : "Validated findings"}
                        </strong>
                        {" · "}
                        <span>
                          {data.relationship_count != null ? `${data.relationship_count} cross-source relationships` : "Verified relationships"}
                        </span>
                      </span>
                    </div>
                    <Button
                      variant="GHOST"
                      size="sm"
                      iconRight={ArrowRight}
                      onClick={() => {
                        dispatchNavigationIntent(NAVIGATION_INTENTS.OPEN_EVIDENCE, { datasetId: selectedDatasetId }, { onNavigateTab });
                      }}
                      ariaLabel="Explore evidence ledger and lineage in Data Explorer"
                    >
                      Explore evidence ledger & lineage
                    </Button>
                  </div>
                </aside>
              )}
            </div>
          </section>
        </EmptyDashboardBoundary>
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
        onNavigateTab={onNavigateTab}
      />

      {/* Governed Executive Scenario Explorer */}
      {showScenarioExplorer && (
        <ExecutiveScenarioExplorer
          datasetId={selectedDatasetId}
          onClose={() => setShowScenarioExplorer(false)}
        />
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
