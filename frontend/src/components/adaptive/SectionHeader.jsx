import React from "react";
import Badge from "../../design-system/components/Badge";
import { resolvePresentationLabel } from "../../design-system/registries/PresentationLabelResolver";
import { checkHumanFacingCopy } from "../../design-system/registries/HumanFacingCopyPolicy";

/**
 * Standardized Section Header with proper semantic H2 element.
 * Enforces Human vs Machine metadata separation:
 * - Machine metadata is preserved in component data-* attributes (data-ai-section, data-analytical-family)
 * - Human-facing UI renders only the clean section anchor title
 * - Technical badges (LEADERSHIP FOCUS, DISTRIBUTIONS & VARIANCE, etc.) are NOT displayed on executive surfaces
 */
export default function SectionHeader({
  id,
  title,
  badge = null,
  subtitle = null,
  analyticalFamily = null,
  analyticalIntent = null,
  sectionType = null,
  showBadge = false,
  className = "",
  actions = null,
}) {
  const cleanTitle = resolvePresentationLabel(title);

  // Subtitle filter: do not render if it contains forbidden internal analytical terminology
  const shouldRenderSubtitle = Boolean(
    subtitle && checkHumanFacingCopy(subtitle).isAllowed
  );

  return (
    <div
      className={`dashboard-section__header ${className}`.trim()}
      data-ai-section={sectionType || id}
      data-analytical-family={analyticalFamily || badge}
      data-analytical-intent={analyticalIntent}
    >
      <div className="dashboard-section__header-main">
        <div className="dashboard-section__title-group">
          <h2 id={id} className="dashboard-section__title">
            {cleanTitle}
          </h2>
          {showBadge && badge && <Badge variant="neutral">{badge}</Badge>}
        </div>
        {shouldRenderSubtitle && <p className="dashboard-section__subtitle">{subtitle}</p>}
      </div>
      {actions && <div className="dashboard-section__header-actions">{actions}</div>}
    </div>
  );
}
