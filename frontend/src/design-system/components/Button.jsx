import React from "react";

/**
 * Standardized Highview Semantic Button.
 * Enforces allowed variants:
 * - PRIMARY: Major executive commitments (e.g. Create Presentation)
 * - SECONDARY: Exploratory actions (e.g. Scenario Explorer)
 * - GHOST: Low-emphasis utility actions (e.g. Reset, Cancel)
 * - DANGER: Irreversible actions (e.g. Delete)
 */
export default function Button({
  variant = "PRIMARY", // PRIMARY | SECONDARY | GHOST | DANGER
  size = "md",         // sm | md | lg
  children,
  icon: Icon,
  iconRight: IconRight,
  onClick,
  disabled = false,
  className = "",
  style = {},
  ariaLabel,
  type = "button",
  ...rest
}) {
  const normVariant = (variant || "PRIMARY").toUpperCase();

  const variantStyles = {
    PRIMARY: {
      backgroundColor: "var(--action-primary-bg, #075443)",
      color: "var(--action-primary-text, #FFFFFF)",
      border: "1px solid var(--action-primary-border, #075443)",
    },
    SECONDARY: {
      backgroundColor: "var(--action-secondary-bg, #183B56)",
      color: "var(--action-secondary-text, #FFFFFF)",
      border: "1px solid var(--action-secondary-border, #183B56)",
    },
    GHOST: {
      backgroundColor: "var(--action-ghost-bg, transparent)",
      color: "var(--action-ghost-text, #172B3A)",
      border: "1px solid var(--action-ghost-border, #D4DDD6)",
    },
    DANGER: {
      backgroundColor: "var(--color-error, #8E1938)",
      color: "#FFFFFF",
      border: "1px solid var(--color-error, #8E1938)",
    },
  }[normVariant] || {
    backgroundColor: "var(--action-primary-bg, #075443)",
    color: "var(--action-primary-text, #FFFFFF)",
    border: "1px solid var(--action-primary-border, #075443)",
  };

  const sizeStyles = {
    sm: {
      padding: "4px 10px",
      fontSize: "0.78rem",
      borderRadius: "6px",
      gap: "5px",
    },
    md: {
      padding: "7px 14px",
      fontSize: "0.85rem",
      borderRadius: "8px",
      gap: "7px",
    },
    lg: {
      padding: "10px 20px",
      fontSize: "0.95rem",
      borderRadius: "10px",
      gap: "8px",
    },
  }[size] || {
    padding: "7px 14px",
    fontSize: "0.85rem",
    borderRadius: "8px",
    gap: "7px",
  };

  return (
    <button
      type={type}
      onClick={onClick}
      disabled={disabled}
      aria-label={ariaLabel}
      className={`hv-btn hv-btn--${normVariant.toLowerCase()} ${className}`.trim()}
      style={{
        display: "inline-flex",
        alignItems: "center",
        justifyContent: "center",
        fontWeight: 600,
        cursor: disabled ? "not-allowed" : "pointer",
        opacity: disabled ? 0.5 : 1,
        transition: "all 0.15s ease",
        lineHeight: 1.2,
        outline: "none",
        ...variantStyles,
        ...sizeStyles,
        ...style,
      }}
      {...rest}
    >
      {Icon && <Icon size={size === "sm" ? 13 : 15} aria-hidden="true" />}
      <span>{children}</span>
      {IconRight && <IconRight size={size === "sm" ? 13 : 15} aria-hidden="true" />}
    </button>
  );
}
