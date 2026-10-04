import React from 'react';
import { SurfaceGuardContext } from './useSurfaceGuard';
import { sanitizeText, sanitizeTitle, sanitizeMetric, hasUnderscores } from './surfaceSanitizer';
import SurfaceGuardChart from './SurfaceGuardChart';
import SurfaceGuardCard from './SurfaceGuardCard';
import SurfaceGuardText from './SurfaceGuardText';

/**
 * SurfaceGuard — Centralized UI Presentation & Invariant Enforcement Layer.
 *
 * Guarantees that no raw database tokens, machine prefixes, or clipped layouts
 * are ever rendered on HighView UI surfaces.
 *
 * Usage:
 * <SurfaceGuard surface="dashboard">
 *   <SurfaceGuard.Card title={rawTitle}>...</SurfaceGuard.Card>
 *   <SurfaceGuard.Chart option={chartOption} />
 *   <SurfaceGuard.Text>{rawToken}</SurfaceGuard.Text>
 * </SurfaceGuard>
 */
export default function SurfaceGuard({ children, surface = 'dashboard', className = '', style = {} }) {
  const contextValue = {
    surface,
    sanitize: sanitizeText,
    sanitizeTitle,
    sanitizeMetric,
    hasUnderscores
  };

  return (
    <SurfaceGuardContext.Provider value={contextValue}>
      <div className={`surface-guard-root surface-guard-${surface} ${className}`} style={style}>
        {children}
      </div>
    </SurfaceGuardContext.Provider>
  );
}

// Compound Sub-Guards
SurfaceGuard.Chart = SurfaceGuardChart;
SurfaceGuard.Card = SurfaceGuardCard;
SurfaceGuard.Text = SurfaceGuardText;
