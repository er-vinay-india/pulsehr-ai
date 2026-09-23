import React, { useMemo } from 'react';
import ReactECharts from './SafeReactECharts';

export default function ExecutiveTrendChart({
  points = [],
  metricName = 'Trend',
  unit = '',
  baseline = null,
  height = 240,
  accentColor = '#63cfb3'
}) {
  const option = useMemo(() => {
    if (!points || points.length === 0) return {};

    const periods = points.map((p) => p.period || p.label || '');
    const values = points.map((p) => (p.value != null ? Number(p.value) : null));
    const isCurrency = unit === '$';

    const fmtVal = (val) => {
      if (val == null || isNaN(val)) return '—';
      if (isCurrency) {
        if (Math.abs(val) >= 1_000_000) return `$${(val / 1_000_000).toFixed(2)}M`;
        if (Math.abs(val) >= 1_000) return `$${(val / 1_000).toFixed(1)}k`;
        return `$${Number(val).toFixed(2)}`;
      }
      return `${Number(val).toLocaleString(undefined, { maximumFractionDigits: 2 })} ${unit}`;
    };

    return {
      backgroundColor: 'transparent',
      tooltip: {
        trigger: 'axis',
        backgroundColor: 'rgba(15, 23, 42, 0.92)',
        borderColor: 'rgba(255, 255, 255, 0.1)',
        textStyle: { color: '#f8fafc', fontSize: 12 },
        formatter: (params) => {
          const item = params[0];
          if (!item) return '';
          return `
            <div style="font-weight:600;margin-bottom:4px;color:#94a3b8;">${item.name}</div>
            <div style="font-size:14px;font-weight:700;color:${accentColor};">
              ${metricName}: ${fmtVal(item.value)}
            </div>
          `;
        }
      },
      grid: {
        left: '4%',
        right: '4%',
        top: '12%',
        bottom: '8%',
        containLabel: true
      },
      xAxis: {
        type: 'category',
        data: periods,
        boundaryGap: false,
        axisLine: { lineStyle: { color: '#334155' } },
        axisLabel: { color: '#94a3b8', fontSize: 10, margin: 10 },
        splitLine: { show: false }
      },
      yAxis: {
        type: 'value',
        axisLine: { show: false },
        axisLabel: {
          color: '#94a3b8',
          fontSize: 10,
          formatter: (v) => fmtVal(v)
        },
        splitLine: {
          lineStyle: { color: 'rgba(255, 255, 255, 0.05)', type: 'dashed' }
        }
      },
      series: [
        {
          name: metricName,
          type: 'line',
          smooth: true,
          showSymbol: points.length < 30,
          symbolSize: 6,
          itemStyle: {
            color: accentColor,
            borderColor: '#0f172a',
            borderWidth: 2
          },
          lineStyle: {
            width: 3,
            color: accentColor,
            shadowColor: `${accentColor}40`,
            shadowBlur: 8
          },
          areaStyle: {
            color: {
              type: 'linear',
              x: 0,
              y: 0,
              x2: 0,
              y2: 1,
              colorStops: [
                { offset: 0, color: `${accentColor}45` },
                { offset: 1, color: `${accentColor}00` }
              ]
            }
          },
          markLine: baseline != null ? {
            symbol: ['none', 'none'],
            data: [
              {
                yAxis: baseline,
                lineStyle: { color: '#f59e0b', type: 'dashed', width: 1.5 },
                label: {
                  show: true,
                  position: 'insideEndTop',
                  formatter: `Avg: ${fmtVal(baseline)}`,
                  fontSize: 10,
                  color: '#f59e0b'
                }
              }
            ]
          } : undefined,
          data: values
        }
      ]
    };
  }, [points, metricName, unit, baseline, accentColor]);

  if (!points || points.length === 0) {
    return (
      <div className="executive-chart-empty">
        <p>No historical timeline data available for this metric.</p>
      </div>
    );
  }

  return (
    <div className="executive-trend-container">
      <ReactECharts
        option={option}
        style={{ height: `${height}px`, width: '100%' }}
        opts={{ renderer: 'canvas' }}
      />
    </div>
  );
}
