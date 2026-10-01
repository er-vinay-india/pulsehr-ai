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

  return (
    <div
      role="img"
      aria-label={`${chartLabel} (${type} chart)`}
      style={{ width: '100%', minWidth: 0, height: '100%', minHeight: '260px' }}
    >
      {pie ? (
        <SafeReactECharts presentationTheme={theme}
          style={{height:'100%',minHeight:'260px',width:'100%'}}
          option={{legend:{type:'scroll',bottom:0}, tooltip:{trigger:'item'},series:[{type:'pie',name:actualChart.series[0].name || '',radius:type==='donut'?['45%','68%']:'68%',center:['50%','44%'],label:{show:false},itemStyle:{borderWidth:2},data:actualChart.categories.map((label,i)=>({name:String(label),value:actualChart.series[0].values?.[i] ?? actualChart.series[0].data?.[i]}))}]}}
        />
      ) : (
        <SafeReactECharts
          presentationTheme={theme}
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
