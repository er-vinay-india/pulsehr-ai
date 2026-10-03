import React, { useEffect, useRef } from "react";
import { AlertTriangle, FileSpreadsheet, Trash2, X } from "lucide-react";

export default function DeleteConsentModal({
  datasetToDelete,
  deleteConsent,
  setDeleteConsent,
  deleting,
  onClose,
  onConfirmDelete,
  error,
}) {
  const dialogRef = useRef(null);
  const cancelRef = useRef(null);
  const latest = useRef(null);
  latest.current = { deleting, onClose };
  const isOpen = Boolean(datasetToDelete);
  useEffect(() => {
    if (!isOpen) return;
    const previousFocus = document.activeElement;
    cancelRef.current?.focus();
    const handleKey = event => {
      if (event.key === 'Escape' && !latest.current.deleting) latest.current.onClose();
      if (event.key !== 'Tab') return;
      const nodes = [...dialogRef.current.querySelectorAll('button:not(:disabled), input:not(:disabled)')];
      const first = nodes[0], last = nodes[nodes.length - 1];
      if (event.shiftKey && document.activeElement === first) { event.preventDefault(); last?.focus(); }
      if (!event.shiftKey && document.activeElement === last) { event.preventDefault(); first?.focus(); }
    };
    document.addEventListener('keydown', handleKey);
    return () => { document.removeEventListener('keydown', handleKey); previousFocus?.focus(); };
  }, [isOpen]);
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
      <div className="modal-dialog" ref={dialogRef} aria-busy={deleting} onClick={(e) => e.stopPropagation()}>
        <div className="modal-header">
          <div className="modal-title-group">
            <div className="modal-icon-badge">
              <AlertTriangle size={20} />
            </div>
            <div>
              <h3 id="modal-title">
                {datasetToDelete.cleanupPending ? "Finish stored file cleanup" : isBulk ? (isAll ? "Delete all workbooks?" : `Delete ${count} workbooks?`) : "Delete this workbook?"}
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
            aria-label="Cancel and close deletion"
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
              <li>Deletes <strong>every sheet and all {totalRows.toLocaleString()} records</strong> in {isBulk ? "these workbooks" : "this workbook"}.</li>
              <li>Removes generated tables, relationships, search data and cached analysis that depend on them.</li>
              <li>Deletes dependent saved presentations, presentation memory and exported files.</li>
              <li>Removes the uploaded {isBulk ? "files" : "file"} from server storage. Other workbooks are kept.</li>
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
          {error && <div className="alert-box alert-error" role="alert">{error}</div>}
        </div>

        <div className="modal-footer">
          <button
            type="button"
            className="btn-cancel"
            ref={cancelRef}
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
                ? "Deleting and cleaning up…"
                : datasetToDelete.cleanupPending
                ? "Retry cleanup"
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
