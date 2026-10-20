import React, { useState, useEffect } from "react";
import { getExplorerSemantics } from "../../../api/client";
import ColumnDetailDrawer from "./ColumnDetailDrawer";
import {
  Sparkles,
  Layers,
  Key,
  MapPin,
  CheckCircle2,
  AlertTriangle,
  HelpCircle,
  Eye,
  Shield,
  Tag,
  AlertCircle,
} from "lucide-react";

export default function SemanticsMode({
  datasetId,
  sheets = [],
  selectedSheetId,
  onSelectSheet,
  themeTokens,
  isDark = false,
}) {
  const [activeSheet, setActiveSheet] = useState(() => selectedSheetId || (sheets[0]?.sheet_id || sheets[0]?.name || ""));
  const [semanticsData, setSemanticsData] = useState(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);
  const [selectedColumn, setSelectedColumn] = useState(null);

  useEffect(() => {
    if (selectedSheetId && sheets.some(s => (s.sheet_id || s.name) === selectedSheetId)) {
      setActiveSheet(selectedSheetId);
    } else if (sheets.length > 0 && !sheets.some(s => (s.sheet_id || s.name) === activeSheet)) {
      setActiveSheet(sheets[0].sheet_id || sheets[0].name);
    }
  }, [selectedSheetId, sheets, activeSheet]);

  useEffect(() => {
    if (!datasetId) return;
    let isCancelled = false;

    async function loadSemantics() {
      setLoading(true);
      setError(null);
      try {
        const res = await getExplorerSemantics(datasetId, activeSheet || null);
        if (!isCancelled) {
          setSemanticsData(res);
        }
      } catch (err) {
        if (!isCancelled) {
          setError(err.message || "Failed to load semantics");
        }
      } finally {
        if (!isCancelled) {
          setLoading(false);
        }
      }
    }

    loadSemantics();
    return () => {
      isCancelled = true;
    };
  }, [datasetId, activeSheet]);

  const handleSheetChange = (sheetId) => {
    setActiveSheet(sheetId);
    if (onSelectSheet) onSelectSheet(sheetId);
  };

  const bgCard = isDark ? "#1e293b" : "#ffffff";
  const borderCol = isDark ? "#334155" : "#e2e8f0";
  const textPrimary = isDark ? "#f8fafc" : "#0f172a";
  const textSecondary = isDark ? "#94a3b8" : "#64748b";
  const bgSubtle = isDark ? "#0f172a" : "#f8fafc";

  const entity = semanticsData?.entities?.[0];
  const grain = semanticsData?.grains?.[0];
  const keys = semanticsData?.candidate_keys || semanticsData?.keys || [];
  const geoResolutions = semanticsData?.geo_resolutions || [];
  const columns = semanticsData?.columns || [];

  return (
    <div className="sdr-semantics-mode-container" style={{ display: "flex", flexDirection: "column", gap: "16px" }}>
      {/* Header & Sheet Selection */}
      <div
        style={{
          background: isDark ? "rgba(30, 41, 59, 0.7)" : "#ffffff",
          border: `1px solid ${borderCol}`,
          borderRadius: "10px",
          padding: "16px",
          display: "flex",
          flexDirection: "column",
          gap: "12px",
        }}
      >
        <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", flexWrap: "wrap", gap: "10px" }}>
          <div style={{ display: "flex", alignItems: "center", gap: "8px" }}>
            <Sparkles size={18} color="#2563eb" />
            <h2 style={{ margin: 0, fontSize: "1.1rem", fontWeight: 700, color: textPrimary }}>
              Semantic Refinery Models (SDR-1 through SDR-4G)
            </h2>
          </div>
          <div style={{ display: "flex", alignItems: "center", gap: "8px" }}>
            <span
              style={{
                fontSize: "0.75rem",
                fontWeight: 600,
                padding: "3px 8px",
                borderRadius: "6px",
                background: "rgba(37, 99, 235, 0.12)",
                color: "#2563eb",
                border: "1px solid rgba(37, 99, 235, 0.3)",
              }}
            >
              Source / Observed
            </span>
            <span
              style={{
                fontSize: "0.75rem",
                fontWeight: 600,
                padding: "3px 8px",
                borderRadius: "6px",
                background: "rgba(168, 85, 247, 0.12)",
                color: "#a855f7",
                border: "1px solid rgba(168, 85, 247, 0.3)",
              }}
            >
              Derived / Enriched
            </span>
          </div>
        </div>

        {/* Sheet Selector Pills */}
        <div style={{ display: "flex", alignItems: "center", gap: "6px", overflowX: "auto", paddingTop: "4px" }}>
          {sheets.map((s) => {
            const sid = s.sheet_id || s.name;
            const isSelected = sid === activeSheet;
            return (
              <button
                key={sid}
                type="button"
                onClick={() => handleSheetChange(sid)}
                style={{
                  padding: "6px 12px",
                  fontSize: "0.8rem",
                  fontWeight: isSelected ? 700 : 500,
                  borderRadius: "8px",
                  border: isSelected ? "1px solid #2563eb" : `1px solid ${borderCol}`,
                  background: isSelected ? (isDark ? "rgba(37, 99, 235, 0.2)" : "rgba(37, 99, 235, 0.08)") : "transparent",
                  color: isSelected ? "#2563eb" : textSecondary,
                  cursor: "pointer",
                  whiteSpace: "nowrap",
                  transition: "all 0.15s ease",
                }}
              >
                {s.display_name || s.name}
              </button>
            );
          })}
        </div>
      </div>

      {loading ? (
        <div style={{ padding: "40px", textAlign: "center", color: textSecondary, fontSize: "0.9rem" }}>
          Loading semantic intelligence…
        </div>
      ) : error ? (
        <div
          style={{
            padding: "16px",
            background: "rgba(239, 68, 68, 0.1)",
            border: "1px solid rgba(239, 68, 68, 0.3)",
            borderRadius: "8px",
            color: "#ef4444",
            display: "flex",
            alignItems: "center",
            gap: "8px",
            fontSize: "0.85rem",
          }}
        >
          <AlertCircle size={16} />
          <span>{error}</span>
        </div>
      ) : (
        <>
          {/* Table-Level Semantic Overview Cards */}
          <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(280px, 1fr))", gap: "12px" }}>
            {/* Entity Hypothesis Card */}
            <div style={{ background: bgCard, border: `1px solid ${borderCol}`, borderRadius: "10px", padding: "14px", display: "flex", flexDirection: "column", gap: "8px" }}>
              <div style={{ display: "flex", alignItems: "center", gap: "6px", color: textSecondary, fontSize: "0.78rem", fontWeight: 600 }}>
                <Layers size={14} color="#2563eb" />
                <span>Entity Hypothesis</span>
              </div>
              {entity ? (
                <div>
                  <div style={{ fontSize: "1.05rem", fontWeight: 700, color: textPrimary }}>
                    {entity.name}
                  </div>
                  <div style={{ fontSize: "0.78rem", color: textSecondary, marginTop: "2px" }}>
                    Status: <span style={{ fontWeight: 600, color: "#10b981" }}>{entity.status}</span> · Confidence: {entity.confidence}
                  </div>
                  {entity.evidence && (
                    <div style={{ fontSize: "0.75rem", color: textSecondary, marginTop: "4px" }}>
                      Evidence: {entity.evidence}
                    </div>
                  )}
                </div>
              ) : (
                <div style={{ fontSize: "0.85rem", color: textSecondary }}>No entity hypothesis established</div>
              )}
            </div>

            {/* Row Grain Card */}
            <div style={{ background: bgCard, border: `1px solid ${borderCol}`, borderRadius: "10px", padding: "14px", display: "flex", flexDirection: "column", gap: "8px" }}>
              <div style={{ display: "flex", alignItems: "center", gap: "6px", color: textSecondary, fontSize: "0.78rem", fontWeight: 600 }}>
                <Tag size={14} color="#10b981" />
                <span>Discovered Row Grain</span>
              </div>
              {grain ? (
                <div>
                  <div style={{ fontSize: "1.05rem", fontWeight: 700, color: textPrimary }}>
                    {grain.expression}
                  </div>
                  <div style={{ fontSize: "0.78rem", color: "#2563eb", fontWeight: 500, marginTop: "4px" }}>
                    {grain.explanation}
                  </div>
                  <div style={{ fontSize: "0.74rem", color: textSecondary, marginTop: "2px" }}>
                    Status: {grain.status} · Width: {grain.width} column(s)
                  </div>
                </div>
              ) : (
                <div style={{ fontSize: "0.85rem", color: textSecondary }}>Row grain unverified</div>
              )}
            </div>

            {/* Candidate Key Card (or NO-KEY STATE) */}
            <div style={{ background: bgCard, border: `1px solid ${borderCol}`, borderRadius: "10px", padding: "14px", display: "flex", flexDirection: "column", gap: "8px" }}>
              <div style={{ display: "flex", alignItems: "center", gap: "6px", color: textSecondary, fontSize: "0.78rem", fontWeight: 600 }}>
                <Key size={14} color={keys.length > 0 ? "#f59e0b" : "#94a3b8"} />
                <span>Candidate Key Intelligence</span>
              </div>
              {keys.length > 0 ? (
                <div>
                  <div style={{ fontSize: "0.95rem", fontWeight: 700, color: textPrimary }}>
                    [{keys[0].columns.join(", ")}]
                  </div>
                  <div style={{ fontSize: "0.78rem", color: textSecondary, marginTop: "2px" }}>
                    {keys[0].status} · {keys[0].unique_ratio_pct}% unique · {keys[0].null_ratio_pct}% nulls
                  </div>
                  <div style={{ fontSize: "0.74rem", color: "#10b981", marginTop: "4px" }}>
                    Authority: {keys[0].authority} ({keys[0].confidence})
                  </div>
                </div>
              ) : (
                <div>
                  <div
                    style={{
                      display: "inline-flex",
                      alignItems: "center",
                      gap: "5px",
                      padding: "4px 8px",
                      borderRadius: "6px",
                      background: "rgba(245, 158, 11, 0.12)",
                      border: "1px solid rgba(245, 158, 11, 0.3)",
                      color: "#f59e0b",
                      fontSize: "0.78rem",
                      fontWeight: 600,
                    }}
                  >
                    <AlertTriangle size={13} />
                    Valid No-Key State
                  </div>
                  <div style={{ fontSize: "0.75rem", color: textSecondary, marginTop: "6px" }}>
                    Multi-attribute observations / non-unique rows. Direct entity joins blocked.
                  </div>
                </div>
              )}
            </div>
          </div>

          {/* Geographic Semantic Resolutions (if present) */}
          {geoResolutions.length > 0 && (
            <div style={{ background: bgCard, border: `1px solid ${borderCol}`, borderRadius: "10px", padding: "14px" }}>
              <div style={{ display: "flex", alignItems: "center", gap: "6px", color: textSecondary, fontSize: "0.78rem", fontWeight: 600, marginBottom: "10px" }}>
                <MapPin size={14} color="#6366f1" />
                <span>Geographic Semantic Resolutions (GEO-1)</span>
              </div>
              <div style={{ display: "flex", flexWrap: "wrap", gap: "8px" }}>
                {geoResolutions.map((geo, idx) => (
                  <div
                    key={idx}
                    style={{
                      padding: "6px 12px",
                      borderRadius: "8px",
                      border: `1px solid ${borderCol}`,
                      background: bgSubtle,
                      fontSize: "0.78rem",
                      display: "flex",
                      alignItems: "center",
                      gap: "6px",
                    }}
                  >
                    <span style={{ fontWeight: 600, color: textPrimary }}>"{geo.input_term}"</span>
                    <span>→</span>
                    {geo.is_ambiguous ? (
                      <span style={{ color: "#f59e0b", fontWeight: 600, display: "inline-flex", alignItems: "center", gap: "4px" }}>
                        <AlertTriangle size={12} />
                        Ambiguous ({geo.candidates_count} matches)
                      </span>
                    ) : (
                      <span style={{ color: "#10b981", fontWeight: 600, display: "inline-flex", alignItems: "center", gap: "4px" }}>
                        <CheckCircle2 size={12} />
                        {geo.resolved_canonical_name} ({geo.entity_type}, {geo.country_code})
                      </span>
                    )}
                  </div>
                ))}
              </div>
            </div>
          )}

          {/* Column Semantic Profiles Table */}
          <div style={{ background: bgCard, border: `1px solid ${borderCol}`, borderRadius: "10px", overflow: "hidden" }}>
            <div style={{ padding: "14px 16px", borderBottom: `1px solid ${borderCol}`, display: "flex", justifyContent: "space-between", alignItems: "center" }}>
              <h3 style={{ margin: 0, fontSize: "0.95rem", fontWeight: 700, color: textPrimary }}>
                Semantic Column Catalog ({columns.length} columns)
              </h3>
              <span style={{ fontSize: "0.75rem", color: textSecondary }}>
                Click any row or "Inspect" to open the detail drawer
              </span>
            </div>

            <div style={{ overflowX: "auto" }}>
              <table style={{ width: "100%", borderCollapse: "collapse", fontSize: "0.82rem", textAlign: "left" }}>
                <thead>
                  <tr style={{ background: isDark ? "#0f172a" : "#f8fafc", borderBottom: `2px solid ${borderCol}` }}>
                    <th style={{ padding: "10px 12px", color: textSecondary, fontWeight: 700 }}>Provenance</th>
                    <th style={{ padding: "10px 12px", color: textPrimary, fontWeight: 700 }}>Column Name</th>
                    <th style={{ padding: "10px 12px", color: textPrimary, fontWeight: 700 }}>Semantic Role</th>
                    <th style={{ padding: "10px 12px", color: textPrimary, fontWeight: 700 }}>Data Type</th>
                    <th style={{ padding: "10px 12px", color: textPrimary, fontWeight: 700 }}>Concept</th>
                    <th style={{ padding: "10px 12px", color: textPrimary, fontWeight: 700 }}>Entity</th>
                    <th style={{ padding: "10px 12px", color: textPrimary, fontWeight: 700 }}>Privacy</th>
                    <th style={{ padding: "10px 12px", color: textPrimary, fontWeight: 700 }}>Confidence</th>
                    <th style={{ padding: "10px 12px", color: textSecondary, fontWeight: 700, textAlign: "right" }}>Action</th>
                  </tr>
                </thead>
                <tbody>
                  {columns.map((col, idx) => {
                    const isEnriched = col.provenance_type === "DERIVED_ENRICHMENT" || col.provenance_type === "DERIVED_RELATIONAL";
                    return (
                      <tr
                        key={col.column_id || idx}
                        onClick={() => setSelectedColumn(col)}
                        style={{
                          borderBottom: `1px solid ${borderCol}`,
                          background: idx % 2 === 1 ? (isDark ? "rgba(255,255,255,0.02)" : "rgba(0,0,0,0.015)") : "transparent",
                          cursor: "pointer",
                        }}
                      >
                        <td style={{ padding: "10px 12px" }}>
                          <span
                            style={{
                              display: "inline-block",
                              padding: "2px 6px",
                              borderRadius: "4px",
                              fontSize: "0.7rem",
                              fontWeight: 700,
                              background: isEnriched ? "rgba(168, 85, 247, 0.12)" : "rgba(37, 99, 235, 0.12)",
                              color: isEnriched ? "#a855f7" : "#2563eb",
                            }}
                          >
                            {isEnriched ? "Derived" : "Source"}
                          </span>
                        </td>
                        <td style={{ padding: "10px 12px", fontWeight: 600, color: textPrimary }}>
                          {col.display_name || col.column_id}
                        </td>
                        <td style={{ padding: "10px 12px", color: textSecondary }}>{col.role}</td>
                        <td style={{ padding: "10px 12px", color: textSecondary }}>{col.data_type}</td>
                        <td style={{ padding: "10px 12px", color: textSecondary }}>{col.concept}</td>
                        <td style={{ padding: "10px 12px", color: textSecondary }}>{col.entity}</td>
                        <td style={{ padding: "10px 12px" }}>
                          <span
                            style={{
                              padding: "2px 6px",
                              borderRadius: "4px",
                              fontSize: "0.72rem",
                              fontWeight: 600,
                              background: col.privacy_raw === "DIRECT_IDENTIFIER" || col.privacy_raw === "SENSITIVE_ATTRIBUTE" ? "rgba(245, 158, 11, 0.12)" : "transparent",
                              color: col.privacy_raw === "DIRECT_IDENTIFIER" || col.privacy_raw === "SENSITIVE_ATTRIBUTE" ? "#f59e0b" : textSecondary,
                            }}
                          >
                            {col.privacy}
                          </span>
                        </td>
                        <td style={{ padding: "10px 12px" }}>
                          <span style={{ color: col.confidence === "High" ? "#10b981" : "#f59e0b", fontWeight: 600 }}>
                            {col.confidence}
                          </span>
                        </td>
                        <td style={{ padding: "10px 12px", textAlign: "right" }}>
                          <button
                            type="button"
                            onClick={(e) => {
                              e.stopPropagation();
                              setSelectedColumn(col);
                            }}
                            style={{
                              padding: "4px 8px",
                              fontSize: "0.75rem",
                              fontWeight: 600,
                              borderRadius: "6px",
                              border: `1px solid ${borderCol}`,
                              background: bgSubtle,
                              color: "#2563eb",
                              cursor: "pointer",
                              display: "inline-flex",
                              alignItems: "center",
                              gap: "4px",
                            }}
                          >
                            <Eye size={12} />
                            Inspect
                          </button>
                        </td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </div>
          </div>
        </>
      )}

      {/* Progressive Disclosure Column Detail Drawer */}
      {selectedColumn && (
        <ColumnDetailDrawer
          column={selectedColumn}
          onClose={() => setSelectedColumn(null)}
          isDark={isDark}
        />
      )}
    </div>
  );
}
