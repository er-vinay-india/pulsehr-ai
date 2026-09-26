import React, { useMemo } from 'react';
import ReactECharts from './SafeReactECharts';

export default function ExecutiveHeatmapChart({
  matrix = null,
  onSelectPair = null,
  height = 280
}) {
  const option = useMemo(() => {
    if (!matrix || !matrix.metrics || matrix.metrics.length < 2) return {};

    const metrics = matrix.metrics;
    const pairs = matrix.pairs || [];

    // Map metrics to indices
    const data = [];
    metrics.forEach((m1, i) => {
      metrics.forEach((m2, j) => {
        if (i === j) {
          data.push([j, i, 1.0, 'Identity']);
        } else {
          const p = pairs.find(
            (item) => (item.x === m1 && item.y === m2) || (item.x === m2 && item.y === m1)
          );
          const coeff = p && p.coefficient != null ? Number(p.coefficient.toFixed(2)) : null;
          data.push([j, i, coeff, p?.excluded_reason || '']);
        }
      });
    });

    return {
      backgroundColor: 'transparent',
      tooltip: {
        position: 'top',
        backgroundColor: '#1c1815',
        borderColor: '#524940',
        textStyle: { color: '#fff9f2', fontSize: 12 },
        formatter: (params) => {
          const [colIdx, rowIdx, val, reason] = params.data;
          const xName = metrics[colIdx];
          const yName = metrics[rowIdx];
          if (xName === yName) return `<b>${xName}</b> (Self)`;
          if (val == null) return `<b>${xName} × ${yName}</b><br/><span style="color:#ded5cb;">${reason || 'Insufficient data'}</span>`;

          let strength = 'Weak';
          if (Math.abs(val) >= 0.7) strength = 'Strong';
          else if (Math.abs(val) >= 0.4) strength = 'Moderate';

          const direction = val > 0 ? 'Positive Relationship' : 'Negative Relationship';

          return `
            <div style="font-weight:600;margin-bottom:4px;color:#ded5cb;">${xName} × ${yName}</div>
            <div style="font-size:13px;font-weight:700;color:${val >= 0 ? '#34d399' : '#fb7185'};">
              ${strength} ${direction} (${val > 0 ? '+' : ''}${val})
            </div>
            <div style="font-size:10px;color:#ded5cb;margin-top:4px;">Click to inspect deep diagnostics in Data Explorer</div>
          `;
        }
      },
      grid: {
        top: '4%',
        bottom: '18%',
        left: '18%',
        right: '4%'
      },
      xAxis: {
        type: 'category',
        data: metrics,
        splitArea: { show: true },
        axisLabel: {
          color: '#ded5cb',
          fontSize: 10,
          interval: 0,
          rotate: 25,
          formatter: (v) => (v.length > 12 ? `${v.slice(0, 10)}…` : v)
        }
      },
      yAxis: {
        type: 'category',
        data: metrics,
        splitArea: { show: true },
        axisLabel: {
          color: '#ded5cb',
          fontSize: 10,
          formatter: (v) => (v.length > 12 ? `${v.slice(0, 10)}…` : v)
        }
      },
      visualMap: {
        min: -1,
        max: 1,
        calculable: false,
        orient: 'horizontal',
        left: 'center',
        bottom: '0%',
        text: ['Positive (+1)', 'Negative (-1)'],
        textStyle: { color: '#ded5cb', fontSize: 10 },
        inRange: {
          color: ['#fb7185', '#1c1815', '#34d399']
        }
      },
      series: [
        {
          name: 'Correlation Matrix',
          type: 'heatmap',
          data: data,
          label: {
            show: metrics.length <= 6,
            color: '#f8fafc',
            fontSize: 10,
            formatter: (p) => (p.data[2] != null ? (p.data[0] === p.data[1] ? '—' : p.data[2]) : '·')
          },
          emphasis: {
            itemStyle: {
              shadowBlur: 10,
              shadowColor: 'rgba(0, 0, 0, 0.5)'
            }
          }
        }
      ]
    };
  }, [matrix]);

  if (!matrix || !matrix.metrics || matrix.metrics.length < 2) {
    return (
      <div className="executive-chart-empty">
        <p>Relationship heatmap requires at least two numeric measures.</p>
      </div>
    );
  }

  const onEvents = {
    click: (params) => {
      if (onSelectPair && params.data) {
        const [colIdx, rowIdx] = params.data;
        const x = matrix.metrics[colIdx];
        const y = matrix.metrics[rowIdx];
        if (x !== y) onSelectPair({ x, y });
      }
    }
  };

  return (
    <div className="executive-heatmap-container">
      <ReactECharts
        option={option}
        onEvents={onEvents}
        style={{ height: `${height}px`, width: '100%' }}
        opts={{ renderer: 'canvas' }}
      />
    </div>
  );
}
