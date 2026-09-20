import React, { useEffect, useState } from 'react';
import {
  X,
  Search,
  FileSpreadsheet,
  Layers,
  HelpCircle,
  ArrowRight,
  Database,
  ExternalLink,
  ShieldAlert,
  Info,
  ChevronRight
} from 'lucide-react';
import { investigateEvidence } from '../api/client';
import { formatDisplayLabel } from '../utils/displayFormatters';

export default function InvestigationDrawer({
  investigationTarget,
  onClose,
  onDrillDown
}) {
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [activeTab, setActiveTab] = useState('evidence'); // 'evidence' | 'records' | 'methodology'
  const [recordSearch, setRecordSearch] = useState('');

  useEffect(() => {
    if (!investigationTarget) return;
    setLoading(true);
    setError('');
    investigateEvidence(investigationTarget)
      .then((res) => {
        if (res.available) {
          setData(res);
        } else {
          setError(res.message || 'No investigation details available.');
        }
      })
      .catch((err) => {
        setError(err.message || 'Failed to load investigation evidence.');
      })
      .finally(() => setLoading(false));
  }, [investigationTarget]);

  if (!investigationTarget) return null;

  const obs = data?.observation;
  const meth = data?.methodology;
  const breakdowns = data?.timelines_and_breakdowns;
  const records = data?.source_records || [];
  const connected = data?.connected_evidence || [];
  const limitations = data?.limitations_and_uncertainty || [];
  const hrQuestions = data?.practical_hr_questions || [];

  // Filter raw records by search query
  const filteredRecords = recordSearch
    ? records.filter((r) =>
        Object.values(r.data || {}).some((val) =>
          String(val).toLowerCase().includes(recordSearch.toLowerCase())
        )
      )
    : records;

  // Extract columns for the raw records table
  const recordColumns = records.length > 0 && records[0].data
    ? Object.keys(records[0].data).filter((k) => !k.startsWith('__'))
    : [];

  return (
    <div className="drawer-overlay" onClick={onClose} role="dialog" aria-modal="true">
      <div className="investigation-drawer-panel" onClick={(e) => e.stopPropagation()}>
        {/* 1. Header with Breadcrumbs and Close Button */}
        <div className="investigation-drawer-header">
          <div className="header-title-meta">
            <div className="drawer-breadcrumbs">
              <span>Workspace</span>
              <ChevronRight size={14} />
              <span>{data?.investigation_type ? data.investigation_type.toUpperCase() : 'INVESTIGATION'}</span>
              <ChevronRight size={14} />
              <span className="current-crumb">{data?.target || investigationTarget.targetId || 'Evidence'}</span>
            </div>
            <h2>{obs?.headline || data?.target || 'Contextual Evidence Investigation'}</h2>
            <div className="drawer-subtitle-tags">
              <span className="source-tag">
                <FileSpreadsheet size={13} />
                {data?.source_file || 'Workspace Sheet'}
              </span>
              {data?.metric && (
                <span className="metric-tag" title={`Source field: ${data.metric}`}>
                  Target Metric: <strong>{formatDisplayLabel(data.metric)}</strong>
                </span>
              )}
            </div>
          </div>
          <button type="button" className="close-btn" onClick={onClose} aria-label="Close Investigation Drawer">
            <X size={20} />
          </button>
        </div>

        {/* 2. Navigation Tabs */}
        <div className="investigation-tabs">
          <button
            className={`inv-tab-btn ${activeTab === 'evidence' ? 'active' : ''}`}
            onClick={() => setActiveTab('evidence')}
          >
            Findings & Evidence
          </button>
          <button
            className={`inv-tab-btn ${activeTab === 'records' ? 'active' : ''}`}
            onClick={() => setActiveTab('records')}
          >
            Source Records ({records.length})
          </button>
          <button
            className={`inv-tab-btn ${activeTab === 'methodology' ? 'active' : ''}`}
            onClick={() => setActiveTab('methodology')}
          >
            Formula & Methodology
          </button>
        </div>

        {/* 3. Drawer Body */}
        <div className="investigation-drawer-body">
          {loading ? (
            <div className="drawer-loading-state">
              <div className="loading-spinner" />
              <p>Gathering evidence, calculation proofs, and verified source records...</p>
            </div>
          ) : error ? (
            <div className="drawer-error-state">
              <ShieldAlert size={28} color="var(--rose-tier)" />
              <p>{error}</p>
              <button className="btn-secondary" onClick={onClose}>Close</button>
            </div>
          ) : (
            <>
              {/* TAB 1: FINDINGS & EVIDENCE */}
              {activeTab === 'evidence' && (
                <div className="tab-pane evidence-pane">
                  {/* Observation KPI Strip */}
                  <div className="observation-kpi-grid">
                    <div className="inv-kpi-card highlight">
                      <div className="inv-kpi-label">Observed Measure</div>
                      <div className="inv-kpi-val">{obs?.observed_value || 'N/A'}</div>
                      <div className="inv-kpi-sub">{obs?.population_count}</div>
                    </div>
                    <div className="inv-kpi-card">
                      <div className="inv-kpi-label">Comparison Benchmark</div>
                      <div className="inv-kpi-val">{obs?.benchmark_value || 'Org Baseline'}</div>
                      <div className="inv-kpi-sub">{obs?.variance || 'Evaluated Standard'}</div>
                    </div>
                    <div className="inv-kpi-card">
                      <div className="inv-kpi-label">Reporting Period</div>
                      <div className="inv-kpi-val" style={{ fontSize: '1rem', marginTop: 4 }}>
                        {obs?.reporting_period || 'Current Session'}
                      </div>
                      <div className="inv-kpi-sub">Source: {data?.sheet_name}</div>
                    </div>
                  </div>

                  {/* Timelines & Breakdowns */}
                  {breakdowns && breakdowns.items && breakdowns.items.length > 0 && (
                    <div className="inv-section-card">
                      <div className="inv-section-title">
                        <Layers size={16} />
                        <span>{breakdowns.title || 'Component Breakdown'}</span>
                      </div>
                      {breakdowns.factual_context && (
                        <p className="factual-context-note">{breakdowns.factual_context}</p>
                      )}
                      <div className="breakdown-items-list">
                        {breakdowns.items.map((item, idx) => (
                          <div key={idx} className="breakdown-item-row">
                            <span className="item-name">{item.name}</span>
                            <div className="item-val-group">
                              <span className="item-val">{item.value} {item.unit}</span>
                              {onDrillDown && item.name && (
                                <button
                                  className="btn-link-action"
                                  onClick={() =>
                                    onDrillDown({
                                      entityType: 'employee',
                                      targetId: item.name,
                                      metric: data?.metric,
                                      sheetId: data?.sheet_id
                                    })
                                  }
                                >
                                  Drill Down <ArrowRight size={12} />
                                </button>
                              )}
                            </div>
                          </div>
                        ))}
                      </div>
                    </div>
                  )}

                  {/* Connected Evidence from other sheets */}
                  {connected.length > 0 && (
                    <div className="inv-section-card connected-evidence-section">
                      <div className="inv-section-title">
                        <Database size={16} color="var(--accent)" />
                        <span>Connected Cross-Sheet Evidence ({connected.length})</span>
                      </div>
                      <p className="section-desc">
                        Matches discovered using verified key relationships across uploaded workbooks.
                      </p>
                      {connected.map((connItem, cIdx) => (
                        <div key={cIdx} className="connected-sheet-box">
                          <div className="conn-header">
                            <span className="conn-sheet-name">
                              <FileSpreadsheet size={14} /> {connItem.related_file} ({connItem.related_sheet})
                            </span>
                            <span className="conn-match-pill">{connItem.matched_count} Matched Records</span>
                          </div>
                          <div className="conn-key-note">Join Key: <code>{connItem.join_key}</code></div>
                          {connItem.sample_rows && connItem.sample_rows.length > 0 && (
                            <div className="conn-samples">
                              {connItem.sample_rows.map((sr, sIdx) => (
                                <div key={sIdx} className="sample-mini-chip">
                                  {Object.entries(sr).slice(0, 4).map(([k, v]) => (
                                    <span key={k}>
                                      <strong>{k}:</strong> {String(v)}
                                    </span>
                                  ))}
                                </div>
                              ))}
                            </div>
                          )}
                        </div>
                      ))}
                    </div>
                  )}

                  {/* Limitations & Uncertainty Notice */}
                  {limitations.length > 0 && (
                    <div className="inv-section-card limitations-card">
                      <div className="inv-section-title">
                        <Info size={16} />
                        <span>Data Limitations & Unobserved Factors</span>
                      </div>
                      <ul className="limitations-list">
                        {limitations.map((lim, lIdx) => (
                          <li key={lIdx}>{lim}</li>
                        ))}
                      </ul>
                    </div>
                  )}

                  {/* Practical Questions for HR */}
                  {hrQuestions.length > 0 && (
                    <div className="inv-section-card hr-questions-card">
                      <div className="inv-section-title">
                        <HelpCircle size={16} color="var(--accent)" />
                        <span>Practical Next Steps for HR</span>
                      </div>
                      <p className="section-desc">
                        Objective, evidence-based follow-up questions to investigate with team leads or in HR systems.
                      </p>
                      <ul className="hr-questions-list">
                        {hrQuestions.map((q, qIdx) => (
                          <li key={qIdx}>
                            <span className="q-bullet">●</span>
                            <span>{q}</span>
                          </li>
                        ))}
                      </ul>
                    </div>
                  )}
                </div>
              )}

              {/* TAB 2: SOURCE RECORDS EXPLORER */}
              {activeTab === 'records' && (
                <div className="tab-pane records-pane">
                  <div className="records-toolbar">
                    <div className="records-search-box">
                      <Search size={15} />
                      <input
                        type="text"
                        placeholder="Search records in this cohort..."
                        value={recordSearch}
                        onChange={(e) => setRecordSearch(e.target.value)}
                      />
                      {recordSearch && (
                        <button className="btn-clear-search" onClick={() => setRecordSearch('')}>✕</button>
                      )}
                    </div>
                    <span className="records-count">
                      Showing {filteredRecords.length} of {records.length} records
                    </span>
                  </div>

                  {filteredRecords.length === 0 ? (
                    <div className="records-empty">No matching records found.</div>
                  ) : (
                    <div className="source-table-wrapper">
                      <table className="source-data-table">
                        <thead>
                          <tr>
                            <th># Row</th>
                            <th>Source File</th>
                            {recordColumns.map((col) => (
                              <th key={col} title={`Source field: ${col}`}>
                                {formatDisplayLabel(col)}
                              </th>
                            ))}
                          </tr>
                        </thead>
                        <tbody>
                          {filteredRecords.map((r, rIdx) => (
                            <tr key={rIdx}>
                              <td className="row-num-cell">#{r.row_index}</td>
                              <td className="row-file-cell">{r.file}</td>
                              {recordColumns.map((col) => (
                                <td key={col} className={col === data?.metric ? 'metric-highlight-cell' : ''}>
                                  {r.data && r.data[col] != null ? String(r.data[col]) : '—'}
                                </td>
                              ))}
                            </tr>
                          ))}
                        </tbody>
                      </table>
                    </div>
                  )}
                </div>
              )}

              {/* TAB 3: FORMULA & METHODOLOGY */}
              {activeTab === 'methodology' && (
                <div className="tab-pane methodology-pane">
                  <div className="inv-section-card">
                    <div className="inv-section-title">
                      <HelpCircle size={16} />
                      <span>Calculation Formula & Definition</span>
                    </div>
                    <div className="formula-display-box">
                      <code>{meth?.formula || 'Direct Row Extraction'}</code>
                    </div>

                    <div className="formula-components-grid">
                      <div className="formula-comp-card">
                        <span className="comp-label">Numerator</span>
                        <span className="comp-val">{meth?.numerator || 'Aggregated Cohort Value'}</span>
                      </div>
                      <div className="formula-comp-card">
                        <span className="comp-label">Denominator</span>
                        <span className="comp-val">{meth?.denominator || 'Cohort Population'}</span>
                      </div>
                    </div>

                    {meth?.steps && meth.steps.length > 0 && (
                      <div className="calculation-steps-block">
                        <h4>Execution Steps</h4>
                        <ol className="steps-ordered-list">
                          {meth.steps.map((step, sIdx) => (
                            <li key={sIdx}>{step}</li>
                          ))}
                        </ol>
                      </div>
                    )}
                  </div>
                </div>
              )}
            </>
          )}
        </div>
      </div>
    </div>
  );
}
