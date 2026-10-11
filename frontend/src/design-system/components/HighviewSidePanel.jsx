import React, { useEffect, useRef } from "react";
import ReactDOM from "react-dom";
import { X } from "lucide-react";

/**
 * HighviewSidePanel: Unified product-wide off-canvas side panel primitive.
 * Enforces the SidePanelMotionInvariant:
 * - Placement: RIGHT EDGE
 * - Motion: travels right -> left into the viewport (translateX(100%) -> translateX(0))
 * - Dismissal: travels left -> right out of the viewport
 * - Dismissible via ESC, overlay click, or close button
 * - Focus trapped inside panel while open, restored to triggering element on close
 */
export default function HighviewSidePanel({
  isOpen,
  onClose,
  title,
  subtitle,
  badge,
  icon: Icon,
  breadcrumbs = [],
  children,
  footer,
  width = "560px",
  maxWidth = "92vw",
  ariaLabel,
  className = "",
}) {
  const panelRef = useRef(null);
  const previousActiveElementRef = useRef(null);

  useEffect(() => {
    if (isOpen) {
      previousActiveElementRef.current = document.activeElement;

      // Lock body scroll while panel is active
      const originalOverflow = document.body.style.overflow;
      document.body.style.overflow = "hidden";

      // Focus panel
      setTimeout(() => {
        if (panelRef.current) {
          panelRef.current.focus();
        }
      }, 50);

      const handleKeyDown = (e) => {
        if (e.key === "Escape") {
          e.preventDefault();
          onClose();
        } else if (e.key === "Tab") {
          // Trap focus within side panel
          if (!panelRef.current) return;
          const focusable = panelRef.current.querySelectorAll(
            'button, [href], input, select, textarea, [tabindex]:not([tabindex="-1"])'
          );
          if (focusable.length === 0) return;
          const first = focusable[0];
          const last = focusable[focusable.length - 1];
          if (e.shiftKey && document.activeElement === first) {
            e.preventDefault();
            last.focus();
          } else if (!e.shiftKey && document.activeElement === last) {
            e.preventDefault();
            first.focus();
          }
        }
      };

      window.addEventListener("keydown", handleKeyDown);
      return () => {
        document.body.style.overflow = originalOverflow;
        window.removeEventListener("keydown", handleKeyDown);
        if (previousActiveElementRef.current && typeof previousActiveElementRef.current.focus === "function") {
          previousActiveElementRef.current.focus();
        }
      };
    }
  }, [isOpen, onClose]);

  if (!isOpen) return null;

  return ReactDOM.createPortal(
    <div
      className="hv-sidepanel-backdrop"
      onClick={onClose}
      role="presentation"
      style={{
        position: "fixed",
        top: 0,
        left: 0,
        right: 0,
        bottom: 0,
        backgroundColor: "rgba(0, 0, 0, 0.55)",
        backdropFilter: "blur(4px)",
        zIndex: 9999,
        display: "flex",
        justifyContent: "flex-end",
      }}
    >
      <aside
        ref={panelRef}
        role="dialog"
        aria-modal="true"
        aria-label={ariaLabel || title || "Side Panel"}
        tabIndex={-1}
        onClick={(e) => e.stopPropagation()}
        className={`hv-sidepanel-panel ${className}`.trim()}
        style={{
          width,
          maxWidth,
          height: "100vh",
          backgroundColor: "var(--color-bg-surface, #ffffff)",
          borderLeft: "1px solid var(--color-border, #D4DDD6)",
          boxShadow: "-16px 0 40px rgba(0, 0, 0, 0.35)",
          display: "flex",
          flexDirection: "column",
          outline: "none",
          animation: "sidePanelSlideInRight 0.24s cubic-bezier(0.16, 1, 0.3, 1) forwards",
        }}
      >
        {/* Panel Header */}
        <header
          className="hv-sidepanel-header"
          style={{
            display: "flex",
            justifyContent: "space-between",
            alignItems: "flex-start",
            padding: "18px 24px",
            borderBottom: "1px solid var(--color-divider, #E5E9E3)",
            backgroundColor: "var(--color-bg-subtle, #EEEFE9)",
            flexShrink: 0,
          }}
        >
          <div style={{ minWidth: 0, flex: 1, paddingRight: "16px" }}>
            {breadcrumbs && breadcrumbs.length > 0 && (
              <div
                className="hv-sidepanel-breadcrumbs"
                style={{
                  fontSize: "0.72rem",
                  fontWeight: 600,
                  color: "var(--color-text-muted, #3C5059)",
                  display: "flex",
                  alignItems: "center",
                  gap: "5px",
                  marginBottom: "4px",
                  textTransform: "uppercase",
                  letterSpacing: "0.04em",
                }}
              >
                {breadcrumbs.map((crumb, idx) => (
                  <React.Fragment key={idx}>
                    {idx > 0 && <span>/</span>}
                    <span>{crumb}</span>
                  </React.Fragment>
                ))}
              </div>
            )}
            <div style={{ display: "flex", alignItems: "center", gap: "8px" }}>
              {Icon && (
                <span
                  style={{
                    color: "var(--color-brand-accent, #075443)",
                    display: "inline-flex",
                    alignItems: "center",
                  }}
                  aria-hidden="true"
                >
                  <Icon size={18} />
                </span>
              )}
              <h2
                className="hv-sidepanel-title"
                style={{
                  margin: 0,
                  fontSize: "1.15rem",
                  fontWeight: 700,
                  lineHeight: 1.25,
                  color: "var(--color-text-primary, #172B3A)",
                }}
              >
                {title}
              </h2>
              {badge && (
                <span
                  style={{
                    fontSize: "0.6875rem",
                    fontWeight: 700,
                    textTransform: "uppercase",
                    letterSpacing: "0.05em",
                    padding: "2px 7px",
                    borderRadius: "4px",
                    backgroundColor: "var(--color-bg-soft-teal, #E7F3ED)",
                    color: "var(--color-success, #075443)",
                    border: "1px solid var(--color-border-strong, #78877F)",
                  }}
                >
                  {badge}
                </span>
              )}
            </div>
            {subtitle && (
              <p
                style={{
                  margin: "4px 0 0 0",
                  fontSize: "0.80rem",
                  color: "var(--color-text-secondary, #334B57)",
                  lineHeight: 1.35,
                }}
              >
                {subtitle}
              </p>
            )}
          </div>

          <button
            type="button"
            onClick={onClose}
            aria-label="Close side panel"
            title="Close (ESC)"
            style={{
              background: "transparent",
              border: "1px solid var(--action-icon-border, #D4DDD6)",
              borderRadius: "6px",
              padding: "4px",
              cursor: "pointer",
              color: "var(--color-text-secondary, #334B57)",
              display: "inline-flex",
              alignItems: "center",
              justifyContent: "center",
              transition: "all 0.15s ease",
            }}
          >
            <X size={18} aria-hidden="true" />
          </button>
        </header>

        {/* Panel Scrollable Body */}
        <div
          className="hv-sidepanel-body"
          style={{
            flex: 1,
            overflowY: "auto",
            padding: "20px 24px",
            color: "var(--color-text-primary, #172B3A)",
          }}
        >
          {children}
        </div>

        {/* Panel Footer (optional) */}
        {footer && (
          <footer
            className="hv-sidepanel-footer"
            style={{
              padding: "14px 24px",
              borderTop: "1px solid var(--color-divider, #E5E9E3)",
              backgroundColor: "var(--color-bg-subtle, #EEEFE9)",
              flexShrink: 0,
            }}
          >
            {footer}
          </footer>
        )}
      </aside>
    </div>,
    document.body
  );
}
