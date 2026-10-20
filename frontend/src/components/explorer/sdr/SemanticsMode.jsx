import React, { useState, useEffect, useMemo } from "react";
import { getExplorerSemantics } from "../../../api/client";
import ColumnDetailDrawer from "./ColumnDetailDrawer";
import StatusBadge from "../common/StatusBadge";
import {
  Sparkles,
  Layers,
  Key,
  MapPin,
  Search,
  Eye,
  Filter,
  AlertCircle,
  FileSpreadsheet,
  Table,
} from "lucide-react";

/**
 * HighView Data Explorer — Semantic Model
 * "Cards summarize. Tables compare. Drawers explain."
 * Replaces card walls with 4 structured data tables:
 * 1. Entities Table
 * 2. Semantic Columns Table
 * 3. Candidate Keys Table
 * 4. Reference Enrichments Table
 */
export default function SemanticsMode({
  datasetId,
  sheets = [],
  selectedSheetId,
  onSelectSheet,
  themeTokens,
  isDark = false,
}) {
  const [activeSheet, setActiveSheet] = useState(() => selectedSheetId || "");
  const [semanticsData, setSemanticsData] = useState(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);
  const [selectedColumn, setSelectedColumn] = useState(null);
  const [searchQuery, setSearchQuery] = useState("");
  const [activeTableTab, setActiveTableTab] = useState("all"); // 'all' | 'entities' | 'columns' | 'keys' | 'enrichments'

  const bgSurface = themeTokens?.colors?.surface || "var(--color-bg-surface)";
  const bgSubtle = themeTokens?.colors?.surfaceHover || "var(--color-bg-subtle)";
  const borderCol = themeTokens?.colors?.borderSubtle || "var(--color-divider)";
  const borderStrong = themeTokens?.colors?.border || "var(--color-border)";
  const textPrimary = themeTokens?.colors?.textPrimary || "var(--color-text-primary)";
  const textSecondary = themeTokens?.colors?.textSecondary || "var(--color-text-secondary)";
  const textMuted = themeTokens?.colors?.textMuted || "var(--color-text-muted)";
  const brandPrimary = themeTokens?.colors?.brandPrimary || "var(--color-brand-primary)";
  const brandSoftBg = themeTokens?.colors?.softBlue || "var(--color-bg-soft-blue)";

  useEffect(() => {
    if (selectedSheetId) {
      setActiveSheet(selectedSheetId);
    }
  }, [selectedSheetId]);

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
          setError(err.message || "Failed to load semantic model");
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

  const handleSheetFilter = (sheetId) => {
    setActiveSheet(sheetId);
    if (onSelectSheet) onSelectSheet(sheetId);
  };

  const entities = semanticsData?.entities || [];
  const grains = semanticsData?.grains || [];
  const keys = semanticsData?.candidate_keys || semanticsData?.keys || [];
  const columns = semanticsData?.columns || [];
  const enrichments = semanticsData?.enrichments || [];
  const geoResolutions = semanticsData?.geo_resolutions || [];

  // Filter columns by search
  const filteredColumns = useMemo(() => {
    if (!searchQuery.trim()) return columns;
    const q = searchQuery.toLowerCase().trim();
    return columns.filter(
      (c) =>
        (c.display_name && c.display_name.toLowerCase().includes(q)) ||
        (c.column_id && c.column_id.toLowerCase().includes(q)) ||
        (c.role && c.role.toLowerCase().includes(q)) ||
        (c.concept && c.concept.toLowerCase().includes(q)) ||
        (c.entity && c.entity.toLowerCase().includes(q)) ||
        (c.sheet_id && String(c.sheet_id).toLowerCase().includes(q))
    );
  }, [columns, searchQuery]);

  // Combined enrichments list
  const combinedEnrichments = useMemo(() => {
    const list = [...enrichments];
    geoResolutions.forEach((g) => {
      list.push({
        source_value: g.input_term,
        derived_value: g.resolved_name || `${g.state_province || ""}, ${g.country || ""}`.trim(),
        type: "Geographic Resolution",
        confidence: g.confidence || "High",
        status: g.status || "Resolved",
      });
    });
    if (!searchQuery.trim()) return list;
    const q = searchQuery.toLowerCase().trim();
    return list.filter(
      (e) =>
        (e.source_value && String(e.source_value).toLowerCase().includes(q)) ||
        (e.derived_value && String(e.derived_value).toLowerCase().includes(q)) ||
        (e.type && String(e.type).toLowerCase().includes(q))
    );
  }, [enrichments, geoResolutions, searchQuery]);

  return (
    <div className="sdr-semantics-mode-container" style={{ display: "flex", flexDirection: "column", gap: "16px" }}>
      {/* Header & Sheet Filter */}
      <div
        style={{
          background: bgSurface,
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
            <Sparkles size={18} color={brandPrimary} aria-hidden="true" />
            <h2 style={{ margin: 0, fontSize: "1.1rem", fontWeight: 700, color: textPrimary }}>
              Semantic Model
            </h2>
          </div>
          <div style={{ display: "flex", alignItems: "center", gap: "8px" }}>
            <StatusBadge status="Source observed" variant="neutral" />
            <StatusBadge status="Derived reference" variant="info" />
          </div>
        </div>
        <p style={{ margin: 0, fontSize: "0.82rem", color: textSecondary }}>
          How HighView understands the structure, roles, and business meaning of this dataset.
        </p>

        {/* Sheet Filter Pills */}
        <div style={{ display: "flex", alignItems: "center", gap: "6px", overflowX: "auto", paddingTop: "4px" }}>
          <button
            type="button"
            onClick={() => handleSheetFilter("")}
            style={{
              padding: "6px 12px",
              fontSize: "0.8rem",
              fontWeight: !activeSheet ? 700 : 500,
              borderRadius: "8px",
              border: !activeSheet ? `1px solid ${brandPrimary}` : `1px solid ${borderCol}`,
              background: !activeSheet ? brandSoftBg : "transparent",
              color: !activeSheet ? brandPrimary : textSecondary,
              cursor: "pointer",
              whiteSpace: "nowrap",
              transition: "all 0.15s ease",
            }}
          >
            All Sheets
          </button>
          {sheets.map((s) => {
            const sid = s.sheet_id || s.name;
            const isSelected = sid === activeSheet;
            return (
              <button
                key={sid}
                type="button"
                onClick={() => handleSheetFilter(sid)}
                style={{
                  padding: "6px 12px",
                  fontSize: "0.8rem",
                  fontWeight: isSelected ? 700 : 500,
                  borderRadius: "8px",
                  border: isSelected ? `1px solid ${brandPrimary}` : `1px solid ${borderCol}`,
                  background: isSelected ? brandSoftBg : "transparent",
                  color: isSelected ? brandPrimary : textSecondary,
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
          Loading semantic model…
        </div>
      ) : error ? (
        <div
          style={{
            padding: "16px",
            background: themeTokens?.colors?.softError || "var(--color-bg-soft-error)",
            border: `1px solid ${themeTokens?.colors?.statusError || "var(--color-error)"}`,
            borderRadius: "8px",
            color: themeTokens?.colors?.statusError || "var(--color-error)",
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
          {/* Top Summary KPI Strip */}
          <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(200px, 1fr))", gap: "10px" }}>
            <div style={{ background: bgSurface, border: `1px solid ${borderCol}`, borderRadius: "8px", padding: "12px 14px", display: "flex", alignItems: "center", gap: "10px" }}>
              <div style={{ padding: "8px", borderRadius: "6px", background: brandSoftBg, color: brandPrimary, display: "flex" }}>
                <Layers size={16} />
              </div>
              <div>
                <div style={{ fontSize: "1.1rem", fontWeight: 700, color: textPrimary }}>{entities.length}</div>
                <div style={{ fontSize: "0.75rem", color: textSecondary }}>Entities Identified</div>
              </div>
            </div>

            <div style={{ background: bgSurface, border: `1px solid ${borderCol}`, borderRadius: "8px", padding: "12px 14px", display: "flex", alignItems: "center", gap: "10px" }}>
              <div style={{ padding: "8px", borderRadius: "6px", background: brandSoftBg, color: brandPrimary, display: "flex" }}>
                <Table size={16} />
              </div>
              <div>
                <div style={{ fontSize: "1.1rem", fontWeight: 700, color: textPrimary }}>{columns.length}</div>
                <div style={{ fontSize: "0.75rem", color: textSecondary }}>Columns Profiled</div>
              </div>
            </div>

            <div style={{ background: bgSurface, border: `1px solid ${borderCol}`, borderRadius: "8px", padding: "12px 14px", display: "flex", alignItems: "center", gap: "10px" }}>
              <div style={{ padding: "8px", borderRadius: "6px", background: brandSoftBg, color: brandPrimary, display: "flex" }}>
                <Key size={16} />
              </div>
              <div>
                <div style={{ fontSize: "1.1rem", fontWeight: 700, color: textPrimary }}>{keys.length}</div>
                <div style={{ fontSize: "0.75rem", color: textSecondary }}>Candidate Keys</div>
              </div>
            </div>

            <div style={{ background: bgSurface, border: `1px solid ${borderCol}`, borderRadius: "8px", padding: "12px 14px", display: "flex", alignItems: "center", gap: "10px" }}>
              <div style={{ padding: "8px", borderRadius: "6px", background: brandSoftBg, color: brandPrimary, display: "flex" }}>
                <MapPin size={16} />
              </div>
              <div>
                <div style={{ fontSize: "1.1rem", fontWeight: 700, color: textPrimary }}>{combinedEnrichments.length}</div>
                <div style={{ fontSize: "0.75rem", color: textSecondary }}>Reference Enrichments</div>
              </div>
            </div>
          </div>

          {/* Table Selector & Search Bar */}
          <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", flexWrap: "wrap", gap: "10px" }}>
            <div style={{ display: "flex", alignItems: "center", gap: "4px" }}>
              {[
                { id: "all", label: "All Tables" },
                { id: "entities", label: `Entities (${entities.length})` },
                { id: "columns", label: `Columns (${columns.length})` },
                { id: "keys", label: `Candidate Keys (${keys.length})` },
                { id: "enrichments", label: `Enrichments (${combinedEnrichments.length})` },
              ].map((tab) => {
                const isActive = activeTableTab === tab.id;
                return (
                  <button
                    key={tab.id}
                    type="button"
                    onClick={() => setActiveTableTab(tab.id)}
                    style={{
                      padding: "6px 12px",
                      fontSize: "0.78rem",
                      fontWeight: isActive ? 700 : 500,
                      borderRadius: "6px",
                      border: isActive ? `1px solid ${brandPrimary}` : `1px solid ${borderCol}`,
                      background: isActive ? brandSoftBg : bgSurface,
                      color: isActive ? brandPrimary : textSecondary,
                      cursor: "pointer",
                      transition: "all 0.15s ease",
                    }}
                  >
                    {tab.label}
                  </button>
                );
              })}
            </div>

            <div
              style={{
                display: "flex",
                alignItems: "center",
                gap: "6px",
                background: bgSurface,
                border: `1px solid ${borderStrong}`,
                borderRadius: "8px",
                padding: "4px 8px",
              }}
            >
              <Search size={13} color={textSecondary} aria-hidden="true" />
              <input
                type="text"
                aria-label="Filter tables"
                placeholder="Search semantic details..."
                value={searchQuery}
                onChange={(e) => setSearchQuery(e.target.value)}
                style={{
                  border: "none",
                  background: "transparent",
                  color: textPrimary,
                  fontSize: "0.8rem",
                  outline: "none",
                  width: "160px",
                }}
              />
            </div>
          </div>

          {/* TABLE A: ENTITIES TABLE */}
          {(activeTableTab === "all" || activeTableTab === "entities") && (
            <div style={{ background: bgSurface, border: `1px solid ${borderCol}`, borderRadius: "10px", overflow: "hidden" }}>
              <div style={{ padding: "12px 16px", borderBottom: `1px solid ${borderCol}`, display: "flex", justifyContent: "space-between", alignItems: "center" }}>
                <h3 style={{ margin: 0, fontSize: "0.9rem", fontWeight: 700, color: textPrimary, display: "flex", alignItems: "center", gap: "6px" }}>
                  <Layers size={15} color={brandPrimary} />
                  Entities Table
                </h3>
                <span style={{ fontSize: "0.75rem", color: textSecondary }}>
                  Core business concepts represented across sheets
                </span>
              </div>
              <div style={{ overflowX: "auto" }}>
                <table style={{ width: "100%", borderCollapse: "collapse", fontSize: "0.82rem", textAlign: "left" }}>
                  <thead>
                    <tr style={{ background: bgSubtle, borderBottom: `2px solid ${borderCol}` }}>
                      <th style={{ padding: "10px 12px", color: textPrimary, fontWeight: 700 }}>Entity</th>
                      <th style={{ padding: "10px 12px", color: textPrimary, fontWeight: 700 }}>Source Sheet</th>
                      <th style={{ padding: "10px 12px", color: textPrimary, fontWeight: 700 }}>Row Grain</th>
                      <th style={{ padding: "10px 12px", color: textPrimary, fontWeight: 700 }}>Supporting Columns</th>
                      <th style={{ padding: "10px 12px", color: textPrimary, fontWeight: 700 }}>Confidence</th>
                      <th style={{ padding: "10px 12px", color: textPrimary, fontWeight: 700 }}>Status</th>
                    </tr>
                  </thead>
                  <tbody>
                    {entities.length > 0 ? (
                      entities.map((ent, idx) => {
                        const matchingGrain = grains.find((g) => g.sheet_id === ent.sheet_id);
                        return (
                          <tr
                            key={ent.entity_id || idx}
                            style={{
                              borderBottom: `1px solid ${borderCol}`,
                              background: idx % 2 === 1 ? bgSubtle : "transparent",
                            }}
                          >
                            <td style={{ padding: "10px 12px", fontWeight: 700, color: textPrimary }}>
                              {ent.name}
                            </td>
                            <td style={{ padding: "10px 12px", color: textSecondary }}>
                              {ent.sheet_id || "All"}
                            </td>
                            <td style={{ padding: "10px 12px", color: textSecondary }}>
                              {matchingGrain ? matchingGrain.expression : "Record"}
                            </td>
                            <td style={{ padding: "10px 12px", color: textSecondary }}>
                              {Array.isArray(ent.supporting_columns) ? ent.supporting_columns.join(", ") : ent.evidence || "—"}
                            </td>
                            <td style={{ padding: "10px 12px" }}>
                              <StatusBadge status={ent.confidence || "High"} />
                            </td>
                            <td style={{ padding: "10px 12px" }}>
                              <StatusBadge status={ent.status || "Identified"} />
                            </td>
                          </tr>
                        );
                      })
                    ) : (
                      <tr>
                        <td colSpan={6} style={{ padding: "20px", textAlign: "center", color: textSecondary }}>
                          No entity definitions established for this view.
                        </td>
                      </tr>
                    )}
                  </tbody>
                </table>
              </div>
            </div>
          )}

          {/* TABLE B: SEMANTIC COLUMNS TABLE */}
          {(activeTableTab === "all" || activeTableTab === "columns") && (
            <div style={{ background: bgSurface, border: `1px solid ${borderCol}`, borderRadius: "10px", overflow: "hidden" }}>
              <div style={{ padding: "12px 16px", borderBottom: `1px solid ${borderCol}`, display: "flex", justifyContent: "space-between", alignItems: "center" }}>
                <h3 style={{ margin: 0, fontSize: "0.9rem", fontWeight: 700, color: textPrimary, display: "flex", alignItems: "center", gap: "6px" }}>
                  <Table size={15} color={brandPrimary} />
                  Semantic Columns Table ({filteredColumns.length})
                </h3>
                <span style={{ fontSize: "0.75rem", color: textSecondary }}>
                  Click row to inspect column profile and value distributions
                </span>
              </div>
              <div style={{ overflowX: "auto" }}>
                <table style={{ width: "100%", borderCollapse: "collapse", fontSize: "0.82rem", textAlign: "left" }}>
                  <thead>
                    <tr style={{ background: bgSubtle, borderBottom: `2px solid ${borderCol}` }}>
                      <th style={{ padding: "10px 12px", color: textPrimary, fontWeight: 700 }}>Column</th>
                      <th style={{ padding: "10px 12px", color: textPrimary, fontWeight: 700 }}>Sheet</th>
                      <th style={{ padding: "10px 12px", color: textPrimary, fontWeight: 700 }}>Meaning</th>
                      <th style={{ padding: "10px 12px", color: textPrimary, fontWeight: 700 }}>Role</th>
                      <th style={{ padding: "10px 12px", color: textPrimary, fontWeight: 700 }}>Type</th>
                      <th style={{ padding: "10px 12px", color: textPrimary, fontWeight: 700 }}>Measure / Dim</th>
                      <th style={{ padding: "10px 12px", color: textPrimary, fontWeight: 700 }}>Unit</th>
                      <th style={{ padding: "10px 12px", color: textPrimary, fontWeight: 700 }}>Privacy</th>
                      <th style={{ padding: "10px 12px", color: textPrimary, fontWeight: 700 }}>Confidence</th>
                      <th style={{ padding: "10px 12px", color: textPrimary, fontWeight: 700 }}>Status</th>
                      <th style={{ padding: "10px 12px", color: textSecondary, fontWeight: 700, textAlign: "right" }}>Action</th>
                    </tr>
                  </thead>
                  <tbody>
                    {filteredColumns.length > 0 ? (
                      filteredColumns.map((col, idx) => {
                        const isEnriched = col.provenance_type === "DERIVED_ENRICHMENT" || col.provenance_type === "DERIVED_RELATIONAL";
                        return (
                          <tr
                            key={col.column_id || idx}
                            onClick={() => setSelectedColumn(col)}
                            style={{
                              borderBottom: `1px solid ${borderCol}`,
                              background: idx % 2 === 1 ? bgSubtle : "transparent",
                              cursor: "pointer",
                            }}
                          >
                            <td style={{ padding: "10px 12px", fontWeight: 700, color: textPrimary }}>
                              {col.display_name || col.column_id}
                            </td>
                            <td style={{ padding: "10px 12px", color: textSecondary }}>
                              {col.sheet_id}
                            </td>
                            <td style={{ padding: "10px 12px", color: textSecondary }}>
                              {col.concept}
                            </td>
                            <td style={{ padding: "10px 12px", color: textSecondary }}>
                              {col.role}
                            </td>
                            <td style={{ padding: "10px 12px", color: textSecondary }}>
                              {col.data_type}
                            </td>
                            <td style={{ padding: "10px 12px", color: textSecondary }}>
                              {col.measure_class || "Dimension"}
                            </td>
                            <td style={{ padding: "10px 12px", color: textSecondary }}>
                              {col.unit || "—"}
                            </td>
                            <td style={{ padding: "10px 12px" }}>
                              <StatusBadge status={col.privacy} size="xs" />
                            </td>
                            <td style={{ padding: "10px 12px" }}>
                              <StatusBadge status={col.confidence} size="xs" />
                            </td>
                            <td style={{ padding: "10px 12px" }}>
                              <StatusBadge
                                status={isEnriched ? "Derived" : "Source"}
                                variant={isEnriched ? "info" : "neutral"}
                                size="xs"
                              />
                            </td>
                            <td style={{ padding: "10px 12px", textAlign: "right" }}>
                              <button
                                type="button"
                                className="btn-secondary"
                                onClick={(e) => {
                                  e.stopPropagation();
                                  setSelectedColumn(col);
                                }}
                                style={{
                                  padding: "4px 8px",
                                  fontSize: "0.74rem",
                                  fontWeight: 600,
                                  borderRadius: "6px",
                                  cursor: "pointer",
                                  display: "inline-flex",
                                  alignItems: "center",
                                  gap: "4px",
                                  minHeight: "unset",
                                  lineHeight: 1.25,
                                }}
                              >
                                <Eye size={12} />
                                Inspect
                              </button>
                            </td>
                          </tr>
                        );
                      })
                    ) : (
                      <tr>
                        <td colSpan={11} style={{ padding: "20px", textAlign: "center", color: textSecondary }}>
                          No columns matched your query.
                        </td>
                      </tr>
                    )}
                  </tbody>
                </table>
              </div>
            </div>
          )}

          {/* TABLE C: CANDIDATE KEYS TABLE */}
          {(activeTableTab === "all" || activeTableTab === "keys") && (
            <div style={{ background: bgSurface, border: `1px solid ${borderCol}`, borderRadius: "10px", overflow: "hidden" }}>
              <div style={{ padding: "12px 16px", borderBottom: `1px solid ${borderCol}`, display: "flex", justifyContent: "space-between", alignItems: "center" }}>
                <h3 style={{ margin: 0, fontSize: "0.9rem", fontWeight: 700, color: textPrimary, display: "flex", alignItems: "center", gap: "6px" }}>
                  <Key size={15} color={brandPrimary} />
                  Candidate Keys Table
                </h3>
                <span style={{ fontSize: "0.75rem", color: textSecondary }}>
                  Uniqueness analysis and identifier candidates
                </span>
              </div>
              <div style={{ overflowX: "auto" }}>
                <table style={{ width: "100%", borderCollapse: "collapse", fontSize: "0.82rem", textAlign: "left" }}>
                  <thead>
                    <tr style={{ background: bgSubtle, borderBottom: `2px solid ${borderCol}` }}>
                      <th style={{ padding: "10px 12px", color: textPrimary, fontWeight: 700 }}>Sheet</th>
                      <th style={{ padding: "10px 12px", color: textPrimary, fontWeight: 700 }}>Candidate Key</th>
                      <th style={{ padding: "10px 12px", color: textPrimary, fontWeight: 700 }}>Columns</th>
                      <th style={{ padding: "10px 12px", color: textPrimary, fontWeight: 700 }}>Uniqueness</th>
                      <th style={{ padding: "10px 12px", color: textPrimary, fontWeight: 700 }}>Confidence</th>
                      <th style={{ padding: "10px 12px", color: textPrimary, fontWeight: 700 }}>Status</th>
                    </tr>
                  </thead>
                  <tbody>
                    {keys.length > 0 ? (
                      keys.map((k, idx) => (
                        <tr
                          key={idx}
                          style={{
                            borderBottom: `1px solid ${borderCol}`,
                            background: idx % 2 === 1 ? bgSubtle : "transparent",
                          }}
                        >
                          <td style={{ padding: "10px 12px", fontWeight: 600, color: textPrimary }}>
                            {k.sheet_id || "Primary"}
                          </td>
                          <td style={{ padding: "10px 12px", color: textPrimary, fontWeight: 600 }}>
                            {k.columns?.join(" + ") || "Key"}
                          </td>
                          <td style={{ padding: "10px 12px", color: textSecondary }}>
                            {k.columns?.join(", ")}
                          </td>
                          <td style={{ padding: "10px 12px", color: textSecondary }}>
                            {k.unique_ratio_pct ? `${k.unique_ratio_pct}% unique` : "100% unique"}
                          </td>
                          <td style={{ padding: "10px 12px" }}>
                            <StatusBadge status={k.confidence || "High"} />
                          </td>
                          <td style={{ padding: "10px 12px" }}>
                            <StatusBadge status={k.status || "Candidate"} />
                          </td>
                        </tr>
                      ))
                    ) : (
                      <tr>
                        <td colSpan={6} style={{ padding: "20px", textAlign: "center", color: textSecondary }}>
                          No reliable record identifier was found. Multi-attribute observations / non-unique rows.
                        </td>
                      </tr>
                    )}
                  </tbody>
                </table>
              </div>
            </div>
          )}

          {/* TABLE D: REFERENCE ENRICHMENTS TABLE */}
          {(activeTableTab === "all" || activeTableTab === "enrichments") && (
            <div style={{ background: bgSurface, border: `1px solid ${borderCol}`, borderRadius: "10px", overflow: "hidden" }}>
              <div style={{ padding: "12px 16px", borderBottom: `1px solid ${borderCol}`, display: "flex", justifyContent: "space-between", alignItems: "center" }}>
                <h3 style={{ margin: 0, fontSize: "0.9rem", fontWeight: 700, color: textPrimary, display: "flex", alignItems: "center", gap: "6px" }}>
                  <MapPin size={15} color={brandPrimary} />
                  Reference Enrichments Table ({combinedEnrichments.length})
                </h3>
                <span style={{ fontSize: "0.75rem", color: textSecondary }}>
                  Standardized values derived from reference data
                </span>
              </div>
              <div style={{ overflowX: "auto" }}>
                <table style={{ width: "100%", borderCollapse: "collapse", fontSize: "0.82rem", textAlign: "left" }}>
                  <thead>
                    <tr style={{ background: bgSubtle, borderBottom: `2px solid ${borderCol}` }}>
                      <th style={{ padding: "10px 12px", color: textPrimary, fontWeight: 700 }}>Source Value</th>
                      <th style={{ padding: "10px 12px", color: textPrimary, fontWeight: 700 }}>Derived Value</th>
                      <th style={{ padding: "10px 12px", color: textPrimary, fontWeight: 700 }}>Type</th>
                      <th style={{ padding: "10px 12px", color: textPrimary, fontWeight: 700 }}>Confidence</th>
                      <th style={{ padding: "10px 12px", color: textPrimary, fontWeight: 700 }}>Status</th>
                    </tr>
                  </thead>
                  <tbody>
                    {combinedEnrichments.length > 0 ? (
                      combinedEnrichments.map((en, idx) => (
                        <tr
                          key={idx}
                          style={{
                            borderBottom: `1px solid ${borderCol}`,
                            background: idx % 2 === 1 ? bgSubtle : "transparent",
                          }}
                        >
                          <td style={{ padding: "10px 12px", fontWeight: 600, color: textPrimary }}>
                            {en.source_value}
                          </td>
                          <td style={{ padding: "10px 12px", color: textPrimary }}>
                            {en.derived_value}
                          </td>
                          <td style={{ padding: "10px 12px", color: textSecondary }}>
                            {en.type}
                          </td>
                          <td style={{ padding: "10px 12px" }}>
                            <StatusBadge status={en.confidence || "High"} />
                          </td>
                          <td style={{ padding: "10px 12px" }}>
                            <StatusBadge status={en.status || "Derived"} />
                          </td>
                        </tr>
                      ))
                    ) : (
                      <tr>
                        <td colSpan={5} style={{ padding: "20px", textAlign: "center", color: textSecondary }}>
                          No reference enrichments applied to this dataset.
                        </td>
                      </tr>
                    )}
                  </tbody>
                </table>
              </div>
            </div>
          )}
        </>
      )}

      {/* Progressive Disclosure Column Detail Drawer */}
      {selectedColumn && (
        <ColumnDetailDrawer
          column={selectedColumn}
          onClose={() => setSelectedColumn(null)}
          themeTokens={themeTokens}
          isDark={isDark}
        />
      )}
    </div>
  );
}
