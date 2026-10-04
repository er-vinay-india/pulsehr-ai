import React, { useState } from 'react';
import SafeReactECharts from '../../charts/SafeReactECharts';
import SafeChart from '../../visualization/components/SafeChart';
import { calculateMargins } from '../../visualization/layout/calculateMargins';
import { calculateChartLayout } from '../../visualization/layout/calculateChartLayout';
import SmartImpactCard from '../../charts/SmartImpactCard';
import { getSlideTheme } from '../../../theme/slideTokens.js';
import { cartesian, numeric } from '../../charts/chartOptions';
import { formatCompactNumber, formatFullNumber, humanizeLabel } from '../../visualization/layout/formatters.js';

export default function SlideChart({ chart, chartData, theme, hideImpactCard = false }) {
  theme = getSlideTheme(theme);
  const isDark = Boolean(theme.is_dark);
  const actualChart = chart || chartData;
  const [headerTooltip, setHeaderTooltip] = useState(null);

  if (!actualChart) {
    return <p style={{ color: theme.muted_text || '#64748b', padding: 12 }}>No chart data available.</p>;
  }

  const chartLabel = humanizeLabel(actualChart.title || actualChart.chart_title || actualChart.series?.[0]?.name || "Data visualization chart");
  const fullChartTitle = humanizeLabel(actualChart.full_title || actualChart.title || actualChart.chart_title || chartLabel);
  const fullChartSubtitle = actualChart.full_subtitle || actualChart.subtitle || actualChart.chart_subtitle ? humanizeLabel(actualChart.full_subtitle || actualChart.subtitle || actualChart.chart_subtitle) : '';
  const type = (actualChart.type || actualChart.chart_type || 'column').toLowerCase();
  const format = value => formatCompactNumber(value, actualChart.unit, 2);
  const formatFull = value => formatFullNumber(value, actualChart.unit);

  const renderHeader = () => (
    <div
      className="slide-chart-header"
      style={{
        position: 'relative',
        textAlign: 'center',
        marginBottom: '6px',
        padding: '0 8px',
        width: '100%',
        minWidth: 0,
        boxSizing: 'border-box'
      }}
    >
      <h4
        title={fullChartTitle}
        onMouseEnter={() => setHeaderTooltip({ text: fullChartTitle, isTitle: true })}
        onMouseLeave={() => setHeaderTooltip(null)}
        style={{
          margin: 0,
          fontSize: '13.5px',
          fontWeight: 700,
          color: isDark ? '#f8fafc' : '#0f172a',
          whiteSpace: 'nowrap',
          overflow: 'hidden',
          textOverflow: 'ellipsis',
          lineHeight: 1.3,
          cursor: 'pointer'
        }}
      >
        {chartLabel}
      </h4>
      {fullChartSubtitle && (
        <p
          title={fullChartSubtitle}
          onMouseEnter={() => setHeaderTooltip({ text: fullChartSubtitle, isTitle: false })}
          onMouseLeave={() => setHeaderTooltip(null)}
          style={{
            margin: '2px 0 0 0',
            fontSize: '11px',
            color: isDark ? '#94a3b8' : '#64748b',
            whiteSpace: 'nowrap',
            overflow: 'hidden',
            textOverflow: 'ellipsis',
            cursor: 'pointer'
          }}
        >
          {fullChartSubtitle}
        </p>
      )}
      {headerTooltip && (
        <div
          role="tooltip"
          aria-hidden="false"
          style={{
            position: 'absolute',
            top: headerTooltip.isTitle ? '22px' : '36px',
            left: '50%',
            transform: 'translateX(-50%)',
            zIndex: 9999,
            backgroundColor: isDark ? 'rgba(15, 23, 42, 0.98)' : 'rgba(255, 255, 255, 0.98)',
            color: isDark ? '#f8fafc' : '#0f172a',
            border: isDark ? '1px solid rgba(255, 255, 255, 0.15)' : '1px solid rgba(0, 0, 0, 0.12)',
            boxShadow: isDark ? '0 8px 24px rgba(0, 0, 0, 0.5)' : '0 6px 20px rgba(0, 0, 0, 0.12)',
            borderRadius: '6px',
            padding: '5px 10px',
            fontSize: '11.5px',
            fontWeight: 600,
            lineHeight: 1.3,
            maxWidth: '340px',
            width: 'max-content',
            wordBreak: 'break-word',
            pointerEvents: 'none',
            backdropFilter: 'blur(8px)',
          }}
        >
          {headerTooltip.text}
        </div>
      )}
    </div>
  );

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
      copy.name = humanizeLabel(copy.name);
      copy.full_name = humanizeLabel(copy.full_name || copy.name);
      if (Array.isArray(copy.children) && copy.children.length > 6) {
        const topChildren = copy.children.slice(0, 5);
        const remaining = copy.children.slice(5);
        const remAvg = remaining.reduce((acc, c) => acc + (Number(c.value) || 0), 0) / remaining.length;
        const remSample = remaining.reduce((acc, c) => acc + (Number(c.sample_size) || 0), 0);
        topChildren.push({
          name: `Other (${remaining.length} cohorts)`,
          full_name: `All Other (${remaining.length}) Cohorts Consolidated`,
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
          const displayName = d.full_name || d.name;
          let text = `<div style="font-weight:700;margin-bottom:2px;max-width:280px;word-break:break-word;">${displayName}</div>`;
          if (d.value != null) text += `<div>Mean Value: <b>${formatFull(d.value)}</b></div>`;
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
          top: '8%',
          left: '18%',
          bottom: '8%',
          right: '28%',
          symbolSize: 12,
          orient: 'LR',
          initialTreeDepth: 3,
          triggerEvent: true,
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
        style={{ width: '100%', minWidth: 0, height: '100%', minHeight: '260px', display: 'flex', flexDirection: 'column' }}
      >
        {!hideImpactCard && actualChart.impact_card && <SmartImpactCard impact={actualChart.impact_card} compact />}
        {renderHeader()}
        <SafeReactECharts presentationTheme={theme} option={treeOption} style={{ height: '240px', width: '100%', flex: '1 1 auto' }} />
        {actualChart.aggregation_disclosure && (
          <p className="chart-aggregation-note" style={{ fontSize: '11px', marginTop: '4px', color: theme.muted_text || '#64748b', textAlign: 'center' }}>
            {actualChart.aggregation_disclosure}
          </p>
        )}
      </div>
    );
  }

  // 3. Variance Waterfall Bridge
  if (type === 'waterfall' || actualChart.waterfall_steps) {
    const steps = (actualChart.waterfall_steps || []).map(s => ({
      ...s,
      label: humanizeLabel(s.label),
      full_label: humanizeLabel(s.full_label || s.label)
    }));
    const cats = steps.length > 0 ? steps.map(s => s.full_label || s.label) : (actualChart.categories || []).map(humanizeLabel);

    const helperBase = actualChart.series?.[0]?.values || [];
    const deltaVals = actualChart.series?.[1]?.values || [];

    const waterfallOption = {
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
          const fullLabel = step?.full_label || step?.label || delta.name;
          const typeLabel = step?.type ? `(${step.type.toUpperCase()})` : '';
          return `<div style="font-weight:700;max-width:280px;word-break:break-word;">${fullLabel} ${typeLabel}</div><div>Value: <b>${formatFull(delta.value)}</b></div>`;
        }
      },
      grid: {
        ...calculateMargins({ categories: cats, isVertical: true, hasLegend: false }),
        top: 24,
        bottom: cats.some(c => String(c).length > 8) ? 45 : 30
      },
      xAxis: {
        type: 'category',
        data: cats,
        triggerEvent: true,
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
              if (step.type === 'decrease' || step.value < 0) return isDark ? '#34d399' : '#059669';
              return isDark ? '#f87171' : '#dc2626';
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
        style={{ width: '100%', minWidth: 0, height: '100%', minHeight: '260px', display: 'flex', flexDirection: 'column' }}
      >
        {!hideImpactCard && actualChart.impact_card && <SmartImpactCard impact={actualChart.impact_card} compact />}
        {renderHeader()}
        <SafeReactECharts presentationTheme={theme} option={waterfallOption} style={{ height: '240px', width: '100%', flex: '1 1 auto' }} />
        {actualChart.aggregation_disclosure && (
          <p className="chart-aggregation-note" style={{ fontSize: '11px', marginTop: '4px', color: theme.muted_text || '#64748b', textAlign: 'center' }}>
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

  const cleanCategories = (actualChart.categories || []).map(c => typeof c === 'string' ? humanizeLabel(c) : c);
  const cleanSeries = (actualChart.series || []).map(s => ({
    ...s,
    name: humanizeLabel(s.name)
  }));

  const refLines = actualChart.reference_lines || actualChart.referenceLines || [];
  const markLineData = refLines.map(rl => ({
    name: rl.label || 'Baseline',
    yAxis: Number(rl.value),
    lineStyle: {
      type: rl.line_style || 'dashed',
      color: isDark ? '#f59e0b' : '#d97706',
      width: 1.5
    },
    label: {
      show: true,
      formatter: `${rl.label || 'Baseline'}: ${format(rl.value)}`,
      fontSize: 10,
      position: 'insideEndTop'
    }
  }));

  const pie = ['pie', 'donut'].includes(type);
  const option = pie ? {
    legend: { show: false },
    tooltip: {
      trigger: 'item',
      confine: true,
      backgroundColor: isDark ? 'rgba(15, 23, 42, 0.95)' : 'rgba(255, 255, 255, 0.98)',
      borderColor: isDark ? '#334155' : '#cbd5e1',
      textStyle: { color: isDark ? '#f1f5f9' : '#1e293b', fontSize: 12 },
      formatter: params => {
        const fullCat = cleanCategories?.[params.dataIndex] || params.name;
        return `<div style="font-weight:700;max-width:280px;word-break:break-word;">${fullCat}</div><div>Value: <b>${formatFull(params.value)} (${params.percent}%)</b></div>`;
      }
    },
    series: [{
      type: 'pie',
      name: cleanSeries[0]?.name || '',
      radius: type === 'donut' ? ['40%', '64%'] : '64%',
      center: ['50%', '50%'],
      avoidLabelOverlap: true,
      label: {
        show: true,
        fontSize: 10,
        color: isDark ? '#e2e8f0' : '#1e293b',
        formatter: p => `${p.name && p.name.length > 14 ? p.name.slice(0, 12) + '…' : p.name}\n${p.percent}%`
      },
      labelLine: { show: true, length: 8, length2: 8 },
      itemStyle: { borderWidth: 2, borderColor: isDark ? '#08111f' : '#ffffff' },
      data: cleanCategories.map((label, i) => ({
        name: String(label),
        value: cleanSeries[0]?.values?.[i] ?? cleanSeries[0]?.data?.[i]
      }))
    }],
  } : cartesian(cleanCategories,
    cleanSeries.map((s, sIdx) => ({
      name: s.name && s.name.length > 20 ? s.name.slice(0, 18) + '…' : s.name,
      type: type === 'line' ? 'line' : 'bar',
      data: cleanCategories.map((_, i) => numeric(s.values?.[i] ?? s.data?.[i])),
      label: {
        show: cleanCategories.length <= 16,
        fontSize: 10,
        position: ['bar', 'horizontal_bar'].includes(type) ? 'right' : 'top',
        formatter: p => format(p.value)
      },
      ...(sIdx === 0 && markLineData.length > 0 ? { markLine: { data: markLineData, symbol: 'none' } } : {})
    })),
    ['bar', 'horizontal_bar'].includes(type), actualChart.unit, isDark);

  if (!pie) {
    const hasLegend = cleanSeries.length > 1;
    option.legend = {
      ...option.legend,
      show: hasLegend,
      type: 'scroll',
      top: 4,
      triggerEvent: true,
      tooltip: { show: true },
      formatter: name => (name && name.length > 18 ? name.slice(0, 16) + '…' : name),
      textStyle: {
        color: isDark ? '#cbd5e1' : '#475569',
        fontSize: 10
      }
    };
    const dynamicMargins = calculateMargins({
      categories: cleanCategories,
      isVertical: !['bar', 'horizontal_bar'].includes(type),
      hasLegend
    });
    const hasDataZoom = cleanCategories.length > 12;
    const rotateLabels = !['bar', 'horizontal_bar'].includes(type) && cleanCategories.length > 5;
    option.grid = {
      ...dynamicMargins,
      top: hasLegend ? 34 : 20,
      bottom: hasDataZoom
        ? Math.max(dynamicMargins.bottom || 0, 56)
        : (rotateLabels ? Math.max(dynamicMargins.bottom || 0, 46) : dynamicMargins.bottom),
      containLabel: true
    };
    option.tooltip = {
      trigger: 'axis',
      axisPointer: { type: type === 'line' ? 'line' : 'shadow' },
      confine: true,
      backgroundColor: isDark ? 'rgba(15, 23, 42, 0.95)' : 'rgba(255, 255, 255, 0.98)',
      borderColor: isDark ? '#334155' : '#cbd5e1',
      textStyle: { color: isDark ? '#f1f5f9' : '#1e293b', fontSize: 12 },
      formatter: params => {
        if (!params || !params.length) return '';
        const catIdx = params[0].dataIndex;
        const fullCat = cleanCategories?.[catIdx] || params[0].name;
        let html = `<div style="font-weight:700;margin-bottom:3px;max-width:280px;word-break:break-word;">${fullCat}</div>`;
        for (const p of params) {
          const sName = cleanSeries?.[p.seriesIndex]?.name || p.seriesName;
          html += `<div style="display:flex;align-items:center;gap:6px;margin-top:2px;">
            <span style="display:inline-block;width:8px;height:8px;border-radius:50%;background-color:${p.color};"></span>
            <span style="font-size:11px;color:${isDark ? '#cbd5e1' : '#475569'};">${sName}:</span>
            <b>${format(p.value)} ${actualChart.unit || ''}</b>
          </div>`;
        }
        return html;
      }
    };
    for (const name of ['xAxis', 'yAxis']) {
      const axis = option[name];
      if (axis && !Array.isArray(axis)) {
        axis.triggerEvent = true;
        if (axis.type === 'value') {
          axis.scale = true;
          axis.axisLabel = {
            ...axis.axisLabel,
            fontSize: 10,
            formatter: format
          };
        } else {
          const rotate = !['bar', 'horizontal_bar'].includes(type) && cleanCategories.length > 5 ? 28 : 0;
          axis.axisLabel = {
            ...axis.axisLabel,
            fontSize: 10,
            rotate,
            hideOverlap: false,
            width: rotate > 0 ? 120 : 85,
            overflow: 'truncate',
            ellipsis: '…'
          };
        }
      }
    }
  }

  return (
    <div
      role="img"
      aria-label={`${chartLabel} (${type} chart)`}
      style={{ width: '100%', minWidth: 0, height: '100%', minHeight: '260px', display: 'flex', flexDirection: 'column' }}
    >
      {!hideImpactCard && actualChart.impact_card && <SmartImpactCard impact={actualChart.impact_card} compact />}
      {renderHeader()}
      <SafeReactECharts presentationTheme={theme} option={option} style={{ height: '240px', width: '100%', flex: '1 1 auto' }} />
      {actualChart.aggregation_disclosure && (
        <p className="chart-aggregation-note" style={{ fontSize: '11px', marginTop: '4px', color: theme.muted_text || '#64748b', textAlign: 'center' }}>
          {actualChart.aggregation_disclosure}
        </p>
      )}
    </div>
  );
}
