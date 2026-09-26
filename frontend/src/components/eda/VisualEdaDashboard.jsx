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

export default function VisualEdaDashboard({
  edaReport,
  loadingEda,
  isRerunningEda,
  onRerunEda,
  onExploreDerivedTable
}) {
  const [activeTab, setActiveTab] = useState('visuals'); // 'visuals' | 'temporal' | 'predictive' | 'multisheet' | 'diagnostics'
  const [selectedMetric, setSelectedMetric] = useState(null);
  const [selectedLinearIndex, setSelectedLinearIndex] = useState(0);

  const visualAnalytics = edaReport?.visual_analytics || {};
  const correlationMatrix = visualAnalytics.correlation_matrix || { metrics: [], pairs: [], matrix: [] };
  const metricDistributions = visualAnalytics.metric_distributions || {};
  const temporalAnalysis = visualAnalytics.temporal_analysis || { has_temporal_data: false, timeline_series: [] };
  const predictiveModeling = visualAnalytics.predictive_modeling || { linear_models: [], logistic_models: [] };

  // Set initial selected metric
  const availableMetrics = correlationMatrix.metrics || [];
  const currentMetric = selectedMetric || availableMetrics[0] || '';
  const currentDist = metricDistributions[currentMetric];

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
      tooltip: {
        position: 'top',
        backgroundColor: '#1c1815',
        borderColor: '#524940',
        textStyle: { color: '#fff9f2', fontSize: 12 },
        formatter: (params) => {
          const [colIdx, rowIdx, val] = params.data;
          const xName = metrics[colIdx];
          const yName = metrics[rowIdx];
          if (xName === yName) return `<b>${xName}</b> (Self Identity: 1.0)`;
          if (val == null) return `<b>${xName} × ${yName}</b><br/>Insufficient variance`;

          const dir = val > 0 ? 'Positive' : 'Negative';
          const strength = Math.abs(val) >= 0.7 ? 'Strong' : Math.abs(val) >= 0.35 ? 'Moderate' : 'Mild';
          const color = val >= 0 ? '#2ed573' : '#ff6b81';
          return `
            <div style="font-weight:600;margin-bottom:4px;color:#c9bdb0;">${xName} ↔ ${yName}</div>
            <div style="font-size:13px;font-weight:700;color:${color};">
              ${strength} ${dir} Correlation: ${val > 0 ? '+' : ''}${val}
            </div>
            <div style="font-size:11px;color:#a89f94;margin-top:4px;">Click cell to inspect pair relationship</div>
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
          color: '#c9bdb0',
          rotate: 35,
          fontSize: 10,
          interval: 0,
          formatter: (v) => v.length > 14 ? v.slice(0, 13) + '…' : v
        },
        axisLine: { lineStyle: { color: '#524940' } }
      },
      yAxis: {
        type: 'category',
        data: metrics,
        splitArea: { show: true },
        axisLabel: {
          color: '#c9bdb0',
          fontSize: 10,
          interval: 0,
          formatter: (v) => v.length > 14 ? v.slice(0, 13) + '…' : v
        },
        axisLine: { lineStyle: { color: '#524940' } }
      },
      visualMap: {
        min: -1,
        max: 1,
        calculable: true,
        orient: 'horizontal',
        left: 'center',
        bottom: '0%',
        text: ['+1.0 (Positive)', '-1.0 (Negative)'],
        textStyle: { color: '#c9bdb0', fontSize: 11 },
        inRange: {
          color: ['#ff6b81', '#3d362f', '#2ed573']
        }
      },
      series: [
        {
          type: 'heatmap',
          data: data,
          label: {
            show: metrics.length <= 8,
            color: '#fff',
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
  }, [correlationMatrix]);

  // 2. Metric Distribution Histogram Option
  const distributionOption = useMemo(() => {
    if (!currentDist || !currentDist.bins?.length) return null;
    const bins = currentDist.bins;

    return {
      backgroundColor: 'transparent',
      tooltip: {
        trigger: 'axis',
        axisPointer: { type: 'shadow' },
        backgroundColor: '#1c1815',
        borderColor: '#524940',
        textStyle: { color: '#fff9f2', fontSize: 12 },
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
        axisLabel: { color: '#c9bdb0', rotate: 25, fontSize: 10 },
        axisLine: { lineStyle: { color: '#524940' } }
      },
      yAxis: {
        type: 'value',
        axisLabel: { color: '#c9bdb0', fontSize: 11 },
        splitLine: { lineStyle: { color: 'rgba(255, 255, 255, 0.05)' } }
      },
      series: [
        {
          name: 'Frequency',
          type: 'bar',
          data: bins.map((b) => b.count),
          itemStyle: {
            color: '#ffb089',
            borderRadius: [4, 4, 0, 0]
          },
          markLine: {
            symbol: 'none',
            data: [
              {
                xAxis: bins.findIndex((b) => currentDist.median >= b.bin_start && currentDist.median <= b.bin_end),
                lineStyle: { color: '#2ed573', type: 'dashed', width: 2 },
                label: { formatter: `Median: ${currentDist.median}`, color: '#2ed573', position: 'end' }
              }
            ]
          }
        }
      ]
    };
  }, [currentDist]);

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
      tooltip: {
        trigger: 'axis',
        backgroundColor: '#1c1815',
        borderColor: '#524940',
        textStyle: { color: '#fff9f2', fontSize: 12 },
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
        textStyle: { color: '#c9bdb0', fontSize: 11 },
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
        axisLabel: { color: '#c9bdb0', rotate: 20, fontSize: 11 },
        axisLine: { lineStyle: { color: '#524940' } }
      },
      yAxis: [
        {
          type: 'value',
          name: 'Days',
          nameTextStyle: { color: '#a89f94', fontSize: 10 },
          axisLabel: { color: '#c9bdb0', fontSize: 11 },
          splitLine: { lineStyle: { color: 'rgba(255, 255, 255, 0.05)' } }
        },
        {
          type: 'value',
          name: 'Rate (%)',
          nameTextStyle: { color: '#a89f94', fontSize: 10 },
          axisLabel: { color: '#c9bdb0', fontSize: 11, formatter: '{value}%' },
          splitLine: { show: false }
        }
      ],
      series: [
        {
          name: 'Avg Attendance (Days)',
          type: 'bar',
          data: avgAtt,
          itemStyle: { color: '#2ed573', borderRadius: [4, 4, 0, 0] }
        },
        {
          name: 'Avg Approved Leaves',
          type: 'bar',
          data: avgLeaves,
          itemStyle: { color: '#ffb089', borderRadius: [4, 4, 0, 0] }
        },
        {
          name: 'Leave Utilization Rate (%)',
          type: 'line',
          yAxisIndex: 1,
          data: leaveRates,
          symbolSize: 8,
          itemStyle: { color: '#ff6b81' },
          lineStyle: { width: 3 }
        }
      ]
    };
  }, [temporalAnalysis]);

  // 4. Linear Regression Scatter Option
  const linearModel = predictiveModeling.linear_models?.[selectedLinearIndex] || predictiveModeling.linear_models?.[0];
  const linearChartOption = useMemo(() => {
    if (!linearModel) return null;
    const scatter = (linearModel.scatter_points || []).map((p) => [p.x, p.y]);
    const trendline = (linearModel.trendline || []).map((p) => [p.x, p.y]);

    return {
      backgroundColor: 'transparent',
      tooltip: {
        trigger: 'item',
        backgroundColor: '#1c1815',
        borderColor: '#524940',
        textStyle: { color: '#fff9f2', fontSize: 12 },
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
        nameTextStyle: { color: '#c9bdb0', fontSize: 11 },
        axisLabel: { color: '#c9bdb0', fontSize: 11 },
        splitLine: { lineStyle: { color: 'rgba(255, 255, 255, 0.05)' } }
      },
      yAxis: {
        type: 'value',
        name: linearModel.y_variable,
        nameTextStyle: { color: '#c9bdb0', fontSize: 11 },
        axisLabel: { color: '#c9bdb0', fontSize: 11 },
        splitLine: { lineStyle: { color: 'rgba(255, 255, 255, 0.05)' } }
      },
      series: [
        {
          name: 'Observations',
          type: 'scatter',
          data: scatter,
          symbolSize: 6,
          itemStyle: {
            color: 'rgba(255, 176, 137, 0.65)',
            borderColor: '#ffb089'
          }
        },
        {
          name: 'OLS Trendline',
          type: 'line',
          data: trendline,
          showSymbol: false,
          lineStyle: { color: '#2ed573', width: 3 },
          markPoint: {
            data: [
              {
                coord: trendline[1],
                value: `R² = ${linearModel.r_squared}`,
                itemStyle: { color: '#2ed573' },
                label: { color: '#1c1815', fontWeight: 'bold' }
              }
            ]
          }
        }
      ]
    };
  }, [linearModel]);

  // 5. Logistic Regression Sigmoid Probability Option
  const logisticModel = predictiveModeling.logistic_models?.[0];
  const logisticChartOption = useMemo(() => {
    if (!logisticModel || !logisticModel.sigmoid_curve?.length) return null;
    const curveData = logisticModel.sigmoid_curve.map((pt) => [pt.x, pt.probability]);

    return {
      backgroundColor: 'transparent',
      tooltip: {
        trigger: 'axis',
        backgroundColor: '#1c1815',
        borderColor: '#524940',
        textStyle: { color: '#fff9f2', fontSize: 12 },
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
        nameTextStyle: { color: '#c9bdb0', fontSize: 11 },
        axisLabel: { color: '#c9bdb0', fontSize: 11 },
        splitLine: { lineStyle: { color: 'rgba(255, 255, 255, 0.05)' } }
      },
      yAxis: {
        type: 'value',
        min: 0,
        max: 1.0,
        name: 'P(High Risk)',
        nameTextStyle: { color: '#c9bdb0', fontSize: 11 },
        axisLabel: { color: '#c9bdb0', fontSize: 11, formatter: (v) => `${(v * 100).toFixed(0)}%` },
        splitLine: { lineStyle: { color: 'rgba(255, 255, 255, 0.05)' } }
      },
      series: [
        {
          name: 'Risk Probability Sigmoid',
          type: 'line',
          smooth: true,
          data: curveData,
          showSymbol: false,
          lineStyle: { color: '#ff6b81', width: 3 },
          areaStyle: {
            color: {
              type: 'linear',
              x: 0,
              y: 0,
              x2: 0,
              y2: 1,
              colorStops: [
                { offset: 0, color: 'rgba(255, 107, 129, 0.35)' },
                { offset: 1, color: 'rgba(255, 107, 129, 0.02)' }
              ]
            }
          },
          markLine: {
            symbol: 'none',
            data: [
              {
                yAxis: 0.5,
                lineStyle: { color: '#ffb089', type: 'dashed' },
                label: { formatter: '50% Threshold', color: '#ffb089', position: 'end' }
              }
            ]
          }
        }
      ]
    };
  }, [logisticModel]);

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
            <h3>{edaReport.sheet_name}</h3>
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
          <div className="summary-chip">
            <div className="chip-label">Normalized Cells</div>
            <div className="chip-val val-accent">{edaReport.summary?.total_normalized_cells}</div>
          </div>
          <div className="summary-chip">
            <div className="chip-label">Null Cells</div>
            <div className="chip-val">{edaReport.summary?.total_null_cells}</div>
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

      {/* 2. Plain-Language Recommendations & Domain Points */}
      {edaReport.recommendations && edaReport.recommendations.length > 0 && (
        <div className="eda-recs-card">
          <h4>
            <Sparkles size={16} />
            HR Executive Analytical Insights & Next Steps
          </h4>
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
                <Activity size={18} color="#ffb089" />
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
                <h4 style={{ color: '#c9bdb0', fontSize: '0.85rem', marginBottom: '0.6rem' }}>
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
                  <BarChart2 size={18} color="#2ed573" />
                  Metric Distribution Histogram & Outlier Inspector
                </h3>
                <p>
                  10-bin frequency distribution, median markers, and IQR outlier boundaries.
                </p>
              </div>

              {availableMetrics.length > 0 && (
                <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                  <label style={{ fontSize: '0.8rem', color: 'var(--fg-secondary)' }}>Select Metric:</label>
                  <select
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
              <Clock size={18} color="#ffb089" />
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
                    background: 'rgba(255, 176, 137, 0.08)',
                    border: '1px solid rgba(255, 176, 137, 0.25)',
                    borderRadius: '8px',
                    padding: '0.85rem 1.1rem'
                  }}
                >
                  <strong style={{ color: '#ffb089', fontSize: '0.9rem' }}>HR Temporal Findings:</strong>
                  <ul style={{ margin: '6px 0 0 1.25rem', padding: 0, fontSize: '0.85rem', color: '#e5dacd' }}>
                    {temporalAnalysis.insights.map((ins, idx) => (
                      <li key={idx} style={{ marginBottom: '4px' }}>{ins}</li>
                    ))}
                  </ul>
                </div>
              )}

              {/* Temporal Correlations Grid */}
              {temporalAnalysis.temporal_correlations?.length > 0 && (
                <div style={{ marginTop: '1.25rem' }}>
                  <h4 style={{ color: '#c9bdb0', fontSize: '0.85rem', marginBottom: '0.6rem' }}>
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
                  <TrendingUp size={18} color="#2ed573" />
                  Linear Regression Studio (Ordinary Least Squares)
                </h3>
                <p>
                  Predict continuous workforce metrics with slope ($\beta$), confidence bounds, and goodness of fit ($R^2$).
                </p>
              </div>

              {predictiveModeling.linear_models?.length > 1 && (
                <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                  <label style={{ fontSize: '0.8rem', color: 'var(--fg-secondary)' }}>Select Model:</label>
                  <select
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
                    background: 'rgba(46, 213, 115, 0.08)',
                    border: '1px solid rgba(46, 213, 115, 0.25)',
                    borderRadius: '8px',
                    padding: '0.75rem 1rem',
                    fontSize: '0.85rem',
                    color: '#e5dacd'
                  }}
                >
                  <strong style={{ color: '#2ed573' }}>HR Head Takeaway:</strong> {linearModel.executive_takeaway}
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
                <Brain size={18} color="#ff6b81" />
                Logistic Regression & Binary Risk Classification
              </h3>
              <p>
                Models the probability of critical workplace outcomes ($P(Y=1|X)$) with Odds Ratios and accuracy metrics.
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
                    <h4 style={{ color: '#c9bdb0', fontSize: '0.85rem', marginBottom: '0.5rem' }}>
                      Probability Sigmoid Curve (P(Risk = 1 | X))
                    </h4>
                    <ReactECharts option={logisticChartOption} style={{ height: '260px', width: '100%' }} />
                  </div>

                  <div>
                    <h4 style={{ color: '#c9bdb0', fontSize: '0.85rem', marginBottom: '0.5rem' }}>
                      2×2 Model Confusion Matrix
                    </h4>
                    <div
                      style={{
                        display: 'grid',
                        gridTemplateColumns: '1fr 1fr',
                        gap: '0.5rem',
                        background: 'rgba(255, 255, 255, 0.02)',
                        border: '1px solid var(--border-subtle)',
                        borderRadius: '8px',
                        padding: '0.75rem'
                      }}
                    >
                      <div style={{ background: 'rgba(46, 213, 115, 0.12)', border: '1px solid rgba(46, 213, 115, 0.3)', borderRadius: '6px', padding: '0.6rem', textAlign: 'center' }}>
                        <div style={{ fontSize: '0.72rem', color: '#2ed573' }}>TRUE POSITIVE (TP)</div>
                        <div style={{ fontSize: '1.25rem', fontWeight: 'bold', color: '#fff9f2' }}>
                          {logisticModel.confusion_matrix?.true_positive}
                        </div>
                      </div>
                      <div style={{ background: 'rgba(255, 107, 129, 0.1)', border: '1px solid rgba(255, 107, 129, 0.25)', borderRadius: '6px', padding: '0.6rem', textAlign: 'center' }}>
                        <div style={{ fontSize: '0.72rem', color: '#ff6b81' }}>FALSE POSITIVE (FP)</div>
                        <div style={{ fontSize: '1.25rem', fontWeight: 'bold', color: '#fff9f2' }}>
                          {logisticModel.confusion_matrix?.false_positive}
                        </div>
                      </div>
                      <div style={{ background: 'rgba(255, 107, 129, 0.1)', border: '1px solid rgba(255, 107, 129, 0.25)', borderRadius: '6px', padding: '0.6rem', textAlign: 'center' }}>
                        <div style={{ fontSize: '0.72rem', color: '#ff6b81' }}>FALSE NEGATIVE (FN)</div>
                        <div style={{ fontSize: '1.25rem', fontWeight: 'bold', color: '#fff9f2' }}>
                          {logisticModel.confusion_matrix?.false_negative}
                        </div>
                      </div>
                      <div style={{ background: 'rgba(46, 213, 115, 0.12)', border: '1px solid rgba(46, 213, 115, 0.3)', borderRadius: '6px', padding: '0.6rem', textAlign: 'center' }}>
                        <div style={{ fontSize: '0.72rem', color: '#2ed573' }}>TRUE NEGATIVE (TN)</div>
                        <div style={{ fontSize: '1.25rem', fontWeight: 'bold', color: '#fff9f2' }}>
                          {logisticModel.confusion_matrix?.true_negative}
                        </div>
                      </div>
                    </div>

                    <div
                      style={{
                        marginTop: '0.85rem',
                        background: 'rgba(255, 107, 129, 0.08)',
                        border: '1px solid rgba(255, 107, 129, 0.25)',
                        borderRadius: '8px',
                        padding: '0.75rem',
                        fontSize: '0.82rem',
                        color: '#e5dacd'
                      }}
                    >
                      <strong style={{ color: '#ff6b81' }}>HR Intervention Point:</strong> {logisticModel.executive_takeaway}
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
              <GitBranch size={18} color="#ffb089" />
              Verified Multi-Sheet Entity Linkages & Cross-Reconciliation
            </h3>
            <p>
              Strict entity key joins (e.g. Employee ID) and verified cross-sheet correlation checks.
            </p>
          </div>

          {/* Entity Links */}
          {edaReport.cross_sheet_intelligence?.entity_links?.length > 0 ? (
            <>
              <h4 style={{ color: '#c9bdb0', fontSize: '0.85rem', marginBottom: '0.6rem' }}>
                Discovered Entity Linkages
              </h4>
              <div className="eda-links-grid">
                {edaReport.cross_sheet_intelligence.entity_links.map((link, idx) => (
                  <div key={idx} className="link-tile">
                    <div className="link-title">
                      <span>{link.left_sheet_name}</span>
                      <ArrowRight size={14} color="#a89f94" />
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
            <p style={{ color: '#a89f94', fontSize: '0.85rem' }}>
              No cross-sheet links detected for this sheet yet.
            </p>
          )}

          {/* Cross-Sheet Correlations */}
          {edaReport.cross_sheet_intelligence?.correlations?.length > 0 && (
            <>
              <h4 style={{ color: '#c9bdb0', fontSize: '0.85rem', marginBottom: '0.6rem', marginTop: '1.25rem' }}>
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
                background: 'rgba(255, 176, 137, 0.08)',
                border: '1px solid rgba(255, 176, 137, 0.25)',
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
                <strong style={{ color: '#ffb089' }}>Synthesized Derived Tables Available:</strong>
                <p style={{ margin: '3px 0 0 0', fontSize: '0.82rem', color: '#e5dacd' }}>
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
                <Table size={18} color="#ffb089" />
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
                      <td className="type-cell">{col.inferred_type}</td>
                      <td className="stat-cell">
                        {col.null_count} ({col.null_percentage}%)
                      </td>
                      <td className="stat-cell">
                        {col.imputation ? (
                          <div style={{ fontSize: '0.82rem', color: 'var(--brand-300)' }}>
                            <span style={{ padding: '2px 6px', background: 'rgba(99, 102, 241, 0.15)', borderRadius: '4px', fontWeight: 600 }}>
                              {col.imputation.strategy.toUpperCase()} → {String(col.imputation.recommended_value)}
                            </span>
                            <div style={{ fontSize: '0.74rem', opacity: 0.8, marginTop: '4px', maxWidth: '250px', lineHeight: 1.25 }}>
                              {col.imputation.rationale}
                            </div>
                          </div>
                        ) : (
                          <span style={{ color: '#2ed573', fontSize: '0.82rem' }}>✓ Complete</span>
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
                          <span style={{ color: '#ff6b81', fontWeight: 600 }}>
                            ⚠️ {col.outlier_count} outliers
                          </span>
                        ) : (
                          <span style={{ color: '#2ed573' }}>✓ Normal</span>
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
                <ShieldCheck size={18} color="#2ed573" />
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
                      <td colSpan={5} style={{ textAlign: 'center', color: '#a89f94', padding: '1rem' }}>
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
    </div>
  );
}
