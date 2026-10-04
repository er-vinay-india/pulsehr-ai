import React from 'react';

export default function ChartHeader({ title, subtitle, meta, style }) {
  if (!title && !subtitle && !meta?.isConsolidated) return null;

  return (
    <div className="safe-chart-header" style={{ marginBottom: 8, ...style }}>
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', gap: 8 }}>
        {title && (
          <h4 style={{
            margin: 0,
            fontSize: '1rem',
            fontWeight: 600,
            lineHeight: 1.25,
            color: 'var(--color-text-primary, #0f172a)'
          }}>
            {title}
          </h4>
        )}
        {meta?.isConsolidated && (
          <span style={{
            fontSize: '0.72rem',
            fontWeight: 500,
            padding: '2px 8px',
            borderRadius: 999,
            backgroundColor: 'var(--color-bg-subtle, rgba(0,0,0,0.05))',
            color: 'var(--color-text-secondary, #64748b)',
            whiteSpace: 'nowrap'
          }}>
            Top 10 + Other ({meta.hiddenCount} tail items)
          </span>
        )}
      </div>
      {subtitle && (
        <p style={{
          margin: '2px 0 0',
          fontSize: '0.8rem',
          color: 'var(--color-text-secondary, #64748b)'
        }}>
          {subtitle}
        </p>
      )}
    </div>
  );
}
