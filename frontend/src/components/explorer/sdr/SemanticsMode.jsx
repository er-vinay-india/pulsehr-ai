import React, { useState, useEffect, useMemo } from "react";
import { getExplorerSemantics } from "../../../api/client";
import ColumnDetailDrawer from "./ColumnDetailDrawer";
import StatusBadge from "../common/StatusBadge";
import DataTable from "../../DataTable";
import {
  Sparkles,
  Layers,
  Key,
  MapPin,
  Eye,
  AlertCircle,
  Table,
  Filter,
  CheckCircle2,
  ShieldCheck,
  Hash,
  Percent,
} from "lucide-react";

/**
 * HighView Data Explorer — Semantic Model
 * "Cards summarize. Tables compare. Drawers explain."
 * Provides 4 structured DataTable exploration surfaces:
 * 1. Entities Table
 * 2. Semantic Columns Table (with instant role filters & completeness micro-bars)
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
  const [activeTableTab, setActiveTableTab] = useState("all"); // 'all' | 'entities' | 'columns' | 'keys' | 'enrichments'
  const [quickRoleFilter, setQuickRoleFilter] = useState("all"); // 'all' | 'identifiers' | 'metrics' | 'dimensions' | 'source' | 'derived'

  const bgSurface = themeTokens?.colors?.surface || "var(--color-bg-surface)";
  const bgSubtle = themeTokens?.colors?.surfaceHover || "var(--color-bg-subtle)";
  const borderCol = themeTokens?.colors?.borderSubtle || "var(--color-divider)";
  const borderStrong = themeTokens?.colors?.border || "var(--color-border)";
  const textPrimary = themeTokens?.colors?.textPrimary || "var(--color-text-primary)";
  const textSecondary = themeTokens?.colors?.textSecondary || "var(--color-text-secondary)";
  const brandPrimary = themeTokens?.colors?.brandPrimary || "var(--color-brand-primary)";
  const brandSoftBg = themeTokens?.colors?.softBlue || "var(--color-bg-soft-blue)";

  useEffect(() => {
    if (selectedSheetId !== undefined && selectedSheetId !== activeSheet) {
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

  // Flatten geo resolutions with enrichments for unified table
  const combinedEnrichments = useMemo(() => {
    const list = enrichments.map((e, idx) => ({
      ...e,
      _rowKey: `enrich-${e.sheet_id || ""}-${idx}`,
      source_value: e.source_value || e.source_column || "—",
      derived_value: e.derived_value || e.target_column || "—",
      type: e.type || e.enrichment_type || "Reference Enrichment",
      confidence: e.confidence || "High",
      status: e.status || "Derived",
    }));

    geoResolutions.forEach((g, idx) => {
      list.push({
        _rowKey: `geo-${idx}`,
        source_value: `${g.source_value} (${g.source_column})`,
        derived_value: `${g.resolved_state || ""}, ${g.resolved_country || ""}`.trim().replace(/^,|,$/g, ""),
        type: "Geographic (GEO-1)",
        confidence: g.confidence || "High",
        status: "Standardized",
      });
    });
    return list;
  }, [enrichments, geoResolutions]);

  // Enrich entities with grain descriptions
  const enrichedEntities = useMemo(() => {
    return entities.map((ent, idx) => {
      const matchingGrain = grains.find((g) => g.sheet_id === ent.sheet_id);
      return {
        ...ent,
        _rowKey: ent.entity_id || `entity-${ent.sheet_id}-${idx}`,
        row_grain: matchingGrain?.grain_description || matchingGrain?.explanation || "Individual record observation",
        supporting_columns_str: ent.supporting_columns?.join(", ") || ent.primary_column || "—",
      };
    });
  }, [entities, grains]);

  // Enrich columns with completeness metrics and display metadata
  const enrichedColumns = useMemo(() => {
    return columns.map((col, idx) => {
      const isEnriched =
        col.provenance_type === "DERIVED_ENRICHMENT" ||
        col.provenance_type === "DERIVED_RELATIONAL" ||
        col.is_derived === true;

      const nullPct = col.null_ratio_pct ?? col.null_percentage ?? 0;
      const populatedPct = Math.max(0, Math.min(100, Math.round((100 - nullPct) * 10) / 10));

      return {
        ...col,
        _rowKey: `${col.sheet_id || "sheet"}-${col.column_id || idx}`,
        original_position: idx,
        status_provenance: isEnriched ? "Derived" : "Source",
        measure_dim_label: col.measure_class || "Dimension",
        populated_pct: populatedPct,
        null_pct: nullPct,
      };
    });
  }, [columns]);

  // Quick Role Counts
  const roleCounts = useMemo(() => {
    let identifiers = 0;
    let metrics = 0;
    let dimensions = 0;
    let source = 0;
    let derived = 0;

    enrichedColumns.forEach((c) => {
      const r = (c.role || "").toLowerCase();
      if (r.includes("identifier") || c.is_identifier_candidate) {
        identifiers++;
      } else if (r.includes("metric") || r.includes("measure")) {
        metrics++;
      } else {
        dimensions++;
      }

      if (c.status_provenance === "Derived" || c.is_derived) {
        derived++;
      } else {
        source++;
      }
    });

    return {
      total: enrichedColumns.length,
      identifiers,
      metrics,
      dimensions,
      source,
      derived,
    };
  }, [enrichedColumns]);

  // Filtered columns based on quick role pills
  const displayedColumns = useMemo(() => {
    if (quickRoleFilter === "all") return enrichedColumns;
    if (quickRoleFilter === "identifiers") {
      return enrichedColumns.filter(
        (c) => (c.role || "").toLowerCase().includes("identifier") || c.is_identifier_candidate
      );
    }
    if (quickRoleFilter === "metrics") {
      return enrichedColumns.filter(
        (c) => (c.role || "").toLowerCase().includes("metric") || (c.role || "").toLowerCase().includes("measure")
      );
    }
    if (quickRoleFilter === "dimensions") {
      return enrichedColumns.filter(
        (c) =>
          !(c.role || "").toLowerCase().includes("identifier") &&
          !(c.role || "").toLowerCase().includes("metric") &&
          !c.is_identifier_candidate
      );
    }
    if (quickRoleFilter === "source") {
      return enrichedColumns.filter((c) => c.status_provenance !== "Derived" && !c.is_derived);
    }
    if (quickRoleFilter === "derived") {
      return enrichedColumns.filter((c) => c.status_provenance === "Derived" || c.is_derived);
    }
    return enrichedColumns;
  }, [enrichedColumns, quickRoleFilter]);

  // Enrich keys
  const enrichedKeys = useMemo(() => {
    return keys.map((k, idx) => {
      return {
        ...k,
        _rowKey: `key-${k.sheet_id || ""}-${idx}`,
        key_label: k.columns?.join(" + ") || "Key",
        columns_str: k.columns?.join(", ") || "—",
        uniqueness_pct: k.unique_ratio_pct ?? 100,
      };
    });
  }, [keys]);

  // Active Grain / Key summary for banner
  const activeGrain = useMemo(() => {
    if (activeSheet) {
      return grains.find((g) => g.sheet_id === activeSheet) || grains[0];
    }
    return grains[0];
  }, [grains, activeSheet]);

  const activeSheetKeys = useMemo(() => {
    if (activeSheet) {
      return keys.filter((k) => k.sheet_id === activeSheet);
    }
    return keys;
  }, [keys, activeSheet]);

  // =========================================================================
  // TABLE COLUMNS CONFIGURATIONS
  // =========================================================================

  // 1. Entities Columns
  const entityColumns = useMemo(
    () => [
      {
        key: "entity_id",
        label: "Entity",
        type: "text",
        sortable: true,
        render: (val, row) => <strong style={{ color: textPrimary }}>{row.concept || val}</strong>,
      },
      {
        key: "sheet_id",
        label: "Source Sheet",
        type: "text",
        sortable: true,
        render: (val) => <span style={{ color: textSecondary }}>{val}</span>,
      },
      {
        key: "row_grain",
        label: "Governed Row Grain",
        type: "text",
        sortable: true,
        render: (val) => <span style={{ color: textSecondary }}>{val}</span>,
      },
      {
        key: "supporting_columns_str",
        label: "Primary Identifier",
        type: "text",
        sortable: true,
        render: (val) => <span style={{ fontFamily: "monospace", color: textSecondary }}>{val}</span>,
      },
      {
        key: "confidence",
        label: "Confidence",
        type: "status",
        sortable: true,
        render: (val) => <StatusBadge status={val || "High"} size="xs" />,
      },
      {
        key: "status",
        label: "Status",
        type: "status",
        sortable: true,
        render: (val) => <StatusBadge status={val || "Identified"} variant="neutral" size="xs" />,
      },
    ],
    [textPrimary, textSecondary]
  );

  // 2. Semantic Columns
  const semanticColumnsConfig = useMemo(
    () => [
      {
        key: "display_name",
        label: "Column",
        type: "text",
        sortable: true,
        defaultVisible: true,
        render: (val, row) => (
          <div>
            <strong style={{ color: textPrimary, display: "block" }}>{val || row.column_id}</strong>
            {val && val !== row.column_id && (
              <span style={{ fontSize: "0.72rem", color: textSecondary, fontFamily: "monospace" }}>
                {row.column_id}
              </span>
            )}
          </div>
        ),
      },
      {
        key: "sheet_id",
        label: "Sheet",
        type: "text",
        sortable: true,
        defaultVisible: true,
        render: (val) => <span style={{ color: textSecondary }}>{val}</span>,
      },
      {
        key: "role",
        label: "Role",
        type: "text",
        sortable: true,
        defaultVisible: true,
        render: (val) => (
          <span
            style={{
              display: "inline-block",
              padding: "2px 7px",
              borderRadius: "4px",
              fontSize: "0.74rem",
              fontWeight: 600,
              background: bgSubtle,
              border: `1px solid ${borderCol}`,
              color: textPrimary,
            }}
          >
            {val || "Dimension"}
          </span>
        ),
      },
      {
        key: "data_type",
        label: "Type",
        type: "text",
        sortable: true,
        defaultVisible: true,
        render: (val) => <span style={{ color: textSecondary }}>{val || "—"}</span>,
      },
      {
        key: "concept",
        label: "Business Concept",
        type: "text",
        sortable: true,
        defaultVisible: true,
        render: (val) => <span style={{ color: textSecondary }}>{val || "—"}</span>,
      },
      {
        key: "completeness",
        label: "Completeness",
        type: "percentage",
        sortable: true,
        defaultVisible: true,
        sortVal: (row) => row.populated_pct,
        render: (_, row) => {
          const pop = row.populated_pct ?? 100;
          return (
            <div style={{ display: "flex", alignItems: "center", gap: "8px", minWidth: "115px" }}>
              <div
                style={{
                  flex: 1,
                  height: "6px",
                  borderRadius: "3px",
                  backgroundColor: "var(--color-bg-soft-error, #FAEAEE)",
                  overflow: "hidden",
                  display: "flex",
                }}
                title={`${pop}% populated, ${row.null_pct}% null`}
              >
                <div
                  style={{
                    width: `${pop}%`,
                    height: "100%",
                    backgroundColor: brandPrimary,
                  }}
                />
              </div>
              <span style={{ fontSize: "0.75rem", fontWeight: 600, color: textPrimary, width: "36px", textAlign: "right" }}>
                {pop}%
              </span>
            </div>
          );
        },
      },
      {
        key: "distinct_count",
        label: "Distinct Values",
        type: "numeric",
        sortable: true,
        defaultVisible: true,
        sortVal: (row) => row.distinct_count ?? 0,
        render: (val, row) => (
          <span style={{ fontSize: "0.78rem", color: textSecondary }}>
            <strong style={{ color: textPrimary }}>{val != null ? val.toLocaleString() : "—"}</strong>
            {row.row_count ? ` / ${row.row_count.toLocaleString()}` : ""}
          </span>
        ),
      },
      {
        key: "confidence",
        label: "Confidence",
        type: "status",
        sortable: true,
        defaultVisible: true,
        statusRankOrder: ["High", "Medium", "Low"],
        render: (val) => <StatusBadge status={val} size="xs" />,
      },
      {
        key: "status_provenance",
        label: "Status",
        type: "status",
        sortable: true,
        defaultVisible: true,
        render: (val) => (
          <StatusBadge
            status={val}
            variant={val === "Derived" ? "info" : "neutral"}
            size="xs"
          />
        ),
      },
      {
        key: "actions",
        label: "Action",
        sortable: false,
        align: "right",
        defaultVisible: true,
        render: (_, row) => (
          <button
            type="button"
            className="btn-secondary"
            onClick={(e) => {
              e.stopPropagation();
              setSelectedColumn(row);
            }}
            aria-label={`Inspect column profile for ${row.display_name || row.column_id}`}
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
        ),
      },
    ],
    [textPrimary, textSecondary, bgSubtle, borderCol, brandPrimary]
  );

  // 3. Candidate Keys Columns
  const keyColumnsConfig = useMemo(
    () => [
      {
        key: "sheet_id",
        label: "Sheet",
        type: "text",
        sortable: true,
        render: (val) => <strong style={{ color: textPrimary }}>{val || "Primary"}</strong>,
      },
      {
        key: "key_label",
        label: "Candidate Key",
        type: "text",
        sortable: true,
        render: (val) => (
          <span style={{ color: textPrimary, fontWeight: 600, display: "flex", alignItems: "center", gap: "6px" }}>
            <Key size={13} color={brandPrimary} />
            {val}
          </span>
        ),
      },
      {
        key: "columns_str",
        label: "Key Columns",
        type: "text",
        sortable: true,
        render: (val) => <span style={{ fontFamily: "monospace", color: textSecondary }}>{val}</span>,
      },
      {
        key: "uniqueness_pct",
        label: "Uniqueness",
        type: "percentage",
        sortable: true,
        render: (val) => (
          <span style={{ color: textPrimary, fontWeight: 600 }}>
            {val}% unique
          </span>
        ),
      },
      {
        key: "confidence",
        label: "Confidence",
        type: "status",
        sortable: true,
        statusRankOrder: ["High", "Medium", "Low"],
        render: (val) => <StatusBadge status={val || "High"} size="xs" />,
      },
      {
        key: "authority",
        label: "Authority",
        type: "status",
        sortable: true,
        render: (val) => <StatusBadge status={val || "Governed"} variant="success" size="xs" />,
      },
    ],
    [textPrimary, textSecondary, brandPrimary]
  );

  // 4. Enrichments Columns
  const enrichmentColumnsConfig = useMemo(
    () => [
      {
        key: "source_value",
        label: "Source Value / Column",
        type: "text",
        sortable: true,
        render: (val) => <strong style={{ color: textPrimary }}>{val}</strong>,
      },
      {
        key: "derived_value",
        label: "Derived Value / Target",
        type: "text",
        sortable: true,
        render: (val) => <span style={{ color: textPrimary, fontWeight: 600 }}>{val}</span>,
      },
      {
        key: "type",
        label: "Enrichment Type",
        type: "text",
        sortable: true,
        render: (val) => <span style={{ color: textSecondary }}>{val}</span>,
      },
      {
        key: "confidence",
        label: "Confidence",
        type: "status",
        sortable: true,
        statusRankOrder: ["High", "Medium", "Low"],
        render: (val) => <StatusBadge status={val || "High"} size="xs" />,
      },
      {
        key: "status",
        label: "Status",
        type: "status",
        sortable: true,
        render: (val) => <StatusBadge status={val || "Derived"} size="xs" />,
      },
    ],
    [textPrimary, textSecondary]
  );

  // =========================================================================
  // FILTERS CONFIGURATIONS
  // =========================================================================

  const semanticColumnsFilters = useMemo(
    () => [
      { key: "sheet_id", label: "Sheet" },
      { key: "role", label: "Role" },
      { key: "measure_dim_label", label: "Measure / Dim" },
      { key: "privacy", label: "Privacy" },
      { key: "confidence", label: "Confidence", options: ["High", "Medium", "Low"] },
      { key: "status_provenance", label: "Status", options: ["Source", "Derived"] },
    ],
    []
  );

  const entityFilters = useMemo(
    () => [
      { key: "sheet_id", label: "Sheet" },
      { key: "confidence", label: "Confidence", options: ["High", "Medium", "Low"] },
    ],
    []
  );

  const keyFilters = useMemo(
    () => [
      { key: "sheet_id", label: "Sheet" },
      { key: "confidence", label: "Confidence", options: ["High", "Medium", "Low"] },
    ],
    []
  );

  const enrichmentFilters = useMemo(
    () => [
      { key: "type", label: "Type" },
      { key: "confidence", label: "Confidence", options: ["High", "Medium", "Low"] },
    ],
    []
  );

  const toggleTab = (tabId) => {
    setActiveTableTab((prev) => (prev === tabId ? "all" : tabId));
  };

  return (
    <div className="sdr-semantics-mode-container" style={{ display: "flex", flexDirection: "column", gap: "16px" }}>
      {/* Interactive KPI Overview Cards */}
      <div
        style={{
          display: "grid",
          gridTemplateColumns: "repeat(auto-fit, minmax(210px, 1fr))",
          gap: "12px",
        }}
        role="region"
        aria-label="Semantic Model KPI Overview"
      >
        {/* Card 1: Business Entities */}
        <div
          role="button"
          tabIndex={0}
          onClick={() => toggleTab("entities")}
          onKeyDown={(e) => {
            if (e.key === "Enter" || e.key === " ") {
              e.preventDefault();
              toggleTab("entities");
            }
          }}
          aria-pressed={activeTableTab === "entities"}
          style={{
            background: bgSurface,
            border: activeTableTab === "entities" ? `2px solid ${brandPrimary}` : `1px solid ${borderCol}`,
            borderRadius: "10px",
            padding: "14px 16px",
            display: "flex",
            alignItems: "center",
            justifyContent: "space-between",
            cursor: "pointer",
            transition: "all 0.18s ease",
            boxShadow: activeTableTab === "entities" ? "0 2px 8px rgba(0,0,0,0.08)" : "none",
          }}
        >
          <div style={{ display: "flex", alignItems: "center", gap: "12px" }}>
            <div
              style={{
                width: "38px",
                height: "38px",
                borderRadius: "8px",
                background: brandSoftBg,
                display: "flex",
                alignItems: "center",
                justifyContent: "center",
              }}
            >
              <Layers size={18} color={brandPrimary} />
            </div>
            <div>
              <div style={{ fontSize: "1.25rem", fontWeight: 700, color: textPrimary, lineHeight: 1.2 }}>
                {entities.length}
              </div>
              <div style={{ fontSize: "0.76rem", color: textSecondary, marginTop: "2px" }}>
                Business Entities
              </div>
            </div>
          </div>
          {activeTableTab === "entities" && (
            <span style={{ fontSize: "0.7rem", fontWeight: 700, color: brandPrimary, background: brandSoftBg, padding: "2px 6px", borderRadius: "4px" }}>
              Active
            </span>
          )}
        </div>

        {/* Card 2: Semantic Columns */}
        <div
          role="button"
          tabIndex={0}
          onClick={() => toggleTab("columns")}
          onKeyDown={(e) => {
            if (e.key === "Enter" || e.key === " ") {
              e.preventDefault();
              toggleTab("columns");
            }
          }}
          aria-pressed={activeTableTab === "columns"}
          style={{
            background: bgSurface,
            border: activeTableTab === "columns" ? `2px solid ${brandPrimary}` : `1px solid ${borderCol}`,
            borderRadius: "10px",
            padding: "14px 16px",
            display: "flex",
            alignItems: "center",
            justifyContent: "space-between",
            cursor: "pointer",
            transition: "all 0.18s ease",
            boxShadow: activeTableTab === "columns" ? "0 2px 8px rgba(0,0,0,0.08)" : "none",
          }}
        >
          <div style={{ display: "flex", alignItems: "center", gap: "12px" }}>
            <div
              style={{
                width: "38px",
                height: "38px",
                borderRadius: "8px",
                background: "var(--color-bg-soft-teal, #E7F3ED)",
                display: "flex",
                alignItems: "center",
                justifyContent: "center",
              }}
            >
              <Sparkles size={18} color="var(--color-success, #075443)" />
            </div>
            <div>
              <div style={{ fontSize: "1.25rem", fontWeight: 700, color: textPrimary, lineHeight: 1.2 }}>
                {columns.length}
              </div>
              <div style={{ fontSize: "0.76rem", color: textSecondary, marginTop: "2px" }}>
                Semantic Columns
              </div>
            </div>
          </div>
          {activeTableTab === "columns" && (
            <span style={{ fontSize: "0.7rem", fontWeight: 700, color: brandPrimary, background: brandSoftBg, padding: "2px 6px", borderRadius: "4px" }}>
              Active
            </span>
          )}
        </div>

        {/* Card 3: Candidate Keys */}
        <div
          role="button"
          tabIndex={0}
          onClick={() => toggleTab("keys")}
          onKeyDown={(e) => {
            if (e.key === "Enter" || e.key === " ") {
              e.preventDefault();
              toggleTab("keys");
            }
          }}
          aria-pressed={activeTableTab === "keys"}
          style={{
            background: bgSurface,
            border: activeTableTab === "keys" ? `2px solid ${brandPrimary}` : `1px solid ${borderCol}`,
            borderRadius: "10px",
            padding: "14px 16px",
            display: "flex",
            alignItems: "center",
            justifyContent: "space-between",
            cursor: "pointer",
            transition: "all 0.18s ease",
            boxShadow: activeTableTab === "keys" ? "0 2px 8px rgba(0,0,0,0.08)" : "none",
          }}
        >
          <div style={{ display: "flex", alignItems: "center", gap: "12px" }}>
            <div
              style={{
                width: "38px",
                height: "38px",
                borderRadius: "8px",
                background: "var(--color-bg-soft-gold, #F6EDDA)",
                display: "flex",
                alignItems: "center",
                justifyContent: "center",
              }}
            >
              <Key size={18} color="var(--color-warning, #65470C)" />
            </div>
            <div>
              <div style={{ fontSize: "1.25rem", fontWeight: 700, color: textPrimary, lineHeight: 1.2 }}>
                {keys.length}
              </div>
              <div style={{ fontSize: "0.76rem", color: textSecondary, marginTop: "2px" }}>
                Candidate Keys
              </div>
            </div>
          </div>
          {activeTableTab === "keys" && (
            <span style={{ fontSize: "0.7rem", fontWeight: 700, color: brandPrimary, background: brandSoftBg, padding: "2px 6px", borderRadius: "4px" }}>
              Active
            </span>
          )}
        </div>

        {/* Card 4: Reference Enrichments */}
        <div
          role="button"
          tabIndex={0}
          onClick={() => toggleTab("enrichments")}
          onKeyDown={(e) => {
            if (e.key === "Enter" || e.key === " ") {
              e.preventDefault();
              toggleTab("enrichments");
            }
          }}
          aria-pressed={activeTableTab === "enrichments"}
          style={{
            background: bgSurface,
            border: activeTableTab === "enrichments" ? `2px solid ${brandPrimary}` : `1px solid ${borderCol}`,
            borderRadius: "10px",
            padding: "14px 16px",
            display: "flex",
            alignItems: "center",
            justifyContent: "space-between",
            cursor: "pointer",
            transition: "all 0.18s ease",
            boxShadow: activeTableTab === "enrichments" ? "0 2px 8px rgba(0,0,0,0.08)" : "none",
          }}
        >
          <div style={{ display: "flex", alignItems: "center", gap: "12px" }}>
            <div
              style={{
                width: "38px",
                height: "38px",
                borderRadius: "8px",
                background: "var(--color-bg-soft-blue, #EAF0F5)",
                display: "flex",
                alignItems: "center",
                justifyContent: "center",
              }}
            >
              <MapPin size={18} color="var(--color-brand-primary, #183B56)" />
            </div>
            <div>
              <div style={{ fontSize: "1.25rem", fontWeight: 700, color: textPrimary, lineHeight: 1.2 }}>
                {combinedEnrichments.length}
              </div>
              <div style={{ fontSize: "0.76rem", color: textSecondary, marginTop: "2px" }}>
                Reference Enrichments
              </div>
            </div>
          </div>
          {activeTableTab === "enrichments" && (
            <span style={{ fontSize: "0.7rem", fontWeight: 700, color: brandPrimary, background: brandSoftBg, padding: "2px 6px", borderRadius: "4px" }}>
              Active
            </span>
          )}
        </div>
      </div>

      {/* Header and Scope Selector */}
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
          <div style={{ display: "flex", alignItems: "center", gap: "6px" }}>
            <StatusBadge status="Deterministic profiling" variant="success" />
            <StatusBadge status="0 black-box predictions" variant="neutral" />
          </div>
        </div>
        <p style={{ margin: 0, fontSize: "0.82rem", color: textSecondary }}>
          Governed semantic meanings, business entity hypotheses, row grain assertions, and candidate keys.
        </p>

        {/* Sheet Selector Pills */}
        <div style={{ display: "flex", alignItems: "center", gap: "6px", overflowX: "auto", paddingTop: "4px" }}>
          <button
            type="button"
            onClick={() => handleSheetFilter("")}
            style={{
              padding: "6px 12px",
              fontSize: "0.8rem",
              fontWeight: activeSheet === "" ? 700 : 500,
              borderRadius: "8px",
              border: activeSheet === "" ? `1px solid ${brandPrimary}` : `1px solid ${borderCol}`,
              background: activeSheet === "" ? brandSoftBg : "transparent",
              color: activeSheet === "" ? brandPrimary : textSecondary,
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

      {/* Governed Row Grain & Key Architecture Banner */}
      {activeGrain && (
        <div
          style={{
            background: bgSurface,
            border: `1px solid ${borderCol}`,
            borderRadius: "10px",
            padding: "14px 16px",
            display: "flex",
            justifyContent: "space-between",
            alignItems: "center",
            flexWrap: "wrap",
            gap: "12px",
          }}
        >
          <div style={{ display: "flex", alignItems: "flex-start", gap: "10px", maxWidth: "700px" }}>
            <div
              style={{
                width: "32px",
                height: "32px",
                borderRadius: "6px",
                background: brandSoftBg,
                display: "flex",
                alignItems: "center",
                justifyContent: "center",
                flexShrink: 0,
                marginTop: "2px",
              }}
            >
              <ShieldCheck size={18} color={brandPrimary} />
            </div>
            <div>
              <div style={{ display: "flex", alignItems: "center", gap: "8px", flexWrap: "wrap" }}>
                <span style={{ fontSize: "0.75rem", fontWeight: 700, textTransform: "uppercase", letterSpacing: "0.04em", color: brandPrimary }}>
                  Governed Row Grain
                </span>
                <span style={{ fontSize: "0.75rem", color: textSecondary }}>
                  ({activeSheet ? `Sheet: ${activeSheet}` : "Primary Sheet"})
                </span>
              </div>
              <div style={{ fontSize: "0.88rem", fontWeight: 600, color: textPrimary, marginTop: "2px" }}>
                {activeGrain.explanation || activeGrain.grain_description || activeGrain.name}
              </div>
            </div>
          </div>

          {activeSheetKeys.length > 0 && (
            <div style={{ display: "flex", alignItems: "center", gap: "6px", flexWrap: "wrap" }}>
              <span style={{ fontSize: "0.75rem", color: textSecondary, fontWeight: 600 }}>
                Candidate Keys:
              </span>
              {activeSheetKeys.map((k, idx) => (
                <span
                  key={idx}
                  style={{
                    display: "inline-flex",
                    alignItems: "center",
                    gap: "4px",
                    padding: "3px 8px",
                    borderRadius: "6px",
                    fontSize: "0.75rem",
                    fontWeight: 600,
                    background: bgSubtle,
                    border: `1px solid ${borderCol}`,
                    color: textPrimary,
                  }}
                >
                  <Key size={12} color={brandPrimary} />
                  {k.columns?.join(" + ") || "Key"}
                  <span style={{ fontSize: "0.7rem", color: "var(--color-success, #075443)" }}>
                    ({k.unique_ratio_pct ?? 100}%)
                  </span>
                </span>
              ))}
            </div>
          )}
        </div>
      )}

      {loading ? (
        <div style={{ padding: "40px", textAlign: "center", color: textSecondary, fontSize: "0.9rem" }}>
          Loading semantic intelligence…
        </div>
      ) : error ? (
        <div
          style={{
            padding: "16px",
            background: "var(--color-bg-soft-error, #FAEAEE)",
            border: "1px solid var(--color-error, #8E1938)",
            borderRadius: "8px",
            color: "var(--color-error, #8E1938)",
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
          {/* Sub-Table Navigation Switcher */}
          <div
            style={{
              display: "flex",
              justifyContent: "space-between",
              alignItems: "center",
              flexWrap: "wrap",
              gap: "8px",
            }}
          >
            <div style={{ display: "flex", alignItems: "center", gap: "6px", flexWrap: "wrap" }}>
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
          </div>

          {/* TABLE A: ENTITIES TABLE */}
          {(activeTableTab === "all" || activeTableTab === "entities") && (
            <div style={{ background: bgSurface, border: `1px solid ${borderCol}`, borderRadius: "10px", padding: "16px", display: "flex", flexDirection: "column", gap: "10px" }}>
              <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
                <h3 style={{ margin: 0, fontSize: "0.95rem", fontWeight: 700, color: textPrimary, display: "flex", alignItems: "center", gap: "6px" }}>
                  <Layers size={15} color={brandPrimary} />
                  Entities Table ({entities.length})
                </h3>
                <span style={{ fontSize: "0.75rem", color: textSecondary }}>
                  Core business concepts represented across sheets
                </span>
              </div>
              <DataTable
                columns={entityColumns}
                rows={enrichedEntities}
                rowKeyProp="_rowKey"
                defaultSortCol="sheet_id"
                defaultSortDir="asc"
                secondarySortCol="entity_id"
                secondarySortDir="asc"
                filters={entityFilters}
                searchFields={["entity_id", "concept", "sheet_id", "row_grain"]}
                searchPlaceholder="Search entities or sheets..."
                pageSize={25}
                enableColumnVisibility={false}
                tableAriaLabel="Business entities table"
                emptyMessage="No entity definitions established for this view."
              />
            </div>
          )}

          {/* TABLE B: SEMANTIC COLUMNS TABLE */}
          {(activeTableTab === "all" || activeTableTab === "columns") && (
            <div style={{ background: bgSurface, border: `1px solid ${borderCol}`, borderRadius: "10px", padding: "16px", display: "flex", flexDirection: "column", gap: "12px" }}>
              <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", flexWrap: "wrap", gap: "8px" }}>
                <div>
                  <h3 style={{ margin: 0, fontSize: "0.95rem", fontWeight: 700, color: textPrimary, display: "flex", alignItems: "center", gap: "6px" }}>
                    <Table size={15} color={brandPrimary} />
                    Semantic Columns Table ({displayedColumns.length} of {columns.length})
                  </h3>
                  <span style={{ fontSize: "0.75rem", color: textSecondary }}>
                    Click row or Inspect to examine value distributions and column diagnostics
                  </span>
                </div>

                {/* Quick Role Filters Pills */}
                <div style={{ display: "flex", alignItems: "center", gap: "6px", flexWrap: "wrap" }}>
                  <span style={{ fontSize: "0.74rem", color: textSecondary, fontWeight: 600, display: "flex", alignItems: "center", gap: "4px" }}>
                    <Filter size={12} /> Filter Role:
                  </span>
                  {[
                    { id: "all", label: `All (${roleCounts.total})` },
                    { id: "identifiers", label: `Identifiers (${roleCounts.identifiers})` },
                    { id: "metrics", label: `Metrics (${roleCounts.metrics})` },
                    { id: "dimensions", label: `Dimensions (${roleCounts.dimensions})` },
                    { id: "source", label: `Source (${roleCounts.source})` },
                    { id: "derived", label: `Derived (${roleCounts.derived})` },
                  ].map((rf) => {
                    const isSelected = quickRoleFilter === rf.id;
                    return (
                      <button
                        key={rf.id}
                        type="button"
                        onClick={() => setQuickRoleFilter(rf.id)}
                        style={{
                          padding: "3px 8px",
                          fontSize: "0.72rem",
                          fontWeight: isSelected ? 700 : 500,
                          borderRadius: "6px",
                          border: isSelected ? `1px solid ${brandPrimary}` : `1px solid ${borderCol}`,
                          background: isSelected ? brandSoftBg : bgSubtle,
                          color: isSelected ? brandPrimary : textSecondary,
                          cursor: "pointer",
                          transition: "all 0.15s ease",
                        }}
                      >
                        {rf.label}
                      </button>
                    );
                  })}
                </div>
              </div>

              <DataTable
                columns={semanticColumnsConfig}
                rows={displayedColumns}
                rowKeyProp="_rowKey"
                onRowClick={(row) => setSelectedColumn(row)}
                selectedRowKey={selectedColumn?._rowKey}
                defaultSortCol="sheet_id"
                defaultSortDir="asc"
                secondarySortCol="original_position"
                secondarySortDir="asc"
                filters={semanticColumnsFilters}
                searchFields={["display_name", "column_id", "sheet_id", "concept", "role", "data_type"]}
                searchPlaceholder="Search columns, sheets, concepts..."
                pageSize={25}
                enableColumnVisibility={true}
                tableAriaLabel="Semantic columns table"
                emptyMessage="No columns matched your query or role filter."
              />
            </div>
          )}

          {/* TABLE C: CANDIDATE KEYS TABLE */}
          {(activeTableTab === "all" || activeTableTab === "keys") && (
            <div style={{ background: bgSurface, border: `1px solid ${borderCol}`, borderRadius: "10px", padding: "16px", display: "flex", flexDirection: "column", gap: "10px" }}>
              <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
                <h3 style={{ margin: 0, fontSize: "0.95rem", fontWeight: 700, color: textPrimary, display: "flex", alignItems: "center", gap: "6px" }}>
                  <Key size={15} color={brandPrimary} />
                  Candidate Keys Table ({keys.length})
                </h3>
                <span style={{ fontSize: "0.75rem", color: textSecondary }}>
                  Uniqueness analysis and identifier candidates
                </span>
              </div>
              <DataTable
                columns={keyColumnsConfig}
                rows={enrichedKeys}
                rowKeyProp="_rowKey"
                defaultSortCol="confidence"
                defaultSortDir="desc"
                secondarySortCol="uniqueness_pct"
                secondarySortDir="desc"
                filters={keyFilters}
                searchFields={["sheet_id", "key_label", "columns_str"]}
                searchPlaceholder="Search candidate keys or sheets..."
                pageSize={25}
                enableColumnVisibility={false}
                tableAriaLabel="Candidate keys table"
                emptyMessage="No reliable record identifier was found. Multi-attribute observations / non-unique rows."
              />
            </div>
          )}

          {/* TABLE D: REFERENCE ENRICHMENTS TABLE */}
          {(activeTableTab === "all" || activeTableTab === "enrichments") && (
            <div style={{ background: bgSurface, border: `1px solid ${borderCol}`, borderRadius: "10px", padding: "16px", display: "flex", flexDirection: "column", gap: "10px" }}>
              <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
                <h3 style={{ margin: 0, fontSize: "0.95rem", fontWeight: 700, color: textPrimary, display: "flex", alignItems: "center", gap: "6px" }}>
                  <MapPin size={15} color={brandPrimary} />
                  Reference Enrichments Table ({combinedEnrichments.length})
                </h3>
                <span style={{ fontSize: "0.75rem", color: textSecondary }}>
                  Standardized values derived from reference data
                </span>
              </div>
              <DataTable
                columns={enrichmentColumnsConfig}
                rows={combinedEnrichments}
                rowKeyProp="_rowKey"
                defaultSortCol="source_value"
                defaultSortDir="asc"
                secondarySortCol="derived_value"
                secondarySortDir="asc"
                filters={enrichmentFilters}
                searchFields={["source_value", "derived_value", "type"]}
                searchPlaceholder="Search source or derived values..."
                pageSize={25}
                enableColumnVisibility={false}
                tableAriaLabel="Reference enrichments table"
                emptyMessage="No reference enrichments applied to this dataset."
              />
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
