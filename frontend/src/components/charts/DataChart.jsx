import React, { useRef, useState, useEffect, useMemo } from 'react';
import SafeReactECharts from './SafeReactECharts';
import { cartesian, numeric, formatValue, formatFullValue, metricUnit } from './chartOptions';
import { useChartTheme } from '../../theme/useChartTheme';
import { useVisualQA } from '../visualization/observers/useVisualQA';
import { repairChartLayout } from '../visualization/repair/repairChartLayout';
import { VISUAL_POLICY } from '../visualization/policy/visualPolicy';
import { formatCompactNumber, humanizeLabel } from '../visualization/layout/formatters';
import Button from '../../design-system/components/Button';
import DataTable from '../DataTable';

export default function DataChart({
  items = [],
  type = 'bar',
  metric = 'Value',
  unit = '',
  onSelect,
  baseline,
  height = 300
}) {
  const containerRef = useRef(null);
  const repairCountRef = useRef(0);

  const {
    isDark,
    palette: activePalette,
    labelColor: textColor,
    headingColor,
    tooltipBg,
    tooltipBorder,
    colors,
  } = useChartTheme();

  const borderColor = colors.surface;
  unit = metricUnit(metric, unit);

  if (!items.length) {
    return <p className="executive-chart-empty">No chart data available.</p>;
  }

  const isPie = type === 'donut' || type === 'pie';
  const maxLabelLen = useMemo(() => {
    return items.reduce((max, i) => Math.max(max, String(i?.label || '').length), 0);
  }, [items]);

  // 1. High-cardinality Top-N consolidation for Cartesian charts (>25 items)
  const { displayItems, isConsolidated, tailCount } = useMemo(() => {
    if (isPie || items.length <= VISUAL_POLICY.TOP_N_CONSOLIDATION_THRESHOLD) {
      return { displayItems: items, isConsolidated: false, tailCount: 0 };
    }

    const topN = VISUAL_POLICY.DEFAULT_TOP_N;
    const sorted = [...items].sort((a, b) => Math.abs(Number(b.value) || 0) - Math.abs(Number(a.value) || 0));
    const topItems = sorted.slice(0, topN);
    const tailItems = sorted.slice(topN);
    const tailSum = tailItems.reduce((acc, i) => acc + (Number(i.value) || 0), 0);

    return {
      displayItems: [
        ...topItems,
        { label: `Other (${tailItems.length} items)`, value: tailSum, isTail: true }
      ],
      isConsolidated: true,
      tailCount: tailItems.length
    };
  }, [items, isPie]);

  // 2. Adaptive orientation: Auto-flip to horizontal bar if > 10 items or label > 16 chars
  const shouldFlipToHorizontal = useMemo(() => {
    if (type !== 'bar') return false;
    return displayItems.length > VISUAL_POLICY.MAX_CATEGORIES_VERTICAL || maxLabelLen > VISUAL_POLICY.MAX_LABEL_CHARS_VERTICAL;
  }, [type, displayItems.length, maxLabelLen]);

  // 3. Construct base chart options
  const baseOption = useMemo(() => {
    const cleanMetric = humanizeLabel(metric);

    if (isPie) {
      return {
        color: activePalette,
        tooltip: {
          trigger: 'item',
          valueFormatter: v => formatFullValue(v, unit),
          backgroundColor: tooltipBg,
          borderColor: tooltipBorder,
          textStyle: { color: headingColor, fontSize: 12 }
        },
        legend: {
          type: 'scroll',
          bottom: 0,
          formatter: name => (typeof name === 'string' ? humanizeLabel(name) : name),
          textStyle: { color: textColor, fontSize: 11 }
        },
        series: [{
          type: 'pie',
          name: cleanMetric,
          radius: type === 'donut' ? ['45%', '68%'] : '68%',
          center: ['50%', '44%'],
          label: { show: false },
          itemStyle: { borderColor, borderWidth: 2 },
          data: displayItems
            .filter(p => numeric(p.value) != null && Number(p.value) >= 0)
            .map(p => ({ name: humanizeLabel(String(p.label)), value: Number(p.value) }))
        }]
      };
    }

    // Cartesian Chart (Column, Bar, Line, Scatter)
    const isHorizontal = shouldFlipToHorizontal;
    return cartesian(
      displayItems.map(p => humanizeLabel(String(p.label))),
      [{
        name: cleanMetric,
        type: type === 'line' ? 'line' : type === 'dot' ? 'scatter' : 'bar',
        data: displayItems.map(p => numeric(p.value)),
        ...(numeric(baseline) != null ? {
          markLine: {
            symbol: 'none',
            label: { show: false },
            data: [{ [type === 'line' ? 'yAxis' : (isHorizontal ? 'xAxis' : 'yAxis')]: Number(baseline) }]
          }
        } : {})
      }],
      isHorizontal,
      unit,
      isDark
    );
  }, [isPie, displayItems, shouldFlipToHorizontal, type, metric, unit, activePalette, tooltipBg, tooltipBorder, headingColor, textColor, borderColor, baseline, isDark]);

  // 4. Active option with self-healing DOM inspection state
  const [activeOption, setActiveOption] = useState(baseOption);

  useEffect(() => {
    repairCountRef.current = 0;
    setActiveOption(baseOption);
  }, [baseOption]);

  // 5. Post-render DOM Visual QA Observer
  const { qaIssues } = useVisualQA(containerRef, {
    enabled: Boolean(activeOption && repairCountRef.current < 2),
    chartOption: activeOption
  });

  // 6. Deterministic Auto-Repair Cascade
  useEffect(() => {
    if (qaIssues && activeOption && repairCountRef.current < 2) {
      repairCountRef.current += 1;
      const { repairedOption, repairsApplied } = repairChartLayout(activeOption, qaIssues);
      if (repairsApplied.length > 0) {
        setActiveOption(repairedOption);
      }
    }
  }, [qaIssues, activeOption]);

  const chartCalculatedHeight = type === 'dot'
    ? Math.max(height, Math.min(displayItems.length, 12) * 48 + 60)
    : height;

  const chartTableCols = useMemo(() => [
    {
      key: 'label',
      label: 'Category',
      sortable: true,
      render: (val, p) => (
        onSelect ? (
          <Button
            variant="GHOST"
            size="sm"
            onClick={() => onSelect(p)}
            style={{ padding: "2px 6px", fontSize: "0.80rem" }}
          >
            {val}
          </Button>
        ) : (
          val
        )
      )
    },
    {
      key: 'value',
      label: metric,
      sortable: true,
      sortType: 'numeric',
      align: 'right',
      render: (val) => (
        <span title={formatFullValue(val, unit)} tabIndex={0} aria-label={formatFullValue(val, unit)}>
          {formatCompactNumber(val, unit)}
        </span>
      )
    }
  ], [metric, unit, onSelect]);

  return (
    <div ref={containerRef} className="data-chart-wrapper" style={{ minWidth: 0, width: '100%' }}>
      {isConsolidated && (
        <div style={{ display: 'flex', justifyContent: 'flex-end', marginBottom: 4 }}>
          <span style={{
            fontSize: '0.72rem',
            fontWeight: 500,
            padding: '2px 8px',
            borderRadius: 999,
            backgroundColor: 'var(--color-bg-subtle, rgba(0,0,0,0.05))',
            color: 'var(--color-text-secondary, #64748b)'
          }}>
            Showing Top 10 of {items.length} segments
          </span>
        </div>
      )}

      <SafeReactECharts
        option={activeOption}
        style={{ height: chartCalculatedHeight, width: '100%' }}
        onEvents={{
          click: p => {
            const matched = items.find(i => String(i.label) === p.name);
            if (matched) onSelect?.(matched);
          }
        }}
      />

      {numeric(baseline) != null && (
        <p style={{ fontSize: '0.8rem', color: textColor, margin: '4px 0' }}>
          Dashed line: average{' '}
          <span tabIndex={0} title={formatFullValue(baseline, unit)} aria-label={formatFullValue(baseline, unit)}>
            {formatCompactNumber(baseline, unit)}
          </span>
        </p>
      )}

      <details className="chart-data-table" style={{ marginTop: 6 }}>
        <summary style={{ cursor: 'pointer', fontSize: '0.82rem', color: 'var(--color-brand-primary, #0284c7)' }}>
          View full dataset ({items.length} rows){onSelect ? ' and investigate' : ''}
        </summary>
        <div style={{ marginTop: 8 }}>
          <DataTable
            columns={chartTableCols}
            rows={items}
            rowKeyProp="label"
            pageSize={10}
            pageSizeOptions={[10, 25, 50]}
            searchPlaceholder={`Search ${metric}...`}
            tableAriaLabel={`${metric} data table`}
          />
        </div>
      </details>
    </div>
  );
}
