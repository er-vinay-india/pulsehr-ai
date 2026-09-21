import React, { useState, useMemo } from 'react';
import { formatDisplayLabel } from '../../utils/displayFormatters';
import DataDensityToolbar from './DataDensityToolbar';
import ChartDetailModal from './ChartDetailModal';

export default function DynamicBarChart({ visualization, onInvestigate }) {
  const bars = visualization.bars || [];
  const unit = visualization.unit || '';
  const isCurrency = unit === '$';
  const categoryCol = visualization.category_col || 'Entity';
  const isHighCount = bars.length > 10;

  const [viewMode, setViewMode] = useState(isHighCount ? 'top' : 'all');
  const [searchQuery, setSearchQuery] = useState('');
  const [showDetailModal, setShowDetailModal] = useState(false);

  const isStore =
    categoryCol.toLowerCase().includes('store') ||
    bars.some((b) => String(b.label).toLowerCase().startsWith('store'));

  const entityType = isStore
    ? 'store'
    : categoryCol.toLowerCase().includes('dept')
    ? 'department'
    : 'category';

  const overallMean =
    visualization.overall_mean != null
      ? visualization.overall_mean
      : bars.length > 0
      ? bars.reduce((acc, b) => acc + b.value, 0) / bars.length
      : 0;

  const overallTotal =
    visualization.overall_total != null
      ? visualization.overall_total
      : bars.reduce((acc, b) => acc + b.value, 0);

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

  // Map each bar with absolute rank
  const allBarsWithRanks = useMemo(() => {
    return bars.map((b, idx) => ({
      ...b,
      rank: idx + 1
    }));
  }, [bars]);

  // Filter based on search query
  const filteredBars = useMemo(() => {
    if (!searchQuery.trim()) return allBarsWithRanks;
    return allBarsWithRanks.filter((b) =>
      String(b.label).toLowerCase().includes(searchQuery.toLowerCase().trim())
    );
  }, [allBarsWithRanks, searchQuery]);

  // Slice displayed bars based on viewMode
  const displayedBars = useMemo(() => {
    if (searchQuery.trim()) return filteredBars;
    if (!isHighCount) return filteredBars;
    if (viewMode === 'top') return filteredBars.slice(0, 10);
    if (viewMode === 'bottom') return filteredBars.slice(-10);
    return filteredBars; // 'all' mode
  }, [filteredBars, searchQuery, isHighCount, viewMode]);

  const maxVal = Math.max(...bars.map((b) => b.value), 1);
  const benchmarkPct = maxVal > 0 ? Math.min(100, Math.max(0, (overallMean / maxVal) * 100)) : 0;

  const entityLabelClean = visualization.category_label || formatDisplayLabel(categoryCol);
  const metricLabelClean = visualization.metric_label || formatDisplayLabel(visualization.metric_col || 'Measure');
  const rankingBasisClean = visualization.ranking_basis || `Ranked by ${metricLabelClean.toLowerCase()}`;

  return (
    <div className="dynamic-bar-chart-wrap bounded-chart-container">
      {/* Density Adaptive Toolbar */}
      <DataDensityToolbar
        totalCount={bars.length}
        visibleCount={displayedBars.length}
        viewMode={viewMode}
        onViewModeChange={setViewMode}
        searchQuery={searchQuery}
        onSearchChange={setSearchQuery}
        entityLabel={entityLabelClean.toLowerCase().endsWith('s') ? entityLabelClean.toLowerCase() : `${entityLabelClean.toLowerCase()}s`}
        rankingBasis={rankingBasisClean}
        benchmarkMean={overallMean}
        isCurrency={isCurrency}
        unit={unit}
        onOpenModal={() => setShowDetailModal(true)}
      />

      {/* Horizontal Bar Visual List (Bounded Height Container) */}
      <div className={`dynamic-bars-list ${viewMode === 'all' || searchQuery ? 'density-bars-scroll-list' : 'density-bars-fixed-list'}`}>
        {displayedBars.map((bar) => {
          const pct = Math.min(100, Math.max(6, (bar.value / maxVal) * 100));
          const diffPct = overallMean ? ((bar.value - overallMean) / overallMean) * 100 : null;
          const isAboveBenchmark = diffPct != null && diffPct >= 0;

          return (
            <div
              key={bar.rank}
              className="dynamic-bar-row interactive-row"
              onClick={() =>
                onInvestigate &&
                onInvestigate({
                  entityType: entityType,
                  targetId: bar.label,
                  metric: visualization.metric_col || visualization.measured_metric,
                  sheetId: visualization.sheet_ids?.[0]
                })
              }
              title={`#${bar.rank} ${bar.label}: ${formatVal(bar.value)} (${isAboveBenchmark ? '+' : ''}${diffPct?.toFixed(1)}% vs network average) · Click to investigate`}
            >
              {/* Rank Chip */}
              <span className={`bar-rank-badge ${bar.rank <= 3 ? 'rank-podium' : ''}`}>
                #{bar.rank}
              </span>

              {/* Entity Label */}
              <span className="dynamic-bar-label" title={bar.label}>
                {bar.label}
              </span>

              {/* Progress Track with Benchmark Reference Marker */}
              <div className="dynamic-track">
                {benchmarkPct > 0 && (
                  <div
                    className="benchmark-marker-line"
                    style={{ left: `${benchmarkPct}%` }}
                    title={`Network Mean: ${formatVal(overallMean)}`}
                  />
                )}
                <div
                  className={`dynamic-fill ${bar.rank <= 3 ? 'fill-top-ranked' : ''}`}
                  style={{ width: `${pct}%` }}
                >
                  <span className="dynamic-val">{formatVal(bar.value)}</span>
                </div>
              </div>

              {/* vs Benchmark Comparison Pill */}
              {diffPct != null && (
                <span className={`bar-diff-pill ${isAboveBenchmark ? 'diff-up' : 'diff-down'}`}>
                  {isAboveBenchmark ? `+${diffPct.toFixed(1)}%` : `${diffPct.toFixed(1)}%`}
                </span>
              )}
            </div>
          );
        })}

        {displayedBars.length === 0 && (
          <div className="density-empty-state">
            <p>No {entityLabelClean.toLowerCase()}s matching "{searchQuery}".</p>
            <button type="button" className="btn-inline-reset" onClick={() => setSearchQuery('')}>
              Clear Search
            </button>
          </div>
        )}
      </div>

      {/* Complete Dataset Detail Modal */}
      <ChartDetailModal
        isOpen={showDetailModal}
        onClose={() => setShowDetailModal(false)}
        title={visualization.title}
        subtitle={visualization.subtitle}
        items={allBarsWithRanks}
        benchmarkMean={overallMean}
        benchmarkTotal={overallTotal}
        unit={unit}
        isCurrency={isCurrency}
        entityLabel={entityLabelClean}
        metricName={metricLabelClean}
        population={visualization.population}
        entityType={entityType}
        sheetId={visualization.sheet_ids?.[0]}
        onInvestigate={onInvestigate}
      />
    </div>
  );
}
