import React, { useState } from 'react';

export default function ChartNarrative({ narrative, evidenceCitation, style }) {
  const [expanded, setExpanded] = useState(false);

  if (!narrative && !evidenceCitation) return null;

  const isLong = narrative && narrative.length > 140;
  const displayText = isLong && !expanded ? `${narrative.slice(0, 130).trim()}…` : narrative;

  return (
    <div
      className="safe-chart-narrative"
      style={{
        marginTop: 8,
        padding: '8px 12px',
        borderRadius: 6,
        backgroundColor: 'var(--color-bg-subtle, rgba(0,0,0,0.02))',
        border: '1px solid var(--color-border, rgba(0,0,0,0.06))',
        fontSize: '0.82rem',
        lineHeight: 1.4,
        color: 'var(--color-text-secondary, #475569)',
        maxHeight: expanded ? '220px' : '80px',
        overflow: 'hidden',
        transition: 'max-height 0.2s ease',
        ...style
      }}
    >
      <div style={{ display: 'flex', alignItems: 'flex-start', justifyContent: 'space-between', gap: 6 }}>
        <div>
          {displayText}
          {isLong && (
            <button
              type="button"
              onClick={() => setExpanded(!expanded)}
              style={{
                background: 'none',
                border: 'none',
                padding: '0 4px',
                color: 'var(--color-brand-primary, #0284c7)',
                fontSize: '0.78rem',
                fontWeight: 600,
                cursor: 'pointer'
              }}
            >
              {expanded ? 'Show less' : 'Read more'}
            </button>
          )}
        </div>
        {evidenceCitation && (
          <span style={{
            fontSize: '0.7rem',
            fontWeight: 600,
            padding: '1px 6px',
            borderRadius: 4,
            backgroundColor: 'var(--color-brand-secondary, rgba(16,185,129,0.1))',
            color: 'var(--color-brand-secondary, #059669)',
            whiteSpace: 'nowrap'
          }}>
            {evidenceCitation}
          </span>
        )}
      </div>
    </div>
  );
}
