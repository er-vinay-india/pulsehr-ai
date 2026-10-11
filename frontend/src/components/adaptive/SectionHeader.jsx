import React from "react";
import Badge from "../../design-system/components/Badge";
import { resolvePresentationLabel } from "../../design-system/registries/PresentationLabelResolver";

/**
 * Standardized Section Header with proper semantic H2 element and optional metadata badge.
 * Enforces typography scale:
 * - H2: Major section anchor (23.2px, 650 weight)
 * - Badge: Eyebrow metadata (11px, 700 uppercase)
 */
export default function SectionHeader({
  id,
  title,
  badge = null,
  subtitle = null,
  className = "",
  actions = null,
}) {
  const cleanTitle = resolvePresentationLabel(title);

  return (
    <div className={`dashboard-section__header ${className}`.trim()}>
      <div className="dashboard-section__header-main">
        <div className="dashboard-section__title-group">
          <h2 id={id} className="dashboard-section__title">
            {cleanTitle}
          </h2>
          {badge && <Badge variant="neutral">{badge}</Badge>}
        </div>
        {subtitle && <p className="dashboard-section__subtitle">{subtitle}</p>}
      </div>
      {actions && <div className="dashboard-section__header-actions">{actions}</div>}
    </div>
  );
}
