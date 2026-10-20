import React, { useState, useEffect, useMemo } from 'react';
import { Table, X, ChevronRight } from 'lucide-react';
import DataTable from '../DataTable';
import { formatDisplayLabel, formatCompleteNumber } from '../../utils/displayFormatters';

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
      if (Math.abs(v) >= 1_000) return `$${(v / 1_000).toFixed(2)}k`;
      return `$${Number(v).toFixed(2)}`;
    }
    const num = Number(v);
    if (!Number.isInteger(num)) {
      return `${num.toLocaleString('en-US', { minimumFractionDigits: 0, maximumFractionDigits: 2 })} ${unit}`.trim();
    }
    return `${Number(v).toLocaleString()} ${unit}`.trim();
  };

  const highest = items.length > 0 ? items.reduce((prev, curr) => (curr.value > prev.value ? curr : prev), items[0]) : null;
  const lowest = items.length > 0 ? items.reduce((prev, curr) => (curr.value < prev.value ? curr : prev), items[0]) : null;
  const spreadRatio = lowest && lowest.value > 0 ? (highest.value / lowest.value).toFixed(2) : null;

  const modalRows = useMemo(() => {
    return items.map((it, idx) => ({
      ...it,
      rank: it.rank || idx + 1,
      _index: idx,
    }));
  }, [items]);

  const modalColumns = useMemo(() => {
    const cols = [
      {
        key: "rank",
        label: "Rank",
        type: "numeric",
        sortable: true,
        defaultVisible: true,
        width: "70px",
        render: (val, r) => (
          <span className="table-rank-chip">#{val || r._index + 1}</span>
        ),
      },
      {
        key: "label",
        label: formatDisplayLabel(entityLabel),
        type: "text",
        sortable: true,
        defaultVisible: true,
        render: (val) => <span className="font-semibold">{val}</span>,
      },
      {
        key: "value",
        label: formatDisplayLabel(metricName),
        type: "numeric",
        sortable: true,
        defaultVisible: true,
        sortVal: (r) => (r.value != null ? Number(r.value) : -Infinity),
        render: (val) => (
          <span className="font-mono" title={`Complete: ${formatCompleteNumber(val)}`} style={{ cursor: "help" }}>
            {formatVal(val)}
          </span>
        ),
      },
    ];

    if (benchmarkMean != null) {
      cols.push({
        key: "diffPct",
        label: "vs Benchmark",
        type: "percentage",
        sortable: true,
        defaultVisible: true,
        sortVal: (r) => (r.value != null && benchmarkMean ? ((r.value - benchmarkMean) / benchmarkMean) * 100 : -Infinity),
        render: (_, r) => {
          const diffPct = benchmarkMean && r.value != null ? ((r.value - benchmarkMean) / benchmarkMean) * 100 : null;
          const isPositive = diffPct != null && diffPct >= 0;
          return diffPct != null ? (
            <span
              className={`diff-pill ${isPositive ? "diff-up" : "diff-down"}`}
              title={`Complete: ${diffPct}%`}
              style={{ cursor: "help" }}
            >
              {isPositive ? `+${diffPct.toFixed(2)}%` : `${diffPct.toFixed(2)}%`}
            </span>
          ) : (
            "—"
          );
        },
      });
    }

    if (benchmarkTotal != null) {
      cols.push({
        key: "sharePct",
        label: "Share of Total",
        type: "percentage",
        sortable: true,
        defaultVisible: true,
        sortVal: (r) => (r.value != null && benchmarkTotal ? (r.value / benchmarkTotal) * 100 : -Infinity),
        render: (_, r) => {
          const sharePct = benchmarkTotal && r.value != null ? ((r.value / benchmarkTotal) * 100).toFixed(2) : null;
          return (
            <span
              className="font-mono text-muted"
              title={sharePct != null ? `Complete: ${(r.value / benchmarkTotal) * 100}%` : ""}
              style={sharePct != null ? { cursor: "help" } : {}}
            >
              {sharePct != null ? `${sharePct}%` : "—"}
            </span>
          );
        },
      });
    }

    if (onInvestigate) {
      cols.push({
        key: "investigate",
        label: "Evidence Drilldown",
        sortable: false,
        filterable: false,
        defaultVisible: true,
        render: (_, item) => (
          <button
            type="button"
            className="btn-table-investigate"
            onClick={(e) => {
              e.stopPropagation();
              onClose();
              onInvestigate({
                entityType,
                targetId: item.label,
                metric: metricName,
                sheetId,
              });
            }}
            title={`Investigate ${item.label}`}
          >
            <span>Investigate</span>
            <ChevronRight size={13} />
          </button>
        ),
      });
    }

    return cols;
  }, [entityLabel, metricName, benchmarkMean, benchmarkTotal, isCurrency, onInvestigate, entityType, sheetId, onClose]);

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

        {/* Reusable Enterprise DataTable */}
        <div style={{ padding: "0 18px 18px", overflowY: "auto" }}>
          <DataTable
            columns={modalColumns}
            rows={modalRows}
            totalRows={modalRows.length}
            pageSize={25}
            searchable={true}
            searchPlaceholder={`Search ${items.length} ${entityLabel.toLowerCase()}s...`}
            columnVisibilityEnabled={true}
            emptyMessage={`No ${entityLabel.toLowerCase()} records match your search.`}
            tableAriaLabel={`${title} dataset view`}
          />
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
