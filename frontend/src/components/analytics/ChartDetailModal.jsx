import React, { useState, useEffect } from 'react';
import { Table, X, Search, ArrowUpDown, ChevronRight } from 'lucide-react';
import { formatDisplayLabel } from '../../utils/displayFormatters';

export default function ChartDetailModal({
  isOpen,
  onClose,
  title,
  subtitle,
  items = [],
  benchmarkMean,
  benchmarkTotal,
  unit = '',
  isCurrency = false,
  entityLabel = 'Entity',
  metricName = 'Observed Value',
  population = 'All records',
  entityType = 'category',
  sheetId = null,
  onInvestigate
}) {
  const [filterText, setFilterText] = useState('');
  const [sortField, setSortField] = useState('rank'); // 'rank', 'label', 'value'
  const [sortAsc, setSortAsc] = useState(true);

  // Close on Escape key
  useEffect(() => {
    if (!isOpen) return;
    const handleKeyDown = (e) => {
      if (e.key === 'Escape') onClose();
    };
    window.addEventListener('keydown', handleKeyDown);
    return () => window.removeEventListener('keydown', handleKeyDown);
  }, [isOpen, onClose]);

  if (!isOpen) return null;

  const formatVal = (v) => {
    if (v == null || isNaN(v)) return '—';
    if (isCurrency) {
      if (Math.abs(v) >= 1_000_000_000) return `$${(v / 1_000_000_000).toFixed(2)}B`;
      if (Math.abs(v) >= 1_000_000) return `$${(v / 1_000_000).toFixed(2)}M`;
      if (Math.abs(v) >= 1_000) return `$${(v / 1_000).toFixed(1)}k`;
      return `$${Number(v).toFixed(2)}`;
    }
    return `${Number(v).toLocaleString()} ${unit}`;
  };

  const highest = items.length > 0 ? items.reduce((prev, curr) => (curr.value > prev.value ? curr : prev), items[0]) : null;
  const lowest = items.length > 0 ? items.reduce((prev, curr) => (curr.value < prev.value ? curr : prev), items[0]) : null;
  const spreadRatio = lowest && lowest.value > 0 ? (highest.value / lowest.value).toFixed(2) : null;

  const filteredItems = items.filter((it) =>
    String(it.label || '').toLowerCase().includes(filterText.toLowerCase().trim())
  );

  const sortedItems = [...filteredItems].sort((a, b) => {
    if (sortField === 'rank') {
      return sortAsc ? (a.rank || 0) - (b.rank || 0) : (b.rank || 0) - (a.rank || 0);
    }
    if (sortField === 'label') {
      return sortAsc ? String(a.label).localeCompare(String(b.label)) : String(b.label).localeCompare(String(a.label));
    }
    if (sortField === 'value') {
      return sortAsc ? a.value - b.value : b.value - a.value;
    }
    return 0;
  });

  const handleSort = (field) => {
    if (sortField === field) {
      setSortAsc(!sortAsc);
    } else {
      setSortField(field);
      setSortAsc(field === 'label' || field === 'rank');
    }
  };

  return (
    <div className="chart-detail-modal-backdrop" onClick={onClose} role="presentation">
      <div
        className="chart-detail-modal-content"
        onClick={(e) => e.stopPropagation()}
        role="dialog"
        aria-modal="true"
        aria-labelledby="detail-modal-title"
      >
        <div className="modal-header">
          <div>
            <div className="modal-title-row">
              <Table size={18} className="modal-header-icon" />
              <h3 id="detail-modal-title">Complete Dataset View: {title}</h3>
            </div>
            <p className="modal-subtitle">
              {subtitle || `Comprehensive tabular profile of ${items.length} records · Scope: ${population}`}
            </p>
          </div>
          <button type="button" className="btn-modal-close" onClick={onClose} aria-label="Close table view">
            <X size={18} />
          </button>
        </div>

        {/* Aggregate KPI Summary Strip */}
        <div className="modal-kpi-summary-strip">
          <div className="modal-kpi-pill">
            <span className="kpi-label">Total Entities:</span>
            <span className="kpi-val">{items.length}</span>
          </div>
          {benchmarkMean != null && (
            <div className="modal-kpi-pill highlight-benchmark">
              <span className="kpi-label">Dataset Benchmark (Mean):</span>
              <span className="kpi-val">{formatVal(benchmarkMean)}</span>
            </div>
          )}
          {highest && (
            <div className="modal-kpi-pill">
              <span className="kpi-label">Highest ({highest.label}):</span>
              <span className="kpi-val text-green">{formatVal(highest.value)}</span>
            </div>
          )}
          {lowest && (
            <div className="modal-kpi-pill">
              <span className="kpi-label">Lowest ({lowest.label}):</span>
              <span className="kpi-val text-coral">{formatVal(lowest.value)}</span>
            </div>
          )}
          {spreadRatio && (
            <div className="modal-kpi-pill">
              <span className="kpi-label">Dispersion Spread:</span>
              <span className="kpi-val">{spreadRatio}x</span>
            </div>
          )}
        </div>

        {/* Search and Table Controls */}
        <div className="modal-toolbar">
          <div className="modal-search-box">
            <Search size={14} className="search-icon" />
            <input
              type="text"
              placeholder={`Search ${items.length} ${entityLabel.toLowerCase()}s...`}
              value={filterText}
              onChange={(e) => setFilterText(e.target.value)}
              className="modal-search-input"
            />
            {filterText && (
              <button
                type="button"
                className="btn-clear-search"
                onClick={() => setFilterText('')}
                aria-label="Clear filter"
              >
                <X size={12} />
              </button>
            )}
          </div>
          <span className="modal-showing-count">
            Showing <strong>{sortedItems.length}</strong> of {items.length} {entityLabel.toLowerCase()}
          </span>
        </div>

        {/* Scrollable Table Container */}
        <div className="modal-table-scroll-wrap">
          <table className="chart-detail-table">
            <thead>
              <tr>
                <th onClick={() => handleSort('rank')} className="sortable-th th-rank">
                  <span>Rank</span>
                  <ArrowUpDown size={12} className={sortField === 'rank' ? 'active-sort' : ''} />
                </th>
                <th onClick={() => handleSort('label')} className="sortable-th th-label" title={`Category dimension: ${entityLabel}`}>
                  <span>{formatDisplayLabel(entityLabel)}</span>
                  <ArrowUpDown size={12} className={sortField === 'label' ? 'active-sort' : ''} />
                </th>
                <th onClick={() => handleSort('value')} className="sortable-th th-val" title={`Source field: ${metricName}`}>
                  <span>{formatDisplayLabel(metricName)}</span>
                  <ArrowUpDown size={12} className={sortField === 'value' ? 'active-sort' : ''} />
                </th>
                {benchmarkMean != null && (
                  <th className="th-benchmark">
                    <span>vs Benchmark</span>
                  </th>
                )}
                {benchmarkTotal != null && (
                  <th className="th-share">
                    <span>Share of Total</span>
                  </th>
                )}
                <th className="th-action">
                  <span>Evidence Drilldown</span>
                </th>
              </tr>
            </thead>
            <tbody>
              {sortedItems.map((item, idx) => {
                const diffPct = benchmarkMean ? ((item.value - benchmarkMean) / benchmarkMean) * 100 : null;
                const sharePct = benchmarkTotal ? ((item.value / benchmarkTotal) * 100).toFixed(2) : null;
                const isPositive = diffPct != null && diffPct >= 0;

                return (
                  <tr key={idx} className="detail-table-row">
                    <td className="td-rank">
                      <span className="table-rank-chip">#{item.rank || idx + 1}</span>
                    </td>
                    <td className="td-label font-semibold">{item.label}</td>
                    <td className="td-val font-mono">{formatVal(item.value)}</td>
                    {benchmarkMean != null && (
                      <td className="td-benchmark">
                        {diffPct != null ? (
                          <span className={`diff-pill ${isPositive ? 'diff-up' : 'diff-down'}`}>
                            {isPositive ? `+${diffPct.toFixed(1)}%` : `${diffPct.toFixed(1)}%`}
                          </span>
                        ) : '—'}
                      </td>
                    )}
                    {benchmarkTotal != null && (
                      <td className="td-share font-mono text-muted">
                        {sharePct != null ? `${sharePct}%` : '—'}
                      </td>
                    )}
                    <td className="td-action">
                      {onInvestigate && (
                        <button
                          type="button"
                          className="btn-table-investigate"
                          onClick={() => {
                            onClose();
                            onInvestigate({
                              entityType: entityType,
                              targetId: item.label,
                              metric: metricName,
                              sheetId: sheetId
                            });
                          }}
                          title={`Investigate ${item.label}`}
                        >
                          <span>Investigate</span>
                          <ChevronRight size={13} />
                        </button>
                      )}
                    </td>
                  </tr>
                );
              })}
              {sortedItems.length === 0 && (
                <tr>
                  <td colSpan={6} className="modal-empty-search">
                    No {entityLabel.toLowerCase()} matched "{filterText}".
                  </td>
                </tr>
              )}
            </tbody>
          </table>
        </div>

        {/* Modal Footer */}
        <div className="modal-footer">
          <span className="footer-pop-note">
            Full data population: <strong>{population}</strong> · Source: Verified Sheet Catalog
          </span>
          <button type="button" className="btn-modal-done" onClick={onClose}>
            Done
          </button>
        </div>
      </div>
    </div>
  );
}
