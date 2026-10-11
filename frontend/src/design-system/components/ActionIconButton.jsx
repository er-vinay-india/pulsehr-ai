import React from "react";
import { getSemanticAction } from "../registries/SemanticActionRegistry";

/**
 * ActionIconButton: Centralized executive icon-only action button.
 * Enforces the minimal-text policy across visual cards and toolbars.
 *
 * Ensures:
 * - Minimal visible text (icon only)
 * - Complete accessible meaning (aria-label + title tooltip)
 * - Centralized semantic action styling with theme tokens
 * - Strict focus ring and keyboard accessibility
 */
export default function ActionIconButton({
  action = "inspect",
  title = "",
  onClick,
  href,
  ariaLabel,
  tooltip,
  size = 14,
  buttonSize = 28,
  className = "",
  style = {},
  variant = "icon", // "icon" | "ghost" | "primary"
  disabled = false,
  ...rest
}) {
  const meta = getSemanticAction(action, title);
  const resolvedAriaLabel = ariaLabel || meta.ariaLabel;
  const resolvedTooltip = tooltip || meta.tooltip;
  const Icon = meta.Icon;
  const sizePx = `${buttonSize}px`;

  const baseStyle = {
    display: "inline-flex",
    alignItems: "center",
    justifyContent: "center",
    width: sizePx,
    height: sizePx,
    minWidth: sizePx,
    maxWidth: sizePx,
    minHeight: sizePx,
    maxHeight: sizePx,
    aspectRatio: "1 / 1",
    boxSizing: "border-box",
    borderRadius: "6px",
    cursor: disabled ? "not-allowed" : "pointer",
    opacity: disabled ? 0.5 : 1,
    transition: "all 0.15s ease",
    textDecoration: "none",
    padding: 0,
    margin: 0,
    flexShrink: 0,
    lineHeight: 1,
    backgroundColor: "var(--action-icon-bg, rgba(0, 0, 0, 0.04))",
    color: "var(--action-icon-text, #334B57)",
    border: "1px solid var(--action-icon-border, #D4DDD6)",
    outline: "none",
    ...style,
  };

  const commonProps = {
    className: `hv-action-icon-btn action-icon-btn--${action} ${className}`.trim(),
    "data-action-key": meta.key || action,
    "data-icon-only": "true",
    style: baseStyle,
    "aria-label": resolvedAriaLabel,
    title: resolvedTooltip,
    ...rest,
  };

  if (href) {
    return (
      <a
        href={href}
        onClick={onClick}
        {...commonProps}
      >
        <Icon size={size} aria-hidden="true" />
      </a>
    );
  }

  return (
    <button
      type="button"
      onClick={onClick}
      disabled={disabled}
      {...commonProps}
    >
      <Icon size={size} aria-hidden="true" />
    </button>
  );
}
