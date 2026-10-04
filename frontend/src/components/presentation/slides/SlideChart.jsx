import React from 'react';
import SafeReactECharts from '../../charts/SafeReactECharts';
import SafeChart from '../../visualization/components/SafeChart';
import { calculateMargins } from '../../visualization/layout/calculateMargins';
import { calculateChartLayout } from '../../visualization/layout/calculateChartLayout';
import SmartImpactCard from '../../charts/SmartImpactCard';
import { getSlideTheme } from '../../../theme/slideTokens.js';
import { cartesian, numeric } from '../../charts/chartOptions';

export default function SlideChart({ chart, chartData, theme, hideImpactCard = false }) {
  theme = getSlideTheme(theme);
  const isDark = Boolean(theme.is_dark);
  const actualChart = chart || chartData;

  if (!actualChart) {
    return <p style={{ color: theme.muted_text || '#64748b', padding: 12 }}>No chart data available.</p>;
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
        {!hideImpactCard && actualChart.impact_card && <SmartImpactCard impact={actualChart.impact_card} compact />}
        <SafeChart spec={actualChart} presentationTheme={theme} height={260} />
      </div>
    );
  }

  // 2. Interactive Breakdown Tree Decomposition
  if (type === 'breakdown_tree' || actualChart.tree_data) {
    const rawTreeData = actualChart.tree_data || {
      name: chartLabel,
      value: actualChart.value || 0,
      children: []
    };

    // Protect against overflowing deep/wide tree nodes by consolidating beyond top 6
    const sanitizeTreeNode = (node) => {
      if (!node) return node;
      const copy = { ...node };
      if (Array.isArray(copy.children) && copy.children.length > 6) {
        const topChildren = copy.children.slice(0, 5);
        const remaining = copy.children.slice(5);
        const remAvg = remaining.reduce((acc, c) => acc + (Number(c.value) || 0), 0) / remaining.length;
        const remSample = remaining.reduce((acc, c) => acc + (Number(c.sample_size) || 0), 0);
        topChildren.push({
          name: `Other (${remaining.length} cohorts)`,
          value: Math.round(remAvg * 100) / 100,
          sample_size: remSample,
          severity: 'normal'
        });
        copy.children = topChildren.map(sanitizeTreeNode);
      } else if (Array.isArray(copy.children)) {
        copy.children = copy.children.map(sanitizeTreeNode);
      }
      return copy;
    };
    const treeData = sanitizeTreeNode(rawTreeData);

    const treeOption = {
      title: {
        text: chartLabel,
        left: 'center',
        top: 4,
        textStyle: {
          fontSize: 14,
          fontWeight: 600,
          color: isDark ? '#f8fafc' : '#0f172a'
        }
      },
      tooltip: {
        trigger: 'item',
        triggerOn: 'mousemove',
        confine: true,
        backgroundColor: isDark ? 'rgba(15, 23, 42, 0.95)' : 'rgba(255, 255, 255, 0.98)',
        borderColor: isDark ? '#334155' : '#cbd5e1',
        textStyle: { color: isDark ? '#f1f5f9' : '#1e293b', fontSize: 12 },
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
          top: '16%',
          left: '18%',
          bottom: '12%',
          right: '28%',
          symbolSize: 10,
          orient: 'LR',
          initialTreeDepth: 3,
          label: {
            position: 'left',
            verticalAlign: 'middle',
            align: 'right',
            fontSize: 11,
            color: isDark ? '#cbd5e1' : '#334155',
            formatter: p => (p.name && p.name.length > 18 ? p.name.slice(0, 16) + '…' : p.name)
          },
          leaves: {
            label: {
              position: 'right',
              verticalAlign: 'middle',
              align: 'left',
              fontSize: 11,
              color: isDark ? '#f8fafc' : '#0f172a',
              formatter: p => (p.name && p.name.length > 20 ? p.name.slice(0, 18) + '…' : p.name)
            }
          },
          itemStyle: {
            color: isDark ? '#38bdf8' : '#0284c7',
            borderColor: isDark ? '#0284c7' : '#0369a1'
          },
          lineStyle: {
            color: isDark ? 'rgba(255,255,255,0.2)' : '#cbd5e1',
            curveness: 0.5
          },
          emphasis: {
            focus: 'descendant'
          },
          animationDuration: 400,
          animationDurationUpdate: 500
        }
      ]
    };

    return (
      <div
        role="img"
        aria-label={`${chartLabel} (breakdown tree)`}
        style={{ width: '100%', minWidth: 0, height: '100%', minHeight: '260px' }}
      >
        {!hideImpactCard && actualChart.impact_card && <SmartImpactCard impact={actualChart.impact_card} compact />}
        <SafeReactECharts presentationTheme={theme} option={treeOption} style={{ height: '260px', width: '100%' }} />
        {actualChart.aggregation_disclosure && (
          <p className="chart-aggregation-note" style={{ fontSize: '11px', marginTop: '4px', color: theme.muted_text || '#64748b' }}>
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
      title: {
        text: chartLabel,
        left: 'center',
        top: 4,
        textStyle: {
          fontSize: 14,
          fontWeight: 600,
          color: isDark ? '#f8fafc' : '#0f172a'
        }
      },
      tooltip: {
        trigger: 'axis',
        axisPointer: { type: 'shadow' },
        confine: true,
        backgroundColor: isDark ? 'rgba(15, 23, 42, 0.95)' : 'rgba(255, 255, 255, 0.98)',
        borderColor: isDark ? '#334155' : '#cbd5e1',
        textStyle: { color: isDark ? '#f1f5f9' : '#1e293b', fontSize: 12 },
        formatter: params => {
          const delta = params.find(p => p.seriesName === 'Delta' || p.seriesName === 'Variance');
          if (!delta) return '';
          const step = steps[delta.dataIndex];
          const typeLabel = step?.type ? `(${step.type.toUpperCase()})` : '';
          return `<div style="font-weight:700;">${delta.name} ${typeLabel}</div><div>Value: <b>${format(delta.value)} ${actualChart.unit || ''}</b></div>`;
        }
      },
      grid: {
        ...calculateMargins({ categories: cats, isVertical: true, hasLegend: false }),
        top: 44,
        bottom: cats.some(c => String(c).length > 8) ? 45 : 32
      },
      xAxis: {
        type: 'category',
        data: cats,
        axisLabel: {
          interval: 0,
          rotate: cats.length > 3 ? 18 : 0,
          fontSize: 11,
          formatter: val => (val && String(val).length > 15 ? String(val).slice(0, 13) + '…' : val),
          color: isDark ? '#cbd5e1' : '#475569'
        },
        axisTick: { alignWithLabel: true }
      },
      yAxis: {
        type: 'value',
        axisLabel: {
          formatter: format,
          fontSize: 11,
          color: isDark ? '#94a3b8' : '#64748b'
        },
        splitLine: {
          lineStyle: {
            color: isDark ? 'rgba(255, 255, 255, 0.08)' : 'rgba(0, 0, 0, 0.06)'
          }
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
            fontSize: 10,
            color: isDark ? '#f1f5f9' : '#1e293b'
          },
          itemStyle: {
            color: params => {
              const step = steps[params.dataIndex];
              if (!step) return '#3b82f6';
              if (step.type === 'total') return isDark ? '#818cf8' : '#4f46e5';
              if (step.type === 'decrease' || step.value < 0) return isDark ? '#34d399' : '#059669'; // Savings or favorable
              return isDark ? '#f87171' : '#dc2626'; // Variance / adverse / leakage
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
        {!hideImpactCard && actualChart.impact_card && <SmartImpactCard impact={actualChart.impact_card} compact />}
        <SafeReactECharts presentationTheme={theme} option={waterfallOption} style={{ height: '260px', width: '100%' }} />
        {actualChart.aggregation_disclosure && (
          <p className="chart-aggregation-note" style={{ fontSize: '11px', marginTop: '4px', color: theme.muted_text || '#64748b' }}>
            {actualChart.aggregation_disclosure}
          </p>
        )}
      </div>
    );
  }

  // 4. Standard Categories / Series validation
  if (!actualChart.categories?.length || !actualChart.series?.length) {
    return <p style={{ color: theme.muted_text || '#64748b', padding: 12 }}>No chart data available.</p>;
  }

  const pie = ['pie', 'donut'].includes(type);
  const option = pie ? {
    title: { text: chartLabel, left: 'center', top: 4, textStyle: { fontSize: 15, color: isDark ? '#f8fafc' : '#0f172a' } },
    legend: { show: false },
    tooltip: { trigger: 'item', confine: true, formatter: '{b}: {c} ({d}%)' },
    series: [{
      type: 'pie', name: actualChart.series[0].name || '',
      radius: type === 'donut' ? ['35%', '58%'] : '58%', center: ['50%', '54%'],
      label: { show: true, fontSize: 11, formatter: '{b}\n{c} ({d}%)' },
      labelLine: { show: true }, itemStyle: { borderWidth: 2 },
      data: actualChart.categories.map((label, i) => ({ name: String(label), value: actualChart.series[0].values?.[i] ?? actualChart.series[0].data?.[i] }))
    }],
  } : cartesian(actualChart.categories,
    actualChart.series.map(s => ({
      name: s.name, type: type === 'line' ? 'line' : 'bar',
      data: actualChart.categories.map((_, i) => numeric(s.values?.[i] ?? s.data?.[i])),
      label: { show: true, fontSize: 11, position: ['bar', 'horizontal_bar'].includes(type) ? 'right' : 'top', formatter: p => format(p.value) }
    })),
    ['bar', 'horizontal_bar'].includes(type), actualChart.unit, isDark);

  if (!pie) {
    option.title = { text: chartLabel, left: 'center', top: 4, textStyle: { fontSize: 15, color: isDark ? '#f8fafc' : '#0f172a' } };
    option.legend = { ...option.legend, show: actualChart.series.length > 1, top: 26 };
    const dynamicMargins = calculateMargins({
      categories: actualChart.categories,
      isVertical: !['bar', 'horizontal_bar'].includes(type),
      hasLegend: actualChart.series.length > 1
    });
    option.grid = {
      ...dynamicMargins,
      top: actualChart.series.length > 1 ? 58 : 42
    };
    for (const name of ['xAxis', 'yAxis']) {
      const axis = option[name];
      if (axis && !Array.isArray(axis)) axis.axisLabel = { ...axis.axisLabel, fontSize: 11, ...(axis.type === 'value' ? { formatter: format } : {}) };
    }
  }

  return (
    <div
      role="img"
      aria-label={`${chartLabel} (${type} chart)`}
      style={{ width: '100%', minWidth: 0, height: '100%', minHeight: '230px' }}
    >
      {!hideImpactCard && actualChart.impact_card && <SmartImpactCard impact={actualChart.impact_card} compact />}
      <SafeReactECharts presentationTheme={theme} option={option} style={{ height: '230px', width: '100%' }} />
      {actualChart.aggregation_disclosure && (
        <p className="chart-aggregation-note" style={{ fontSize: '11px', marginTop: '4px', color: theme.muted_text || '#64748b' }}>
          {actualChart.aggregation_disclosure}
        </p>
      )}
    </div>
  );
}
