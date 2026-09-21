import React from "react";
import { ChevronLeft, ChevronRight, ChevronsLeft, ChevronsRight } from "lucide-react";

export default function DataTablePagination({
  serverPage,
  serverTotalPages,
  onPageChange,
  loading,
}) {
  return (
    <div
      className="datatable-pagination"
      style={{
        display: "flex",
        justifyContent: "space-between",
        alignItems: "center",
        flexWrap: "wrap",
        gap: "0.85rem",
        marginTop: "1rem",
        paddingTop: "0.85rem",
        borderTop: "1px solid var(--border-subtle)"
      }}
    >
      <div style={{ fontSize: "0.8rem", color: "var(--fg-secondary)" }}>
        Page <strong>{serverPage}</strong> of <strong>{serverTotalPages}</strong>
      </div>

      <div style={{ display: "flex", alignItems: "center", gap: "0.4rem" }}>
        <button
          className="btn-secondary"
          disabled={serverPage <= 1 || loading}
          onClick={() => onPageChange(1)}
          style={{ padding: "0.35rem 0.5rem", fontSize: "0.75rem" }}
          title="First Page"
        >
          <ChevronsLeft size={14} />
        </button>
        <button
          className="btn-secondary"
          disabled={serverPage <= 1 || loading}
          onClick={() => onPageChange(serverPage - 1)}
          style={{ padding: "0.35rem 0.65rem", fontSize: "0.75rem" }}
        >
          <ChevronLeft size={14} style={{ marginRight: "2px" }} />
          Previous
        </button>
        <button
          className="btn-secondary"
          disabled={serverPage >= serverTotalPages || loading}
          onClick={() => onPageChange(serverPage + 1)}
          style={{ padding: "0.35rem 0.65rem", fontSize: "0.75rem" }}
        >
          Next
          <ChevronRight size={14} style={{ marginLeft: "2px" }} />
        </button>
        <button
          className="btn-secondary"
          disabled={serverPage >= serverTotalPages || loading}
          onClick={() => onPageChange(serverTotalPages)}
          style={{ padding: "0.35rem 0.5rem", fontSize: "0.75rem" }}
          title="Last Page"
        >
          <ChevronsRight size={14} />
        </button>
      </div>
    </div>
  );
}
