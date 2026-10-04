import React from 'react';
import SafeReactECharts from '../../charts/SafeReactECharts';
import SafeChart from '../../visualization/components/SafeChart';
import { calculateMargins } from '../../visualization/layout/calculateMargins';
import { calculateChartLayout } from '../../visualization/layout/calculateChartLayout';
import SmartImpactCard from '../../charts/SmartImpactCard';
import { getSlideTheme } from '../../../theme/slideTokens.js';
import { cartesian, numeric } from '../../charts/chartOptions';

export default function SlideChart({ chart, chartData, theme }) {
  theme = getSlideTheme(theme);
  const isDark = theme.is_dark;
  const actualChart = chart || chartData;

  if (!actualChart) {
    return <p style={{ color: theme.muted_text, padding: 12 }}>No chart data available.</p>;
  }

  const chartLabel = actualChart.title || actualChart.chart_title || actualChart.series?.[0]?.name || "Data visualization chart";
  const type = (actualChart.type || actualChart.chart_type || 'column').toLowerCase();
  const format = value => Math.abs(Number(value)) >= 1e6 ? `${(Number(value)/1e6).toFixed(1)}M` : Number(value).toLocaleString(undefined, { maximumFractionDigits: 2 });

  // 1. Direct ECharts Option object passed
  if (actualChart.xAxis || (actualChart.series && actualChart.series[0]?.type && actualChart.series[0]?.data)) {
    return (
      <div
        role="img"
        aria-label={chartLabel}
        style={{ width: '100%', minWidth: 0, height: '100%', minHeight: '260px' }}
      >
        {actualChart.impact_card && <SmartImpactCard impact={actualChart.impact_card} compact />}
        <SafeChart spec={actualChart} presentationTheme={theme} height={260} />
      </div>
    );
  }

  // 2. Interactive Breakdown Tree Decomposition
  if (type === 'breakdown_tree' || actualChart.tree_data) {
    const treeData = actualChart.tree_data || {
      name: chartLabel,
      value: actualChart.value || 0,
      children: []
    };

    const treeOption = {
      title: { text: chartLabel, left: 'center', textStyle: { fontSize: 16, color: isDark ? '#f8fafc' : '#0f172a' } },
      tooltip: {
        trigger: 'item',
        triggerOn: 'mousemove',
        formatter: params => {
          const d = params.data;
          if (!d) return '';
          let text = `<div style="font-weight:700;margin-bottom:2px;">${d.name}</div>`;
          if (d.value != null) text += `<div>Mean Value: <b>${format(d.value)} ${d.unit || actualChart.unit || ''}</b></div>`;
          if (d.sample_size) text += `<div>Cohort Size: <b>n = ${d.sample_size}</b></div>`;
          if (d.severity) {
            const isCrit = String(d.severity).toLowerCase().includes('crit');
            text += `<div style="margin-top:3px;font-weight:700;color:${isCrit ? '#ef4444' : '#f59e0b'};">${String(d.severity).toUpperCase()} DISPARITY</div>`;
          }
          return text;
        }
      },
      series: [
        {
          type: 'tree',
          data: [treeData],
          top: '14%',
          left: '18%',
          bottom: '14%',
          right: '25%',
          symbolSize: 12,
          orient: 'LR',
          initialTreeDepth: 3,
          label: {
            position: 'left',
            verticalAlign: 'middle',
            align: 'right',
            fontSize: 12,
            color: isDark ? '#e2e8f0' : '#1e293b',
            formatter: '{b}'
          },
          leaves: {
            label: {
              position: 'right',
              verticalAlign: 'middle',
              align: 'left',
              fontSize: 12,
              color: isDark ? '#f8fafc' : '#0f172a'
            }
          },
          itemStyle: {
            color: isDark ? '#38bdf8' : '#0284c7',
            borderColor: isDark ? '#0284c7' : '#0369a1'
          },
          lineStyle: {
            color: isDark ? 'rgba(255,255,255,0.25)' : '#cbd5e1',
            curveness: 0.5
          },
          emphasis: {
            focus: 'descendant'
          },
          animationDuration: 550,
          animationDurationUpdate: 750
        }
      ]
    };

    return (
      <div
        role="img"
        aria-label={`${chartLabel} (breakdown tree)`}
        style={{ width: '100%', minWidth: 0, height: '100%', minHeight: '260px' }}
      >
        {actualChart.impact_card && <SmartImpactCard impact={actualChart.impact_card} compact />}
        <SafeReactECharts presentationTheme={theme} option={treeOption} style={{ height: '100%', minHeight: '260px', width: '100%' }} />
        {actualChart.aggregation_disclosure && (
          <p className="chart-aggregation-note" style={{ fontSize: '11px', marginTop: '4px', color: theme.muted_text }}>
            {actualChart.aggregation_disclosure}
          </p>
        )}
      </div>
    );
  }

  // 3. Variance Waterfall Bridge
  if (type === 'waterfall' || actualChart.waterfall_steps) {
    const cats = actualChart.categories || (actualChart.waterfall_steps || []).map(s => s.label);
    const steps = actualChart.waterfall_steps || [];

    const helperBase = actualChart.series?.[0]?.values || [];
    const deltaVals = actualChart.series?.[1]?.values || [];

    const waterfallOption = {
      title: { text: chartLabel, left: 'center', textStyle: { fontSize: 16, color: isDark ? '#f8fafc' : '#0f172a' } },
      tooltip: {
        trigger: 'axis',
        axisPointer: { type: 'shadow' },
        formatter: params => {
          const delta = params.find(p => p.seriesName === 'Delta' || p.seriesName === 'Variance');
          if (!delta) return '';
          const step = steps[delta.dataIndex];
          const typeLabel = step?.type ? `(${step.type.toUpperCase()})` : '';
          return `<div style="font-weight:700;">${delta.name} ${typeLabel}</div><div>Value: <b>${format(delta.value)} ${actualChart.unit || ''}</b></div>`;
        }
      },
      grid: calculateMargins({ categories: cats, isVertical: true, hasLegend: false }),
      xAxis: {
        type: 'category',
        data: cats,
        axisLabel: {
          interval: 0,
          rotate: cats.length > 3 ? 15 : 0,
          fontSize: 12,
          color: isDark ? '#cbd5e1' : '#475569'
        }
      },
      yAxis: {
        type: 'value',
        axisLabel: {
          formatter: format,
          color: isDark ? '#94a3b8' : '#64748b'
        }
      },
      series: [
        {
          name: 'Helper Base',
          type: 'bar',
          stack: 'Waterfall',
          itemStyle: { borderColor: 'transparent', color: 'transparent' },
          emphasis: { itemStyle: { borderColor: 'transparent', color: 'transparent' } },
          data: helperBase
        },
        {
          name: 'Variance',
          type: 'bar',
          stack: 'Waterfall',
          label: {
            show: true,
            position: 'top',
            formatter: p => format(p.value),
            fontSize: 11,
            color: isDark ? '#f1f5f9' : '#1e293b'
          },
          itemStyle: {
            color: params => {
              const step = steps[params.dataIndex];
              if (!step) return '#3b82f6';
              if (step.type === 'total') return isDark ? '#818cf8' : '#6366f1';
              if (step.type === 'decrease' || step.value < 0) return '#10b981'; // Savings or favorable
              return '#ef4444'; // Variance / adverse / leakage
            },
            borderRadius: [4, 4, 0, 0]
          },
          data: deltaVals
        }
      ]
    };

    return (
      <div
        role="img"
        aria-label={`${chartLabel} (variance waterfall)`}
        style={{ width: '100%', minWidth: 0, height: '100%', minHeight: '260px' }}
      >
        {actualChart.impact_card && <SmartImpactCard impact={actualChart.impact_card} compact />}
        <SafeReactECharts presentationTheme={theme} option={waterfallOption} style={{ height: '100%', minHeight: '260px', width: '100%' }} />
        {actualChart.aggregation_disclosure && (
          <p className="chart-aggregation-note" style={{ fontSize: '11px', marginTop: '4px', color: theme.muted_text }}>
            {actualChart.aggregation_disclosure}
          </p>
        )}
      </div>
    );
  }

  // 4. Standard Categories / Series validation
  if (!actualChart.categories?.length || !actualChart.series?.length) {
    return <p style={{ color: theme.muted_text, padding: 12 }}>No chart data available.</p>;
  }

  const pie = ['pie', 'donut'].includes(type);
  const option = pie ? {
    title: { text: chartLabel, left: 'center', textStyle: { fontSize: 18 } },
    legend: { show: false }, tooltip: { trigger: 'item', formatter: '{b}: {c} ({d}%)' },
    series: [{
      type: 'pie', name: actualChart.series[0].name || '',
      radius: type === 'donut' ? ['35%', '58%'] : '58%', center: ['50%', '54%'],
      label: { show: true, fontSize: 14, formatter: '{b}\n{c} ({d}%)' },
      labelLine: { show: true }, itemStyle: { borderWidth: 2 },
      data: actualChart.categories.map((label, i) => ({ name: String(label), value: actualChart.series[0].values?.[i] ?? actualChart.series[0].data?.[i] }))
    }],
  } : cartesian(actualChart.categories,
    actualChart.series.map(s => ({
      name: s.name, type: type === 'line' ? 'line' : 'bar',
      data: actualChart.categories.map((_, i) => numeric(s.values?.[i] ?? s.data?.[i])),
      label: { show: true, fontSize: 14, position: ['bar', 'horizontal_bar'].includes(type) ? 'right' : 'top', formatter: p => format(p.value) }
    })),
    ['bar', 'horizontal_bar'].includes(type), actualChart.unit, isDark);

  if (!pie) {
    option.title = { text: chartLabel, left: 'center', textStyle: { fontSize: 18 } };
    option.legend = { ...option.legend, show: actualChart.series.length > 1, top: 26 };
    const dynamicMargins = calculateMargins({
      categories: actualChart.categories,
      isVertical: !['bar', 'horizontal_bar'].includes(type),
      hasLegend: actualChart.series.length > 1
    });
    option.grid = {
      ...dynamicMargins,
      top: actualChart.series.length > 1 ? 65 : 48
    };
    for (const name of ['xAxis', 'yAxis']) {
      const axis = option[name];
      if (axis && !Array.isArray(axis)) axis.axisLabel = { ...axis.axisLabel, fontSize: 14, ...(axis.type === 'value' ? { formatter: format } : {}) };
    }
  }

  return (
    <div
      role="img"
      aria-label={`${chartLabel} (${type} chart)`}
      style={{ width: '100%', minWidth: 0, height: '100%', minHeight: '230px' }}
    >
      {actualChart.impact_card && <SmartImpactCard impact={actualChart.impact_card} compact />}
      <SafeReactECharts presentationTheme={theme} option={option} style={{ height: '100%', minHeight: '230px', width: '100%' }} />
      {actualChart.aggregation_disclosure && (
        <p className="chart-aggregation-note" style={{ fontSize: '11px', marginTop: '4px', color: theme.muted_text }}>
          {actualChart.aggregation_disclosure}
        </p>
      )}
    </div>
  );
}
