import React, { useState, useEffect } from "react";
import { getExplorerAnalyticalViews } from "../../../api/client";
import LineageDrawer from "./LineageDrawer";
import StatusBadge from "../common/StatusBadge";
import RankingsExplorer from "../RankingsExplorer";
import TrendsExplorer from "../TrendsExplorer";
import DistributionsExplorer from "../DistributionsExplorer";
import {
  LayoutDashboard,
  ShieldCheck,
  AlertTriangle,
  Award,
  GitBranch,
  Layers,
  CheckCircle2,
  Clock,
  ArrowRight,
  Eye,
  AlertCircle,
  Table,
  TrendingUp,
  BarChart2,
} from "lucide-react";

/**
 * HighView Data Explorer — Analysis
 * "Cards summarize. Tables compare. Drawers explain."
 * Primary representation:
 * 1. Analysis Table (Reconstructed views, grains, freshness, modes)
 * 2. Analytical Facts Table (Full exact metric values, units, denominators, lineage)
 * Optional sub-tabs for Rankings, Trends, and Distributions.
 */
export default function AnalyticalViewsMode({
  datasetId,
  themeTokens,
  isDark = false,
  edaReport = null,
  rankingSchema = null,
  selectedSheet = null,
  initialSubView = "views", // 'views' | 'rankings' | 'trends' | 'distributions'
}) {
  const [viewsData, setViewsData] = useState(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);
  const [subView, setSubView] = useState(initialSubView || "views");
  const [selectedViewId, setSelectedViewId] = useState(null);
  const [selectedFact, setSelectedFact] = useState(null);

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
    if (!datasetId) return;
    let isCancelled = false;

    async function loadViews() {
      setLoading(true);
      setError(null);
      try {
        const res = await getExplorerAnalyticalViews(datasetId);
        if (!isCancelled) {
          setViewsData(res);
          if (res?.views?.length > 0) {
            setSelectedViewId(res.views[0].view_id);
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
  const filteredFacts = allFacts.filter((f) => !selectedViewId || f.analytical_view_id === selectedViewId);

  return (
    <div className="sdr-analytical-views-mode-container" style={{ display: "flex", flexDirection: "column", gap: "16px" }}>
      {/* Header & Sub-view Pills */}
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
            <LayoutDashboard size={18} color={brandPrimary} aria-hidden="true" />
            <h2 style={{ margin: 0, fontSize: "1.1rem", fontWeight: 700, color: textPrimary }}>
              Analysis
            </h2>
          </div>
          <div style={{ display: "flex", alignItems: "center", gap: "8px" }}>
            <StatusBadge status="Virtual Materialization" variant="info" />
            <StatusBadge status="Current" variant="success" />
          </div>
        </div>
        <p style={{ margin: 0, fontSize: "0.82rem", color: textSecondary }}>
          Governed analytical calculations, verified metrics, rankings, and trends.
        </p>

        {/* Sub-view Navigation */}
        <div style={{ display: "flex", alignItems: "center", gap: "6px", overflowX: "auto", paddingTop: "4px" }}>
          {[
            { id: "views", label: "Analytical Views & Facts", icon: Table },
            { id: "rankings", label: "Rankings", icon: Award },
            { id: "trends", label: "Trends", icon: TrendingUp },
            { id: "distributions", label: "Value Ranges", icon: BarChart2 },
          ].map((item) => {
            const Icon = item.icon;
            const isActive = subView === item.id;
            return (
              <button
                key={item.id}
                type="button"
                onClick={() => setSubView(item.id)}
                style={{
                  display: "inline-flex",
                  alignItems: "center",
                  gap: "6px",
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
                <Icon size={13} />
                <span>{item.label}</span>
              </button>
            );
          })}
        </div>
      </div>

      {/* Sub-view: Rankings */}
      {subView === "rankings" && (
        <RankingsExplorer
          datasetId={datasetId}
          themeTokens={themeTokens}
          isDark={isDark}
        />
      )}

      {/* Sub-view: Trends */}
      {subView === "trends" && (
        <TrendsExplorer
          edaReport={edaReport}
          rankingSchema={rankingSchema}
          selectedSheet={selectedSheet}
          themeTokens={themeTokens}
          isDark={isDark}
        />
      )}

      {/* Sub-view: Distributions */}
      {subView === "distributions" && (
        <DistributionsExplorer
          edaReport={edaReport}
          rankingSchema={rankingSchema}
          themeTokens={themeTokens}
          isDark={isDark}
        />
      )}

      {/* Primary Sub-view: Analytical Views & Facts */}
      {subView === "views" && (
        <>
          {loading ? (
            <div style={{ padding: "40px", textAlign: "center", color: textSecondary, fontSize: "0.9rem" }}>
              Loading analysis tables…
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
                <LayoutDashboard size={24} color={brandPrimary} />
              </div>
              <h3 style={{ margin: "0 0 8px", fontSize: "1.1rem", fontWeight: 700, color: textPrimary }}>
                No analytical views are available yet
              </h3>
              <p style={{ fontSize: "0.85rem", color: textSecondary, maxWidth: "480px", margin: "0 auto", lineHeight: 1.5 }}>
                Analytical views are synthesized from verified relationships and governed measures.
              </p>
            </section>
          ) : (
            <>
              {/* Top Summary Strip */}
              <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(220px, 1fr))", gap: "10px" }}>
                <div style={{ background: bgSurface, border: `1px solid ${borderCol}`, borderRadius: "8px", padding: "12px 14px", display: "flex", alignItems: "center", gap: "10px" }}>
                  <div style={{ padding: "8px", borderRadius: "6px", background: brandSoftBg, color: brandPrimary, display: "flex" }}>
                    <LayoutDashboard size={16} />
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
                      {allViews.filter(v => !v.is_stale).length} / {allViews.length} Current
                    </div>
                    <div style={{ fontSize: "0.75rem", color: textSecondary }}>Freshness Status</div>
                  </div>
                </div>
              </div>

              {/* TABLE 1: ANALYSIS VIEWS TABLE */}
              <div style={{ background: bgSurface, border: `1px solid ${borderCol}`, borderRadius: "10px", overflow: "hidden" }}>
                <div style={{ padding: "12px 16px", borderBottom: `1px solid ${borderCol}`, display: "flex", justifyContent: "space-between", alignItems: "center" }}>
                  <h3 style={{ margin: 0, fontSize: "0.9rem", fontWeight: 700, color: textPrimary, display: "flex", alignItems: "center", gap: "6px" }}>
                    <Table size={15} color={brandPrimary} />
                    Analysis Table ({allViews.length})
                  </h3>
                  <span style={{ fontSize: "0.75rem", color: textSecondary }}>
                    Select an analysis to inspect its metric facts and calculation lineage
                  </span>
                </div>
                <div style={{ overflowX: "auto" }}>
                  <table style={{ width: "100%", borderCollapse: "collapse", fontSize: "0.82rem", textAlign: "left" }}>
                    <thead>
                      <tr style={{ background: bgSubtle, borderBottom: `2px solid ${borderCol}` }}>
                        <th style={{ padding: "10px 12px", color: textPrimary, fontWeight: 700 }}>Analysis Name</th>
                        <th style={{ padding: "10px 12px", color: textPrimary, fontWeight: 700 }}>Source Data</th>
                        <th style={{ padding: "10px 12px", color: textPrimary, fontWeight: 700 }}>Result Grain</th>
                        <th style={{ padding: "10px 12px", color: textPrimary, fontWeight: 700 }}>Measures</th>
                        <th style={{ padding: "10px 12px", color: textPrimary, fontWeight: 700 }}>Status</th>
                        <th style={{ padding: "10px 12px", color: textPrimary, fontWeight: 700 }}>Freshness</th>
                        <th style={{ padding: "10px 12px", color: textPrimary, fontWeight: 700 }}>Mode</th>
                        <th style={{ padding: "10px 12px", color: textSecondary, fontWeight: 700, textAlign: "right" }}>Action</th>
                      </tr>
                    </thead>
                    <tbody>
                      {allViews.map((v, idx) => {
                        const isSelected = v.view_id === selectedViewId;
                        return (
                          <tr
                            key={v.view_id || idx}
                            onClick={() => setSelectedViewId(v.view_id)}
                            style={{
                              borderBottom: `1px solid ${borderCol}`,
                              background: isSelected ? brandSoftBg : idx % 2 === 1 ? bgSubtle : "transparent",
                              cursor: "pointer",
                            }}
                          >
                            <td style={{ padding: "10px 12px", fontWeight: 700, color: textPrimary }}>
                              {v.name}
                            </td>
                            <td style={{ padding: "10px 12px", color: textSecondary }}>
                              {v.source_sheets?.join(", ")}
                            </td>
                            <td style={{ padding: "10px 12px", color: textSecondary }}>
                              {v.result_grain}
                            </td>
                            <td style={{ padding: "10px 12px", color: textSecondary }}>
                              {v.derived_measures?.map(m => m.measure_name).join(", ") || v.measure_columns?.join(", ") || "—"}
                            </td>
                            <td style={{ padding: "10px 12px" }}>
                              <StatusBadge status={v.status} size="xs" />
                            </td>
                            <td style={{ padding: "10px 12px" }}>
                              <StatusBadge
                                status={v.is_stale ? "Needs refresh" : "Current"}
                                variant={v.is_stale ? "warning" : "success"}
                                size="xs"
                              />
                            </td>
                            <td style={{ padding: "10px 12px" }}>
                              <StatusBadge status={v.materialization_mode} variant="info" size="xs" />
                            </td>
                            <td style={{ padding: "10px 12px", textAlign: "right" }}>
                              <button
                                type="button"
                                onClick={(e) => {
                                  e.stopPropagation();
                                  setSelectedViewId(v.view_id);
                                }}
                                style={{
                                  padding: "4px 8px",
                                  fontSize: "0.74rem",
                                  fontWeight: 600,
                                  borderRadius: "6px",
                                  border: `1px solid ${borderCol}`,
                                  background: bgSubtle,
                                  color: brandPrimary,
                                  cursor: "pointer",
                                  display: "inline-flex",
                                  alignItems: "center",
                                  gap: "4px",
                                }}
                              >
                                <Eye size={12} />
                                Select
                              </button>
                            </td>
                          </tr>
                        );
                      })}
                    </tbody>
                  </table>
                </div>
              </div>

              {/* Stale Warning Banner if active view is stale */}
              {activeView && activeView.is_stale && (
                <div
                  style={{
                    background: themeTokens?.colors?.softError || "var(--color-bg-soft-error)",
                    border: `1px solid ${themeTokens?.colors?.statusError || "var(--color-error)"}`,
                    borderRadius: "8px",
                    padding: "12px 14px",
                    color: themeTokens?.colors?.statusError || "var(--color-error)",
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
                      {activeView.rejection_reason || "Upstream dependency drift detected. This view cannot be served as current truth until re-verified."}
                    </div>
                  </div>
                </div>
              )}

              {/* TABLE 2: ANALYTICAL FACTS TABLE */}
              <div style={{ background: bgSurface, border: `1px solid ${borderCol}`, borderRadius: "10px", overflow: "hidden" }}>
                <div style={{ padding: "12px 16px", borderBottom: `1px solid ${borderCol}`, display: "flex", justifyContent: "space-between", alignItems: "center" }}>
                  <h3 style={{ margin: 0, fontSize: "0.9rem", fontWeight: 700, color: textPrimary, display: "flex", alignItems: "center", gap: "6px" }}>
                    <Award size={15} color={brandPrimary} />
                    Analytical Facts Table for "{activeView?.name || "Selected Analysis"}" ({filteredFacts.length} facts)
                  </h3>
                  <span style={{ fontSize: "0.75rem", color: textSecondary }}>
                    Exact metric values, denominators, and calculation lineage
                  </span>
                </div>
                <div style={{ overflowX: "auto" }}>
                  <table style={{ width: "100%", borderCollapse: "collapse", fontSize: "0.82rem", textAlign: "left" }}>
                    <thead>
                      <tr style={{ background: bgSubtle, borderBottom: `2px solid ${borderCol}` }}>
                        <th style={{ padding: "10px 12px", color: textPrimary, fontWeight: 700 }}>Metric</th>
                        <th style={{ padding: "10px 12px", color: textPrimary, fontWeight: 700 }}>Value</th>
                        <th style={{ padding: "10px 12px", color: textPrimary, fontWeight: 700 }}>Unit</th>
                        <th style={{ padding: "10px 12px", color: textPrimary, fontWeight: 700 }}>Grain</th>
                        <th style={{ padding: "10px 12px", color: textPrimary, fontWeight: 700 }}>Denominator</th>
                        <th style={{ padding: "10px 12px", color: textPrimary, fontWeight: 700 }}>Source</th>
                        <th style={{ padding: "10px 12px", color: textPrimary, fontWeight: 700 }}>Status</th>
                        <th style={{ padding: "10px 12px", color: textSecondary, fontWeight: 700, textAlign: "right" }}>Lineage</th>
                      </tr>
                    </thead>
                    <tbody>
                      {filteredFacts.length > 0 ? (
                        filteredFacts.map((fact, idx) => (
                          <tr
                            key={fact.fact_id || idx}
                            style={{
                              borderBottom: `1px solid ${borderCol}`,
                              background: idx % 2 === 1 ? bgSubtle : "transparent",
                            }}
                          >
                            <td style={{ padding: "10px 12px", fontWeight: 700, color: textPrimary }}>
                              {fact.metric_name}
                            </td>
                            <td style={{ padding: "10px 12px", fontWeight: 700, fontFamily: "monospace", color: brandPrimary }}>
                              {fact.formatted_value || String(fact.exact_value)}
                            </td>
                            <td style={{ padding: "10px 12px", color: textSecondary }}>
                              {fact.unit || "—"}
                            </td>
                            <td style={{ padding: "10px 12px", color: textSecondary }}>
                              {fact.grain || "RECORD"}
                            </td>
                            <td style={{ padding: "10px 12px", color: textSecondary }}>
                              {fact.denominator || "—"}
                            </td>
                            <td style={{ padding: "10px 12px", color: textSecondary }}>
                              {fact.provenance || "Reconstructed"}
                            </td>
                            <td style={{ padding: "10px 12px" }}>
                              <StatusBadge status={fact.status || "Verified"} size="xs" />
                            </td>
                            <td style={{ padding: "10px 12px", textAlign: "right" }}>
                              <button
                                type="button"
                                onClick={() => setSelectedFact(fact)}
                                style={{
                                  padding: "4px 8px",
                                  fontSize: "0.74rem",
                                  fontWeight: 600,
                                  borderRadius: "6px",
                                  border: `1px solid ${borderCol}`,
                                  background: bgSubtle,
                                  color: brandPrimary,
                                  cursor: "pointer",
                                  display: "inline-flex",
                                  alignItems: "center",
                                  gap: "4px",
                                }}
                              >
                                <GitBranch size={12} />
                                Lineage
                              </button>
                            </td>
                          </tr>
                        ))
                      ) : (
                        <tr>
                          <td colSpan={8} style={{ padding: "20px", textAlign: "center", color: textSecondary }}>
                            No facts recorded for this view.
                          </td>
                        </tr>
                      )}
                    </tbody>
                  </table>
                </div>
              </div>
            </>
          )}
        </>
      )}

      {/* Calculation Lineage Drawer (Progressive Disclosure) */}
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
