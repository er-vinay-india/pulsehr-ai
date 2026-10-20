import React, { useState, useEffect, useMemo } from "react";
import { getExplorerRelationships } from "../../../api/client";
import StatusBadge from "../common/StatusBadge";
import DataTable from "../../DataTable";
import { SkeletonBlock } from "../../loaders";
import {
  GitMerge,
  ShieldCheck,
  AlertTriangle,
  Layers,
  Table,
  Network,
  X,
  Eye,
  AlertCircle,
} from "lucide-react";

/**
 * HighView Data Explorer — Relationships
 * Governed cross-sheet connections, verified key integrity, and safe aggregation rules.
 * Uses shared Enterprise DataTable with type-aware sorting, governed status ranking,
 * compact search, column visibility, and detail drawer.
 */
export default function RelationshipsMode({
  datasetId,
  sheets = [],
  selectedSheetId,
  onSelectSheet,
  themeTokens,
  isDark = false,
}) {
  const [activeSheet, setActiveSheet] = useState(() => selectedSheetId || "");
  const [relData, setRelData] = useState(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);
  const [selectedRel, setSelectedRel] = useState(null);
  const [safetyFilter, setSafetyFilter] = useState("ALL"); // 'ALL' | 'SAFE' | 'AGG' | 'UNSAFE'
  const [viewMode, setViewMode] = useState("table"); // 'table' | 'graph'

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

    async function loadRelationships() {
      setLoading(true);
      setError(null);
      try {
        const res = await getExplorerRelationships(datasetId, activeSheet || null);
        if (!isCancelled) {
          setRelData(res);
        }
      } catch (err) {
        if (!isCancelled) {
          setError(err.message || "Failed to load relationships");
        }
      } finally {
        if (!isCancelled) {
          setLoading(false);
        }
      }
    }

    loadRelationships();
    return () => {
      isCancelled = true;
    };
  }, [datasetId, activeSheet]);

  const handleSheetFilter = (sheetId) => {
    setActiveSheet(sheetId);
    if (onSelectSheet) onSelectSheet(sheetId);
  };

  const allRelationships = relData?.relationships || [];

  // Filter based on safety pill
  const pillFilteredRelationships = useMemo(() => {
    if (safetyFilter === "SAFE") {
      return allRelationships.filter((r) => r.safety_status_raw === "SAFE");
    }
    if (safetyFilter === "AGG") {
      return allRelationships.filter((r) => r.safety_status_raw === "AGGREGATION_REQUIRED");
    }
    if (safetyFilter === "UNSAFE") {
      return allRelationships.filter(
        (r) =>
          r.safety_status_raw === "UNSAFE_FANOUT" ||
          r.safety_status_raw === "UNSAFE_GRAIN_MISMATCH" ||
          r.safety_status_raw === "NEEDS_REVIEW"
      );
    }
    return allRelationships;
  }, [allRelationships, safetyFilter]);

  const summary = relData?.summary || {
    total_relationships: allRelationships.length,
    safe_joins: allRelationships.filter((r) => r.safety_status_raw === "SAFE").length,
    aggregation_required: allRelationships.filter((r) => r.safety_status_raw === "AGGREGATION_REQUIRED").length,
    unsafe_blocked: allRelationships.filter((r) => r.safety_status_raw?.startsWith("UNSAFE")).length,
  };

  // DataTable column definitions
  const relationshipColumns = useMemo(
    () => [
      {
        key: "left_sheet",
        label: "From Sheet",
        type: "text",
        sortable: true,
        defaultVisible: true,
        render: (val) => <strong style={{ color: textPrimary }}>{val}</strong>,
      },
      {
        key: "left_columns",
        label: "From Key",
        type: "text",
        sortable: true,
        defaultVisible: false,
        render: (val) => (
          <span style={{ fontFamily: "monospace", color: textSecondary }}>
            {Array.isArray(val) ? val.join(", ") : String(val ?? "—")}
          </span>
        ),
      },
      {
        key: "right_sheet",
        label: "To Sheet",
        type: "text",
        sortable: true,
        defaultVisible: true,
        render: (val) => <strong style={{ color: textPrimary }}>{val}</strong>,
      },
      {
        key: "right_columns",
        label: "To Key",
        type: "text",
        sortable: true,
        defaultVisible: false,
        render: (val) => (
          <span style={{ fontFamily: "monospace", color: textSecondary }}>
            {Array.isArray(val) ? val.join(", ") : String(val ?? "—")}
          </span>
        ),
      },
      {
        key: "cardinality",
        label: "Cardinality",
        type: "text",
        sortable: true,
        defaultVisible: true,
        render: (val) => <span style={{ color: textSecondary }}>{val}</span>,
      },
      {
        key: "coverage_left_pct",
        label: "Coverage",
        type: "percentage",
        sortable: true,
        defaultVisible: true,
        render: (val, row) => (
          <span style={{ color: textSecondary }}>{row.coverage_summary || `${val}%`}</span>
        ),
      },
      {
        key: "safety_status",
        label: "Safety",
        type: "status",
        sortable: true,
        defaultVisible: true,
        statusRankOrder: ["Safe to join", "Safe after aggregation", "Needs review", "Unsafe to join"],
        render: (val) => <StatusBadge status={val} />,
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
              setSelectedRel(row);
            }}
            aria-label={`View details for connection ${row.left_sheet} to ${row.right_sheet}`}
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
            Details
          </button>
        ),
      },
    ],
    [textPrimary, textSecondary]
  );

  // DataTable filter definitions
  const relationshipFilters = useMemo(
    () => [
      {
        key: "safety_status",
        label: "Safety",
        options: ["Safe to join", "Safe after aggregation", "Needs review", "Unsafe to join"],
      },
      {
        key: "cardinality",
        label: "Cardinality",
      },
      {
        key: "left_sheet",
        label: "From Sheet",
      },
      {
        key: "right_sheet",
        label: "To Sheet",
      },
    ],
    []
  );

  return (
    <div className="sdr-relationships-mode-container" style={{ display: "flex", flexDirection: "column", gap: "16px" }}>
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
            <GitMerge size={18} color={brandPrimary} />
          </div>
          <div>
            <div style={{ fontSize: "1.2rem", fontWeight: 700, color: textPrimary }}>
              {summary.total_relationships}
            </div>
            <div style={{ fontSize: "0.75rem", color: textSecondary }}>
              Validated Connections
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
            <ShieldCheck size={18} color="var(--color-success, #075443)" />
          </div>
          <div>
            <div style={{ fontSize: "1.2rem", fontWeight: 700, color: textPrimary }}>
              {summary.safe_joins}
            </div>
            <div style={{ fontSize: "0.75rem", color: textSecondary }}>
              Direct Safe Joins
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
            <Layers size={18} color="var(--color-warning, #65470C)" />
          </div>
          <div>
            <div style={{ fontSize: "1.2rem", fontWeight: 700, color: textPrimary }}>
              {summary.aggregation_required}
            </div>
            <div style={{ fontSize: "0.75rem", color: textSecondary }}>
              Preaggregation Required
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
          <div style={{ width: "36px", height: "36px", borderRadius: "8px", background: "var(--color-bg-soft-error, #FAEAEE)", display: "flex", alignItems: "center", justifyContent: "center" }}>
            <AlertTriangle size={18} color="var(--color-error, #8E1938)" />
          </div>
          <div>
            <div style={{ fontSize: "1.2rem", fontWeight: 700, color: textPrimary }}>
              {summary.unsafe_blocked}
            </div>
            <div style={{ fontSize: "0.75rem", color: textSecondary }}>
              Unsafe Joins Blocked
            </div>
          </div>
        </div>
      </div>

      {/* Header and View Mode Switch */}
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
            <GitMerge size={18} color={brandPrimary} aria-hidden="true" />
            <h2 style={{ margin: 0, fontSize: "1.1rem", fontWeight: 700, color: textPrimary }}>
              Relationships & Join Intelligence
            </h2>
          </div>

          <div style={{ display: "flex", alignItems: "center", gap: "8px" }}>
            {/* View Mode Toggle: Table (default) vs Graph */}
            <div
              style={{
                display: "inline-flex",
                background: bgSubtle,
                padding: "2px",
                borderRadius: "8px",
                border: `1px solid ${borderCol}`,
              }}
            >
              <button
                type="button"
                onClick={() => setViewMode("table")}
                aria-pressed={viewMode === "table"}
                style={{
                  display: "inline-flex",
                  alignItems: "center",
                  gap: "5px",
                  padding: "5px 10px",
                  fontSize: "0.78rem",
                  fontWeight: viewMode === "table" ? 700 : 500,
                  borderRadius: "6px",
                  border: "none",
                  background: viewMode === "table" ? bgSurface : "transparent",
                  color: viewMode === "table" ? brandPrimary : textSecondary,
                  cursor: "pointer",
                  boxShadow: viewMode === "table" ? "0 1px 3px rgba(0,0,0,0.08)" : "none",
                }}
              >
                <Table size={13} />
                Table
              </button>
              <button
                type="button"
                onClick={() => setViewMode("graph")}
                aria-pressed={viewMode === "graph"}
                style={{
                  display: "inline-flex",
                  alignItems: "center",
                  gap: "5px",
                  padding: "5px 10px",
                  fontSize: "0.78rem",
                  fontWeight: viewMode === "graph" ? 700 : 500,
                  borderRadius: "6px",
                  border: "none",
                  background: viewMode === "graph" ? bgSurface : "transparent",
                  color: viewMode === "graph" ? brandPrimary : textSecondary,
                  cursor: "pointer",
                  boxShadow: viewMode === "graph" ? "0 1px 3px rgba(0,0,0,0.08)" : "none",
                }}
              >
                <Network size={13} />
                Graph
              </button>
            </div>
          </div>
        </div>

        <p style={{ margin: 0, fontSize: "0.82rem", color: textSecondary }}>
          Governed connections between sheets, verified key integrity, and safe aggregation rules.
        </p>

        {/* Sheet Selector Pills (if workbook has multiple sheets) */}
        {sheets && sheets.length > 0 && (
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
        )}

        {/* Safety Filter Tabs */}
        <div style={{ display: "flex", alignItems: "center", gap: "6px", overflowX: "auto", paddingTop: "4px" }}>
          {[
            { id: "ALL", label: `All Connections (${allRelationships.length})` },
            { id: "SAFE", label: "Safe to Join" },
            { id: "AGG", label: "Safe After Aggregation" },
            { id: "UNSAFE", label: "Unsafe / Review" },
          ].map((f) => {
            const isActive = safetyFilter === f.id;
            return (
              <button
                key={f.id}
                type="button"
                onClick={() => setSafetyFilter(f.id)}
                style={{
                  padding: "6px 12px",
                  fontSize: "0.8rem",
                  fontWeight: isActive ? 700 : 500,
                  borderRadius: "8px",
                  border: isActive ? `1px solid ${brandPrimary}` : `1px solid ${borderCol}`,
                  background: isActive ? brandSoftBg : "transparent",
                  color: isActive ? brandPrimary : textSecondary,
                  cursor: "pointer",
                  whiteSpace: "nowrap",
                  transition: "all 0.15s ease",
                }}
              >
                {f.label}
              </button>
            );
          })}
        </div>
      </div>

      {loading ? (
        <div
          role="status"
          aria-label="Loading relationship intelligence"
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
          <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
            <span style={{ fontSize: "0.82rem", fontWeight: 600, color: textSecondary }}>
              Loading relationship intelligence…
            </span>
          </div>
          <SkeletonBlock variant="table-row" count={6} columns={6} />
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
      ) : allRelationships.length === 0 ? (
        <section
          style={{
            background: bgSurface,
            border: `1px solid ${borderCol}`,
            borderRadius: "10px",
            padding: "48px 24px",
            textAlign: "center",
          }}
        >
          <div style={{ width: "48px", height: "48px", borderRadius: "24px", background: brandSoftBg, display: "flex", alignItems: "center", justifyContent: "center", margin: "0 auto 16px" }}>
            <GitMerge size={24} color={brandPrimary} />
          </div>
          <h3 style={{ margin: "0 0 8px", fontSize: "1.1rem", fontWeight: 700, color: textPrimary }}>
            No validated relationships were found
          </h3>
          <p style={{ fontSize: "0.85rem", color: textSecondary, maxWidth: "480px", margin: "0 auto", lineHeight: 1.5 }}>
            This dataset either has a single sheet or contains no cross-sheet keys matching verified uniqueness constraints.
          </p>
        </section>
      ) : viewMode === "graph" ? (
        /* OPTIONAL TOPOLOGY GRAPH VIEW */
        <div style={{ background: bgSurface, border: `1px solid ${borderCol}`, borderRadius: "10px", padding: "20px" }}>
          <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: "16px" }}>
            <h3 style={{ margin: 0, fontSize: "0.9rem", fontWeight: 700, color: textPrimary }}>
              Sheet Topology Graph
            </h3>
            <span style={{ fontSize: "0.75rem", color: textSecondary }}>
              Visual map of cross-sheet connections
            </span>
          </div>
          <div style={{ display: "flex", flexWrap: "wrap", gap: "16px", alignItems: "center", justifyContent: "center", minHeight: "220px", padding: "20px" }}>
            {relData?.graph?.nodes?.map((node) => (
              <div
                key={node.id}
                style={{
                  padding: "12px 18px",
                  borderRadius: "8px",
                  border: `1px solid ${borderStrong}`,
                  background: bgSubtle,
                  color: textPrimary,
                  fontWeight: 700,
                  fontSize: "0.85rem",
                  boxShadow: "0 2px 4px rgba(0,0,0,0.05)",
                }}
              >
                <Layers size={14} style={{ marginRight: "6px", display: "inline" }} />
                {node.name}
              </div>
            ))}
          </div>
        </div>
      ) : (
        /* PRIMARY DATA TABLE VIEW */
        <DataTable
          columns={relationshipColumns}
          rows={pillFilteredRelationships}
          rowKeyProp="relationship_id"
          onRowClick={(row) => setSelectedRel(row)}
          selectedRowKey={selectedRel?.relationship_id}
          defaultSortCol="safety_status"
          defaultSortDir="asc"
          secondarySortCol="left_sheet"
          secondarySortDir="asc"
          filters={relationshipFilters}
          searchFields={["left_sheet", "right_sheet", "cardinality", "safety_status"]}
          searchPlaceholder="Search sheets, keys, or cardinality..."
          pageSize={25}
          enableColumnVisibility={true}
          tableAriaLabel="Validated relationships table"
          emptyMessage="No relationships match the selected filters."
        />
      )}

      {/* Connection Details Drawer (Progressive Disclosure) */}
      {selectedRel && (
        <div
          role="dialog"
          aria-modal="true"
          aria-label="Relationship Details"
          style={{
            position: "fixed",
            top: 0,
            right: 0,
            bottom: 0,
            width: "min(480px, 92vw)",
            background: bgSurface,
            borderLeft: `1px solid ${borderStrong}`,
            boxShadow: "-4px 0 24px rgba(0,0,0,0.15)",
            zIndex: 1000,
            display: "flex",
            flexDirection: "column",
            animation: "slideInRight 0.2s ease",
          }}
        >
          {/* Drawer Header */}
          <div
            style={{
              padding: "16px 20px",
              borderBottom: `1px solid ${borderCol}`,
              display: "flex",
              justifyContent: "space-between",
              alignItems: "center",
            }}
          >
            <div>
              <div style={{ fontSize: "0.75rem", color: textSecondary, fontWeight: 700 }}>
                Connection Details
              </div>
              <h3 style={{ margin: "2px 0 0", fontSize: "1.05rem", fontWeight: 700, color: textPrimary }}>
                {selectedRel.left_sheet} ➔ {selectedRel.right_sheet}
              </h3>
            </div>
            <button
              type="button"
              onClick={() => setSelectedRel(null)}
              aria-label="Close drawer"
              style={{
                background: "transparent",
                border: "none",
                cursor: "pointer",
                color: textSecondary,
                padding: "4px",
              }}
            >
              <X size={18} />
            </button>
          </div>

          {/* Drawer Body */}
          <div style={{ padding: "20px", overflowY: "auto", display: "flex", flexDirection: "column", gap: "16px", flex: 1 }}>
            {/* Join Safety Status */}
            <div style={{ padding: "12px", borderRadius: "8px", background: bgSubtle, border: `1px solid ${borderCol}` }}>
              <div style={{ fontSize: "0.75rem", color: textSecondary, fontWeight: 600 }}>Safety Assessment</div>
              <div style={{ marginTop: "4px" }}>
                <StatusBadge status={selectedRel.safety_status} size="sm" />
              </div>
              <p style={{ margin: "8px 0 0", fontSize: "0.8rem", color: textSecondary, lineHeight: 1.4 }}>
                {selectedRel.safety_status_raw === "SAFE"
                  ? "This join preserves unique row grain and introduces zero fan-out risk."
                  : selectedRel.preaggregation_explanation
                  ? selectedRel.preaggregation_explanation
                  : "Aggregation must be performed before joining to avoid duplicate metric counts."}
              </p>
            </div>

            {/* Key Alignment Table */}
            <div>
              <div style={{ fontSize: "0.8rem", fontWeight: 700, color: textPrimary, marginBottom: "8px" }}>
                Key Mapping
              </div>
              <div style={{ border: `1px solid ${borderCol}`, borderRadius: "8px", overflow: "hidden" }}>
                <table style={{ width: "100%", fontSize: "0.8rem", borderCollapse: "collapse" }}>
                  <tbody>
                    <tr style={{ borderBottom: `1px solid ${borderCol}` }}>
                      <td style={{ padding: "8px 12px", color: textSecondary, width: "35%" }}>Left Sheet</td>
                      <td style={{ padding: "8px 12px", fontWeight: 600, color: textPrimary }}>{selectedRel.left_sheet}</td>
                    </tr>
                    <tr style={{ borderBottom: `1px solid ${borderCol}` }}>
                      <td style={{ padding: "8px 12px", color: textSecondary }}>Left Keys</td>
                      <td style={{ padding: "8px 12px", fontFamily: "monospace", color: textPrimary }}>{selectedRel.left_columns?.join(", ")}</td>
                    </tr>
                    <tr style={{ borderBottom: `1px solid ${borderCol}` }}>
                      <td style={{ padding: "8px 12px", color: textSecondary }}>Right Sheet</td>
                      <td style={{ padding: "8px 12px", fontWeight: 600, color: textPrimary }}>{selectedRel.right_sheet}</td>
                    </tr>
                    <tr style={{ borderBottom: `1px solid ${borderCol}` }}>
                      <td style={{ padding: "8px 12px", color: textSecondary }}>Right Keys</td>
                      <td style={{ padding: "8px 12px", fontFamily: "monospace", color: textPrimary }}>{selectedRel.right_columns?.join(", ")}</td>
                    </tr>
                    <tr style={{ borderBottom: `1px solid ${borderCol}` }}>
                      <td style={{ padding: "8px 12px", color: textSecondary }}>Cardinality</td>
                      <td style={{ padding: "8px 12px", color: textPrimary }}>{selectedRel.cardinality}</td>
                    </tr>
                    <tr>
                      <td style={{ padding: "8px 12px", color: textSecondary }}>Coverage</td>
                      <td style={{ padding: "8px 12px", color: textPrimary }}>{selectedRel.coverage_summary || `${selectedRel.coverage_left_pct}%`}</td>
                    </tr>
                  </tbody>
                </table>
              </div>
            </div>

            {/* Technical Details (Progressive Disclosure) */}
            <details style={{ marginTop: "8px" }}>
              <summary style={{ cursor: "pointer", fontSize: "0.78rem", color: textSecondary, fontWeight: 600 }}>
                Technical Details
              </summary>
              <div style={{ marginTop: "8px", padding: "10px", background: bgSubtle, borderRadius: "6px", fontSize: "0.75rem", fontFamily: "monospace", color: textSecondary, overflowX: "auto" }}>
                <div>Relationship ID: {selectedRel.relationship_id}</div>
                <div>Join Method: {selectedRel.join_plan_id || "Direct"}</div>
                <div>Target Grain: {selectedRel.result_grain || "PRESERVED"}</div>
              </div>
            </details>
          </div>
        </div>
      )}
    </div>
  );
}
