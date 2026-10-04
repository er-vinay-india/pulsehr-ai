import React, { useRef, useState, useEffect } from 'react';
import SafeReactECharts from '../../charts/SafeReactECharts';
import ChartHeader from './ChartHeader';
import ChartNarrative from './ChartNarrative';
import { normalizeChartSpec } from '../normalize/normalizeChartSpec';
import { useVisualQA } from '../observers/useVisualQA';
import { repairChartLayout } from '../repair/repairChartLayout';
import { useTheme } from '../../../context/ThemeContext';
import { isCurrentThemeDark } from '../../charts/chartOptions';

export default function SafeChart({
  spec,
  height = 320,
  presentationTheme,
  onEvents,
  className = '',
  style = {}
}) {
  const containerRef = useRef(null);
  const repairCountRef = useRef(0);

  let themeContext;
  try {
    themeContext = useTheme();
  } catch (e) {
    themeContext = null;
  }
  const isDark = themeContext ? themeContext.isDark : isCurrentThemeDark();

  // 1. Initial Normalization & Validation
  const [normalizedResult, setNormalizedResult] = useState(() => {
    return normalizeChartSpec(spec, { isDark });
  });

  const [activeOption, setActiveOption] = useState(() => {
    return normalizedResult?.option || null;
  });

  // Re-normalize if input spec changes
  useEffect(() => {
    repairCountRef.current = 0;
    const res = normalizeChartSpec(spec, { isDark });
    setNormalizedResult(res);
    setActiveOption(res.option);
  }, [spec, isDark]);

  // 2. DOM Visual QA Observer
  const { qaIssues } = useVisualQA(containerRef, {
    enabled: Boolean(activeOption && repairCountRef.current < 2),
    chartOption: activeOption
  });

  // 3. Deterministic Auto-Repair Cascade
  useEffect(() => {
    if (qaIssues && activeOption && repairCountRef.current < 2) {
      repairCountRef.current += 1;
      const { repairedOption, repairsApplied } = repairChartLayout(activeOption, qaIssues);
      if (repairsApplied.length > 0) {
        setActiveOption(repairedOption);
      }
    }
  }, [qaIssues, activeOption]);

  // Handle Validation Failures gracefully
  if (!normalizedResult.isValid) {
    return (
      <div
        className={`safe-chart-fallback ${className}`}
        style={{
          padding: 16,
          borderRadius: 8,
          border: '1px dashed var(--color-border, #cbd5e1)',
          backgroundColor: 'var(--color-bg-subtle, rgba(0,0,0,0.02))',
          textAlign: 'center',
          minHeight: 180,
          display: 'flex',
          flexDirection: 'column',
          alignItems: 'center',
          justifyContent: 'center',
          gap: 6,
          ...style
        }}
      >
        <p style={{ margin: 0, fontWeight: 600, color: 'var(--color-text-secondary, #64748b)' }}>
          Visualization Specification Invalid
        </p>
        <p style={{ margin: 0, fontSize: '0.8rem', color: 'var(--color-text-muted, #94a3b8)' }}>
          {normalizedResult.errors?.[0]?.message || 'Required axes or data series are missing.'}
        </p>
      </div>
    );
  }

  const { title, subtitle, narrative, evidence_citation, evidenceCitation } = spec || {};
  const meta = normalizedResult.meta;
  const citation = evidence_citation || evidenceCitation;

  return (
    <div
      ref={containerRef}
      className={`safe-chart-container ${className}`}
      style={{
        display: 'flex',
        flexDirection: 'column',
        width: '100%',
        minWidth: 0,
        ...style
      }}
    >
      <ChartHeader title={title} subtitle={subtitle} meta={meta} />

      <div
        className="safe-chart-plot-area"
        style={{
          flex: '1 1 auto',
          minHeight: `${height}px`,
          width: '100%',
          overflow: 'hidden'
        }}
      >
        <SafeReactECharts
          option={activeOption}
          presentationTheme={presentationTheme}
          onEvents={onEvents}
          style={{ height: '100%', minHeight: `${height}px`, width: '100%' }}
        />
      </div>

      <ChartNarrative narrative={narrative} evidenceCitation={citation} />
    </div>
  );
}
