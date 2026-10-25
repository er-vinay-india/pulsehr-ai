import React from "react";
import { DASHBOARD_STATES } from "../../contracts/DashboardStateContract";
import EmptyDashboardState from "./EmptyDashboardState";
import Button from "../../design-system/components/Button";
import { FileSpreadsheet } from "lucide-react";
import "../../styles/explorer-workspace.scss";

/**
 * EmptyDashboardBoundary (Zero-Data Render Firewall)
 *
 * Prevents analytical components, charts, KPI strips, and evidence cards
 * from ever mounting when the workspace catalog has zero datasets or the
 * dashboard is in an empty state.
 */
export default function EmptyDashboardBoundary({
  dashboardState = DASHBOARD_STATES.LOADING,
  error = null,
  onRetry = () => {},
  onNavigateTab,
  onOpenUpload,
  children,
}) {
  // 1. Zero-Data State (CATALOG_EMPTY): Mount ONLY the approved empty-state component
  if (dashboardState === DASHBOARD_STATES.CATALOG_EMPTY) {
    return (
      <div className="empty-dashboard-boundary" data-testid="empty-dashboard-boundary">
        <EmptyDashboardState
          onNavigateTab={onNavigateTab}
          onOpenUpload={onOpenUpload}
        />
      </div>
    );
  }

  // 2. Sanitized Error State (DATASET_ERROR): Mount sanitized error notice
  if (dashboardState === DASHBOARD_STATES.DATASET_ERROR && error) {
    const serviceUnavailable = ["NETWORK", "SERVER_ERROR"].includes(error.category);
    return (
      <section
        className="dashboard-error-boundary explorer-empty-state"
        data-testid="dashboard-error-boundary"
        role="alert"
        aria-labelledby="dashboard-error-title"
      >
        <div className="explorer-empty-icon" aria-hidden="true"><FileSpreadsheet size={28} /></div>
        <h2 id="dashboard-error-title">{serviceUnavailable ? "Dashboard couldn’t be loaded" : error.title || "Dashboard unavailable"}</h2>
        <p>{serviceUnavailable
          ? "Check that the server is available, then try again."
          : error.userMessage || error.message || "The requested analysis could not be displayed."}</p>
        {!serviceUnavailable && error.actionText && <p>{error.actionText}</p>}
        <Button variant="PRIMARY" size="lg" onClick={onRetry} ariaLabel="Try again loading dashboard">
          Try again
        </Button>
      </section>
    );
  }

  // 3. Normal Governed Content (DATASET_READY or LOADING with stale-while-revalidate)
  return children;
}
