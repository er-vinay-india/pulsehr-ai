import React from 'react';
import { ExternalLink } from 'lucide-react';
import { formatDisplayLabel } from '../../utils/displayFormatters';

export default function ChartEvidenceHeader({ visualization, onInvestigate }) {
  const metric = visualization.measured_metric || visualization.title;
  const metricDisplay = visualization.metric_label || formatDisplayLabel(metric);
  const unit = visualization.unit || 'units';
  const pop = visualization.population || 'All Active Records';
  const sources = visualization.source_sheets || [visualization.sheet_badge];
  const coverage = visualization.coverage_pct != null ? `${visualization.coverage_pct}%` : '100%';
  const missing = visualization.missing_records || 0;

  return (
    <div className="chart-evidence-header-bar">
      <div className="evidence-meta-row">
        <div className="evidence-meta-pill" title={`Source field: ${metric}`}>
          <span className="meta-label">Measuring:</span>
          <span className="meta-value">{metricDisplay} ({unit})</span>
        </div>
        <div className="evidence-meta-pill" title="Population Cohort and Active Scope">
          <span className="meta-label">Population:</span>
          <span className="meta-value">{pop}</span>
        </div>
        <div className="evidence-meta-pill" title="Source Worksheets">
          <span className="meta-label">Source:</span>
          <span className="meta-value">{sources.join(', ')}</span>
        </div>
        <div className="evidence-meta-pill" title="Data Completeness">
          <span className="meta-label">Coverage:</span>
          <span className="meta-value coverage-green">{coverage}</span>
          {missing > 0 && <span className="meta-missing">({missing} omitted)</span>}
        </div>
      </div>

      {onInvestigate && (
        <button
          type="button"
          className="btn-chart-investigate-action"
          onClick={() =>
            onInvestigate({
              entityType: visualization.chart_type === 'burnout_strain' || visualization.chart_type === 'bradford_factor' ? 'department' : 'model_group',
              targetId: visualization.title,
              metric: metric,
              chartId: visualization.id,
              sheetId: visualization.sheet_ids?.[0]
            })
          }
          title="Open deep investigation panel for this chart"
        >
          <span>Investigate Evidence</span>
          <ExternalLink size={12} />
        </button>
      )}
    </div>
  );
}
