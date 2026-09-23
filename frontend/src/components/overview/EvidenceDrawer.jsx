import React, { useEffect } from 'react';
import { X, ArrowRight, Database, CheckCircle, ShieldCheck, FileSpreadsheet } from 'lucide-react';

const fmt = (n) => (n == null ? 'Unavailable' : Number(n).toLocaleString(undefined, { maximumFractionDigits: 2 }));

export default function EvidenceDrawer({
  isOpen,
  onClose,
  finding,
  onNavigateExplorer
}) {
  useEffect(() => {
    const handleKeyDown = (e) => {
      if (e.key === 'Escape' && isOpen) onClose();
    };
    window.addEventListener('keydown', handleKeyDown);
    return () => window.removeEventListener('keydown', handleKeyDown);
  }, [isOpen, onClose]);

  if (!isOpen || !finding) return null;

  const d = finding.detail || {};

  return (
    <div className="offcanvas-backdrop" onClick={onClose}>
      <aside
        className="offcanvas-drawer"
        onClick={(e) => e.stopPropagation()}
        role="dialog"
        aria-modal="true"
        aria-label="Evidence & Methodology Drawer"
      >
        <div className="offcanvas-header">
          <div className="offcanvas-title-group">
            <span className="offcanvas-eyebrow">
              <ShieldCheck size={14} color="#10b981" /> Verified Evidence Ledger
            </span>
            <h3>{finding.title}</h3>
          </div>
          <button
            type="button"
            className="offcanvas-close-btn"
            onClick={onClose}
            aria-label="Close drawer"
          >
            <X size={18} />
          </button>
        </div>

        <div className="offcanvas-body">
          {/* Provenance Box */}
          <div className="evidence-provenance-card">
            <div className="provenance-row">
              <span className="prov-label">Data Source</span>
              <span className="prov-val">
                <FileSpreadsheet size={13} style={{ marginRight: 4 }} />
                {finding.source?.file || 'Current Workspace'} / {finding.source?.sheet}
              </span>
            </div>
            <div className="provenance-row">
              <span className="prov-label">Ledger Key</span>
              <code className="prov-code">{finding.id}</code>
            </div>
            {d.total_rows != null && (
              <div className="provenance-row">
                <span className="prov-label">Sample Coverage</span>
                <span className="prov-val">
                  <strong>{Number(d.used_rows || 0).toLocaleString()}</strong> valid rows of {Number(d.total_rows || 0).toLocaleString()} total records
                </span>
              </div>
            )}
          </div>

          {/* Methodology Note */}
          <div className="evidence-section">
            <h4>Calculation Methodology</h4>
            <p className="method-desc">{finding.method}</p>
          </div>

          {/* Group Breakdown Table */}
          {d.groups && d.groups.length > 0 && (
            <div className="evidence-section">
              <h4>Segment Breakdown ({d.dimension})</h4>
              <div className="evidence-table-wrap">
                <table className="evidence-table">
                  <thead>
                    <tr>
                      <th>Segment</th>
                      <th>Mean</th>
                      <th>Median</th>
                      <th>Valid Records</th>
                    </tr>
                  </thead>
                  <tbody>
                    {d.groups.map((g) => (
                      <tr key={g.group}>
                        <td><strong>{g.group}</strong></td>
                        <td>{fmt(g.value)}</td>
                        <td>{fmt(g.median)}</td>
                        <td>{Number(g.used_rows || 0).toLocaleString()}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </div>
          )}

          {/* Time-series Breakdown Table */}
          {d.points && d.points.length > 0 && (
            <div className="evidence-section">
              <h4>Timeline Observations</h4>
              <div className="evidence-table-wrap">
                <table className="evidence-table">
                  <thead>
                    <tr>
                      <th>Month</th>
                      <th>Recorded Mean</th>
                      <th>Sample Count</th>
                    </tr>
                  </thead>
                  <tbody>
                    {d.points.map((p) => (
                      <tr key={p.period}>
                        <td>{p.period}</td>
                        <td>{fmt(p.value)}</td>
                        <td>{Number(p.used_rows || 0).toLocaleString()}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </div>
          )}
        </div>

        <div className="offcanvas-footer">
          <button
            type="button"
            className="btn-deep-explore"
            onClick={() => {
              onClose();
              if (onNavigateExplorer) onNavigateExplorer();
            }}
          >
            <Database size={15} />
            <span>Open in Data Explorer</span>
            <ArrowRight size={14} />
          </button>
        </div>
      </aside>
    </div>
  );
}
