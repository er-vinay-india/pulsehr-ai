import React, { useState, useEffect, useMemo } from "react";
import { getExplorerAnalyticalViews, getExplorerAnalyticalFacts } from "../../../api/client";
import LineageDrawer from "./LineageDrawer";
import StatusBadge from "../common/StatusBadge";
import DataTable from "../../DataTable";
import { SkeletonBlock } from "../../loaders";
import {
  LineChart,
  Table,
  GitBranch,
  ShieldAlert,
  AlertTriangle,
  Award,
  Layers,
  Clock,
  Eye,
  AlertCircle,
} from "lucide-react";

/**
 * HighView Data Explorer — Analytical Views & Facts
 * Governed analysis calculations, virtual views, freshness gating, and metric lineage.
 * Uses shared Enterprise DataTable for both:
 * 1. Analysis Views Table
 * 2. Analytical Facts Table (with true underlying numeric value sorting)
 */
export default function AnalyticalViewsMode({
  datasetId,
  themeTokens,
  isDark = false,
  edaReport = null,
  rankingSchema = null,
  selectedSheet = null,
  initialSubView = "views",
}) {
  const [viewsData, setViewsData] = useState(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);
  const [selectedViewId, setSelectedViewId] = useState(null);
  const [selectedFact, setSelectedFact] = useState(null);

  const bgSurface = themeTokens?.colors?.surface || "var(--color-bg-surface)";
  const borderCol = themeTokens?.colors?.borderSubtle || "var(--color-divider)";
  const textPrimary = themeTokens?.colors?.textPrimary || "var(--color-text-primary)";
  const textSecondary = themeTokens?.colors?.textSecondary || "var(--color-text-secondary)";
  const brandPrimary = themeTokens?.colors?.brandPrimary || "var(--color-brand-primary)";
  const brandSoftBg = themeTokens?.colors?.softBlue || "var(--color-bg-soft-blue)";

  useEffect(() => {
    if (!datasetId) return;
    let isCancelled = false;

    async function loadViews() {
      setLoading(true);
      setError(null);
      try {
        const res = await getExplorerAnalyticalViews(datasetId);
        if (!isCancelled) {
          setViewsData(res);
          const views = res?.views || [];
          if (views.length > 0 && !selectedViewId) {
            setSelectedViewId(views[0].view_id);
          }
        }
      } catch (err) {
        if (!isCancelled) {
          setError(err.message || "Failed to load analytical views");
        }
      } finally {
        if (!isCancelled) {
          setLoading(false);
        }
      }
    }

    loadViews();
    return () => {
      isCancelled = true;
    };
  }, [datasetId]);

  const allViews = viewsData?.views || [];
  const allFacts = viewsData?.facts || [];

  const activeView = allViews.find((v) => v.view_id === selectedViewId) || allViews[0];

  // Facts for the active view
  const currentViewFacts = useMemo(() => {
    if (!activeView) return [];
    return allFacts.filter((f) => f.analytical_view_id === activeView.view_id);
  }, [allFacts, activeView]);

  // Enrich Views for DataTable
  const enrichedViews = useMemo(() => {
    return allViews.map((v) => {
      const isStale = Boolean(v.is_stale);
      return {
        ...v,
        _rowKey: v.view_id,
        source_sheets_str: v.source_sheets?.join(", ") || "—",
        measures_str:
          v.derived_measures?.map((m) => m.measure_name).join(", ") ||
          v.measure_columns?.join(", ") ||
          "—",
        freshness: isStale ? "Needs refresh" : "Current",
        mode_label: v.materialization_mode || "virtual",
      };
    });
  }, [allViews]);

  // Enrich Facts for DataTable
  const enrichedFacts = useMemo(() => {
    return currentViewFacts.map((fact, idx) => {
      const numVal =
        typeof fact.exact_value === "number"
          ? fact.exact_value
          : Number(String(fact.exact_value || fact.value || 0).replace(/[^0-9.-]+/g, ""));
      return {
        ...fact,
        _rowKey: fact.fact_id || `fact-${idx}`,
        numeric_value: isNaN(numVal) ? 0 : numVal,
        unit_str: fact.unit || "—",
        grain_str: fact.grain || "RECORD",
        denominator_str: fact.denominator || "—",
        provenance_str: fact.provenance || "Reconstructed",
        status_str: fact.status || "Verified",
      };
    });
  }, [currentViewFacts]);

  // =========================================================================
  // VIEW COLUMNS CONFIG
  // =========================================================================

  const viewColumns = useMemo(
    () => [
      {
        key: "name",
        label: "Analysis Name",
        type: "text",
        sortable: true,
        render: (val) => <strong style={{ color: textPrimary }}>{val}</strong>,
      },
      {
        key: "source_sheets_str",
        label: "Source Data",
        type: "text",
        sortable: true,
        render: (val) => <span style={{ color: textSecondary }}>{val}</span>,
      },
      {
        key: "result_grain",
        label: "Result Grain",
        type: "text",
        sortable: true,
        render: (val) => <span style={{ color: textSecondary }}>{val}</span>,
      },
      {
        key: "measures_str",
        label: "Measures",
        type: "text",
        sortable: true,
        render: (val) => <span style={{ color: textSecondary }}>{val}</span>,
      },
      {
        key: "status",
        label: "Status",
        type: "status",
        sortable: true,
        render: (val) => <StatusBadge status={val} size="xs" />,
      },
      {
        key: "freshness",
        label: "Freshness",
        type: "status",
        sortable: true,
        statusRankOrder: ["Current", "Needs refresh", "Stale"],
        render: (val, row) => (
          <StatusBadge
            status={val}
            variant={row.is_stale ? "warning" : "success"}
            size="xs"
          />
        ),
      },
      {
        key: "mode_label",
        label: "Mode",
        type: "status",
        sortable: true,
        render: (val) => <StatusBadge status={val} variant="info" size="xs" />,
      },
      {
        key: "actions",
        label: "Action",
        sortable: false,
        align: "right",
        render: (_, row) => {
          const isSelected = row.view_id === selectedViewId;
          return (
            <button
              type="button"
              className="btn-secondary"
              onClick={(e) => {
                e.stopPropagation();
                setSelectedViewId(row.view_id);
              }}
              aria-label={`Select analysis ${row.name}`}
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
                background: isSelected ? "var(--color-brand-primary, #183B56)" : undefined,
                color: isSelected ? "#ffffff" : undefined,
              }}
            >
              <Eye size={12} />
              {isSelected ? "Selected" : "Select"}
            </button>
          );
        },
      },
    ],
    [textPrimary, textSecondary, selectedViewId]
  );

  const viewFilters = useMemo(
    () => [
      { key: "freshness", label: "Freshness", options: ["Current", "Needs refresh"] },
      { key: "status", label: "Status" },
      { key: "mode_label", label: "Mode", options: ["virtual", "materialized"] },
    ],
    []
  );

  // =========================================================================
  // FACT COLUMNS CONFIG (With Underlying Numeric Value Sorting)
  // =========================================================================

  const factColumns = useMemo(
    () => [
      {
        key: "metric_name",
        label: "Metric",
        type: "text",
        sortable: true,
        render: (val) => <strong style={{ color: textPrimary }}>{val}</strong>,
      },
      {
        key: "numeric_value",
        label: "Value",
        type: "number",
        sortable: true,
        align: "right",
        sortKey: (row) => row.numeric_value,
        render: (val, row) => (
          <span
            style={{
              fontWeight: 700,
              fontFamily: "monospace",
              color: brandPrimary,
            }}
            title={`Exact unrounded value: ${row.exact_value}`}
          >
            {row.formatted_value || String(row.exact_value)}
          </span>
        ),
      },
      {
        key: "unit_str",
        label: "Unit",
        type: "text",
        sortable: true,
        render: (val) => <span style={{ color: textSecondary }}>{val}</span>,
      },
      {
        key: "grain_str",
        label: "Grain",
        type: "text",
        sortable: true,
        render: (val) => <span style={{ color: textSecondary }}>{val}</span>,
      },
      {
        key: "denominator_str",
        label: "Denominator",
        type: "text",
        sortable: true,
        render: (val) => <span style={{ color: textSecondary }}>{val}</span>,
      },
      {
        key: "provenance_str",
        label: "Source",
        type: "text",
        sortable: true,
        render: (val) => <span style={{ color: textSecondary }}>{val}</span>,
      },
      {
        key: "status_str",
        label: "Status",
        type: "status",
        sortable: true,
        render: (val) => <StatusBadge status={val} size="xs" />,
      },
      {
        key: "actions",
        label: "Lineage",
        sortable: false,
        align: "right",
        render: (_, row) => (
          <button
            type="button"
            className="btn-secondary"
            onClick={() => setSelectedFact(row)}
            aria-label={`View step-by-step lineage for ${row.metric_name}`}
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
            <GitBranch size={12} />
            Lineage
          </button>
        ),
      },
    ],
    [textPrimary, textSecondary, brandPrimary]
  );

  const factFilters = useMemo(
    () => [
      { key: "unit_str", label: "Unit" },
      { key: "grain_str", label: "Grain" },
      { key: "provenance_str", label: "Provenance" },
      { key: "status_str", label: "Status" },
    ],
    []
  );

  return (
    <div className="sdr-analytical-views-container" style={{ display: "flex", flexDirection: "column", gap: "16px" }}>
      {/* Header & Freshness Protection Banner */}
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
            <LineChart size={18} color={brandPrimary} aria-hidden="true" />
            <h2 style={{ margin: 0, fontSize: "1.1rem", fontWeight: 700, color: textPrimary }}>
              Governed Analysis & Metrics
            </h2>
          </div>
          <div style={{ display: "flex", alignItems: "center", gap: "8px", flexWrap: "wrap" }}>
            <StatusBadge status="Automated lineage" variant="success" />
            <StatusBadge status="Stale views blocked" variant="warning" />
          </div>
        </div>
        <p style={{ margin: 0, fontSize: "0.82rem", color: textSecondary }}>
          Governed analytical measures, verified calculation lineage, and strict freshness gating.
        </p>
      </div>

      {loading ? (
        <div
          role="status"
          aria-label="Loading analytical views"
          style={{
            display: "flex",
            flexDirection: "column",
            gap: "16px",
          }}
        >
          <SkeletonBlock variant="card" count={3} />
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
            <SkeletonBlock variant="table-row" count={6} columns={6} />
          </div>
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
      ) : allViews.length === 0 ? (
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
            <LineChart size={24} color={brandPrimary} />
          </div>
          <h3 style={{ margin: "0 0 8px", fontSize: "1.1rem", fontWeight: 700, color: textPrimary }}>
            No analytical views established
          </h3>
          <p style={{ fontSize: "0.85rem", color: textSecondary, maxWidth: "480px", margin: "0 auto", lineHeight: 1.5 }}>
            No governed analytical views have been generated yet for this dataset.
          </p>
        </section>
      ) : (
        <>
          {/* KPI Summary Cards */}
          <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(200px, 1fr))", gap: "12px" }}>
            <div style={{ background: bgSurface, border: `1px solid ${borderCol}`, borderRadius: "8px", padding: "12px 14px", display: "flex", alignItems: "center", gap: "10px" }}>
              <div style={{ padding: "8px", borderRadius: "6px", background: brandSoftBg, color: brandPrimary, display: "flex" }}>
                <Layers size={16} />
              </div>
              <div>
                <div style={{ fontSize: "1.1rem", fontWeight: 700, color: textPrimary }}>{allViews.length}</div>
                <div style={{ fontSize: "0.75rem", color: textSecondary }}>Analytical Views</div>
              </div>
            </div>

            <div style={{ background: bgSurface, border: `1px solid ${borderCol}`, borderRadius: "8px", padding: "12px 14px", display: "flex", alignItems: "center", gap: "10px" }}>
              <div style={{ padding: "8px", borderRadius: "6px", background: brandSoftBg, color: brandPrimary, display: "flex" }}>
                <Award size={16} />
              </div>
              <div>
                <div style={{ fontSize: "1.1rem", fontWeight: 700, color: textPrimary }}>{allFacts.length}</div>
                <div style={{ fontSize: "0.75rem", color: textSecondary }}>Verified Facts</div>
              </div>
            </div>

            <div style={{ background: bgSurface, border: `1px solid ${borderCol}`, borderRadius: "8px", padding: "12px 14px", display: "flex", alignItems: "center", gap: "10px" }}>
              <div style={{ padding: "8px", borderRadius: "6px", background: brandSoftBg, color: brandPrimary, display: "flex" }}>
                <Clock size={16} />
              </div>
              <div>
                <div style={{ fontSize: "1.1rem", fontWeight: 700, color: textPrimary }}>
                  {allViews.filter((v) => !v.is_stale).length} / {allViews.length} Current
                </div>
                <div style={{ fontSize: "0.75rem", color: textSecondary }}>Freshness Status</div>
              </div>
            </div>
          </div>

          {/* TABLE 1: ANALYSIS VIEWS TABLE */}
          <div style={{ background: bgSurface, border: `1px solid ${borderCol}`, borderRadius: "10px", padding: "16px", display: "flex", flexDirection: "column", gap: "10px" }}>
            <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
              <h3 style={{ margin: 0, fontSize: "0.95rem", fontWeight: 700, color: textPrimary, display: "flex", alignItems: "center", gap: "6px" }}>
                <Table size={15} color={brandPrimary} />
                Analysis Views Table ({allViews.length})
              </h3>
              <span style={{ fontSize: "0.75rem", color: textSecondary }}>
                Select an analysis to inspect its metric facts and calculation lineage
              </span>
            </div>
            <DataTable
              columns={viewColumns}
              rows={enrichedViews}
              rowKeyProp="_rowKey"
              onRowClick={(row) => setSelectedViewId(row.view_id)}
              selectedRowKey={selectedViewId}
              defaultSortCol="freshness"
              defaultSortDir="asc"
              secondarySortCol="name"
              secondarySortDir="asc"
              filters={viewFilters}
              searchFields={["name", "source_sheets_str", "measures_str", "result_grain"]}
              searchPlaceholder="Search analytical views..."
              pageSize={25}
              enableColumnVisibility={false}
              tableAriaLabel="Analytical views table"
              emptyMessage="No analytical views match your search or filters."
            />
          </div>

          {/* Selected View Stale Warning Banner (if stale) */}
          {activeView?.is_stale && (
            <div
              style={{
                background: "var(--color-bg-soft-error, #FAEAEE)",
                border: "1px solid var(--color-error, #8E1938)",
                borderRadius: "8px",
                padding: "12px 14px",
                color: "var(--color-error, #8E1938)",
                display: "flex",
                alignItems: "flex-start",
                gap: "10px",
              }}
            >
              <AlertTriangle size={18} style={{ flexShrink: 0, marginTop: "2px" }} />
              <div>
                <div style={{ fontWeight: 700, fontSize: "0.88rem" }}>
                  Analysis Needs Refresh
                </div>
                <div style={{ fontSize: "0.8rem", marginTop: "2px", opacity: 0.9 }}>
                  {activeView.rejection_reason ||
                    "Upstream dependency drift detected. This view cannot be served as current truth until re-verified."}
                </div>
              </div>
            </div>
          )}

          {/* TABLE 2: ANALYTICAL FACTS TABLE */}
          <div style={{ background: bgSurface, border: `1px solid ${borderCol}`, borderRadius: "10px", padding: "16px", display: "flex", flexDirection: "column", gap: "10px" }}>
            <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
              <h3 style={{ margin: 0, fontSize: "0.95rem", fontWeight: 700, color: textPrimary, display: "flex", alignItems: "center", gap: "6px" }}>
                <Award size={15} color={brandPrimary} />
                Analytical Facts Table for "{activeView?.name || "Selected Analysis"}" ({currentViewFacts.length} facts)
              </h3>
              <span style={{ fontSize: "0.75rem", color: textSecondary }}>
                Exact metric values, denominators, and calculation lineage
              </span>
            </div>
            <DataTable
              columns={factColumns}
              rows={enrichedFacts}
              rowKeyProp="_rowKey"
              defaultSortCol="metric_name"
              defaultSortDir="asc"
              filters={factFilters}
              searchFields={["metric_name", "unit_str", "grain_str", "denominator_str", "provenance_str"]}
              searchPlaceholder="Search metrics or units..."
              pageSize={25}
              enableColumnVisibility={false}
              tableAriaLabel={`Analytical facts for ${activeView?.name}`}
              emptyMessage="No facts recorded for this view or matching filters."
            />
          </div>
        </>
      )}

      {/* Step-by-Step Lineage Drawer */}
      {selectedFact && (
        <LineageDrawer
          fact={selectedFact}
          onClose={() => setSelectedFact(null)}
          themeTokens={themeTokens}
          isDark={isDark}
        />
      )}
    </div>
  );
}
