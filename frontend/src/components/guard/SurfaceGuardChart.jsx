import React from 'react';
import SafeChart from '../visualization/components/SafeChart';

/**
 * SurfaceGuard.Chart
 * Hardens chart rendering with ECharts layout calculation, axis margin fits, label rotation,
 * and DOM visual QA repair cascade.
 */
export default function SurfaceGuardChart(props) {
  return <SafeChart {...props} />;
}
