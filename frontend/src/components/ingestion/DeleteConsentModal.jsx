import React from "react";
import { AlertTriangle, FileSpreadsheet, Trash2, X } from "lucide-react";

export default function DeleteConsentModal({
  datasetToDelete,
  deleteConsent,
  setDeleteConsent,
  deleting,
  onClose,
  onConfirmDelete,
}) {
  if (!datasetToDelete) return null;

  const isBulk = Boolean(datasetToDelete.isBulk);
  const isAll = Boolean(datasetToDelete.isAll);
  const datasets = datasetToDelete.datasets || (datasetToDelete.id ? [datasetToDelete] : []);
  const count = datasets.length;
  const totalRows = datasetToDelete.totalRows ?? datasets.reduce((sum, d) => sum + (Number(d.row_count) || 0), 0);

  return (
    <div
      className="modal-overlay"
      onClick={() => !deleting && onClose()}
      role="dialog"
      aria-modal="true"
      aria-labelledby="modal-title"
    >
      <div className="modal-dialog" onClick={(e) => e.stopPropagation()}>
        <div className="modal-header">
          <div className="modal-title-group">
            <div className="modal-icon-badge">
              <AlertTriangle size={20} />
            </div>
            <div>
              <h3 id="modal-title">
                {isBulk ? (isAll ? "Confirm Delete All Datasets" : `Confirm Bulk Deletion (${count} Datasets)`) : "Confirm Dataset Deletion"}
              </h3>
              <p>Explicit consent required before permanent removal</p>
            </div>
          </div>
          <button
            type="button"
            className="modal-close-btn"
            onClick={() => !deleting && onClose()}
            disabled={deleting}
            title="Cancel and close"
          >
            <X size={18} />
          </button>
        </div>

        <div className="modal-body">
          <div className="modal-target-box">
            <FileSpreadsheet size={24} color="var(--accent-500)" style={{ flexShrink: 0 }} />
            <div style={{ flex: 1, minWidth: 0 }}>
              <div className="target-name">
                {isBulk
                  ? (isAll ? `All Workspace Datasets (${count} files)` : `${count} Selected Datasets`)
                  : datasetToDelete.original_name}
              </div>
              <div className="target-meta">
                {isBulk ? (
                  <span><strong>{totalRows.toLocaleString()}</strong> total rows across <strong>{count}</strong> file(s)</span>
                ) : (
                  <>
                    <span>{(datasetToDelete.file_type || "file").toUpperCase()}</span> · <span>{datasetToDelete.row_count} rows</span> · <span>{datasetToDelete.sheet_count || 1} sheet(s)</span>
                  </>
                )}
              </div>
              {isBulk && datasets.length > 0 && (
                <div style={{ marginTop: "6px", fontSize: "0.75rem", color: "var(--fg-muted)", maxHeight: "70px", overflowY: "auto", borderTop: "1px dashed var(--border-subtle, #3d362f)", paddingTop: "4px" }}>
                  {datasets.map((d, i) => (
                    <div key={d.id || i} style={{ whiteSpace: "nowrap", overflow: "hidden", textOverflow: "ellipsis" }}>
                      • {d.display_name || d.original_name} ({d.row_count || 0} rows)
                    </div>
                  ))}
                </div>
              )}
            </div>
          </div>

          <div className="modal-warning-box">
            <div className="warning-title">
              <AlertTriangle size={15} />
              <span>Permanent Irreversible Action</span>
            </div>
            <ul>
              <li>Permanently erases all <strong>{totalRows.toLocaleString()} indexed rows</strong> and cell values.</li>
              <li>Cleanses associated <strong>vector chunks & BM25 search indices</strong>.</li>
              <li>Unlinks all <strong>exact-key joins</strong> and relationships connected to {isBulk ? "these sheets" : "this sheet"}.</li>
              <li>Removes stored {isBulk ? "files" : "file"} from local server storage.</li>
            </ul>
          </div>

          <label className="modal-consent-checkbox">
            <input
              type="checkbox"
              checked={deleteConsent}
              onChange={(e) => setDeleteConsent(e.target.checked)}
              disabled={deleting}
            />
            <span>
              I understand that this action is permanent, cannot be undone, and will immediately remove {isBulk ? "these datasets" : "this dataset"} from all analytics and Copilot searches.
            </span>
          </label>
        </div>

        <div className="modal-footer">
          <button
            type="button"
            className="btn-cancel"
            onClick={onClose}
            disabled={deleting}
          >
            Cancel
          </button>
          <button
            type="button"
            className="btn-danger-confirm"
            onClick={onConfirmDelete}
            disabled={!deleteConsent || deleting}
          >
            <Trash2 size={14} />
            <span>
              {deleting
                ? "Deleting..."
                : isBulk
                ? isAll
                  ? "Permanently Delete All"
                  : `Permanently Delete (${count})`
                : "Permanently Delete"}
            </span>
          </button>
        </div>
      </div>
    </div>
  );
}
