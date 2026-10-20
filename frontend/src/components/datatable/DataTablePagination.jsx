import React from "react";
import { ChevronLeft, ChevronRight, ChevronsLeft, ChevronsRight } from "lucide-react";

export default function DataTablePagination({
  currentPage = 1,
  totalPages = 1,
  onPageChange = () => {},
  pageSize = 25,
  onPageSizeChange = null,
  pageSizeOptions = [15, 25, 50, 100],
  loading = false,
  totalRows = 0,
}) {
  if (totalPages <= 1 && totalRows <= pageSize && !onPageSizeChange) {
    return null;
  }

  return (
    <div
      className="datatable-pagination"
      style={{
        display: "flex",
        justifyContent: "space-between",
        alignItems: "center",
        flexWrap: "wrap",
        gap: "0.85rem",
        marginTop: "0.75rem",
        paddingTop: "0.75rem",
        borderTop: "1px solid var(--color-divider, #E5E9E3)",
      }}
    >
      {/* Left: Page & Row Count Information */}
      <div style={{ display: "flex", alignItems: "center", gap: "12px", fontSize: "0.78rem", color: "var(--color-text-secondary, #334B57)" }}>
        <span>
          Page <strong>{currentPage}</strong> of <strong>{Math.max(1, totalPages)}</strong>
          {totalRows > 0 && ` (${totalRows.toLocaleString()} total rows)`}
        </span>

        {onPageSizeChange && (
          <div style={{ display: "inline-flex", alignItems: "center", gap: "6px" }}>
            <label htmlFor="datatable-page-size" style={{ fontSize: "0.75rem" }}>
              Per page:
            </label>
            <select
              id="datatable-page-size"
              value={pageSize}
              onChange={(e) => onPageSizeChange(Number(e.target.value))}
              aria-label="Rows per page"
              style={{
                fontSize: "0.75rem",
                padding: "2px 6px",
                borderRadius: "4px",
                border: "1px solid var(--color-border, #D4DDD6)",
                background: "var(--color-bg-surface, #ffffff)",
                color: "var(--color-text-primary, #172B3A)",
                cursor: "pointer",
              }}
            >
              {pageSizeOptions.map((opt) => (
                <option key={opt} value={opt}>
                  {opt}
                </option>
              ))}
            </select>
          </div>
        )}
      </div>

      {/* Right: Navigation Controls */}
      <div style={{ display: "flex", alignItems: "center", gap: "0.4rem" }}>
        <button
          type="button"
          className="btn-secondary"
          disabled={currentPage <= 1 || loading}
          onClick={() => onPageChange(1)}
          aria-label="First page"
          style={{
            padding: "0.3rem 0.5rem",
            fontSize: "0.75rem",
            minHeight: "unset",
            opacity: currentPage <= 1 ? 0.4 : 1,
            cursor: currentPage <= 1 ? "not-allowed" : "pointer",
          }}
          title="First page"
        >
          <ChevronsLeft size={14} />
        </button>
        <button
          type="button"
          className="btn-secondary"
          disabled={currentPage <= 1 || loading}
          onClick={() => onPageChange(currentPage - 1)}
          aria-label="Previous page"
          style={{
            padding: "0.3rem 0.65rem",
            fontSize: "0.75rem",
            minHeight: "unset",
            display: "inline-flex",
            alignItems: "center",
            gap: "2px",
            opacity: currentPage <= 1 ? 0.4 : 1,
            cursor: currentPage <= 1 ? "not-allowed" : "pointer",
          }}
        >
          <ChevronLeft size={14} />
          Prev
        </button>
        <button
          type="button"
          className="btn-secondary"
          disabled={currentPage >= totalPages || loading}
          onClick={() => onPageChange(currentPage + 1)}
          aria-label="Next page"
          style={{
            padding: "0.3rem 0.65rem",
            fontSize: "0.75rem",
            minHeight: "unset",
            display: "inline-flex",
            alignItems: "center",
            gap: "2px",
            opacity: currentPage >= totalPages ? 0.4 : 1,
            cursor: currentPage >= totalPages ? "not-allowed" : "pointer",
          }}
        >
          Next
          <ChevronRight size={14} />
        </button>
        <button
          type="button"
          className="btn-secondary"
          disabled={currentPage >= totalPages || loading}
          onClick={() => onPageChange(totalPages)}
          aria-label="Last page"
          style={{
            padding: "0.3rem 0.5rem",
            fontSize: "0.75rem",
            minHeight: "unset",
            opacity: currentPage >= totalPages ? 0.4 : 1,
            cursor: currentPage >= totalPages ? "not-allowed" : "pointer",
          }}
          title="Last page"
        >
          <ChevronsRight size={14} />
        </button>
      </div>
    </div>
  );
}
