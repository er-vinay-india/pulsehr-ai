import React from 'react';
import SafeReactECharts from '../charts/SafeReactECharts';
import { numeric } from '../charts/chartOptions';
import { useTheme } from '../../context/ThemeContext';

export default function ElasticityChart({ data, onInvestigate }) {
  const { isDark } = useTheme();
  const points = (data?.scatter_points || []).filter(p => numeric(p.absent_days) != null && numeric(p.performance) != null);
  if (!points.length) return <p>No paired observations available.</p>;

  const textColor = isDark ? '#CBD5E1' : '#334155';
  const headingColor = isDark ? '#F8FAFC' : '#0B1F3A';
  const axisLineColor = isDark ? '#26384D' : '#CBD5E1';
  const splitLineColor = isDark ? 'rgba(248, 250, 252, 0.08)' : 'rgba(11, 31, 58, 0.08)';
  const tooltipBg = isDark ? '#172A40' : '#FFFFFF';
  const tooltipBorder = isDark ? '#26384D' : '#CBD5E1';
  const pointColor = isDark ? '#5EEAD4' : '#005A6B';
  const thresholdColor = isDark ? '#FBBF24' : '#B7791F';

  return <div><p style={{ color: textColor }}>Slope: <strong>{data?.beta_coefficient ?? '—'}</strong> · R²: <strong>{data?.r_squared ?? '—'}</strong></p>
    <SafeReactECharts option={{
      backgroundColor: 'transparent',
      grid: { left: 55, right: 20, top: 24, bottom: 48 },
      tooltip: {
        trigger: 'item',
        renderMode: 'richText',
        backgroundColor: tooltipBg,
        borderColor: tooltipBorder,
        borderWidth: 1,
        textStyle: { color: headingColor, fontSize: 12 },
        formatter: p => `${p.data.name}\nAbsent days: ${p.value[0]}\nPerformance: ${p.value[1]}`
      },
      xAxis: {
        type: 'value',
        name: 'Absent days',
        nameLocation: 'middle',
        nameGap: 28,
        nameTextStyle: { color: headingColor, fontSize: 11, fontWeight: 600 },
        axisLine: { lineStyle: { color: axisLineColor } },
        axisLabel: { color: textColor, fontSize: 11 },
        splitLine: { lineStyle: { color: splitLineColor, type: 'dashed' } }
      },
      yAxis: {
        type: 'value',
        name: 'Performance',
        nameTextStyle: { color: headingColor, fontSize: 11, fontWeight: 600 },
        axisLine: { lineStyle: { color: axisLineColor } },
        axisLabel: { color: textColor, fontSize: 11 },
        splitLine: { lineStyle: { color: splitLineColor, type: 'dashed' } }
      },
      series: [{
        type: 'scatter',
        symbolSize: 8,
        itemStyle: { color: pointColor },
        data: points.map(p => ({ name: p.name, value: [Number(p.absent_days), Number(p.performance)] })),
        ...(numeric(data?.tipping_point_days) != null ? {
          markLine: {
            symbol: 'none',
            lineStyle: { color: thresholdColor, type: 'dashed', width: 2 },
            label: { color: textColor },
            data: [{ xAxis: Number(data.tipping_point_days), name: 'Reported threshold' }]
          }
        } : {})
      }]
    }}
      onEvents={{ click: p => onInvestigate?.({ entityType: 'employee', targetId: p.data.name, metric: 'Performance Score' }) }} />
  </div>;
}
