import React from "react";
import { DASHBOARD_STATES } from "../../contracts/DashboardStateContract";
import EmptyDashboardState from "./EmptyDashboardState";
import Button from "../../design-system/components/Button";
import { AlertCircle, RefreshCw } from "lucide-react";

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
    return (
      <div className="dashboard-error-boundary" data-testid="dashboard-error-boundary">
        <div className="adaptive-status-notice error" role="alert" style={{ margin: "24px 0" }}>
          <AlertCircle size={20} />
          <div style={{ flex: 1 }}>
            <strong>{error.title || "Intelligence Notice"}</strong>
            <p style={{ margin: "4px 0 0 0", fontSize: "0.88rem" }}>{error.userMessage || "The requested analysis could not be displayed."}</p>
            {error.actionText && (
              <p style={{ margin: "4px 0 0 0", fontSize: "0.80rem", opacity: 0.85 }}>{error.actionText}</p>
            )}
          </div>
          <Button
            variant="GHOST"
            size="sm"
            icon={RefreshCw}
            onClick={onRetry}
            ariaLabel="Retry loading analysis"
          >
            Retry
          </Button>
        </div>
      </div>
    );
  }

  // 3. Normal Governed Content (DATASET_READY or LOADING with stale-while-revalidate)
  return children;
}
