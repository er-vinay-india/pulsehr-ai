import React from 'react';
import { Table, Search, X } from 'lucide-react';

export default function DataDensityToolbar({
  totalCount,
  visibleCount,
  viewMode,
  onViewModeChange,
  searchQuery,
  onSearchChange,
  entityLabel = 'entities',
  rankingBasis = '',
  benchmarkMean,
  isCurrency = false,
  unit = '',
  onOpenModal
}) {
  const formatVal = (v) => {
    if (v == null || isNaN(v)) return '—';
    if (isCurrency) {
      if (Math.abs(v) >= 1_000_000) return `$${(v / 1_000_000).toFixed(2)}M`;
      if (Math.abs(v) >= 1_000) return `$${(v / 1_000).toFixed(1)}k`;
      return `$${Number(v).toFixed(2)}`;
    }
    return `${Number(v).toLocaleString()} ${unit}`;
  };

  const isHighCount = totalCount > 10;

  return (
    <div className="density-toolbar-wrap">
      {/* Top Meta Line: Status disclosure + Benchmark */}
      <div className="density-meta-line">
        <div className="density-subset-pill">
          {searchQuery ? (
            <span>
              Matching <strong>{visibleCount}</strong> of <strong>{totalCount}</strong> {entityLabel}
            </span>
          ) : viewMode === 'top' && isHighCount ? (
            <span>
              Showing <strong>Top {visibleCount}</strong> of <strong>{totalCount}</strong> {entityLabel} · {rankingBasis}
            </span>
          ) : viewMode === 'bottom' && isHighCount ? (
            <span>
              Showing <strong>Bottom {visibleCount}</strong> of <strong>{totalCount}</strong> {entityLabel} · Lowest Performer View
            </span>
          ) : (
            <span>
              Showing all <strong>{totalCount}</strong> {entityLabel}
            </span>
          )}
        </div>

        {benchmarkMean != null && (
          <div className="density-benchmark-chip" title="Weighted dataset average across all records">
            <span className="benchmark-label">Network Mean:</span>
            <span className="benchmark-value">{formatVal(benchmarkMean)}</span>
          </div>
        )}
      </div>

      {/* Control Strip: Segmented View Buttons + In-Chart Search */}
      {isHighCount && (
        <div className="density-controls-row">
          <div className="density-mode-switcher" role="group" aria-label="Ranking view mode">
            <button
              type="button"
              className={`density-mode-btn ${viewMode === 'top' && !searchQuery ? 'active' : ''}`}
              onClick={() => {
                onSearchChange('');
                onViewModeChange('top');
              }}
              title="View Top 10 highest ranking entities"
            >
              Top 10
            </button>
            <button
              type="button"
              className={`density-mode-btn ${viewMode === 'bottom' && !searchQuery ? 'active' : ''}`}
              onClick={() => {
                onSearchChange('');
                onViewModeChange('bottom');
              }}
              title="View Bottom 10 lowest ranking entities"
            >
              Bottom 10
            </button>
            <button
              type="button"
              className={`density-mode-btn ${viewMode === 'all' && !searchQuery ? 'active' : ''}`}
              onClick={() => {
                onSearchChange('');
                onViewModeChange('all');
              }}
              title={`View all ${totalCount} entities in a contained scrollable list`}
            >
              All (Scroll)
            </button>
            <button
              type="button"
              className="density-mode-btn btn-table-trigger"
              onClick={onOpenModal}
              title="Open full sortable detail table"
            >
              <Table size={12} />
              <span>Table ({totalCount})</span>
            </button>
          </div>

          <div className="density-search-wrap">
            <Search size={12} className="density-search-icon" />
            <input
              type="text"
              placeholder={`Filter ${entityLabel}...`}
              value={searchQuery}
              onChange={(e) => onSearchChange(e.target.value)}
              className="density-search-input"
            />
            {searchQuery && (
              <button
                type="button"
                className="density-search-clear"
                onClick={() => onSearchChange('')}
                aria-label="Clear filter"
              >
                <X size={11} />
              </button>
            )}
          </div>
        </div>
      )}
    </div>
  );
}
