import React, { useMemo } from 'react';
import ReactECharts from './SafeReactECharts';

export default function ExecutiveBarComparisonChart({
  groups = [],
  metricName = 'Comparison',
  baseline = null,
  focusGroup = null,
  unit = '',
  height = 260,
  maxItems = 8
}) {
  const option = useMemo(() => {
    if (!groups || groups.length === 0) return {};

    // Take top items if there are too many, plus the focus group if not included
    let displayGroups = [...groups];
    if (displayGroups.length > maxItems) {
      const topItems = displayGroups.slice(0, maxItems);
      if (focusGroup && !topItems.some((g) => g.group === focusGroup)) {
        const found = displayGroups.find((g) => g.group === focusGroup);
        if (found) topItems[topItems.length - 1] = found;
      }
      displayGroups = topItems;
    }

    // Sort descending for horizontal bar
    displayGroups.sort((a, b) => (a.value || 0) - (b.value || 0));

    const categories = displayGroups.map((g) => g.group || g.label || '');
    const values = displayGroups.map((g) => (g.value != null ? Number(g.value) : 0));
    const isCurrency = unit === '$';

    const fmtVal = (val) => {
      if (val == null || isNaN(val)) return '—';
      if (isCurrency) {
        if (Math.abs(val) >= 1_000_000) return `$${(val / 1_000_000).toFixed(2)}M`;
        if (Math.abs(val) >= 1_000) return `$${(val / 1_000).toFixed(1)}k`;
        return `$${Number(val).toFixed(2)}`;
      }
      return `${Number(val).toLocaleString(undefined, { maximumFractionDigits: 1 })} ${unit}`;
    };

    return {
      backgroundColor: 'transparent',
      tooltip: {
        trigger: 'axis',
        axisPointer: { type: 'shadow' },
        backgroundColor: 'rgba(15, 23, 42, 0.95)',
        borderColor: 'rgba(255, 255, 255, 0.1)',
        textStyle: { color: '#f8fafc', fontSize: 12 },
        formatter: (params) => {
          const item = params[0];
          if (!item) return '';
          const diff = baseline != null ? item.value - baseline : null;
          const diffPct = baseline ? ((diff / Math.abs(baseline)) * 100).toFixed(1) : null;
          return `
            <div style="font-weight:600;color:#94a3b8;margin-bottom:4px;">${item.name}</div>
            <div style="font-size:14px;font-weight:700;color:#38bdf8;">
              ${metricName}: ${fmtVal(item.value)}
            </div>
            ${
              diffPct != null
                ? `<div style="font-size:11px;color:${diff >= 0 ? '#10b981' : '#f43f5e'};margin-top:2px;">
                    ${diff >= 0 ? '+' : ''}${diffPct}% vs avg (${fmtVal(baseline)})
                   </div>`
                : ''
            }
          `;
        }
      },
      grid: {
        left: '3%',
        right: '6%',
        top: '6%',
        bottom: '4%',
        containLabel: true
      },
      xAxis: {
        type: 'value',
        axisLine: { show: false },
        axisLabel: {
          color: '#94a3b8',
          fontSize: 10,
          formatter: (v) => fmtVal(v)
        },
        splitLine: {
          lineStyle: { color: 'rgba(255, 255, 255, 0.06)', type: 'dashed' }
        }
      },
      yAxis: {
        type: 'category',
        data: categories,
        axisLine: { lineStyle: { color: '#334155' } },
        axisTick: { show: false },
        axisLabel: {
          color: '#cbd5e1',
          fontSize: 11,
          formatter: (name) => (name.length > 18 ? `${name.slice(0, 16)}…` : name)
        }
      },
      series: [
        {
          name: metricName,
          type: 'bar',
          barMaxWidth: 20,
          itemStyle: {
            borderRadius: [0, 4, 4, 0],
            color: (params) => {
              const name = categories[params.dataIndex];
              const isFocus = focusGroup && name === focusGroup;
              if (isFocus) {
                return {
                  type: 'linear',
                  x: 0,
                  y: 0,
                  x2: 1,
                  y2: 0,
                  colorStops: [
                    { offset: 0, color: '#f59e0b' },
                    { offset: 1, color: '#fbbf24' }
                  ]
                };
              }
              return {
                type: 'linear',
                x: 0,
                y: 0,
                x2: 1,
                y2: 0,
                colorStops: [
                  { offset: 0, color: '#38bdf8' },
                  { offset: 1, color: '#818cf8' }
                ]
              };
            }
          },
          markLine: baseline != null ? {
            symbol: ['none', 'none'],
            data: [
              {
                xAxis: baseline,
                lineStyle: { color: '#f43f5e', type: 'dashed', width: 1.5 },
                label: {
                  show: true,
                  position: 'end',
                  formatter: 'Avg',
                  fontSize: 10,
                  color: '#f43f5e'
                }
              }
            ]
          } : undefined,
          data: values
        }
      ]
    };
  }, [groups, metricName, baseline, focusGroup, unit, maxItems]);

  if (!groups || groups.length === 0) {
    return (
      <div className="executive-chart-empty">
        <p>No comparative segments available.</p>
      </div>
    );
  }

  return (
    <div className="executive-bar-container">
      <ReactECharts
        option={option}
        style={{ height: `${Math.max(height, groups.length * 36)}px`, width: '100%' }}
        opts={{ renderer: 'canvas' }}
      />
    </div>
  );
}
