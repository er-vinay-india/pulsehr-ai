import React from 'react';
import SafeReactECharts from '../../charts/SafeReactECharts';
import { getSlideTheme } from '../../../theme/slideTokens.js';
import { cartesian, numeric } from '../../charts/chartOptions';


export default function SlideChart({ chart, chartData, theme }) {
  theme = getSlideTheme(theme);
  const isDark = theme.is_dark;
  const actualChart = chart || chartData;

  if (!actualChart) {
    return <p style={{color:theme.muted_text,padding:12}}>No chart data available.</p>;
  }

  const chartLabel = actualChart.title || actualChart.chart_title || actualChart.series?.[0]?.name || "Data visualization chart";

  // If actualChart is already an ECharts option object (contains xAxis or direct series configuration)
  if (actualChart.xAxis || (actualChart.series && actualChart.series[0]?.type && actualChart.series[0]?.data)) {
    return (
      <div
        role="img"
        aria-label={chartLabel}
        style={{ width: '100%', minWidth: 0, height: '100%', minHeight: '260px' }}
      >
        <SafeReactECharts presentationTheme={theme} option={actualChart} style={{ height: '100%', minHeight: '260px', width: '100%' }} />
      </div>
    );
  }

  if (!actualChart.categories?.length || !actualChart.series?.length) {
    return <p style={{color:theme.muted_text,padding:12}}>No chart data available.</p>;
  }

  const type = (actualChart.type || actualChart.chart_type || 'column').toLowerCase();
  const pie = ['pie', 'donut'].includes(type);
  const format = value => Math.abs(Number(value)) >= 1e6 ? `${(Number(value)/1e6).toFixed(1)}M` : Number(value).toLocaleString(undefined, { maximumFractionDigits: 2 });
  const option = pie ? {
    title: { text: chartLabel, left: 'center', textStyle: { fontSize: 18 } },
    legend: { show: false }, tooltip: { trigger: 'item', formatter: '{b}: {c} ({d}%)' },
    series: [{ type: 'pie', name: actualChart.series[0].name || '',
      radius: type === 'donut' ? ['35%', '58%'] : '58%', center: ['50%', '54%'],
      label: { show: true, fontSize: 14, formatter: '{b}\n{c} ({d}%)' },
      labelLine: { show: true }, itemStyle: { borderWidth: 2 },
      data: actualChart.categories.map((label, i) => ({ name: String(label), value: actualChart.series[0].values?.[i] ?? actualChart.series[0].data?.[i] })) }],
  } : cartesian(actualChart.categories,
    actualChart.series.map(s => ({ name: s.name, type: type === 'line' ? 'line' : 'bar',
      data: actualChart.categories.map((_, i) => numeric(s.values?.[i] ?? s.data?.[i])),
      label: { show: true, fontSize: 14, position: ['bar', 'horizontal_bar'].includes(type) ? 'right' : 'top', formatter: p => format(p.value) } })),
    ['bar', 'horizontal_bar'].includes(type), actualChart.unit, isDark);
  if (!pie) {
    option.title = { text: chartLabel, left: 'center', textStyle: { fontSize: 18 } };
    option.legend = { ...option.legend, show: actualChart.series.length > 1, top: 26 };
    option.grid = { left: 30, right: 55, top: actualChart.series.length > 1 ? 65 : 48, bottom: 28, containLabel: true };
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
      <SafeReactECharts presentationTheme={theme} option={option} style={{ height: '100%', minHeight: '230px', width: '100%' }} />
      {actualChart.aggregation_disclosure && (
        <p className="chart-aggregation-note" style={{ fontSize: '11px', marginTop: '4px' }}>
          {actualChart.aggregation_disclosure}
        </p>
      )}
    </div>
  );
}
