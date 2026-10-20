import React from "react";
import { Filter, X } from "lucide-react";
import Popover from "../common/Popover";

export default function DataTableFilterPopover({
  filters = [],
  activeFilters = {},
  onFilterChange = () => {},
  onClearFilters = () => {},
  isOpen,
  onOpenChange,
}) {
  const activeCount = Object.values(activeFilters).filter(Boolean).length;

  return (
    <Popover
      open={isOpen}
      onOpenChange={onOpenChange}
      trigger={
        <button
          type="button"
          className="btn-secondary"
          aria-label={`Filter records${activeCount > 0 ? `, ${activeCount} active` : ""}`}
          style={{
            display: "inline-flex",
            alignItems: "center",
            gap: "6px",
            fontSize: "0.78rem",
            padding: "0.4rem 0.75rem",
            background: activeCount > 0 ? "var(--color-bg-soft-blue, rgba(35, 78, 112, 0.1))" : undefined,
            borderColor: activeCount > 0 ? "var(--color-brand-primary, #183B56)" : undefined,
          }}
          title="Filter table by column values"
        >
          <Filter size={13} />
          <span>Filters</span>
          {activeCount > 0 && (
            <span
              style={{
                fontSize: "0.7rem",
                fontWeight: 700,
                background: "var(--color-brand-primary, #183B56)",
                color: "#ffffff",
                borderRadius: "10px",
                padding: "1px 6px",
                marginLeft: "2px",
              }}
            >
              {activeCount}
            </span>
          )}
        </button>
      }
    >
      <div
        className="filter-popover-content"
        style={{
          width: "280px",
          padding: "12px",
          display: "flex",
          flexDirection: "column",
          gap: "12px",
          background: "var(--color-bg-surface, #ffffff)",
          color: "var(--color-text-primary, #172B3A)",
        }}
      >
        <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", borderBottom: "1px solid var(--color-border, #D4DDD6)", paddingBottom: "8px" }}>
          <span style={{ fontSize: "0.82rem", fontWeight: 700 }}>Filter records</span>
          {activeCount > 0 && (
            <button
              type="button"
              onClick={onClearFilters}
              style={{
                background: "none",
                border: "none",
                fontSize: "0.74rem",
                color: "var(--color-brand-primary, #183B56)",
                cursor: "pointer",
                padding: 0,
                fontWeight: 600,
              }}
            >
              Clear all
            </button>
          )}
        </div>

        {filters.map((f) => {
          const currentVal = activeFilters[f.key] || "";
          return (
            <div key={f.key} style={{ display: "flex", flexDirection: "column", gap: "4px" }}>
              <label
                htmlFor={`filter-${f.key}`}
                style={{ fontSize: "0.75rem", fontWeight: 600, color: "var(--color-text-secondary, #334B57)" }}
              >
                {f.label}
              </label>
              <select
                id={`filter-${f.key}`}
                value={currentVal}
                onChange={(e) => onFilterChange(f.key, e.target.value)}
                style={{
                  fontSize: "0.78rem",
                  padding: "6px 8px",
                  borderRadius: "6px",
                  border: "1px solid var(--color-border, #D4DDD6)",
                  background: "var(--color-bg-surface, #ffffff)",
                  color: "var(--color-text-primary, #172B3A)",
                  outline: "none",
                  cursor: "pointer",
                }}
              >
                <option value="">All {f.label}</option>
                {f.options?.map((opt) => {
                  const optVal = typeof opt === "string" ? opt : opt.value;
                  const optLabel = typeof opt === "string" ? opt : opt.label;
                  return (
                    <option key={optVal} value={optVal}>
                      {optLabel}
                    </option>
                  );
                })}
              </select>
            </div>
          );
        })}
      </div>
    </Popover>
  );
}
