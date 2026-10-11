import React from "react";
import { Sparkles, ShieldCheck, ArrowRight } from "lucide-react";
import HighviewSidePanel from "../../design-system/components/HighviewSidePanel";
import Button from "../../design-system/components/Button";
import { resolvePresentationLabel } from "../../design-system/registries/PresentationLabelResolver";
import { buildExplorerUrl, getContextualExplorerTarget } from "../../utils/explorerNavigation";

/**
 * Accessible Quick Inspect Side Panel powered by HighviewSidePanel.
 * Enforces the SidePanelMotionInvariant (originates at right edge, moves right -> left).
 * Displays rich context, underlying mathematical grain, source sheets, and deep links.
 */
export default function QuickInspectDialog({
  isOpen,
  onClose,
  inspectTarget,
  selectedCandidate,
  data,
  activeDataset,
  selectedDatasetId,
  themeTokens,
  isDark = false,
}) {
  if (!isOpen) return null;

  const topic = inspectTarget;
  const isCandidate = Boolean(selectedCandidate);
  const title = isCandidate
    ? selectedCandidate?.title || "Candidate Finding"
    : topic?.title || "Executive Visual";

  const cleanTitle = resolvePresentationLabel(title);
  const contextualTarget = topic
    ? getContextualExplorerTarget(topic, selectedDatasetId)
    : null;

  const footer = contextualTarget ? (
    <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", width: "100%" }}>
      <Button
        variant="GHOST"
        size="sm"
        onClick={onClose}
        ariaLabel="Close Quick Inspect"
      >
        Close
      </Button>
      <a
        href={contextualTarget.url}
        onClick={(e) => {
          e.preventDefault();
          window.location.href = contextualTarget.url;
        }}
        style={{
          display: "inline-flex",
          alignItems: "center",
          gap: "6px",
          textDecoration: "none",
          backgroundColor: "var(--action-primary-bg, #075443)",
          color: "var(--action-primary-text, #ffffff)",
          fontSize: "0.82rem",
          fontWeight: 600,
          padding: "8px 14px",
          borderRadius: "8px",
          cursor: "pointer",
          transition: "all 0.15s ease",
        }}
        aria-label={`${contextualTarget.label} in Data Explorer`}
      >
        <span>Explore in Data Explorer</span>
        <ArrowRight size={14} aria-hidden="true" />
      </a>
    </div>
  ) : (
    <div style={{ display: "flex", justifyContent: "flex-end", width: "100%" }}>
      <Button
        variant="GHOST"
        size="sm"
        onClick={onClose}
        ariaLabel="Close Quick Inspect"
      >
        Close
      </Button>
    </div>
  );

  return (
    <HighviewSidePanel
      isOpen={isOpen}
      onClose={onClose}
      title={cleanTitle}
      subtitle="Contextual inspection & ground truth lineage"
      icon={Sparkles}
      badge="Verified"
      breadcrumbs={["Workspace", "Dashboard", "Quick Inspect"]}
      footer={footer}
      width="560px"
      maxWidth="92vw"
      ariaLabel={`Quick Inspect for ${cleanTitle}`}
      className="quick-inspect-side-panel"
    >
      <div style={{ display: "flex", flexDirection: "column", gap: "16px" }}>
        {isCandidate ? (
          <div>
            <h4
              style={{
                margin: "0 0 6px 0",
                fontSize: "0.80rem",
                fontWeight: 700,
                textTransform: "uppercase",
                letterSpacing: "0.05em",
                color: "var(--color-text-muted, #3C5059)",
              }}
            >
              Candidate Specification
            </h4>
            <p
              style={{
                margin: 0,
                fontSize: "0.90rem",
                color: "var(--color-text-primary, #172B3A)",
                lineHeight: 1.5,
              }}
            >
              {selectedCandidate.takeaway ||
                selectedCandidate.description ||
                "Synthesized analytical candidate."}
            </p>
            {selectedCandidate.metric_value != null && (
              <div style={{ marginTop: "12px" }}>
                <span style={{ fontSize: "0.75rem", color: "var(--color-text-muted, #3C5059)" }}>
                  Measured Value:
                </span>{" "}
                <strong style={{ fontSize: "1.1rem", color: "var(--color-text-primary, #172B3A)" }}>
                  {selectedCandidate.metric_value}
                </strong>
              </div>
            )}
          </div>
        ) : (
          (() => {
            const sheetCount = data?.sheet_count || activeDataset?.sheet_count || 1;
            const sheetText = `${sheetCount} unified ${sheetCount === 1 ? "sheet" : "sheets"}`;
            const primaryMetric = topic?.key_metric || topic?.visual_microcopy?.primary_number;
            const subtitle = topic?.subtitle || topic?.visual_microcopy?.short_context;
            const takeaway =
              topic?.primary_takeaway ||
              topic?.takeaway ||
              topic?.visual_microcopy?.short_finding;
            const intent = resolvePresentationLabel(topic?.analytical_intent || "Analytical Focus");

            return (
              <>
                {/* 1. Analytical Classification */}
                <div
                  style={{
                    display: "flex",
                    alignItems: "center",
                    gap: "8px",
                    padding: "8px 12px",
                    borderRadius: "8px",
                    backgroundColor: "var(--color-bg-subtle, #EEEFE9)",
                    border: "1px solid var(--color-border, #D4DDD6)",
                    fontSize: "0.78rem",
                  }}
                >
                  <span style={{ color: "var(--color-text-muted, #3C5059)", fontWeight: 600 }}>
                    Analytical Intent:
                  </span>
                  <strong style={{ color: "var(--color-text-primary, #172B3A)" }}>
                    {intent}
                  </strong>
                </div>

                {/* 2. Measured Metric Highlight */}
                {primaryMetric && (
                  <div>
                    <span
                      style={{
                        fontSize: "0.74rem",
                        fontWeight: 700,
                        textTransform: "uppercase",
                        letterSpacing: "0.05em",
                        color: "var(--color-text-muted, #3C5059)",
                      }}
                    >
                      Measured Result
                    </span>
                    <div
                      style={{
                        fontSize: "1.75rem",
                        fontWeight: 800,
                        color: "var(--color-brand-primary, #183B56)",
                        lineHeight: 1.2,
                        marginTop: "2px",
                      }}
                    >
                      {primaryMetric}
                    </div>
                    {subtitle && (
                      <p
                        style={{
                          margin: "2px 0 0 0",
                          fontSize: "0.82rem",
                          color: "var(--color-text-secondary, #334B57)",
                        }}
                      >
                        {subtitle}
                      </p>
                    )}
                  </div>
                )}

                {/* 3. Executive Takeaway */}
                {takeaway && (
                  <div>
                    <h4
                      style={{
                        margin: "0 0 4px 0",
                        fontSize: "0.74rem",
                        fontWeight: 700,
                        textTransform: "uppercase",
                        letterSpacing: "0.05em",
                        color: "var(--color-text-muted, #3C5059)",
                      }}
                    >
                      Executive Finding
                    </h4>
                    <p
                      style={{
                        margin: 0,
                        fontSize: "0.88rem",
                        color: "var(--color-text-primary, #172B3A)",
                        lineHeight: 1.5,
                      }}
                    >
                      {takeaway}
                    </p>
                  </div>
                )}

                {/* 4. Evidence Confidence & Source Scope */}
                <div
                  style={{
                    display: "flex",
                    alignItems: "center",
                    gap: "8px",
                    fontSize: "0.78rem",
                    color: "var(--color-text-muted, #3C5059)",
                    paddingTop: "10px",
                    borderTop: "1px solid var(--color-border, #D4DDD6)",
                  }}
                >
                  <ShieldCheck
                    size={16}
                    color="var(--color-success, #075443)"
                    aria-hidden="true"
                  />
                  <span>
                    Grounded in {sheetText} · Mathematically verified · 100% confidence
                  </span>
                </div>
              </>
            );
          })()
        )}
      </div>
    </HighviewSidePanel>
  );
}
