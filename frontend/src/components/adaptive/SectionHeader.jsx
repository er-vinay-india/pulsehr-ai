import React from "react";

/**
 * Standardized Section Header with proper semantic H2 element and optional metadata badge.
 */
export default function SectionHeader({
  id,
  title,
  badge = null,
  subtitle = null,
  className = "",
  actions = null,
}) {
  return (
    <div className={`dashboard-section__header ${className}`.trim()}>
      <div className="dashboard-section__header-main">
        <div className="dashboard-section__title-group">
          <h2 id={id} className="dashboard-section__title">
            {title}
          </h2>
          {badge && <span className="dashboard-section__badge">{badge}</span>}
        </div>
        {subtitle && <p className="dashboard-section__subtitle">{subtitle}</p>}
      </div>
      {actions && <div className="dashboard-section__header-actions">{actions}</div>}
    </div>
  );
}
