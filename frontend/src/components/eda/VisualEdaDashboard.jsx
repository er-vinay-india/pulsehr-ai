import React, { useState, useMemo } from 'react';
import {
  Sparkles,
  TrendingUp,
  GitBranch,
  ArrowRight,
  Table,
  ShieldCheck,
  Layers,
  Activity,
  Brain,
  Clock,
  BarChart2,
  HelpCircle,
  AlertTriangle,
  CheckCircle2,
  ChevronRight
} from 'lucide-react';
import ReactECharts from '../charts/SafeReactECharts';
import { useTheme } from '../../context/ThemeContext';
import { getThemeTokens } from '../../theme/tokens';

export default function VisualEdaDashboard({
  edaReport,
  loadingEda,
  isRerunningEda,
  onRerunEda,
  onExploreDerivedTable
}) {
  const { isDark } = useTheme();
  const themeTokens = getThemeTokens(isDark);
  const [activeTab, setActiveTab] = useState('visuals'); // 'visuals' | 'temporal' | 'predictive' | 'multisheet' | 'diagnostics'
  const [selectedMetric, setSelectedMetric] = useState(null);
  const [selectedLinearIndex, setSelectedLinearIndex] = useState(0);

  const visualAnalytics = edaReport?.visual_analytics || {};
  const correlationMatrix = visualAnalytics.correlation_matrix || { metrics: [], pairs: [], matrix: [] };
  const metricDistributions = visualAnalytics.metric_distributions || {};
  const temporalAnalysis = visualAnalytics.temporal_analysis || { has_temporal_data: false, timeline_series: [] };
  const predictiveModeling = visualAnalytics.predictive_modeling || { linear_models: [], logistic_models: [] };
  const groupByAnalytics = visualAnalytics.group_by_analytics || { dimensions: [], measures: [], breakdowns: {}, insights: [] };

  const typeBreakdown = useMemo(() => {
    if (edaReport?.summary?.data_types_breakdown) {
      return edaReport.summary.data_types_breakdown;
    }
    const diags = edaReport?.column_diagnostics || {};
    const res = { numeric: 0, categorical: 0, datetime: 0, identifier: 0, boolean: 0 };
    Object.values(diags).forEach(d => {
      const t = d.inferred_type || 'categorical';
      if (t.startsWith('numeric')) res.numeric++;
      else if (t.includes('date') || t.includes('time')) res.datetime++;
      else if (t.includes('id')) res.identifier++;
      else res.categorical++;
    });
    return res;
  }, [edaReport]);

  const [selectedGroupDim, setSelectedGroupDim] = useState(null);
  const [selectedGroupMeas, setSelectedGroupMeas] = useState(null);

  const availableGroupDims = useMemo(() => {
    const rawDims = groupByAnalytics.dimensions || [];
    const bds = groupByAnalytics.breakdowns || {};
    const valid = rawDims.filter(d => Object.keys(bds[d] || {}).length > 0);
    return valid.length > 0 ? valid : rawDims;
  }, [groupByAnalytics]);

  const currentGroupDim = useMemo(() => {
    if (selectedGroupDim && availableGroupDims.includes(selectedGroupDim)) {
      return selectedGroupDim;
    }
    return availableGroupDims[0] || '';
  }, [selectedGroupDim, availableGroupDims]);

  const availableGroupMeasures = useMemo(() => {
    if (!currentGroupDim || !groupByAnalytics.breakdowns?.[currentGroupDim]) {
      return groupByAnalytics.measures || [];
    }
    const mList = Object.keys(groupByAnalytics.breakdowns[currentGroupDim]);
    return mList.length > 0 ? mList : (groupByAnalytics.measures || []);
  }, [groupByAnalytics, currentGroupDim]);

  const currentGroupMeas = useMemo(() => {
    if (selectedGroupMeas && availableGroupMeasures.includes(selectedGroupMeas)) {
      return selectedGroupMeas;
    }
    return availableGroupMeasures[0] || '';
  }, [selectedGroupMeas, availableGroupMeasures]);

  const currentBreakdown = useMemo(() => {
    if (!currentGroupDim || !currentGroupMeas) return null;
    return groupByAnalytics.breakdowns?.[currentGroupDim]?.[currentGroupMeas] || null;
  }, [groupByAnalytics, currentGroupDim, currentGroupMeas]);

  const hasGroupBy = availableGroupDims.length > 0 && availableGroupMeasures.length > 0;

  // Set initial selected metric
  const availableMetrics = correlationMatrix.metrics || [];
  const currentMetric = selectedMetric || availableMetrics[0] || '';
  const currentDist = metricDistributions[currentMetric];

  const isEducation =
    availableMetrics.some((m) => {
      const lower = m.toLowerCase();
      return lower.includes('score') || lower.includes('math') || lower.includes('reading') || lower.includes('writing') || lower.includes('student');
    }) ||
    edaReport?.domain === 'education' ||
    edaReport?.domain === 'education_academic' ||
    edaReport?.inferred_domain === 'education' ||
    edaReport?.inferred_domain === 'education_academic';

  const isHr =
    !isEducation &&
    (edaReport?.domain === 'hr' ||
      edaReport?.domain === 'workforce_hr' ||
      edaReport?.inferred_domain === 'hr' ||
      edaReport?.inferred_domain === 'workforce_hr' ||
      availableMetrics.some((m) => {
        const lower = m.toLowerCase();
        return lower.includes('attendance') || lower.includes('leave') || lower.includes('headcount') || lower.includes('salary');
      }));

  // 1. Correlation Heatmap Option
  const heatmapOption = useMemo(() => {
    const metrics = correlationMatrix.metrics || [];
    const matrix = correlationMatrix.matrix || [];
    if (!metrics.length || !matrix.length) return null;

    const data = [];
    metrics.forEach((m1, i) => {
      metrics.forEach((m2, j) => {
        const val = matrix[i]?.[j];
        data.push([j, i, val != null ? Number(val.toFixed(2)) : null]);
      });
    });

    return {
      backgroundColor: 'transparent',
      color: themeTokens.chart.palette,
      tooltip: {
        position: 'top',
        backgroundColor: themeTokens.colors.surface,
        borderColor: themeTokens.colors.borderStrong,
        textStyle: { color: themeTokens.colors.textPrimary, fontSize: 12 },
        formatter: (params) => {
          const [colIdx, rowIdx, val] = params.data;
          const xName = metrics[colIdx];
          const yName = metrics[rowIdx];
          if (xName === yName) return `<b>${xName}</b> (Self Identity: 1.0)`;
          if (val == null) return `<b>${xName} × ${yName}</b><br/>Insufficient variance`;

          const dir = val > 0 ? 'Positive' : 'Negative';
          const strength = Math.abs(val) >= 0.7 ? 'Strong' : Math.abs(val) >= 0.35 ? 'Moderate' : 'Mild';
          const color = val >= 0 ? themeTokens.colors.statusSuccess : themeTokens.colors.statusError;
          return `
            <div style="font-weight:600;margin-bottom:4px;color:${themeTokens.colors.textSecondary};">${xName} ↔ ${yName}</div>
            <div style="font-size:13px;font-weight:700;color:${color};">
              ${strength} ${dir} Correlation: ${val > 0 ? '+' : ''}${val}
            </div>
            <div style="font-size:11px;color:${themeTokens.colors.textMuted};margin-top:4px;">Click cell to inspect pair relationship</div>
          `;
        }
      },
      grid: {
        top: 20,
        bottom: 70,
        left: '4%',
        right: '4%',
        containLabel: true
      },
      xAxis: {
        type: 'category',
        data: metrics,
        splitArea: { show: true },
        axisLabel: {
          color: themeTokens.colors.textSecondary,
          rotate: 35,
          fontSize: 10,
          interval: 0,
          formatter: (v) => v.length > 14 ? v.slice(0, 13) + '…' : v
        },
        axisLine: { lineStyle: { color: themeTokens.colors.borderStrong } }
      },
      yAxis: {
        type: 'category',
        data: metrics,
        splitArea: { show: true },
        axisLabel: {
          color: themeTokens.colors.textSecondary,
          fontSize: 10,
          interval: 0,
          formatter: (v) => v.length > 14 ? v.slice(0, 13) + '…' : v
        },
        axisLine: { lineStyle: { color: themeTokens.colors.borderStrong } }
      },
      visualMap: {
        min: -1,
        max: 1,
        calculable: true,
        orient: 'horizontal',
        left: 'center',
        bottom: '0%',
        text: ['+1.0 (Positive)', '-1.0 (Negative)'],
        textStyle: { color: themeTokens.colors.textSecondary, fontSize: 11 },
        inRange: {
          color: themeTokens.chart.heatmapPalette
        }
      },
      series: [
        {
          type: 'heatmap',
          data: data,
          label: {
            show: metrics.length <= 8,
            color: themeTokens.chart.heatmapText,
            fontSize: 10,
            formatter: (p) => p.data[2] != null ? p.data[2].toFixed(2) : ''
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
  }, [correlationMatrix, themeTokens]);

  // 2. Metric Distribution Histogram Option
  const distributionOption = useMemo(() => {
    if (!currentDist || !currentDist.bins?.length) return null;
    const bins = currentDist.bins;

    return {
      backgroundColor: 'transparent',
      color: themeTokens.chart.palette,
      tooltip: {
        trigger: 'axis',
        axisPointer: { type: 'shadow' },
        backgroundColor: themeTokens.colors.surface,
        borderColor: themeTokens.colors.borderStrong,
        textStyle: { color: themeTokens.colors.textPrimary, fontSize: 12 },
        formatter: (params) => {
          const p = params[0];
          return `<b>Range: ${p.name}</b><br/>Employees / Rows: <b>${p.value}</b>`;
        }
      },
      grid: {
        top: 25,
        bottom: 40,
        left: 45,
        right: 25,
        containLabel: true
      },
      xAxis: {
        type: 'category',
        data: bins.map((b) => b.label),
        axisLabel: { color: themeTokens.colors.textSecondary, rotate: 25, fontSize: 10 },
        axisLine: { lineStyle: { color: themeTokens.colors.borderStrong } }
      },
      yAxis: {
        type: 'value',
        axisLabel: { color: themeTokens.colors.textSecondary, fontSize: 11 },
        splitLine: { lineStyle: { color: themeTokens.chart.splitLine } }
      },
      series: [
        {
          name: 'Frequency',
          type: 'bar',
          data: bins.map((b) => b.count),
          itemStyle: {
            color: themeTokens.colors.gold,
            borderRadius: [4, 4, 0, 0]
          },
          markLine: {
            symbol: 'none',
            data: [
              {
                xAxis: bins.findIndex((b) => currentDist.median >= b.bin_start && currentDist.median <= b.bin_end),
                lineStyle: { color: themeTokens.colors.statusSuccess, type: 'dashed', width: 2 },
                label: { formatter: `Median: ${currentDist.median}`, color: themeTokens.colors.statusSuccess, position: 'end' }
              }
            ]
          }
        }
      ]
    };
  }, [currentDist, themeTokens]);

  // 3. Temporal Date-Separated Trajectory Option
  const temporalOption = useMemo(() => {
    const series = temporalAnalysis.timeline_series || [];
    if (!series.length) return null;

    const labels = series.map((s) => s.period_label);
    const avgAtt = series.map((s) => s.average_attendance);
    const avgLeaves = series.map((s) => s.average_leaves);
    const leaveRates = series.map((s) => s.leave_rate_percentage);

    return {
      backgroundColor: 'transparent',
      color: themeTokens.chart.palette,
      tooltip: {
        trigger: 'axis',
        backgroundColor: themeTokens.colors.surface,
        borderColor: themeTokens.colors.borderStrong,
        textStyle: { color: themeTokens.colors.textPrimary, fontSize: 12 },
        formatter: (params) => {
          let html = `<b>Period: ${params[0].name}</b><br/>`;
          params.forEach((p) => {
            html += `<span style="color:${p.color};">●</span> ${p.seriesName}: <b>${p.value}${p.seriesName.includes('Rate') ? '%' : ' days'}</b><br/>`;
          });
          return html;
        }
      },
      legend: {
        data: ['Avg Attendance (Days)', 'Avg Approved Leaves', 'Leave Utilization Rate (%)'],
        textStyle: { color: themeTokens.colors.textSecondary, fontSize: 11 },
        top: 0
      },
      grid: {
        top: 40,
        bottom: 45,
        left: 45,
        right: 50,
        containLabel: true
      },
      xAxis: {
        type: 'category',
        data: labels,
        axisLabel: { color: themeTokens.colors.textSecondary, rotate: 20, fontSize: 11 },
        axisLine: { lineStyle: { color: themeTokens.colors.borderStrong } }
      },
      yAxis: [
        {
          type: 'value',
          name: 'Days',
          nameTextStyle: { color: themeTokens.colors.textMuted, fontSize: 10 },
          axisLabel: { color: themeTokens.colors.textSecondary, fontSize: 11 },
          splitLine: { lineStyle: { color: themeTokens.chart.splitLine } }
        },
        {
          type: 'value',
          name: 'Rate (%)',
          nameTextStyle: { color: themeTokens.colors.textMuted, fontSize: 10 },
          axisLabel: { color: themeTokens.colors.textSecondary, fontSize: 11, formatter: '{value}%' },
          splitLine: { show: false }
        }
      ],
      series: [
        {
          name: 'Avg Attendance (Days)',
          type: 'bar',
          data: avgAtt,
          itemStyle: { color: themeTokens.colors.statusSuccess, borderRadius: [4, 4, 0, 0] }
        },
        {
          name: 'Avg Approved Leaves',
          type: 'bar',
          data: avgLeaves,
          itemStyle: { color: themeTokens.colors.gold, borderRadius: [4, 4, 0, 0] }
        },
        {
          name: 'Leave Utilization Rate (%)',
          type: 'line',
          yAxisIndex: 1,
          data: leaveRates,
          symbolSize: 8,
          itemStyle: { color: themeTokens.colors.statusError },
          lineStyle: { width: 3 }
        }
      ]
    };
  }, [temporalAnalysis, themeTokens]);

  // 4. Linear Regression Scatter Option
  const linearModel = predictiveModeling.linear_models?.[selectedLinearIndex] || predictiveModeling.linear_models?.[0];
  const linearChartOption = useMemo(() => {
    if (!linearModel) return null;
    const scatter = (linearModel.scatter_points || []).map((p) => [p.x, p.y]);
    const trendline = (linearModel.trendline || []).map((p) => [p.x, p.y]);

    return {
      backgroundColor: 'transparent',
      color: themeTokens.chart.palette,
      tooltip: {
        trigger: 'item',
        backgroundColor: themeTokens.colors.surface,
        borderColor: themeTokens.colors.borderStrong,
        textStyle: { color: themeTokens.colors.textPrimary, fontSize: 12 },
        formatter: (params) => {
          if (params.seriesName === 'OLS Trendline') {
            return `<b>Fitted Line:</b> ${linearModel.equation}`;
          }
          return `<b>Employee Record:</b><br/>${linearModel.x_variable}: <b>${params.value[0]}</b><br/>${linearModel.y_variable}: <b>${params.value[1]}</b>`;
        }
      },
      grid: {
        top: 25,
        bottom: 45,
        left: 55,
        right: 35,
        containLabel: true
      },
      xAxis: {
        type: 'value',
        name: linearModel.x_variable,
        nameLocation: 'middle',
        nameGap: 28,
        nameTextStyle: { color: themeTokens.colors.textSecondary, fontSize: 11 },
        axisLabel: { color: themeTokens.colors.textSecondary, fontSize: 11 },
        splitLine: { lineStyle: { color: themeTokens.chart.splitLine } }
      },
      yAxis: {
        type: 'value',
        name: linearModel.y_variable,
        nameTextStyle: { color: themeTokens.colors.textSecondary, fontSize: 11 },
        axisLabel: { color: themeTokens.colors.textSecondary, fontSize: 11 },
        splitLine: { lineStyle: { color: themeTokens.chart.splitLine } }
      },
      series: [
        {
          name: 'Observations',
          type: 'scatter',
          data: scatter,
          symbolSize: 6,
          itemStyle: {
            color: themeTokens.colors.softGold,
            borderColor: themeTokens.colors.gold
          }
        },
        {
          name: 'OLS Trendline',
          type: 'line',
          data: trendline,
          showSymbol: false,
          lineStyle: { color: themeTokens.colors.statusSuccess, width: 3 },
          markPoint: {
            data: [
              {
                coord: trendline[1],
                value: `R² = ${linearModel.r_squared}`,
                itemStyle: { color: themeTokens.colors.statusSuccess },
                label: { color: themeTokens.colors.textOnBrand, fontWeight: 'bold' }
              }
            ]
          }
        }
      ]
    };
  }, [linearModel, themeTokens]);

  // 5. Logistic Regression Sigmoid Probability Option
  const logisticModel = predictiveModeling.logistic_models?.[0];
  const logisticChartOption = useMemo(() => {
    if (!logisticModel || !logisticModel.sigmoid_curve?.length) return null;
    const curveData = logisticModel.sigmoid_curve.map((pt) => [pt.x, pt.probability]);

    return {
      backgroundColor: 'transparent',
      color: themeTokens.chart.palette,
      tooltip: {
        trigger: 'axis',
        backgroundColor: themeTokens.colors.surface,
        borderColor: themeTokens.colors.borderStrong,
        textStyle: { color: themeTokens.colors.textPrimary, fontSize: 12 },
        formatter: (params) => {
          const pt = params[0];
          return `<b>${logisticModel.x_variable}: ${pt.value[0]}</b><br/>Risk Probability: <b>${(pt.value[1] * 100).toFixed(1)}%</b>`;
        }
      },
      grid: {
        top: 25,
        bottom: 45,
        left: 55,
        right: 35,
        containLabel: true
      },
      xAxis: {
        type: 'value',
        name: logisticModel.x_variable,
        nameLocation: 'middle',
        nameGap: 28,
        nameTextStyle: { color: themeTokens.colors.textSecondary, fontSize: 11 },
        axisLabel: { color: themeTokens.colors.textSecondary, fontSize: 11 },
        splitLine: { lineStyle: { color: themeTokens.chart.splitLine } }
      },
      yAxis: {
        type: 'value',
        min: 0,
        max: 1.0,
        name: 'P(High Risk)',
        nameTextStyle: { color: themeTokens.colors.textSecondary, fontSize: 11 },
        axisLabel: { color: themeTokens.colors.textSecondary, fontSize: 11, formatter: (v) => `${(v * 100).toFixed(0)}%` },
        splitLine: { lineStyle: { color: themeTokens.chart.splitLine } }
      },
      series: [
        {
          name: 'Risk Probability Sigmoid',
          type: 'line',
          smooth: true,
          data: curveData,
          showSymbol: false,
          lineStyle: { color: themeTokens.colors.statusError, width: 3 },
          areaStyle: {
            color: {
              type: 'linear',
              x: 0,
              y: 0,
              x2: 0,
              y2: 1,
              colorStops: [
                { offset: 0, color: themeTokens.colors.softError },
                { offset: 1, color: themeTokens.colors.surface }
              ]
            }
          },
          markLine: {
            symbol: 'none',
            data: [
              {
                yAxis: 0.5,
                lineStyle: { color: themeTokens.colors.gold, type: 'dashed' },
                label: { formatter: '50% Threshold', color: themeTokens.colors.gold, position: 'end' }
              }
            ]
          }
        }
      ]
    };
  }, [logisticModel, themeTokens]);

  // Group-By Category Bar Chart Option
  const groupByBarOption = useMemo(() => {
    if (!currentBreakdown) return null;
    const cats = currentBreakdown.categories || [];
    const means = currentBreakdown.means || [];
    const topCat = currentBreakdown.top_category;
    const overallMean = currentBreakdown.overall_mean;

    return {
      backgroundColor: 'transparent',
      color: themeTokens.chart.palette,
      tooltip: {
        trigger: 'axis',
        axisPointer: { type: 'shadow' },
        backgroundColor: themeTokens.colors.surface,
        borderColor: themeTokens.colors.borderStrong,
        textStyle: { color: themeTokens.colors.textPrimary, fontSize: 12 },
        formatter: (params) => {
          const item = params[0];
          const idx = item.dataIndex;
          const count = currentBreakdown.counts?.[idx] ?? '';
          const total = currentBreakdown.totals?.[idx] ?? '';
          const isTop = cats[idx] === topCat;
          return `
            <div style="font-weight:700;margin-bottom:4px;color:${themeTokens.colors.textPrimary};">${item.name} ${isTop ? '🏆 (Top Cohort)' : ''}</div>
            <div style="color:${themeTokens.colors.gold};font-size:13px;font-weight:600;">Mean ${currentBreakdown.measure_label}: ${item.value}</div>
            <div style="color:${themeTokens.colors.textMuted};font-size:11px;margin-top:2px;">Sample Count: ${count} records</div>
            <div style="color:${themeTokens.colors.textMuted};font-size:11px;">Aggregated Total: ${total}</div>
          `;
        }
      },
      grid: {
        top: 35,
        bottom: 50,
        left: '5%',
        right: '5%',
        containLabel: true
      },
      xAxis: {
        type: 'category',
        data: cats,
        axisLabel: {
          color: themeTokens.colors.textSecondary,
          rotate: cats.length > 5 ? 25 : 0,
          fontSize: 11
        },
        axisLine: { lineStyle: { color: themeTokens.colors.borderStrong } }
      },
      yAxis: {
        type: 'value',
        name: `Mean ${currentBreakdown.measure_label}`,
        nameTextStyle: { color: themeTokens.colors.textMuted, fontSize: 11 },
        splitLine: { lineStyle: { color: themeTokens.chart.splitLine } },
        axisLabel: { color: themeTokens.colors.textMuted, fontSize: 11 }
      },
      series: [
        {
          name: `Mean ${currentBreakdown.measure_label}`,
          type: 'bar',
          data: means.map((val, idx) => ({
            value: val,
            itemStyle: {
              color: cats[idx] === topCat ? themeTokens.colors.gold : themeTokens.colors.brandBlue,
              borderRadius: [4, 4, 0, 0]
            }
          })),
          markLine: overallMean != null ? {
            data: [{ type: 'average', name: 'Overall Mean', yAxis: overallMean }],
            lineStyle: { color: themeTokens.colors.statusSuccess, type: 'dashed', width: 2 },
            label: {
              formatter: `Overall Mean: ${overallMean}`,
              position: 'insideEndTop',
              color: themeTokens.colors.statusSuccess,
              fontSize: 11
            }
          } : undefined
        }
      ]
    };
  }, [currentBreakdown, themeTokens]);

  // Group-By Donut Distribution Option
  const groupByDonutOption = useMemo(() => {
    if (!currentBreakdown || !currentBreakdown.table_rows) return null;
    const pieData = currentBreakdown.table_rows.map((r) => ({
      name: r.category,
      value: r.count
    }));

    return {
      backgroundColor: 'transparent',
      color: themeTokens.chart.palette,
      tooltip: {
        trigger: 'item',
        backgroundColor: themeTokens.colors.surface,
        borderColor: themeTokens.colors.borderStrong,
        textStyle: { color: themeTokens.colors.textPrimary, fontSize: 12 },
        formatter: '{b}: {c} records ({d}%)'
      },
      legend: {
        bottom: 0,
        textStyle: { color: themeTokens.colors.textSecondary, fontSize: 11 }
      },
      series: [
        {
          name: 'Record Share',
          type: 'pie',
          radius: ['45%', '70%'],
          center: ['50%', '45%'],
          avoidLabelOverlap: false,
          itemStyle: {
            borderRadius: 6,
            borderColor: themeTokens.colors.surface,
            borderWidth: 2
          },
          label: {
            show: false,
            position: 'center'
          },
          emphasis: {
            label: {
              show: true,
              fontSize: 13,
              fontWeight: 'bold',
              color: themeTokens.colors.textPrimary,
              formatter: '{b}\n{d}%'
            }
          },
          data: pieData
        }
      ]
    };
  }, [currentBreakdown, themeTokens]);

  if (loadingEda) {
    return (
      <div className="card-panel" style={{ padding: '3rem', textAlign: 'center' }}>
        <p style={{ color: 'var(--fg-secondary)', fontSize: '1rem' }}>
          Generating and calculating full exploratory statistical & predictive analytics...
        </p>
      </div>
    );
  }

  if (!edaReport) {
    return (
      <div className="card-panel" style={{ padding: '3rem', textAlign: 'center' }}>
        <p style={{ color: 'var(--fg-secondary)', fontSize: '1rem' }}>
          Select a sheet to inspect Exploratory Data Analysis & Advanced Modeling.
        </p>
      </div>
    );
  }

  return (
    <div className="eda-dashboard">
      {/* 1. Hero Summary Card */}
      <div className="eda-hero-card">
        <div className="eda-score-box">
          <div
            className={`score-circle ${
              edaReport.health_score >= 90
                ? 'score-excellent'
                : edaReport.health_score >= 70
                ? 'score-good'
                : 'score-attention'
            }`}
          >
            <span>{edaReport.health_score}%</span>
            <span className="score-label">Health</span>
          </div>
          <div className="score-text">
            <h2>{edaReport.sheet_name}</h2>
            <p>Tabular data hygiene score computed across missingness, IQR anomalies, and type coercions.</p>
            <span
              className={`status-badge ${
                edaReport.health_score >= 90
                  ? 'status-excellent'
                  : edaReport.health_score >= 70
                  ? 'status-good'
                  : 'status-attention'
              }`}
            >
              {edaReport.health_status}
            </span>
          </div>
        </div>

        <div className="eda-summary-chips">
          <div className="summary-chip">
            <div className="chip-label">Rows Ingested</div>
            <div className="chip-val">{edaReport.summary?.total_rows}</div>
          </div>
          <div className="summary-chip">
            <div className="chip-label">Columns</div>
            <div className="chip-val">{edaReport.summary?.total_columns}</div>
          </div>

          {/* Data Types Information Chip */}
          <div className="summary-chip chip-types-highlight" title="Data Types breakdown across columns">
            <div className="chip-label">Data Types Info</div>
            <div className="chip-val text-types" style={{ fontSize: '1.05rem', fontWeight: 700 }}>
              {typeBreakdown.numeric || 0} Num · {typeBreakdown.categorical || 0} Cat
              {typeBreakdown.datetime > 0 ? ` · ${typeBreakdown.datetime} Date` : ''}
              {typeBreakdown.identifier > 0 ? ` · ${typeBreakdown.identifier} ID` : ''}
            </div>
          </div>

          {/* Missing / Null Cells Chip - Highlighted in Big Font */}
          <div
            className={`summary-chip ${(edaReport.summary?.total_null_cells || 0) > 0 ? 'chip-warning-highlight' : 'chip-clean-highlight'}`}
            title={(edaReport.summary?.total_null_cells || 0) > 0 ? `${edaReport.summary?.total_null_cells} missing cells found` : 'Complete sheet with zero nulls'}
          >
            <div className="chip-label">Missing / Null Cells</div>
            <div
              className={`chip-val ${(edaReport.summary?.total_null_cells || 0) > 0 ? 'val-warning' : 'text-clean'}`}
              style={{ fontSize: '1.25rem', fontWeight: 800 }}
            >
              {(edaReport.summary?.total_null_cells || 0) > 0
                ? `⚠️ ${edaReport.summary?.total_null_cells} (${edaReport.summary?.null_cells_pct ?? 0}%)`
                : '✓ 0 (100% Clean)'}
            </div>
          </div>

          {/* Incomplete Rows Chip - Highlighted in Big Font */}
          <div
            className={`summary-chip ${(edaReport.summary?.incomplete_rows_count || 0) > 0 ? 'chip-warning-highlight' : 'chip-clean-highlight'}`}
            title="Rows containing at least one missing cell"
          >
            <div className="chip-label">Incomplete Rows</div>
            <div
              className={`chip-val ${(edaReport.summary?.incomplete_rows_count || 0) > 0 ? 'val-warning' : 'text-clean'}`}
              style={{ fontSize: '1.15rem', fontWeight: 700 }}
            >
              {(edaReport.summary?.incomplete_rows_count || 0) > 0
                ? `⚠️ ${edaReport.summary?.incomplete_rows_count} (${edaReport.summary?.incomplete_rows_pct ?? 0}%)`
                : '✓ 0 Rows'}
            </div>
          </div>

          <div className="summary-chip">
            <div className="chip-label">Normalized Cells</div>
            <div className="chip-val val-accent">{edaReport.summary?.total_normalized_cells}</div>
          </div>
          <div className="summary-chip">
            <div className="chip-label">Anomalies</div>
            <div className="chip-val val-warning">{edaReport.summary?.total_anomalies}</div>
          </div>
        </div>

        <button
          className="btn-rerun-eda"
          onClick={onRerunEda}
          disabled={isRerunningEda}
        >
          {isRerunningEda ? 'Recomputing...' : 'Re-run EDA Pipeline'}
        </button>
      </div>

      {/* Incomplete Sheet Alert Ribbon if missing values detected */}
      {(edaReport.summary?.total_null_cells || 0) > 0 && (
        <div className="incomplete-sheet-alert-ribbon" style={{ margin: '0 0 1rem 0' }}>
          <div className="alert-ribbon-left">
            <div className="alert-ribbon-icon">
              <AlertTriangle size={20} color="#f43f5e" />
            </div>
            <div className="alert-ribbon-text">
              <div className="alert-ribbon-title">
                Incomplete Dataset Warning: {edaReport.summary.total_null_cells} Missing / Null Values Detected
              </div>
              <div className="alert-ribbon-desc">
                {edaReport.summary.columns_with_nulls_count || 'Multiple'} columns have missing data affecting{' '}
                {edaReport.summary.incomplete_rows_count || 'several'} rows ({edaReport.summary.incomplete_rows_pct ?? 0}% of rows).
                Check the Schema Diagnostics tab for column-by-column missingness rates and automated imputation models,
                or upload a corrected sheet.
              </div>
            </div>
          </div>
          <button
            type="button"
            className="btn-upload-corrected"
            onClick={() => { window.location.hash = 'upload'; }}
          >
            Upload Corrected Sheet
          </button>
        </div>
      )}

      {/* 2. Plain-Language Recommendations & Domain Points */}
      {edaReport.recommendations && edaReport.recommendations.length > 0 && (
        <div className="eda-recs-card">
          <h3>
            <Sparkles size={16} />
            {isHr ? 'HR Executive Analytical Insights & Next Steps' : (isEducation ? 'Academic Leadership Analytical Insights & Next Steps' : 'Executive Analytical Insights & Next Steps')}
          </h3>
          <ul>
            {edaReport.recommendations.map((rec, idx) => (
              <li key={idx}>{rec}</li>
            ))}
          </ul>
        </div>
      )}

      {/* 3. Unified Sub-Tab Navigation Bar */}
      <div
        className="eda-subtabs-bar"
        style={{
          display: 'flex',
          gap: '0.5rem',
          borderBottom: '1px solid var(--border-subtle)',
          paddingBottom: '0.75rem',
          flexWrap: 'wrap'
        }}
      >
        <button
          className={`toggle-btn ${activeTab === 'visuals' ? 'active' : ''}`}
          onClick={() => setActiveTab('visuals')}
          style={{ display: 'inline-flex', alignItems: 'center', gap: '6px' }}
        >
          <BarChart2 size={15} />
          <span>Distributions & Correlation Matrix</span>
        </button>

        {hasGroupBy && (
          <button
            className={`toggle-btn ${activeTab === 'groupings' ? 'active' : ''}`}
            onClick={() => setActiveTab('groupings')}
            style={{ display: 'inline-flex', alignItems: 'center', gap: '6px' }}
          >
            <Layers size={15} />
            <span>📊 Group-By & Dimensional Breakdowns</span>
          </button>
        )}

        {temporalAnalysis.has_temporal_data && (
          <button
            className={`toggle-btn ${activeTab === 'temporal' ? 'active' : ''}`}
            onClick={() => setActiveTab('temporal')}
            style={{ display: 'inline-flex', alignItems: 'center', gap: '6px' }}
          >
            <Clock size={15} />
            <span>Date-Separated Temporal Dynamics</span>
          </button>
        )}

        <button
          className={`toggle-btn ${activeTab === 'predictive' ? 'active' : ''}`}
          onClick={() => setActiveTab('predictive')}
          style={{ display: 'inline-flex', alignItems: 'center', gap: '6px' }}
        >
          <Brain size={15} />
          <span>Predictive Modeling (Linear & Logistic)</span>
        </button>

        <button
          className={`toggle-btn ${activeTab === 'multisheet' ? 'active' : ''}`}
          onClick={() => setActiveTab('multisheet')}
          style={{ display: 'inline-flex', alignItems: 'center', gap: '6px' }}
        >
          <GitBranch size={15} />
          <span>Verified Multi-Sheet Linkages</span>
        </button>

        <button
          className={`toggle-btn ${activeTab === 'diagnostics' ? 'active' : ''}`}
          onClick={() => setActiveTab('diagnostics')}
          style={{ display: 'inline-flex', alignItems: 'center', gap: '6px' }}
        >
          <Table size={15} />
          <span>Schema Diagnostics & Audit</span>
        </button>
      </div>

      {/* TAB 1: VISUAL DISTRIBUTIONS & CORRELATIONS */}
      {activeTab === 'visuals' && (
        <div style={{ display: 'flex', flexDirection: 'column', gap: '1.25rem' }}>
          {/* Section A: Interactive Correlation Matrix Heatmap */}
          <div className="eda-section-card">
            <div className="section-header">
              <h3>
                <Activity size={18} color={themeTokens.colors.gold} />
                Realistic Intra-Sheet Correlation Matrix
              </h3>
              <p>
                Pearson ($r$) association matrix computed strictly on validated quantitative metrics (excluding non-metric identifiers and keys).
              </p>
            </div>

            {heatmapOption ? (
              <div style={{ marginTop: '0.5rem', overflowX: 'auto', WebkitOverflowScrolling: 'touch' }}>
                <div style={{ minWidth: '460px' }}>
                  <ReactECharts option={heatmapOption} style={{ height: '340px', width: '100%' }} />
                </div>
              </div>
            ) : (
              <p style={{ color: 'var(--fg-muted)', fontSize: '0.85rem' }}>
                Insufficient numeric metric columns with variance to generate a correlation matrix.
              </p>
            )}

            {correlationMatrix.pairs?.length > 0 && (
              <div style={{ marginTop: '1.25rem' }}>
                <h4 style={{ color: 'var(--color-text-secondary, #334155)', fontSize: '0.85rem', marginBottom: '0.6rem' }}>
                  Top Ranked Metric Associations ($p &lt; 0.05$)
                </h4>
                <div className="eda-correlations-grid">
                  {correlationMatrix.pairs.slice(0, 6).map((pair, idx) => (
                    <div key={idx} className="correlation-tile">
                      <div className="corr-top-row">
                        <div className="corr-metrics">
                          {pair.x} ↔ {pair.y}
                        </div>
                        <span className={`corr-badge ${pair.direction === 'negative' ? 'negative' : 'positive'}`}>
                          {pair.strength.toUpperCase()} (r = {pair.coefficient > 0 ? '+' : ''}{pair.coefficient})
                        </span>
                      </div>
                      <div className="corr-sheets-label">
                        Sample Size: {pair.sample_size} records · Spearman ρ: {pair.spearman_rho}
                      </div>
                      <div className="corr-narrative">
                        {pair.direction === 'positive'
                          ? `Higher '${pair.x}' directly correlates with higher '${pair.y}'.`
                          : `Higher '${pair.x}' is inversely associated with '${pair.y}'.`}
                      </div>
                    </div>
                  ))}
                </div>
              </div>
            )}
          </div>

          {/* Section B: Metric Distribution Histogram & Outlier Bounds */}
          <div className="eda-section-card">
            <div
              className="section-header"
              style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', flexWrap: 'wrap', gap: '0.75rem' }}
            >
              <div>
                <h3>
                  <BarChart2 size={18} color={themeTokens.colors.statusSuccess} />
                  Metric Distribution Histogram & Outlier Inspector
                </h3>
                <p>
                  10-bin frequency distribution, median markers, and IQR outlier boundaries.
                </p>
              </div>

              {availableMetrics.length > 0 && (
                <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                  <label htmlFor="eda-metric-select" style={{ fontSize: '0.8rem', color: 'var(--color-text-secondary, #334155)', fontWeight: 600 }}>Select Metric:</label>
                  <select
                    id="eda-metric-select"
                    aria-label="Select metric for distribution analysis"
                    value={currentMetric}
                    onChange={(e) => setSelectedMetric(e.target.value)}
                    style={{
                      background: 'var(--surface-inset)',
                      border: '1px solid var(--border-subtle)',
                      borderRadius: '6px',
                      color: 'var(--fg-primary)',
                      padding: '0.35rem 0.65rem',
                      fontSize: '0.8rem'
                    }}
                  >
                    {availableMetrics.map((m) => (
                      <option key={m} value={m}>
                        {m}
                      </option>
                    ))}
                  </select>
                </div>
              )}
            </div>

            {currentDist ? (
              <div style={{ marginTop: '1rem' }}>
                <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(130px, 1fr))', gap: '0.75rem', marginBottom: '1rem' }}>
                  <div className="summary-chip">
                    <div className="chip-label">Mean (μ)</div>
                    <div className="chip-val">{currentDist.mean}</div>
                  </div>
                  <div className="summary-chip">
                    <div className="chip-label">Median</div>
                    <div className="chip-val val-accent">{currentDist.median}</div>
                  </div>
                  <div className="summary-chip">
                    <div className="chip-label">Std Dev (σ)</div>
                    <div className="chip-val">{currentDist.std}</div>
                  </div>
                  <div className="summary-chip">
                    <div className="chip-label">Min / Max</div>
                    <div className="chip-val">{currentDist.min} / {currentDist.max}</div>
                  </div>
                  <div className="summary-chip">
                    <div className="chip-label">IQR (Q1 - Q3)</div>
                    <div className="chip-val">{currentDist.q25} - {currentDist.q75}</div>
                  </div>
                </div>

                <ReactECharts option={distributionOption} style={{ height: '260px', width: '100%' }} />
              </div>
            ) : (
              <p style={{ color: 'var(--fg-muted)', fontSize: '0.85rem' }}>
                No distribution data available for the selected metric.
              </p>
            )}
          </div>
        </div>
      )}

      {/* TAB 2: DATE-SEPARATED TEMPORAL DYNAMICS */}
      {activeTab === 'temporal' && (
        <div className="eda-section-card">
          <div className="section-header">
            <h3>
              <Clock size={18} color={themeTokens.colors.gold} />
              Date-Separated Temporal Attendance & Leave Progression
            </h3>
            <p>
              Data separated across distinct weekly periods to trace attendance patterns, leave spikes, and burnout trajectories.
            </p>
          </div>

          {temporalOption ? (
            <div style={{ marginTop: '1rem' }}>
              <ReactECharts option={temporalOption} style={{ height: '320px', width: '100%' }} />

              {/* Temporal Takeaways */}
              {temporalAnalysis.insights && temporalAnalysis.insights.length > 0 && (
                <div
                  style={{
                    marginTop: '1.25rem',
                    background: themeTokens.colors.softGold,
                    border: '1px solid var(--color-border-strong)',
                    borderRadius: '8px',
                    padding: '0.85rem 1.1rem'
                  }}
                >
                  <strong style={{ color: themeTokens.colors.gold, fontSize: '0.9rem' }}>{isHr ? 'HR Temporal Findings:' : 'Temporal Trend Findings:'}</strong>
                  <ul style={{ margin: '6px 0 0 1.25rem', padding: 0, fontSize: '0.85rem', color: themeTokens.colors.textSecondary }}>
                    {temporalAnalysis.insights.map((ins, idx) => (
                      <li key={idx} style={{ marginBottom: '4px' }}>{ins}</li>
                    ))}
                  </ul>
                </div>
              )}

              {/* Temporal Correlations Grid */}
              {temporalAnalysis.temporal_correlations?.length > 0 && (
                <div style={{ marginTop: '1.25rem' }}>
                  <h4 style={{ color: 'var(--color-text-secondary, #334155)', fontSize: '0.85rem', marginBottom: '0.6rem' }}>
                    Week-over-Week Leave Persistence ($p &lt; 0.05$)
                  </h4>
                  <div className="eda-correlations-grid">
                    {temporalAnalysis.temporal_correlations.map((tc, idx) => (
                      <div key={idx} className="correlation-tile">
                        <div className="corr-top-row">
                          <div className="corr-metrics">{tc.period_a} ↔ {tc.period_b}</div>
                          <span className={`corr-badge ${tc.direction === 'negative' ? 'negative' : 'positive'}`}>
                            r = {tc.correlation > 0 ? '+' : ''}{tc.correlation}
                          </span>
                        </div>
                        <div className="corr-narrative">{tc.interpretation}</div>
                      </div>
                    ))}
                  </div>
                </div>
              )}
            </div>
          ) : (
            <p style={{ color: 'var(--fg-muted)', fontSize: '0.85rem' }}>
              No multi-period temporal columns detected in this sheet.
            </p>
          )}
        </div>
      )}

      {/* TAB 3: PREDICTIVE MODELING (LINEAR & LOGISTIC REGRESSION) */}
      {activeTab === 'predictive' && (
        <div style={{ display: 'flex', flexDirection: 'column', gap: '1.25rem' }}>
          {/* Section A: Linear Regression (OLS) */}
          <div className="eda-section-card">
            <div
              className="section-header"
              style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', flexWrap: 'wrap', gap: '0.75rem' }}
            >
              <div>
                <h3>
                  <TrendingUp size={18} color={themeTokens.colors.statusSuccess} />
                  Linear Regression Studio (Ordinary Least Squares)
                </h3>
                <p>
                  Predict continuous workforce metrics with slope ($\beta$), confidence bounds, and goodness of fit ($R^2$).
                </p>
              </div>

              {predictiveModeling.linear_models?.length > 1 && (
                <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                  <label htmlFor="eda-linear-model-select" style={{ fontSize: '0.8rem', color: 'var(--color-text-secondary, #334155)', fontWeight: 600 }}>Select Model:</label>
                  <select
                    id="eda-linear-model-select"
                    aria-label="Select linear regression model"
                    value={selectedLinearIndex}
                    onChange={(e) => setSelectedLinearIndex(Number(e.target.value))}
                    style={{
                      background: 'var(--surface-inset)',
                      border: '1px solid var(--border-subtle)',
                      borderRadius: '6px',
                      color: 'var(--fg-primary)',
                      padding: '0.35rem 0.65rem',
                      fontSize: '0.8rem'
                    }}
                  >
                    {predictiveModeling.linear_models.map((lm, idx) => (
                      <option key={idx} value={idx}>
                        {lm.x_variable} → {lm.y_variable} (R² = {lm.r_squared})
                      </option>
                    ))}
                  </select>
                </div>
              )}
            </div>

            {linearModel ? (
              <div style={{ marginTop: '1rem' }}>
                {/* Stats Row */}
                <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(140px, 1fr))', gap: '0.75rem', marginBottom: '1rem' }}>
                  <div className="summary-chip">
                    <div className="chip-label">Fitted Equation</div>
                    <div className="chip-val val-accent" style={{ fontSize: '0.85rem' }}>
                      {linearModel.equation}
                    </div>
                  </div>
                  <div className="summary-chip">
                    <div className="chip-label">R² Goodness of Fit</div>
                    <div className="chip-val">{linearModel.r_squared} ({((linearModel.r_squared || 0) * 100).toFixed(0)}% var)</div>
                  </div>
                  <div className="summary-chip">
                    <div className="chip-label">Slope (β)</div>
                    <div className="chip-val">{linearModel.slope}</div>
                  </div>
                  <div className="summary-chip">
                    <div className="chip-label">p-value</div>
                    <div className="chip-val">{linearModel.p_value < 0.001 ? '< 0.001' : linearModel.p_value}</div>
                  </div>
                  <div className="summary-chip">
                    <div className="chip-label">RMSE</div>
                    <div className="chip-val">{linearModel.rmse}</div>
                  </div>
                </div>

                {/* Scatter + Fitted Line */}
                <ReactECharts option={linearChartOption} style={{ height: '300px', width: '100%' }} />

                {/* Plain-Language HR Takeaway */}
                <div
                  style={{
                    marginTop: '1rem',
                    background: themeTokens.colors.mint,
                    border: '1px solid var(--color-border-strong)',
                    borderRadius: '8px',
                    padding: '0.75rem 1rem',
                    fontSize: '0.85rem',
                    color: themeTokens.colors.textSecondary
                  }}
                >
                  <strong style={{ color: themeTokens.colors.statusSuccess }}>{isHr ? 'HR Head Takeaway:' : (isEducation ? 'Academic Lead Takeaway:' : 'Executive Takeaway:')}</strong> {linearModel.executive_takeaway}
                </div>
              </div>
            ) : (
              <p style={{ color: 'var(--fg-muted)', fontSize: '0.85rem' }}>
                No continuous regression candidate pairs found with sufficient variance.
              </p>
            )}
          </div>

          {/* Section B: Logistic Regression & Risk Classifier */}
          <div className="eda-section-card">
            <div className="section-header">
              <h3>
                <Brain size={18} color={themeTokens.colors.statusError} />
                Logistic Regression & Binary Risk Classification
              </h3>
              <p>
                Models the probability of critical {isHr ? 'workplace' : (isEducation ? 'academic achievement' : 'performance')} outcomes ($P(Y=1|X)$) with Odds Ratios and accuracy metrics.
              </p>
            </div>

            {logisticModel ? (
              <div style={{ marginTop: '1rem' }}>
                {/* Stats Row */}
                <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(140px, 1fr))', gap: '0.75rem', marginBottom: '1rem' }}>
                  <div className="summary-chip">
                    <div className="chip-label">Target Outcome</div>
                    <div className="chip-val val-warning" style={{ fontSize: '0.8rem' }}>
                      {logisticModel.outcome_label}
                    </div>
                  </div>
                  <div className="summary-chip">
                    <div className="chip-label">Odds Ratio (OR)</div>
                    <div className="chip-val val-accent">{logisticModel.odds_ratio}x</div>
                  </div>
                  <div className="summary-chip">
                    <div className="chip-label">Odds Change (%)</div>
                    <div className="chip-val">{logisticModel.pct_change_in_odds >= 0 ? `+${logisticModel.pct_change_in_odds}%` : `${logisticModel.pct_change_in_odds}%`}</div>
                  </div>
                  <div className="summary-chip">
                    <div className="chip-label">Model Accuracy</div>
                    <div className="chip-val">{((logisticModel.accuracy || 0) * 100).toFixed(1)}%</div>
                  </div>
                  <div className="summary-chip">
                    <div className="chip-label">Pseudo-R²</div>
                    <div className="chip-val">{logisticModel.pseudo_r_squared}</div>
                  </div>
                </div>

                {/* Sigmoid Curve + Confusion Matrix Grid */}
                <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(280px, 1fr))', gap: '1rem', alignItems: 'center' }}>
                  <div>
                    <h4 style={{ color: 'var(--color-text-secondary, #334155)', fontSize: '0.85rem', marginBottom: '0.5rem' }}>
                      Probability Sigmoid Curve (P(Risk = 1 | X))
                    </h4>
                    <ReactECharts option={logisticChartOption} style={{ height: '260px', width: '100%' }} />
                  </div>

                  <div>
                    <h4 style={{ color: 'var(--color-text-secondary, #334155)', fontSize: '0.85rem', marginBottom: '0.5rem' }}>
                      2×2 Model Confusion Matrix
                    </h4>
                    <div
                      style={{
                        display: 'grid',
                        gridTemplateColumns: '1fr 1fr',
                        gap: '0.5rem',
                        background: themeTokens.chart.splitLine,
                        border: '1px solid var(--border-subtle)',
                        borderRadius: '8px',
                        padding: '0.75rem'
                      }}
                    >
                      <div style={{ background: themeTokens.colors.mint, border: '1px solid var(--color-border-strong)', borderRadius: '6px', padding: '0.6rem', textAlign: 'center' }}>
                        <div style={{ fontSize: '0.72rem', color: themeTokens.colors.statusSuccess }}>TRUE POSITIVE (TP)</div>
                        <div style={{ fontSize: '1.25rem', fontWeight: 'bold', color: themeTokens.colors.textPrimary }}>
                          {logisticModel.confusion_matrix?.true_positive}
                        </div>
                      </div>
                      <div style={{ background: themeTokens.colors.softError, border: '1px solid var(--color-border-strong)', borderRadius: '6px', padding: '0.6rem', textAlign: 'center' }}>
                        <div style={{ fontSize: '0.72rem', color: themeTokens.colors.statusError }}>FALSE POSITIVE (FP)</div>
                        <div style={{ fontSize: '1.25rem', fontWeight: 'bold', color: themeTokens.colors.textPrimary }}>
                          {logisticModel.confusion_matrix?.false_positive}
                        </div>
                      </div>
                      <div style={{ background: themeTokens.colors.softError, border: '1px solid var(--color-border-strong)', borderRadius: '6px', padding: '0.6rem', textAlign: 'center' }}>
                        <div style={{ fontSize: '0.72rem', color: themeTokens.colors.statusError }}>FALSE NEGATIVE (FN)</div>
                        <div style={{ fontSize: '1.25rem', fontWeight: 'bold', color: themeTokens.colors.textPrimary }}>
                          {logisticModel.confusion_matrix?.false_negative}
                        </div>
                      </div>
                      <div style={{ background: themeTokens.colors.mint, border: '1px solid var(--color-border-strong)', borderRadius: '6px', padding: '0.6rem', textAlign: 'center' }}>
                        <div style={{ fontSize: '0.72rem', color: themeTokens.colors.statusSuccess }}>TRUE NEGATIVE (TN)</div>
                        <div style={{ fontSize: '1.25rem', fontWeight: 'bold', color: themeTokens.colors.textPrimary }}>
                          {logisticModel.confusion_matrix?.true_negative}
                        </div>
                      </div>
                    </div>

                    <div
                      style={{
                        marginTop: '0.85rem',
                        background: themeTokens.colors.softError,
                        border: '1px solid var(--color-border-strong)',
                        borderRadius: '8px',
                        padding: '0.75rem',
                        fontSize: '0.82rem',
                        color: themeTokens.colors.textSecondary
                      }}
                    >
                      <strong style={{ color: themeTokens.colors.statusError }}>{isHr ? 'HR Intervention Point:' : (isEducation ? 'Academic Intervention Point:' : 'Target Intervention Point:')}</strong> {logisticModel.executive_takeaway}
                    </div>
                  </div>
                </div>
              </div>
            ) : (
              <p style={{ color: 'var(--fg-muted)', fontSize: '0.85rem' }}>
                No binary classification risk target could be derived from this sheet.
              </p>
            )}
          </div>
        </div>
      )}

      {/* TAB 4: VERIFIED MULTI-SHEET LINKAGES */}
      {activeTab === 'multisheet' && (
        <div className="eda-section-card">
          <div className="section-header">
            <h3>
              <GitBranch size={18} color={themeTokens.colors.gold} />
              Verified Multi-Sheet Entity Linkages & Cross-Reconciliation
            </h3>
            <p>
              Strict entity key joins (e.g. Employee ID) and verified cross-sheet correlation checks.
            </p>
          </div>

          {/* Entity Links */}
          {edaReport.cross_sheet_intelligence?.entity_links?.length > 0 ? (
            <>
              <h4 style={{ color: 'var(--color-text-secondary, #334155)', fontSize: '0.85rem', marginBottom: '0.6rem' }}>
                Discovered Entity Linkages
              </h4>
              <div className="eda-links-grid">
                {edaReport.cross_sheet_intelligence.entity_links.map((link, idx) => (
                  <div key={idx} className="link-tile">
                    <div className="link-title">
                      <span>{link.left_sheet_name}</span>
                      <ArrowRight size={14} color={themeTokens.colors.textMuted} />
                      <span>{link.right_sheet_name}</span>
                    </div>
                    <div className="link-meta">
                      <span className="badge-pill">
                        {link.left_column} ↔ {link.right_column}
                      </span>
                      <span className="badge-cardinality">{link.cardinality} cardinality</span>
                      <span className="badge-cardinality">{link.matching_keys} matches ({link.coverage_pct}%)</span>
                    </div>
                  </div>
                ))}
              </div>
            </>
          ) : (
            <p style={{ color: 'var(--color-text-secondary, #334155)', fontSize: '0.85rem' }}>
              No cross-sheet links detected for this sheet yet.
            </p>
          )}

          {/* Cross-Sheet Correlations */}
          {edaReport.cross_sheet_intelligence?.correlations?.length > 0 && (
            <>
              <h4 style={{ color: 'var(--color-text-secondary, #334155)', fontSize: '0.85rem', marginBottom: '0.6rem', marginTop: '1.25rem' }}>
                Cross-Sheet Statistical Correlations ($p &lt; 0.05$)
              </h4>
              <div className="eda-correlations-grid">
                {edaReport.cross_sheet_intelligence.correlations.map((corr, idx) => (
                  <div key={idx} className="correlation-tile">
                    <div className="corr-top-row">
                      <div className="corr-metrics">
                        {corr.left_metric} ↔ {corr.right_metric}
                      </div>
                      <span className={`corr-badge ${corr.direction === 'negative' ? 'negative' : 'positive'}`}>
                        {corr.strength.toUpperCase()} (r = {corr.pearson_r})
                      </span>
                    </div>
                    <div className="corr-sheets-label">
                      {corr.left_sheet_name} vs. {corr.right_sheet_name} · N = {corr.sample_size} entities (Join: {corr.join_key})
                    </div>
                    <div className="corr-narrative">{corr.narrative}</div>
                  </div>
                ))}
              </div>
            </>
          )}

          {/* Derived Tables Shortcut */}
          {edaReport.cross_sheet_intelligence?.derived_tables?.length > 0 && (
            <div
              style={{
                marginTop: '1.25rem',
                background: themeTokens.colors.softGold,
                border: '1px solid var(--color-border-strong)',
                borderRadius: '8px',
                padding: '0.85rem 1.1rem',
                display: 'flex',
                justifyContent: 'space-between',
                alignItems: 'center',
                flexWrap: 'wrap',
                gap: '0.75rem'
              }}
            >
              <div>
                <strong style={{ color: themeTokens.colors.gold }}>Synthesized Derived Tables Available:</strong>
                <p style={{ margin: '3px 0 0 0', fontSize: '0.82rem', color: themeTokens.colors.textSecondary }}>
                  {edaReport.cross_sheet_intelligence.derived_tables.map((d) => d.display_name).join(', ')}
                </p>
              </div>
              <button
                className="btn-secondary"
                onClick={() => {
                  const firstDerived = edaReport.cross_sheet_intelligence.derived_tables[0];
                  if (firstDerived && onExploreDerivedTable) {
                    onExploreDerivedTable(firstDerived.id);
                  }
                }}
              >
                Explore Synthesized Table →
              </button>
            </div>
          )}
        </div>
      )}

      {/* TAB 5: SCHEMA DIAGNOSTICS & CLEANING AUDIT TRAIL */}
      {activeTab === 'diagnostics' && (
        <div style={{ display: 'flex', flexDirection: 'column', gap: '1.25rem' }}>
          {/* Column Diagnostics Table */}
          <div className="eda-section-card">
            <div className="section-header">
              <h3>
                <Table size={18} color={themeTokens.colors.gold} />
                Column Profiles, Null Rates & Imputation Strategies
              </h3>
              <p>
                Null distribution, unique cardinality, interquartile range (IQR) bounds, and outlier detection.
              </p>
            </div>

            <div className="eda-table-container">
              <table className="eda-data-grid">
                <thead>
                  <tr>
                    <th>Column Name</th>
                    <th>Type</th>
                    <th>Missing Values</th>
                    <th>Imputation Strategy</th>
                    <th>Distinct Values</th>
                    <th>Distribution (Min / Max / Mean / Median)</th>
                    <th>Outliers Flagged</th>
                  </tr>
                </thead>
                <tbody>
                  {Object.values(edaReport.column_diagnostics || {}).map((col, idx) => (
                    <tr key={idx}>
                      <td>
                        <strong>{col.column}</strong>
                      </td>
                      <td className="type-cell">
                        <span
                          className={`col-type-badge badge-${(col.inferred_type || 'categorical').split('_')[0]}`}
                          style={{
                            padding: '3px 8px',
                            borderRadius: '5px',
                            fontWeight: 700,
                            fontSize: '0.74rem',
                            display: 'inline-block'
                          }}
                        >
                          {col.inferred_type.replace('_', ' ')}
                        </span>
                      </td>
                      <td className="stat-cell">
                        {col.null_count > 0 ? (
                          <span style={{ color: '#f43f5e', fontWeight: 700 }}>
                            ⚠️ {col.null_count} ({col.null_percentage}%)
                          </span>
                        ) : (
                          <span style={{ color: '#10b981', fontWeight: 600 }}>
                            ✓ 0 (0.0%)
                          </span>
                        )}
                      </td>
                      <td className="stat-cell">
                        {col.imputation ? (
                          <div style={{ fontSize: '0.82rem', color: 'var(--brand-300)' }}>
                            <span style={{ padding: '2px 6px', background: themeTokens.colors.softBlue, borderRadius: '4px', fontWeight: 600 }}>
                              {col.imputation.strategy.toUpperCase()} → {String(col.imputation.recommended_value)}
                            </span>
                            <div style={{ fontSize: '0.74rem', opacity: 0.8, marginTop: '4px', maxWidth: '250px', lineHeight: 1.25 }}>
                              {col.imputation.rationale}
                            </div>
                          </div>
                        ) : (
                          <span style={{ color: themeTokens.colors.statusSuccess, fontSize: '0.82rem' }}>✓ Complete</span>
                        )}
                      </td>
                      <td className="stat-cell">{col.distinct_count}</td>
                      <td className="stat-cell">
                        {col.min != null
                          ? `${col.min} / ${col.max} · μ: ${col.mean} (med: ${col.median})`
                          : '—'}
                      </td>
                      <td>
                        {col.outlier_count > 0 ? (
                          <span style={{ color: themeTokens.colors.statusError, fontWeight: 600 }}>
                            ⚠️ {col.outlier_count} outliers
                          </span>
                        ) : (
                          <span style={{ color: themeTokens.colors.statusSuccess }}>✓ Normal</span>
                        )}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>

          {/* Transformation Audit Trail */}
          <div className="eda-section-card">
            <div className="section-header">
              <h3>
                <ShieldCheck size={18} color={themeTokens.colors.statusSuccess} />
                Data Cleansing & Normalization Audit Trail
              </h3>
              <p>
                Source-preserving transformations performed during the EDA phase prior to downstream modeling.
              </p>
            </div>

            <div className="eda-table-container">
              <table className="eda-data-grid">
                <thead>
                  <tr>
                    <th>Target Column</th>
                    <th>Inferred Semantic Type</th>
                    <th>Standardized Format / Unit</th>
                    <th>Cells Coerced</th>
                    <th>Transformation Rule Applied</th>
                  </tr>
                </thead>
                <tbody>
                  {edaReport.transformations_log && edaReport.transformations_log.length > 0 ? (
                    edaReport.transformations_log.map((t, idx) => {
                      const diag = edaReport.column_diagnostics?.[t.column] || {};
                      return (
                        <tr key={idx}>
                          <td>
                            <strong>{t.column}</strong>
                          </td>
                          <td className="type-cell">{t.inferred_type}</td>
                          <td>{diag.unit ? `Unit: ${diag.unit}` : 'Standard numeric / string'}</td>
                          <td className="stat-cell">{t.cells_transformed} cells</td>
                          <td>{t.transformation}</td>
                        </tr>
                      );
                    })
                  ) : (
                    <tr>
                      <td colSpan={5} style={{ textAlign: 'center', color: themeTokens.colors.textMuted, padding: '1rem' }}>
                        All column values in this sheet are already in canonical format; no type coercions required.
                      </td>
                    </tr>
                  )}
                </tbody>
              </table>
            </div>
          </div>
        </div>
      )}

      {/* TAB: GROUP-BY & DIMENSIONAL BREAKDOWNS */}
      {activeTab === 'groupings' && (
        <div style={{ display: 'flex', flexDirection: 'column', gap: '1.25rem' }}>
          {/* Section: Dimension & Metric Selection */}
          <div className="eda-section-card">
            <div className="section-header" style={{ marginBottom: '1rem' }}>
              <h3>
                <Layers size={18} color={themeTokens.colors.gold} />
                Dimensional Segmentation & Group-By Projections
              </h3>
              <p>
                Multi-dimensional aggregations grouping quantitative measures by categorical domains and date-derived temporal cycles (such as Day of the Week, Departments, or Education levels).
              </p>
            </div>

            {/* Pill Pickers */}
            <div style={{ display: 'flex', flexWrap: 'wrap', gap: '1.5rem', marginBottom: '1.25rem' }}>
              <div>
                <div style={{ fontSize: '0.75rem', fontWeight: 600, color: 'var(--fg-muted)', textTransform: 'uppercase', marginBottom: '0.4rem', letterSpacing: '0.04em' }}>
                  Group-By Dimension
                </div>
                <div style={{ display: 'flex', flexWrap: 'wrap', gap: '0.4rem' }}>
                  {availableGroupDims.map((dim) => {
                    const isSelected = dim === currentGroupDim;
                    const label = dim.replace(/_/g, ' ').replace(/\b\w/g, (c) => c.toUpperCase());
                    return (
                      <button
                        key={dim}
                        type="button"
                        onClick={() => setSelectedGroupDim(dim)}
                        style={{
                          padding: '0.35rem 0.75rem',
                          borderRadius: '6px',
                          border: isSelected ? `1px solid ${themeTokens.colors.gold}` : '1px solid var(--border-subtle)',
                          background: isSelected ? themeTokens.colors.softGold : 'var(--bg-surface)',
                          color: isSelected ? themeTokens.colors.gold : 'var(--fg-secondary)',
                          fontSize: '0.8rem',
                          fontWeight: isSelected ? 600 : 400,
                          cursor: 'pointer',
                          transition: 'all 0.15s ease'
                        }}
                      >
                        {label}
                      </button>
                    );
                  })}
                </div>
              </div>

              <div>
                <div style={{ fontSize: '0.75rem', fontWeight: 600, color: 'var(--fg-muted)', textTransform: 'uppercase', marginBottom: '0.4rem', letterSpacing: '0.04em' }}>
                  Aggregated Metric / Measure
                </div>
                <div style={{ display: 'flex', flexWrap: 'wrap', gap: '0.4rem' }}>
                  {availableGroupMeasures.map((meas) => {
                    const isSelected = meas === currentGroupMeas;
                    const label = meas.replace(/_/g, ' ').replace(/\b\w/g, (c) => c.toUpperCase());
                    return (
                      <button
                        key={meas}
                        type="button"
                        onClick={() => setSelectedGroupMeas(meas)}
                        style={{
                          padding: '0.35rem 0.75rem',
                          borderRadius: '6px',
                          border: isSelected ? `1px solid ${themeTokens.colors.brandBlue}` : '1px solid var(--border-subtle)',
                          background: isSelected ? themeTokens.colors.softBlue : 'var(--bg-surface)',
                          color: isSelected ? themeTokens.colors.brandBlue : 'var(--fg-secondary)',
                          fontSize: '0.8rem',
                          fontWeight: isSelected ? 600 : 400,
                          cursor: 'pointer',
                          transition: 'all 0.15s ease'
                        }}
                      >
                        {label}
                      </button>
                    );
                  })}
                </div>
              </div>
            </div>

            {/* Key Disparity / Pattern Insight Banner */}
            {currentBreakdown && (
              <div
                style={{
                  background: themeTokens.colors.softGold,
                  border: '1px solid var(--color-border-strong)',
                  borderRadius: '8px',
                  padding: '1rem',
                  display: 'flex',
                  flexDirection: 'column',
                  gap: '0.75rem',
                  marginBottom: '1rem'
                }}
              >
                <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                  <Sparkles size={18} color={themeTokens.colors.gold} />
                  <span style={{ fontSize: '0.9rem', fontWeight: 700, color: themeTokens.colors.textPrimary }}>
                    Executive Dimensional Pattern & Disparity Callout
                  </span>
                </div>
                <div style={{ fontSize: '0.88rem', color: themeTokens.colors.textSecondary, lineHeight: '1.45' }}>
                  {currentBreakdown.insight}
                </div>

                <div style={{ display: 'flex', flexWrap: 'wrap', gap: '0.75rem', marginTop: '0.25rem' }}>
                  <div style={{ background: themeTokens.colors.surface, padding: '0.35rem 0.7rem', borderRadius: '5px', fontSize: '0.78rem' }}>
                    <span style={{ color: themeTokens.colors.textMuted }}>🏆 Top Segment: </span>
                    <strong style={{ color: themeTokens.colors.gold }}>{currentBreakdown.top_category}</strong>{' '}
                    <span style={{ color: themeTokens.colors.textMuted }}>(Avg: {currentBreakdown.top_mean})</span>
                  </div>
                  <div style={{ background: themeTokens.colors.surface, padding: '0.35rem 0.7rem', borderRadius: '5px', fontSize: '0.78rem' }}>
                    <span style={{ color: themeTokens.colors.textMuted }}>🔻 Lagging Segment: </span>
                    <strong style={{ color: themeTokens.colors.statusError }}>{currentBreakdown.bottom_category}</strong>{' '}
                    <span style={{ color: themeTokens.colors.textMuted }}>(Avg: {currentBreakdown.bottom_mean})</span>
                  </div>
                  <div style={{ background: themeTokens.colors.surface, padding: '0.35rem 0.7rem', borderRadius: '5px', fontSize: '0.78rem' }}>
                    <span style={{ color: themeTokens.colors.textMuted }}>📈 Segment Lift / Gap: </span>
                    <strong style={{ color: themeTokens.colors.statusSuccess }}>+{currentBreakdown.disparity_pct}%</strong>
                  </div>
                  <div style={{ background: themeTokens.colors.surface, padding: '0.35rem 0.7rem', borderRadius: '5px', fontSize: '0.78rem' }}>
                    <span style={{ color: themeTokens.colors.textMuted }}>📊 Overall Average: </span>
                    <strong style={{ color: themeTokens.colors.textPrimary }}>{currentBreakdown.overall_mean}</strong>
                  </div>
                </div>
              </div>
            )}

            {/* Visual Charts Grid (Bar + Donut) */}
            {currentBreakdown ? (
              <div
                style={{
                  display: 'grid',
                  gridTemplateColumns: 'repeat(auto-fit, minmax(360px, 1fr))',
                  gap: '1rem',
                  marginTop: '1rem'
                }}
              >
                {/* Chart 1: Bar Chart */}
                <div
                  style={{
                    background: 'var(--bg-surface-elevated, rgba(255,255,255,0.02))',
                    border: '1px solid var(--border-subtle)',
                    borderRadius: '8px',
                    padding: '1rem'
                  }}
                >
                  <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '0.5rem' }}>
                    <h4 style={{ fontSize: '0.85rem', fontWeight: 600, color: 'var(--fg-secondary)' }}>
                      Mean {currentBreakdown.measure_label} by {currentBreakdown.dimension_label}
                    </h4>
                    <span style={{ fontSize: '0.75rem', color: themeTokens.colors.gold }}>Highlighted: Top Segment</span>
                  </div>
                  {groupByBarOption && (
                    <ReactECharts option={groupByBarOption} style={{ height: '300px', width: '100%' }} />
                  )}
                </div>

                {/* Chart 2: Donut Distribution Chart */}
                <div
                  style={{
                    background: 'var(--bg-surface-elevated, rgba(255,255,255,0.02))',
                    border: '1px solid var(--border-subtle)',
                    borderRadius: '8px',
                    padding: '1rem'
                  }}
                >
                  <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '0.5rem' }}>
                    <h4 style={{ fontSize: '0.85rem', fontWeight: 600, color: 'var(--fg-secondary)' }}>
                      Record Share Distribution across {currentBreakdown.dimension_label}
                    </h4>
                    <span style={{ fontSize: '0.75rem', color: themeTokens.colors.textMuted }}>Total: {currentBreakdown.total_records} rows</span>
                  </div>
                  {groupByDonutOption && (
                    <ReactECharts option={groupByDonutOption} style={{ height: '300px', width: '100%' }} />
                  )}
                </div>
              </div>
            ) : (
              <p style={{ color: 'var(--fg-muted)', fontSize: '0.85rem', marginTop: '1rem' }}>
                Select a valid dimension and measure above to view group-by aggregations.
              </p>
            )}

            {/* Rollup Breakdown Data Grid */}
            {currentBreakdown && currentBreakdown.table_rows && (
              <div style={{ marginTop: '1.5rem' }}>
                <h4 style={{ fontSize: '0.85rem', fontWeight: 600, color: 'var(--fg-secondary)', marginBottom: '0.6rem' }}>
                  Tabular Rollup Breakdown ({currentBreakdown.dimension_label} × {currentBreakdown.measure_label})
                </h4>
                <div className="eda-table-container">
                  <table className="eda-data-grid">
                    <thead>
                      <tr>
                        <th>{currentBreakdown.dimension_label} Category</th>
                        <th style={{ textAlign: 'right' }}>Record Count</th>
                        <th style={{ textAlign: 'right' }}>Sample Share</th>
                        <th style={{ textAlign: 'right' }}>Mean {currentBreakdown.measure_label}</th>
                        <th style={{ textAlign: 'right' }}>Total Sum</th>
                        <th style={{ textAlign: 'right' }}>Metric Share</th>
                      </tr>
                    </thead>
                    <tbody>
                      {currentBreakdown.table_rows.map((row, idx) => {
                        const isTop = row.category === currentBreakdown.top_category;
                        return (
                          <tr key={idx} style={isTop ? { background: themeTokens.colors.softGold } : undefined}>
                            <td>
                              <strong>{row.category}</strong>
                              {isTop && (
                                <span style={{ marginLeft: '6px', fontSize: '0.7rem', color: themeTokens.colors.gold, fontWeight: 600 }}>
                                  [Top Cohort]
                                </span>
                              )}
                            </td>
                            <td className="stat-cell" style={{ textAlign: 'right' }}>{row.count}</td>
                            <td style={{ textAlign: 'right' }}>{row.share_records_pct}%</td>
                            <td className="stat-cell" style={{ textAlign: 'right', fontWeight: 700, color: isTop ? themeTokens.colors.gold : 'inherit' }}>
                              {row.mean}
                            </td>
                            <td className="stat-cell" style={{ textAlign: 'right' }}>{row.total}</td>
                            <td style={{ textAlign: 'right' }}>{row.share_measure_pct}%</td>
                          </tr>
                        );
                      })}
                    </tbody>
                  </table>
                </div>
              </div>
            )}
          </div>

          {/* Section: Discovered Sheet-Level Dimensional Insights */}
          {groupByAnalytics.insights && groupByAnalytics.insights.length > 0 && (
            <div className="eda-section-card">
              <div className="section-header">
                <h3>
                  <TrendingUp size={18} color={themeTokens.colors.statusSuccess} />
                  All Discovered Cross-Dimensional Patterns & Cohort Findings
                </h3>
                <p>
                  Automated statistical findings across all discrete categories and temporal day-of-week cycles for this sheet.
                </p>
              </div>
              <ul style={{ margin: '0.75rem 0 0 0', paddingLeft: '1.25rem', color: themeTokens.colors.textSecondary, fontSize: '0.85rem', lineHeight: '1.6' }}>
                {groupByAnalytics.insights.map((ins, idx) => (
                  <li key={idx} style={{ marginBottom: '0.4rem' }}>{ins}</li>
                ))}
              </ul>
            </div>
          )}
        </div>
      )}
    </div>
  );
}
