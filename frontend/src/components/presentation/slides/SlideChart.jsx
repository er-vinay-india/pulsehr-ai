import React from 'react';
import SafeReactECharts from '../../charts/SafeReactECharts';
import DataChart from '../../charts/DataChart';
import { cartesian, numeric } from '../../charts/chartOptions';
import { useTheme } from '../../../context/ThemeContext';

export default function SlideChart({ chart, chartData, theme }) {
  const { isDark } = useTheme();
  const actualChart = chart || chartData;

  if (!actualChart) {
    return <p className="text-muted p-3">No chart data available.</p>;
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
        <SafeReactECharts option={actualChart} style={{ height: '100%', minHeight: '260px', width: '100%' }} />
      </div>
    );
  }

  if (!actualChart.categories?.length || !actualChart.series?.length) {
    return <p className="text-muted p-3">No chart data available.</p>;
  }

  const type = (actualChart.type || actualChart.chart_type || 'column').toLowerCase();
  const pie = ['pie', 'donut'].includes(type);

  return (
    <div
      role="img"
      aria-label={`${chartLabel} (${type} chart)`}
      style={{ width: '100%', minWidth: 0, height: '100%', minHeight: '260px' }}
    >
      {pie ? (
        <DataChart
          type={type}
          items={actualChart.categories.map((label, i) => ({
            label,
            value: actualChart.series[0].values?.[i] ?? actualChart.series[0].data?.[i]
          }))}
          unit={actualChart.unit || ''}
          metric={actualChart.series[0].name || ''}
        />
      ) : (
        <SafeReactECharts
          option={cartesian(
            actualChart.categories,
            actualChart.series.map(s => ({
              name: s.name,
              type: type === 'line' ? 'line' : 'bar',
              data: actualChart.categories.map((_, i) => numeric(s.values?.[i] ?? s.data?.[i]))
            })),
            ['bar', 'horizontal_bar'].includes(type),
            actualChart.unit,
            isDark
          )}
          style={{ height: '100%', minHeight: '260px', width: '100%' }}
        />
      )}
      {actualChart.aggregation_disclosure && (
        <p className="chart-aggregation-note" style={{ fontSize: '11px', marginTop: '4px' }}>
          {actualChart.aggregation_disclosure}
        </p>
      )}
    </div>
  );
}
