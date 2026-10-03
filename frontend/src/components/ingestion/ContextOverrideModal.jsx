import React, { useState } from "react";
import { X, Check, AlertTriangle, Sliders, Database, Layers, HelpCircle, Save } from "lucide-react";
import { patchWorkspaceContext } from "../../api/client";
import Select from "../common/Select.jsx";

const DOMAIN_OPTIONS = [
  "Workforce Operations",
  "Commercial Sales",
  "Corporate Finance",
  "Business Operations",
  "Supply Chain & Logistics",
  "Software Engineering",
  "Cloud Infrastructure & SRE",
  "Academic & Clinical Research",
  "Education & Training",
  "Generic Analytics"
];

const COLUMN_ROLE_OPTIONS = [
  "METRIC",
  "CATEGORY",
  "CURRENCY",
  "PERCENTAGE",
  "DATE",
  "IDENTIFIER",
  "STATUS",
  "LOCATION",
  "PERSON",
  "ORGANIZATION"
];

export default function ContextOverrideModal({
  workspaceId,
  workspaceContext,
  onClose,
  onSuccess
}) {
  const summary = workspaceContext.context_summary || {};
  const userReq = workspaceContext.user_request || {};
  const datasets = workspaceContext.datasets || [];
  const relationships = workspaceContext.relationships || [];

  // Form states
  const [domain, setDomain] = useState(summary.domain || "Generic Analytics");
  const [objective, setObjective] = useState(userReq.raw_instruction || userReq.normalized_objective || "");
  const [primaryDatasetId, setPrimaryDatasetId] = useState(workspaceContext.primary_dataset_id || (datasets[0]?.dataset_id || ""));
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState(null);

  // Column role overrides: { [colName]: role }
  const [columnRoles, setColumnRoles] = useState(() => {
    const init = {};
    datasets.forEach((ds) => {
      (ds.columns || []).forEach((c) => {
        init[c.name] = c.semantic_role || "METRIC";
      });
    });
    return init;
  });

  // Join decisions: { [relId]: boolean }
  const [joinDecisions, setJoinDecisions] = useState(() => {
    const init = {};
    relationships.forEach((r) => {
      init[r.relationship_id] = r.is_safe;
    });
    return init;
  });

  const handleRoleChange = (colName, newRole) => {
    setColumnRoles((prev) => ({ ...prev, [colName]: newRole }));
  };

  const handleJoinToggle = (relId, isManyToMany) => {
    if (isManyToMany) return; // Permanent invariant: unsafe many-to-many cannot be auto-enabled
    setJoinDecisions((prev) => ({ ...prev, [relId]: !prev[relId] }));
  };

  const handleSave = async (e) => {
    e.preventDefault();
    setSaving(true);
    setError(null);

    try {
      const patch = {
        domain: domain.trim(),
        user_objective: objective.trim(),
        primary_dataset_id: primaryDatasetId,
        column_roles: columnRoles,
        join_decisions: joinDecisions
      };

      const updated = await patchWorkspaceContext(workspaceId, patch);
      if (onSuccess) {
        onSuccess(updated);
      }
    } catch (err) {
      setError(err.message || "Failed to update context corrections");
    } finally {
      setSaving(false);
    }
  };

  return (
    <div
      className="modal-overlay"
      onClick={() => !saving && onClose()}
      role="dialog"
      aria-modal="true"
      aria-labelledby="override-modal-title"
    >
      <div
        className="modal-dialog"
        onClick={(e) => e.stopPropagation()}
        style={{ maxWidth: "680px", width: "95%" }}
      >
        <div className="modal-header">
          <div className="modal-title-group">
            <div className="modal-icon-badge">
              <Sliders size={20} color="var(--brand-accent, #155EEF)" />
            </div>
            <div>
              <h3 id="override-modal-title" style={{ margin: 0, fontSize: "1.05rem" }}>
                Review & Correct Data Understanding
              </h3>
              <p style={{ margin: "2px 0 0 0", fontSize: "0.8rem", color: "var(--fg-muted, #94A3B8)" }}>
                Corrections propagate across EDA, Dashboard & Presentation without re-ingesting data.
              </p>
            </div>
          </div>
          <button
            type="button"
            className="modal-close-btn"
            onClick={() => !saving && onClose()}
            disabled={saving}
            title="Cancel"
          >
            <X size={18} />
          </button>
        </div>

        <form onSubmit={handleSave}>
          <div className="modal-body" style={{ maxHeight: "70vh", overflowY: "auto", display: "flex", flexDirection: "column", gap: "1rem" }}>
            {error && (
              <div style={{ padding: "0.5rem 0.75rem", background: "rgba(239,68,68,0.1)", border: "1px solid rgba(239,68,68,0.3)", borderRadius: "6px", color: "#EF4444", fontSize: "0.8rem" }}>
                {error}
              </div>
            )}

            {/* Domain Selection */}
            <div>
              <label style={{ display: "block", fontSize: "0.8rem", fontWeight: 600, color: "var(--fg-secondary, #CBD5E1)", marginBottom: "4px" }}>
                Domain Context
              </label>
              <Select
                value={domain}
                onChange={(e) => setDomain(e.target.value)}
                options={DOMAIN_OPTIONS.map((d) => ({ value: d, label: d }))}
                fullWidth
              />
            </div>

            {/* User Goal / Objective */}
            <div>
              <label style={{ display: "block", fontSize: "0.8rem", fontWeight: 600, color: "var(--fg-secondary, #CBD5E1)", marginBottom: "4px" }}>
                What would you like to understand? (User Goal)
              </label>
              <textarea
                rows={2}
                value={objective}
                onChange={(e) => setObjective(e.target.value)}
                placeholder="e.g. Compare department compliance and identify departments with unusually high leave."
                style={{
                  width: "100%",
                  padding: "0.5rem 0.75rem",
                  fontSize: "0.85rem",
                  background: "var(--surface-secondary, rgba(15,23,42,0.8))",
                  color: "var(--fg-primary, #F8FAFC)",
                  border: "1px solid var(--border-subtle, rgba(255,255,255,0.12))",
                  borderRadius: "6px",
                  resize: "vertical"
                }}
              />
            </div>

            {/* Primary Dataset (if multiple) */}
            {datasets.length > 1 && (
              <div>
                <label style={{ display: "block", fontSize: "0.8rem", fontWeight: 600, color: "var(--fg-secondary, #CBD5E1)", marginBottom: "4px" }}>
                  Primary Analytical Dataset
                </label>
                <Select
                  value={primaryDatasetId}
                  onChange={(e) => setPrimaryDatasetId(e.target.value)}
                  options={datasets.map((ds) => ({
                    value: ds.dataset_id,
                    label: `${ds.name} (${ds.row_count} rows)`
                  }))}
                  fullWidth
                />
              </div>
            )}

            {/* Column Semantic Roles Review */}
            <div>
              <label style={{ display: "block", fontSize: "0.8rem", fontWeight: 600, color: "var(--fg-secondary, #CBD5E1)", marginBottom: "4px" }}>
                Column Semantic Classification
              </label>
              <div
                style={{
                  border: "1px solid var(--border-subtle, rgba(255,255,255,0.08))",
                  borderRadius: "6px",
                  maxHeight: "180px",
                  overflowY: "auto"
                }}
              >
                <table style={{ width: "100%", borderCollapse: "collapse", fontSize: "0.75rem" }}>
                  <thead>
                    <tr style={{ background: "rgba(255,255,255,0.04)", textAlign: "left", color: "var(--fg-muted, #94A3B8)" }}>
                      <th style={{ padding: "6px 10px" }}>Column</th>
                      <th style={{ padding: "6px 10px" }}>Assigned Semantic Role</th>
                      <th style={{ padding: "6px 10px" }}>Sensitive</th>
                    </tr>
                  </thead>
                  <tbody>
                    {datasets.flatMap((ds) =>
                      (ds.columns || []).map((col, idx) => (
                        <tr
                          key={`${ds.dataset_id}-${col.name}-${idx}`}
                          style={{ borderTop: "1px solid rgba(255,255,255,0.04)" }}
                        >
                          <td style={{ padding: "6px 10px", fontWeight: 500, color: "var(--fg-primary, #F8FAFC)" }}>
                            {col.name}
                          </td>
                          <td style={{ padding: "4px 10px" }}>
                            <Select
                              size="sm"
                              value={columnRoles[col.name] || col.semantic_role || "METRIC"}
                              onChange={(e) => handleRoleChange(col.name, e.target.value)}
                              options={COLUMN_ROLE_OPTIONS.map((r) => ({ value: r, label: r }))}
                              triggerStyle={{ minHeight: "28px", padding: "2px 8px", fontSize: "0.72rem" }}
                            />
                          </td>
                          <td style={{ padding: "6px 10px", color: col.is_sensitive ? "var(--amber-tier, #F59E0B)" : "var(--fg-muted, #94A3B8)" }}>
                            {col.is_sensitive ? "Yes" : "No"}
                          </td>
                        </tr>
                      ))
                    )}
                  </tbody>
                </table>
              </div>
            </div>

            {/* Candidate Joins Review */}
            {relationships.length > 0 && (
              <div>
                <label style={{ display: "block", fontSize: "0.8rem", fontWeight: 600, color: "var(--fg-secondary, #CBD5E1)", marginBottom: "4px" }}>
                  Multi-Sheet Relationships & Joins
                </label>
                <div style={{ display: "flex", flexDirection: "column", gap: "6px" }}>
                  {relationships.map((rel) => {
                    const isM2M = rel.cardinality === "MANY_TO_MANY";
                    const isChecked = Boolean(joinDecisions[rel.relationship_id]);

                    return (
                      <div
                        key={rel.relationship_id}
                        style={{
                          padding: "6px 10px",
                          borderRadius: "6px",
                          background: isM2M ? "rgba(245, 158, 11, 0.08)" : "rgba(255,255,255,0.03)",
                          border: isM2M ? "1px solid rgba(245, 158, 11, 0.2)" : "1px solid rgba(255,255,255,0.06)",
                          fontSize: "0.75rem"
                        }}
                      >
                        <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between" }}>
                          <span>
                            <strong>{rel.left_column}</strong> ↔ <strong>{rel.right_column}</strong> ({rel.cardinality})
                          </span>
                          <label style={{ display: "flex", alignItems: "center", gap: "4px", cursor: isM2M ? "not-allowed" : "pointer" }}>
                            <input
                              type="checkbox"
                              checked={isChecked}
                              disabled={isM2M}
                              onChange={() => handleJoinToggle(rel.relationship_id, isM2M)}
                            />
                            <span style={{ fontSize: "0.7rem", color: isM2M ? "var(--amber-tier, #F59E0B)" : "var(--fg-secondary, #CBD5E1)" }}>
                              {isM2M ? "Blocked (Unsafe)" : (isChecked ? "Active Join" : "Disabled")}
                            </span>
                          </label>
                        </div>
                        {isM2M && (
                          <div style={{ marginTop: "3px", fontSize: "0.7rem", color: "var(--amber-tier, #F59E0B)" }}>
                            Automatic join disabled because both sides contain repeated keys.
                          </div>
                        )}
                      </div>
                    );
                  })}
                </div>
              </div>
            )}
          </div>

          <div className="modal-footer" style={{ padding: "0.75rem 1.25rem", display: "flex", justifyContent: "flex-end", gap: "8px" }}>
            <button
              type="button"
              className="btn-secondary"
              onClick={onClose}
              disabled={saving}
              style={{ fontSize: "0.8rem", padding: "0.35rem 0.85rem" }}
            >
              Cancel
            </button>
            <button
              type="submit"
              className="btn-primary"
              disabled={saving}
              style={{
                fontSize: "0.8rem",
                padding: "0.35rem 0.85rem",
                display: "inline-flex",
                alignItems: "center",
                gap: "5px"
              }}
            >
              <Save size={13} />
              <span>{saving ? "Applying Corrections..." : "Save Corrections"}</span>
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}
