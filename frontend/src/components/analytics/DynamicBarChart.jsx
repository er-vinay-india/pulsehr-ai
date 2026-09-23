import DataChart from '../charts/DataChart';
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

      <DataChart items={displayedBars} metric={metricLabelClean} unit={unit} baseline={visualization.overall_mean}
        onSelect={bar => bar && onInvestigate?.({ entityType, targetId: bar.label, metric: visualization.metric_col || visualization.measured_metric, sheetId: visualization.sheet_ids?.[0] })} />
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
