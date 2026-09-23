import React, { useMemo } from 'react';
import ReactECharts from './SafeReactECharts';

export default function ExecutiveDonutChart({
  slices = [],
  total = null,
  metricName = 'Composition',
  height = 250,
  centerTitle = 'Total',
  unit = ''
}) {
  const option = useMemo(() => {
    if (!slices || slices.length === 0) return {};

    const computedTotal = total != null ? total : slices.reduce((acc, s) => acc + (s.count || s.value || 0), 0);

    // Color palette for segments
    const colors = ['#38bdf8', '#818cf8', '#63cfb3', '#f59e0b', '#ec4899', '#94a3b8'];

    const formattedData = slices.map((s, idx) => ({
      name: s.label || s.name || `Segment ${idx + 1}`,
      value: s.count != null ? s.count : s.value != null ? s.value : 0,
      itemStyle: { color: s.color || colors[idx % colors.length] }
    }));

    return {
      backgroundColor: 'transparent',
      tooltip: {
        trigger: 'item',
        backgroundColor: 'rgba(15, 23, 42, 0.95)',
        borderColor: 'rgba(255, 255, 255, 0.1)',
        textStyle: { color: '#f8fafc', fontSize: 12 },
        formatter: (params) => {
          const pct = params.percent || 0;
          return `
            <div style="font-weight:600;color:#94a3b8;margin-bottom:4px;">${params.name}</div>
            <div style="font-size:14px;font-weight:700;color:${params.color};">
              ${params.value.toLocaleString()} ${unit} (${pct.toFixed(1)}%)
            </div>
          `;
        }
      },
      legend: {
        orient: 'vertical',
        right: '5%',
        top: 'middle',
        itemWidth: 10,
        itemHeight: 10,
        textStyle: { color: '#cbd5e1', fontSize: 11 },
        formatter: (name) => (name.length > 15 ? `${name.slice(0, 13)}…` : name)
      },
      series: [
        {
          name: metricName,
          type: 'pie',
          radius: ['52%', '78%'],
          center: ['38%', '50%'],
          avoidLabelOverlap: false,
          itemStyle: {
            borderRadius: 6,
            borderColor: '#0f172a',
            borderWidth: 2
          },
          label: {
            show: false,
            position: 'center'
          },
          emphasis: {
            scale: true,
            scaleSize: 6,
            label: {
              show: true,
              fontSize: 14,
              fontWeight: 'bold',
              color: '#f8fafc',
              formatter: '{b}\n{d}%'
            }
          },
          labelLine: { show: false },
          data: formattedData
        }
      ]
    };
  }, [slices, total, metricName, unit]);

  if (!slices || slices.length === 0) {
    return (
      <div className="executive-chart-empty">
        <p>No composition data available.</p>
      </div>
    );
  }

  return (
    <div className="executive-donut-container">
      <ReactECharts
        option={option}
        style={{ height: `${height}px`, width: '100%' }}
        opts={{ renderer: 'canvas' }}
      />
    </div>
  );
}
