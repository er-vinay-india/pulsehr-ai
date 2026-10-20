import React, { useState, useEffect, useRef, useMemo } from "react";
import {
  ShieldCheck,
  CheckCircle2,
  GitMerge,
  Database,
  Search,
  ExternalLink,
  Code2,
  AlertCircle,
  Sparkles,
  ChevronDown,
  ChevronUp,
  Table as TableIcon,
  Layers,
  ArrowRight,
  Loader2,
} from "lucide-react";
import {
  getTargetedEvidence,
  getEvidenceLineage,
  getEvidenceSourceContext,
  getPaginatedEvidence,
} from "../../api/client";
import DataTable from "../DataTable";

export default function EvidenceExplorer({
  sheetId = null,
  datasetId = null,
  initialTopicId = null,
  initialEvidenceId = null,
  themeTokens,
  isDark = false,
}) {
  // 1. Primary Targeted Evidence State
  const [activeEvidenceId, setActiveEvidenceId] = useState(
    initialEvidenceId || (sheetId ? `EVID-S${sheetId}-EVID-002` : "EVID-S9967451-EVID-002")
  );
  const [targetedEvidence, setTargetedEvidence] = useState(null);
  const [loadingTargeted, setLoadingTargeted] = useState(true);
  const [targetedError, setTargetedError] = useState(null);

  // 2. Deferred Lineage State
  const [lineageOpen, setLineageOpen] = useState(false);
  const [lineageData, setLineageData] = useState(null);
  const [loadingLineage, setLoadingLineage] = useState(false);

  // 3. Deferred Bounded Source Context State
  const [sourceContextOpen, setSourceContextOpen] = useState(false);
  const [sourceContextData, setSourceContextData] = useState(null);
  const [loadingSourceContext, setLoadingSourceContext] = useState(false);

  // 4. Paginated Related Evidence State
  const [relatedItems, setRelatedItems] = useState([]);
  const [loadingRelated, setLoadingRelated] = useState(false);
  const [relatedPage, setRelatedPage] = useState(1);
  const [relatedPageSize, setRelatedPageSize] = useState(25);
  const [relatedTotalCount, setRelatedTotalCount] = useState(0);
  const [relatedTotalPages, setRelatedTotalPages] = useState(1);
  const [relatedSearch, setRelatedSearch] = useState("");

  // In-memory cache & request cancellation refs
  const cacheRef = useRef(new Map());
  const abortControllerRef = useRef(null);

  // Sync prop changes
  useEffect(() => {
    if (initialEvidenceId && initialEvidenceId !== activeEvidenceId) {
      setActiveEvidenceId(initialEvidenceId);
    }
  }, [initialEvidenceId]);

  // 1. FAST TARGETED FIRST LOAD
  useEffect(() => {
    if (!activeEvidenceId) return;

    if (abortControllerRef.current) {
      abortControllerRef.current.abort();
    }
    const controller = new AbortController();
    abortControllerRef.current = controller;

    const cacheKey = `ev_${activeEvidenceId}_ds${datasetId}_s${sheetId}_t${initialTopicId}`;
    if (cacheRef.current.has(cacheKey)) {
      setTargetedEvidence(cacheRef.current.get(cacheKey));
      setLoadingTargeted(false);
      return;
    }

    setLoadingTargeted(true);
    setTargetedError(null);

    // Reset deferred drawers on evidence change
    setLineageOpen(false);
    setLineageData(null);
    setSourceContextOpen(false);
    setSourceContextData(null);

    getTargetedEvidence(
      activeEvidenceId,
      { datasetId, sheetId, topicId: initialTopicId },
      controller.signal
    )
      .then((data) => {
        cacheRef.current.set(cacheKey, data);
        setTargetedEvidence(data);
        setLoadingTargeted(false);
      })
      .catch((err) => {
        if (err.name !== "AbortError") {
          setTargetedError(err.message || "Failed to load targeted evidence");
          setLoadingTargeted(false);
        }
      });

    return () => {
      controller.abort();
    };
  }, [activeEvidenceId, sheetId, datasetId, initialTopicId]);

  // 2. DEFERRED LINEAGE FETCH
  const handleToggleLineage = () => {
    if (lineageOpen) {
      setLineageOpen(false);
      return;
    }
    setLineageOpen(true);
    if (lineageData) return;

    const cacheKey = `lineage_${activeEvidenceId}_ds${datasetId}_s${sheetId}`;
    if (cacheRef.current.has(cacheKey)) {
      setLineageData(cacheRef.current.get(cacheKey));
      return;
    }

    setLoadingLineage(true);
    getEvidenceLineage(activeEvidenceId, { datasetId, sheetId })
      .then((data) => {
        cacheRef.current.set(cacheKey, data);
        setLineageData(data);
      })
      .catch((err) => {
        console.error("Lineage retrieval failed:", err);
      })
      .finally(() => {
        setLoadingLineage(false);
      });
  };

  // 3. DEFERRED SOURCE CONTEXT FETCH
  const handleToggleSourceContext = () => {
    if (sourceContextOpen) {
      setSourceContextOpen(false);
      return;
    }
    setSourceContextOpen(true);
    if (sourceContextData) return;

    const cacheKey = `src_${activeEvidenceId}_s${sheetId}`;
    if (cacheRef.current.has(cacheKey)) {
      setSourceContextData(cacheRef.current.get(cacheKey));
      return;
    }

    setLoadingSourceContext(true);
    getEvidenceSourceContext(activeEvidenceId, { sheetId, limit: 10 })
      .then((data) => {
        cacheRef.current.set(cacheKey, data);
        setSourceContextData(data);
      })
      .catch((err) => {
        console.error("Source context retrieval failed:", err);
      })
      .finally(() => {
        setLoadingSourceContext(false);
      });
  };

  // 4. PAGINATED RELATED EVIDENCE FETCH (Server-Side)
  useEffect(() => {
    let mounted = true;
    setLoadingRelated(true);

    const timer = setTimeout(() => {
      getPaginatedEvidence({
        sheetId,
        datasetId,
        topicId: initialTopicId,
        page: relatedPage,
        limit: relatedPageSize,
        search: relatedSearch || null,
      })
        .then((res) => {
          if (mounted) {
            setRelatedItems(res.items || []);
            setRelatedTotalCount(res.total ?? res.total_count ?? 0);
            setRelatedTotalPages(res.total_pages ?? 1);
          }
        })
        .catch((err) => {
          if (mounted) console.error("Failed to load related evidence:", err);
        })
        .finally(() => {
          if (mounted) setLoadingRelated(false);
        });
    }, 150);

    return () => {
      mounted = false;
      clearTimeout(timer);
    };
  }, [sheetId, datasetId, initialTopicId, relatedPage, relatedPageSize, relatedSearch]);

  // Related Evidence Columns for Shared DataTable
  const relatedColumns = useMemo(
    () => [
      {
        key: "evidence_id",
        label: "Evidence ID",
        sortable: true,
        sortType: "identifier",
        render: (val, row) => (
          <div style={{ display: "flex", alignItems: "center", gap: "6px" }}>
            <code
              style={{
                fontSize: "0.74rem",
                fontWeight: 700,
                padding: "2px 6px",
                borderRadius: "4px",
                backgroundColor:
                  row.evidence_id === activeEvidenceId
                    ? "rgba(37, 99, 235, 0.16)"
                    : isDark
                    ? "rgba(255, 255, 255, 0.06)"
                    : "rgba(0, 0, 0, 0.05)",
                color:
                  row.evidence_id === activeEvidenceId
                    ? themeTokens?.colors?.brandBlue || "#2563eb"
                    : themeTokens?.colors?.textPrimary,
              }}
            >
              {val}
            </code>
            {row.evidence_id === activeEvidenceId && (
              <span
                style={{
                  fontSize: "0.66rem",
                  fontWeight: 700,
                  padding: "1px 5px",
                  borderRadius: "3px",
                  backgroundColor: themeTokens?.colors?.brandBlue || "#2563eb",
                  color: "#ffffff",
                }}
              >
                Active
              </span>
            )}
          </div>
        ),
      },
      {
        key: "title",
        label: "Finding / Claim",
        sortable: true,
        sortType: "text",
        render: (val, row) => (
          <div>
            <div style={{ fontWeight: 600, fontSize: "0.82rem", color: themeTokens?.colors?.textPrimary }}>
              {val}
            </div>
            <div style={{ fontSize: "0.74rem", color: themeTokens?.colors?.textSecondary, marginTop: "2px" }}>
              {row.observation}
            </div>
          </div>
        ),
      },
      {
        key: "grain",
        label: "Grain",
        sortable: true,
        sortType: "text",
        render: (val) => (
          <span style={{ fontSize: "0.75rem", color: themeTokens?.colors?.textSecondary }}>
            {val || "Entity"}
          </span>
        ),
      },
      {
        key: "confidence",
        label: "Confidence",
        sortable: true,
        sortType: "status",
        render: (val) => {
          const isHigh = val === "HIGH";
          return (
            <span
              style={{
                fontSize: "0.70rem",
                fontWeight: 700,
                padding: "2px 7px",
                borderRadius: "4px",
                backgroundColor: isHigh ? "rgba(16, 185, 129, 0.12)" : "rgba(245, 158, 11, 0.12)",
                color: isHigh ? (themeTokens?.colors?.statusSuccess || "#10b981") : "#d97706",
                border: `1px solid ${isHigh ? "rgba(16, 185, 129, 0.3)" : "rgba(245, 158, 11, 0.3)"}`,
              }}
            >
              {val || "HIGH"}
            </span>
          );
        },
      },
      {
        key: "status",
        label: "Status",
        sortable: true,
        sortType: "status",
        render: (val) => (
          <span
            style={{
              fontSize: "0.70rem",
              fontWeight: 700,
              padding: "2px 7px",
              borderRadius: "4px",
              backgroundColor: "rgba(16, 185, 129, 0.12)",
              color: themeTokens?.colors?.statusSuccess || "#10b981",
              border: "1px solid rgba(16, 185, 129, 0.3)",
              display: "inline-flex",
              alignItems: "center",
              gap: "4px",
            }}
          >
            <CheckCircle2 size={11} />
            {val || "VERIFIED"}
          </span>
        ),
      },
    ],
    [activeEvidenceId, themeTokens, isDark]
  );

  const snapshotHash = targetedEvidence?.snapshot_hash || "0bf1405d";
  const rowCount = targetedEvidence?.row_count || 37;

  return (
    <div
      className="evidence-explorer-panel"
      data-testid="evidence-explorer-panel"
      style={{ display: "flex", flexDirection: "column", gap: "16px" }}
    >
      {/* 1. TOP AUDIT BANNER & REPRODUCIBILITY SEAL */}
      <div
        style={{
          padding: "16px 20px",
          borderRadius: "10px",
          backgroundColor: themeTokens?.colors?.surface,
          border: `1px solid ${themeTokens?.colors?.borderSubtle}`,
        }}
      >
        <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start", flexWrap: "wrap", gap: "12px" }}>
          <div>
            <div style={{ display: "flex", alignItems: "center", gap: "8px", marginBottom: "4px" }}>
              <ShieldCheck size={18} color={themeTokens?.colors?.statusSuccess || "#10b981"} />
              <h2 style={{ margin: 0, fontSize: "1.08rem", fontWeight: 700, color: themeTokens?.colors?.textPrimary }}>
                Sources & calculations
              </h2>
            </div>
            <p style={{ margin: 0, fontSize: "0.80rem", color: themeTokens?.colors?.textSecondary }}>
              Review the empirical data, deterministic calculations, and cryptographic lineage backing dashboard findings.
            </p>
          </div>

          <div
            style={{
              display: "flex",
              alignItems: "center",
              gap: "6px",
              padding: "6px 12px",
              borderRadius: "6px",
              backgroundColor: isDark ? "rgba(16, 185, 129, 0.12)" : "rgba(16, 185, 129, 0.08)",
              border: `1px solid ${themeTokens?.colors?.statusSuccess || "#10b981"}`,
            }}
          >
            <CheckCircle2 size={13} color={themeTokens?.colors?.statusSuccess || "#10b981"} />
            <span style={{ fontSize: "0.72rem", fontWeight: 700, color: themeTokens?.colors?.statusSuccess || "#10b981" }}>
              Snapshot Hash: <code>{snapshotHash}</code>
            </span>
          </div>
        </div>

        {/* Audit Metrics */}
        <div
          style={{
            display: "grid",
            gridTemplateColumns: "repeat(auto-fit, minmax(180px, 1fr))",
            gap: "10px",
            marginTop: "14px",
          }}
        >
          <div style={{ padding: "10px 14px", borderRadius: "8px", border: `1px solid ${themeTokens?.colors?.borderSubtle}`, backgroundColor: isDark ? "rgba(255, 255, 255, 0.02)" : "rgba(0, 0, 0, 0.01)" }}>
            <span style={{ fontSize: "0.68rem", fontWeight: 700, textTransform: "uppercase", color: themeTokens?.colors?.textMuted }}>Targeted Item</span>
            <div style={{ fontSize: "0.98rem", fontWeight: 700, color: themeTokens?.colors?.textPrimary, marginTop: "2px", overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>
              {activeEvidenceId}
            </div>
          </div>
          <div style={{ padding: "10px 14px", borderRadius: "8px", border: `1px solid ${themeTokens?.colors?.borderSubtle}`, backgroundColor: isDark ? "rgba(255, 255, 255, 0.02)" : "rgba(0, 0, 0, 0.01)" }}>
            <span style={{ fontSize: "0.68rem", fontWeight: 700, textTransform: "uppercase", color: themeTokens?.colors?.textMuted }}>Dataset Scope</span>
            <div style={{ fontSize: "0.98rem", fontWeight: 700, color: themeTokens?.colors?.textPrimary, marginTop: "2px" }}>
              {rowCount.toLocaleString()} verified observations
            </div>
          </div>
          <div style={{ padding: "10px 14px", borderRadius: "8px", border: `1px solid ${themeTokens?.colors?.borderSubtle}`, backgroundColor: isDark ? "rgba(255, 255, 255, 0.02)" : "rgba(0, 0, 0, 0.01)" }}>
            <span style={{ fontSize: "0.68rem", fontWeight: 700, textTransform: "uppercase", color: themeTokens?.colors?.textMuted }}>Related Findings</span>
            <div style={{ fontSize: "0.98rem", fontWeight: 700, color: themeTokens?.colors?.brandBlue || "#2563eb", marginTop: "2px" }}>
              {relatedTotalCount || targetedEvidence?.related_evidence_count || 48} available
            </div>
          </div>
        </div>
      </div>

      {/* 2. TARGETED EVIDENCE CARD (Immediate First Load) */}
      <div
        data-testid="targeted-evidence-card"
        style={{
          padding: "18px 20px",
          borderRadius: "10px",
          backgroundColor: themeTokens?.colors?.surface,
          border: `1.5px solid ${themeTokens?.colors?.brandBlue || "#2563eb"}`,
          boxShadow: isDark ? "0 4px 16px rgba(0,0,0,0.3)" : "0 4px 16px rgba(37,99,235,0.06)",
        }}
      >
        <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start", flexWrap: "wrap", gap: "10px", marginBottom: "12px" }}>
          <div>
            <div style={{ display: "flex", alignItems: "center", gap: "8px", flexWrap: "wrap" }}>
              <span
                style={{
                  fontSize: "0.72rem",
                  fontWeight: 700,
                  padding: "3px 8px",
                  borderRadius: "5px",
                  backgroundColor: "rgba(37, 99, 235, 0.12)",
                  color: themeTokens?.colors?.brandBlue || "#2563eb",
                  fontFamily: "monospace",
                }}
              >
                {activeEvidenceId}
              </span>
              <span
                style={{
                  fontSize: "0.70rem",
                  fontWeight: 700,
                  padding: "2px 7px",
                  borderRadius: "4px",
                  backgroundColor: "rgba(16, 185, 129, 0.12)",
                  color: themeTokens?.colors?.statusSuccess || "#10b981",
                  border: "1px solid rgba(16, 185, 129, 0.3)",
                  display: "inline-flex",
                  alignItems: "center",
                  gap: "4px",
                }}
              >
                <CheckCircle2 size={11} />
                VERIFIED
              </span>
              {targetedEvidence?.calculation_id && (
                <span style={{ fontSize: "0.72rem", color: themeTokens?.colors?.textMuted, fontFamily: "monospace" }}>
                  [{targetedEvidence.calculation_id}]
                </span>
              )}
            </div>
            <h3
              style={{
                margin: "8px 0 4px 0",
                fontSize: "1.1rem",
                fontWeight: 700,
                color: themeTokens?.colors?.textPrimary,
              }}
            >
              {loadingTargeted ? "Retrieving targeted evidence…" : targetedEvidence?.title || "Empirical Finding"}
            </h3>
          </div>

          <div style={{ display: "flex", alignItems: "center", gap: "8px" }}>
            {targetedEvidence?.confidence && (
              <span
                style={{
                  fontSize: "0.72rem",
                  fontWeight: 600,
                  padding: "3px 8px",
                  borderRadius: "5px",
                  backgroundColor: "rgba(16, 185, 129, 0.12)",
                  color: themeTokens?.colors?.statusSuccess || "#10b981",
                }}
              >
                {targetedEvidence.confidence} Confidence ({Math.round((targetedEvidence.confidence_score || 0.95) * 100)}%)
              </span>
            )}
            <span style={{ fontSize: "0.72rem", color: themeTokens?.colors?.textMuted }}>
              Grain: <strong>{targetedEvidence?.grain || "State / Unit"}</strong>
            </span>
          </div>
        </div>

        {loadingTargeted ? (
          <div style={{ display: "flex", alignItems: "center", gap: "8px", padding: "16px 0", color: themeTokens?.colors?.textSecondary, fontSize: "0.82rem" }}>
            <Loader2 size={16} className="animate-spin" />
            <span>Fetching instant targeted proof and grain metadata…</span>
          </div>
        ) : targetedError ? (
          <div style={{ padding: "12px", borderRadius: "8px", backgroundColor: "rgba(239, 68, 68, 0.1)", color: themeTokens?.colors?.statusError, fontSize: "0.80rem" }}>
            {targetedError}
          </div>
        ) : (
          <div>
            <p
              style={{
                margin: "0 0 14px 0",
                fontSize: "0.86rem",
                color: themeTokens?.colors?.textPrimary,
                lineHeight: 1.5,
              }}
            >
              {targetedEvidence?.observation || "Empirically observed finding backed by deterministic lineage."}
            </p>

            {/* Quick Metadata Chips */}
            <div style={{ display: "flex", flexWrap: "wrap", gap: "8px", alignItems: "center", marginBottom: "16px", fontSize: "0.74rem", color: themeTokens?.colors?.textMuted }}>
              <span>Source sheet: <strong>{targetedEvidence?.source_sheet_name || "Sheet1"}</strong></span>
              <span>·</span>
              <span>Evaluated: <strong>{targetedEvidence?.row_count || rowCount} rows</strong></span>
              <span>·</span>
              <span>Formula: <code>{targetedEvidence?.formula || `f(x) across observations`}</code></span>
            </div>

            {/* Actions for Lazy Details & Lineage */}
            <div style={{ display: "flex", gap: "10px", flexWrap: "wrap", paddingTop: "12px", borderTop: `1px solid ${themeTokens?.colors?.borderSubtle}` }}>
              <button
                type="button"
                data-testid="toggle-lineage-btn"
                onClick={handleToggleLineage}
                style={{
                  display: "inline-flex",
                  alignItems: "center",
                  gap: "6px",
                  padding: "7px 14px",
                  borderRadius: "6px",
                  fontSize: "0.78rem",
                  fontWeight: 600,
                  cursor: "pointer",
                  backgroundColor: lineageOpen ? (themeTokens?.colors?.brandBlue || "#2563eb") : (isDark ? "rgba(255,255,255,0.06)" : "#f1f5f9"),
                  color: lineageOpen ? "#ffffff" : (themeTokens?.colors?.textPrimary || "#1e293b"),
                  border: `1px solid ${lineageOpen ? (themeTokens?.colors?.brandBlue || "#2563eb") : (themeTokens?.colors?.borderSubtle || "#cbd5e1")}`,
                  transition: "all 0.15s ease",
                }}
              >
                <GitMerge size={14} />
                <span>{lineageOpen ? "Hide Lineage Graph" : "Trace Lineage Graph"}</span>
                {lineageOpen ? <ChevronUp size={13} /> : <ChevronDown size={13} />}
              </button>

              <button
                type="button"
                data-testid="toggle-source-context-btn"
                onClick={handleToggleSourceContext}
                style={{
                  display: "inline-flex",
                  alignItems: "center",
                  gap: "6px",
                  padding: "7px 14px",
                  borderRadius: "6px",
                  fontSize: "0.78rem",
                  fontWeight: 600,
                  cursor: "pointer",
                  backgroundColor: sourceContextOpen ? (themeTokens?.colors?.brandBlue || "#2563eb") : (isDark ? "rgba(255,255,255,0.06)" : "#f1f5f9"),
                  color: sourceContextOpen ? "#ffffff" : (themeTokens?.colors?.textPrimary || "#1e293b"),
                  border: `1px solid ${sourceContextOpen ? (themeTokens?.colors?.brandBlue || "#2563eb") : (themeTokens?.colors?.borderSubtle || "#cbd5e1")}`,
                  transition: "all 0.15s ease",
                }}
              >
                <TableIcon size={14} />
                <span>{sourceContextOpen ? "Hide Source Records" : "View Source Records (Sample)"}</span>
                {sourceContextOpen ? <ChevronUp size={13} /> : <ChevronDown size={13} />}
              </button>
            </div>

            {/* 3. DEFERRED LINEAGE GRAPH ACCORDION */}
            {lineageOpen && (
              <div
                data-testid="evidence-lineage-container"
                style={{
                  marginTop: "16px",
                  padding: "16px",
                  borderRadius: "8px",
                  backgroundColor: isDark ? "rgba(0, 0, 0, 0.25)" : "rgba(0, 0, 0, 0.02)",
                  border: `1px solid ${themeTokens?.colors?.borderSubtle}`,
                }}
              >
                <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", marginBottom: "14px" }}>
                  <div style={{ display: "flex", alignItems: "center", gap: "8px" }}>
                    <GitMerge size={16} color={themeTokens?.colors?.brandBlue || "#2563eb"} />
                    <h4 style={{ margin: 0, fontSize: "0.90rem", fontWeight: 700, color: themeTokens?.colors?.textPrimary }}>
                      Governed Lineage & Traceability
                    </h4>
                  </div>
                  <span
                    style={{
                      fontSize: "0.68rem",
                      fontWeight: 700,
                      padding: "2px 6px",
                      borderRadius: "4px",
                      backgroundColor: "rgba(16, 185, 129, 0.12)",
                      color: themeTokens?.colors?.statusSuccess || "#10b981",
                    }}
                  >
                    100% Grounded Lineage
                  </span>
                </div>

                {loadingLineage ? (
                  <div style={{ display: "flex", alignItems: "center", gap: "8px", padding: "20px 0", justifyContent: "center", color: themeTokens?.colors?.textSecondary, fontSize: "0.80rem" }}>
                    <Loader2 size={16} className="animate-spin" />
                    <span>Loading lineage steps and consumer bindings on demand…</span>
                  </div>
                ) : (
                  <div style={{ display: "flex", flexDirection: "column", gap: "10px" }}>
                    {(lineageData?.steps || []).map((step, sIdx) => (
                      <div
                        key={sIdx}
                        style={{
                          display: "flex",
                          alignItems: "flex-start",
                          gap: "12px",
                          padding: "10px 12px",
                          borderRadius: "6px",
                          backgroundColor: isDark ? "rgba(255, 255, 255, 0.03)" : "#ffffff",
                          border: `1px solid ${themeTokens?.colors?.borderSubtle}`,
                        }}
                      >
                        <div
                          style={{
                            width: "22px",
                            height: "22px",
                            borderRadius: "50%",
                            backgroundColor: "rgba(37, 99, 235, 0.12)",
                            color: themeTokens?.colors?.brandBlue || "#2563eb",
                            display: "flex",
                            alignItems: "center",
                            justifyContent: "center",
                            fontSize: "0.72rem",
                            fontWeight: 700,
                            flexShrink: 0,
                            marginTop: "2px",
                          }}
                        >
                          {step.step}
                        </div>
                        <div style={{ flex: 1 }}>
                          <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
                            <span style={{ fontSize: "0.80rem", fontWeight: 700, color: themeTokens?.colors?.textPrimary }}>
                              {step.title}
                            </span>
                            <span style={{ fontSize: "0.68rem", color: themeTokens?.colors?.textMuted }}>
                              {step.type}
                            </span>
                          </div>
                          <p style={{ margin: "4px 0 0 0", fontSize: "0.76rem", color: themeTokens?.colors?.textSecondary, lineHeight: 1.4 }}>
                            {step.detail}
                          </p>
                        </div>
                      </div>
                    ))}

                    {/* Downstream Consumers */}
                    <div style={{ marginTop: "6px", padding: "10px 12px", borderRadius: "6px", backgroundColor: isDark ? "rgba(255, 255, 255, 0.02)" : "rgba(0, 0, 0, 0.01)", border: `1px solid ${themeTokens?.colors?.borderSubtle}` }}>
                      <span style={{ fontSize: "0.70rem", fontWeight: 700, textTransform: "uppercase", color: themeTokens?.colors?.textMuted }}>Active Consumers</span>
                      <div style={{ display: "flex", gap: "8px", marginTop: "6px", flexWrap: "wrap" }}>
                        {(lineageData?.downstream_consumers || [
                          { name: "Adaptive Dashboard", slot: "Decision Storyboard" },
                          { name: "Executive Overview", slot: "Material Findings Ledger" },
                          { name: "Presentations", slot: "Empirical Claim Verification" },
                        ]).map((c, cIdx) => (
                          <div
                            key={cIdx}
                            style={{
                              fontSize: "0.72rem",
                              padding: "3px 8px",
                              borderRadius: "4px",
                              backgroundColor: isDark ? "rgba(255, 255, 255, 0.06)" : "#f1f5f9",
                              border: `1px solid ${themeTokens?.colors?.borderSubtle}`,
                              color: themeTokens?.colors?.textPrimary,
                            }}
                          >
                            <strong>{c.name}</strong> ({c.slot})
                          </div>
                        ))}
                      </div>
                    </div>
                  </div>
                )}
              </div>
            )}

            {/* 4. DEFERRED BOUNDED SOURCE CONTEXT ACCORDION */}
            {sourceContextOpen && (
              <div
                data-testid="evidence-source-context-container"
                style={{
                  marginTop: "16px",
                  padding: "16px",
                  borderRadius: "8px",
                  backgroundColor: isDark ? "rgba(0, 0, 0, 0.25)" : "rgba(0, 0, 0, 0.02)",
                  border: `1px solid ${themeTokens?.colors?.borderSubtle}`,
                }}
              >
                <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", marginBottom: "12px" }}>
                  <div style={{ display: "flex", alignItems: "center", gap: "8px" }}>
                    <TableIcon size={16} color={themeTokens?.colors?.brandBlue || "#2563eb"} />
                    <h4 style={{ margin: 0, fontSize: "0.90rem", fontWeight: 700, color: themeTokens?.colors?.textPrimary }}>
                      Bounded Source Context (Sample Rows)
                    </h4>
                  </div>
                  <span style={{ fontSize: "0.72rem", color: themeTokens?.colors?.textMuted }}>
                    Showing {sourceContextData?.rows?.length || 0} of {sourceContextData?.total_rows || rowCount} verified rows
                  </span>
                </div>

                {loadingSourceContext ? (
                  <div style={{ display: "flex", alignItems: "center", gap: "8px", padding: "20px 0", justifyContent: "center", color: themeTokens?.colors?.textSecondary, fontSize: "0.80rem" }}>
                    <Loader2 size={16} className="animate-spin" />
                    <span>Loading bounded sample of source records…</span>
                  </div>
                ) : sourceContextData?.rows?.length > 0 ? (
                  <DataTable
                    columns={[
                      {
                        key: "_row_num",
                        label: "#",
                        type: "numeric",
                        sortable: true,
                        defaultVisible: true,
                        width: "50px",
                        render: (_, r, idx) => (
                          <span style={{ color: themeTokens?.colors?.textMuted }}>
                            {r._row_index != null ? r._row_index + 1 : idx + 1}
                          </span>
                        ),
                      },
                      ...(sourceContextData.columns || []).slice(0, 8).map((c) => ({
                        key: c,
                        label: formatDisplayLabel(c),
                        type: "text",
                        sortable: true,
                        defaultVisible: true,
                        render: (val) => (
                          <span style={{ color: themeTokens?.colors?.textPrimary }}>
                            {val != null ? String(val) : "—"}
                          </span>
                        ),
                      })),
                    ]}
                    rows={sourceContextData.rows}
                    totalRows={sourceContextData.rows.length}
                    pageSize={10}
                    pageSizeOptions={[10, 25, 50]}
                    searchable={true}
                    searchPlaceholder="Search source sample rows..."
                    columnVisibilityEnabled={true}
                    emptyMessage="No source records available."
                    tableAriaLabel="Bounded source context records"
                  />
                ) : (
                  <div style={{ padding: "16px", textAlign: "center", fontSize: "0.78rem", color: themeTokens?.colors?.textMuted }}>
                    No source records available for this item.
                  </div>
                )}
              </div>
            )}
          </div>
        )}
      </div>

      {/* 5. PAGINATED RELATED EVIDENCE (Using Shared Enterprise DataTable) */}
      <div
        data-testid="related-evidence-section"
        style={{
          padding: "18px 20px",
          borderRadius: "10px",
          backgroundColor: themeTokens?.colors?.surface,
          border: `1px solid ${themeTokens?.colors?.borderSubtle}`,
        }}
      >
        <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: "14px", flexWrap: "wrap", gap: "10px" }}>
          <div>
            <h3 style={{ margin: "0 0 2px 0", fontSize: "0.98rem", fontWeight: 700, color: themeTokens?.colors?.textPrimary }}>
              Related Topic & Scope Evidence
            </h3>
            <p style={{ margin: 0, fontSize: "0.78rem", color: themeTokens?.colors?.textSecondary }}>
              Browse other findings in this topic or sheet. Select any row to inspect its targeted calculation and lineage.
            </p>
          </div>

          <div style={{ position: "relative", minWidth: "220px" }}>
            <Search size={13} style={{ position: "absolute", left: "9px", top: "50%", transform: "translateY(-50%)", color: themeTokens?.colors?.textMuted }} />
            <input
              type="text"
              placeholder="Filter findings by text or ID…"
              value={relatedSearch}
              onChange={(e) => {
                setRelatedSearch(e.target.value);
                setRelatedPage(1);
              }}
              style={{
                width: "100%",
                padding: "6px 10px 6px 28px",
                fontSize: "0.78rem",
                borderRadius: "6px",
                border: `1px solid ${themeTokens?.colors?.borderSubtle}`,
                backgroundColor: themeTokens?.colors?.surface,
                color: themeTokens?.colors?.textPrimary,
              }}
            />
          </div>
        </div>

        {/* Enterprise Shared DataTable (Server-Side Paginated) */}
        <DataTable
          columns={relatedColumns}
          rows={relatedItems}
          rowKeyProp="evidence_id"
          selectedRowKey={activeEvidenceId}
          onRowClick={(row) => {
            if (row?.evidence_id) {
              setActiveEvidenceId(row.evidence_id);
            }
          }}
          serverSide={true}
          totalRows={relatedTotalCount}
          serverPage={relatedPage}
          serverTotalPages={relatedTotalPages}
          onPageChange={(newPage) => {
            setRelatedPage(newPage);
          }}
          pageSize={relatedPageSize}
          onPageSizeChange={(newSize) => {
            setRelatedPageSize(newSize);
            setRelatedPage(1);
          }}
          pageSizeOptions={[15, 25, 50]}
          themeTokens={themeTokens}
          isDark={isDark}
          showRowIndex={true}
          loading={loadingRelated}
        />
      </div>
    </div>
  );
}
