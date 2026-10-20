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
} from "lucide-react";

/**
 * HighView Data Explorer — Semantic Model
 * "Cards summarize. Tables compare. Drawers explain."
 * Provides 4 structured DataTable exploration surfaces:
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
  const [activeTableTab, setActiveTableTab] = useState("all"); // 'all' | 'entities' | 'columns' | 'keys' | 'enrichments'

  const bgSurface = themeTokens?.colors?.surface || "var(--color-bg-surface)";
  const borderCol = themeTokens?.colors?.borderSubtle || "var(--color-divider)";
  const textPrimary = themeTokens?.colors?.textPrimary || "var(--color-text-primary)";
  const textSecondary = themeTokens?.colors?.textSecondary || "var(--color-text-secondary)";
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

  // Flatten geo resolutions with enrichments for unified table
  const combinedEnrichments = useMemo(() => {
    const list = [...enrichments];
    geoResolutions.forEach((g) => {
      list.push({
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
        _rowKey: ent.entity_id || `entity-${idx}`,
        row_grain: matchingGrain?.grain_description || "Individual record observation",
        supporting_columns_str: ent.supporting_columns?.join(", ") || ent.primary_column || "—",
      };
    });
  }, [entities, grains]);

  // Enrich columns with provenance string and position index
  const enrichedColumns = useMemo(() => {
    return columns.map((col, idx) => {
      const isEnriched =
        col.provenance_type === "DERIVED_ENRICHMENT" ||
        col.provenance_type === "DERIVED_RELATIONAL";
      return {
        ...col,
        _rowKey: col.column_id || `col-${idx}`,
        original_position: idx,
        status_provenance: isEnriched ? "Derived" : "Source",
        measure_dim_label: col.measure_class || "Dimension",
      };
    });
  }, [columns]);

  // Enrich keys
  const enrichedKeys = useMemo(() => {
    return keys.map((k, idx) => {
      return {
        ...k,
        _rowKey: `key-${idx}`,
        key_label: k.columns?.join(" + ") || "Key",
        columns_str: k.columns?.join(", ") || "—",
        uniqueness_pct: k.unique_ratio_pct ?? 100,
      };
    });
  }, [keys]);

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
        label: "Row Grain",
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
        render: (val) => <StatusBadge status={val || "Established"} variant="neutral" size="xs" />,
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
          <strong style={{ color: textPrimary }}>{val || row.column_id}</strong>
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
        key: "concept",
        label: "Meaning",
        type: "text",
        sortable: true,
        defaultVisible: true,
        render: (val) => <span style={{ color: textSecondary }}>{val || "—"}</span>,
      },
      {
        key: "role",
        label: "Role",
        type: "text",
        sortable: true,
        defaultVisible: true,
        render: (val) => <span style={{ color: textSecondary }}>{val || "—"}</span>,
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
        key: "measure_dim_label",
        label: "Measure / Dim",
        type: "text",
        sortable: true,
        defaultVisible: true,
        render: (val) => <span style={{ color: textSecondary }}>{val}</span>,
      },
      {
        key: "unit",
        label: "Unit",
        type: "text",
        sortable: true,
        defaultVisible: false,
        render: (val) => <span style={{ color: textSecondary }}>{val || "—"}</span>,
      },
      {
        key: "privacy",
        label: "Privacy",
        type: "status",
        sortable: true,
        defaultVisible: false,
        render: (val) => <StatusBadge status={val} size="xs" />,
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
    [textPrimary, textSecondary]
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
        render: (val) => <span style={{ color: textPrimary, fontWeight: 600 }}>{val}</span>,
      },
      {
        key: "columns_str",
        label: "Columns",
        type: "text",
        sortable: true,
        render: (val) => <span style={{ fontFamily: "monospace", color: textSecondary }}>{val}</span>,
      },
      {
        key: "uniqueness_pct",
        label: "Uniqueness",
        type: "percentage",
        sortable: true,
        render: (val) => <span style={{ color: textSecondary }}>{val}% unique</span>,
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
        render: (val) => <StatusBadge status={val || "Candidate"} size="xs" />,
      },
    ],
    [textPrimary, textSecondary]
  );

  // 4. Enrichments Columns
  const enrichmentColumnsConfig = useMemo(
    () => [
      {
        key: "source_value",
        label: "Source Value",
        type: "text",
        sortable: true,
        render: (val) => <strong style={{ color: textPrimary }}>{val}</strong>,
      },
      {
        key: "derived_value",
        label: "Derived Value",
        type: "text",
        sortable: true,
        render: (val) => <span style={{ color: textPrimary }}>{val}</span>,
      },
      {
        key: "type",
        label: "Type",
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

  return (
    <div className="sdr-semantics-mode-container" style={{ display: "flex", flexDirection: "column", gap: "16px" }}>
      {/* Overview Cards (KPIs) */}
      <div
        style={{
          display: "grid",
          gridTemplateColumns: "repeat(auto-fit, minmax(200px, 1fr))",
          gap: "12px",
        }}
      >
        <div
          style={{
            background: bgSurface,
            border: `1px solid ${borderCol}`,
            borderRadius: "10px",
            padding: "14px 16px",
            display: "flex",
            alignItems: "center",
            gap: "12px",
          }}
        >
          <div style={{ width: "36px", height: "36px", borderRadius: "8px", background: brandSoftBg, display: "flex", alignItems: "center", justifyContent: "center" }}>
            <Layers size={18} color={brandPrimary} />
          </div>
          <div>
            <div style={{ fontSize: "1.2rem", fontWeight: 700, color: textPrimary }}>
              {entities.length}
            </div>
            <div style={{ fontSize: "0.75rem", color: textSecondary }}>
              Business Entities
            </div>
          </div>
        </div>

        <div
          style={{
            background: bgSurface,
            border: `1px solid ${borderCol}`,
            borderRadius: "10px",
            padding: "14px 16px",
            display: "flex",
            alignItems: "center",
            gap: "12px",
          }}
        >
          <div style={{ width: "36px", height: "36px", borderRadius: "8px", background: "var(--color-bg-soft-teal, #E7F3ED)", display: "flex", alignItems: "center", justifyContent: "center" }}>
            <Sparkles size={18} color="var(--color-success, #075443)" />
          </div>
          <div>
            <div style={{ fontSize: "1.2rem", fontWeight: 700, color: textPrimary }}>
              {columns.length}
            </div>
            <div style={{ fontSize: "0.75rem", color: textSecondary }}>
              Semantic Columns
            </div>
          </div>
        </div>

        <div
          style={{
            background: bgSurface,
            border: `1px solid ${borderCol}`,
            borderRadius: "10px",
            padding: "14px 16px",
            display: "flex",
            alignItems: "center",
            gap: "12px",
          }}
        >
          <div style={{ width: "36px", height: "36px", borderRadius: "8px", background: "var(--color-bg-soft-gold, #F6EDDA)", display: "flex", alignItems: "center", justifyContent: "center" }}>
            <Key size={18} color="var(--color-warning, #65470C)" />
          </div>
          <div>
            <div style={{ fontSize: "1.2rem", fontWeight: 700, color: textPrimary }}>
              {keys.length}
            </div>
            <div style={{ fontSize: "0.75rem", color: textSecondary }}>
              Candidate Keys
            </div>
          </div>
        </div>

        <div
          style={{
            background: bgSurface,
            border: `1px solid ${borderCol}`,
            borderRadius: "10px",
            padding: "14px 16px",
            display: "flex",
            alignItems: "center",
            gap: "12px",
          }}
        >
          <div style={{ width: "36px", height: "36px", borderRadius: "8px", background: "var(--color-bg-soft-blue, #EAF0F5)", display: "flex", alignItems: "center", justifyContent: "center" }}>
            <MapPin size={18} color="var(--color-brand-primary, #183B56)" />
          </div>
          <div>
            <div style={{ fontSize: "1.2rem", fontWeight: 700, color: textPrimary }}>
              {combinedEnrichments.length}
            </div>
            <div style={{ fontSize: "0.75rem", color: textSecondary }}>
              Reference Enrichments
            </div>
          </div>
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
            <div style={{ background: bgSurface, border: `1px solid ${borderCol}`, borderRadius: "10px", padding: "16px", display: "flex", flexDirection: "column", gap: "10px" }}>
              <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
                <h3 style={{ margin: 0, fontSize: "0.95rem", fontWeight: 700, color: textPrimary, display: "flex", alignItems: "center", gap: "6px" }}>
                  <Table size={15} color={brandPrimary} />
                  Semantic Columns Table ({columns.length})
                </h3>
                <span style={{ fontSize: "0.75rem", color: textSecondary }}>
                  Click row or Inspect to examine value distributions and column diagnostics
                </span>
              </div>
              <DataTable
                columns={semanticColumnsConfig}
                rows={enrichedColumns}
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
                emptyMessage="No columns matched your query."
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
                rowKeyProp={(r, i) => `enrich-${i}`}
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
