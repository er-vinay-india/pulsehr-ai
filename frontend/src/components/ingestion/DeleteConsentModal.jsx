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
              <h3 id="modal-title">Confirm Dataset Deletion</h3>
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
              <div className="target-name">{datasetToDelete.original_name}</div>
              <div className="target-meta">
                <span>{datasetToDelete.file_type.toUpperCase()}</span> · <span>{datasetToDelete.row_count} rows</span> · <span>{datasetToDelete.sheet_count} sheet(s)</span>
              </div>
            </div>
          </div>

          <div className="modal-warning-box">
            <div className="warning-title">
              <AlertTriangle size={15} />
              <span>Permanent Irreversible Action</span>
            </div>
            <ul>
              <li>Permanently erases all <strong>{datasetToDelete.row_count} indexed rows</strong> and cell values.</li>
              <li>Cleanses associated <strong>vector chunks & BM25 search indices</strong>.</li>
              <li>Unlinks all <strong>exact-key joins</strong> and relationships connected to this sheet.</li>
              <li>Removes stored file from local server storage.</li>
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
              I understand that this action is permanent, cannot be undone, and will immediately remove these rows from all analytics and Copilot searches.
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
            <span>{deleting ? "Deleting..." : "Permanently Delete"}</span>
          </button>
        </div>
      </div>
    </div>
  );
}
