import { useMemo } from 'react';
import { useTheme } from '../context/ThemeContext';
import { lightTokens, darkTokens, getThemeTokens } from './tokens';

/**
 * useChartTheme — Unified hook for rendering WCAG AAA compliant charts.
 * 
 * Automatically synchronizes with the app's global ThemeContext.
 * Eliminates per-card manual color ternaries and provides standardized ECharts configs.
 */
export function useChartTheme() {
  const { theme, isDark } = useTheme();

  const themeTokens = useMemo(() => getThemeTokens(isDark), [isDark]);
  const chart = themeTokens.chart;
  const colors = themeTokens.colors;

  const helpers = useMemo(() => ({
    getAxisLabel: (overrides = {}) => ({
      color: chart.text,
      fontSize: 12,
      fontWeight: 600,
      ...overrides,
    }),
    getNameTextStyle: (overrides = {}) => ({
      color: chart.title,
      fontSize: 12,
      fontWeight: 700,
      ...overrides,
    }),
    getAxisLine: (overrides = {}) => ({
      lineStyle: {
        color: chart.axisLine,
        width: 1.5,
        ...(overrides.lineStyle || {}),
      },
      ...overrides,
    }),
    getSplitLine: (overrides = {}) => ({
      lineStyle: {
        color: chart.splitLine,
        type: 'dashed',
        ...(overrides.lineStyle || {}),
      },
      ...overrides,
    }),
    getTooltip: (overrides = {}) => ({
      backgroundColor: chart.tooltipBg,
      borderColor: chart.tooltipBorder,
      borderWidth: 1,
      textStyle: {
        color: chart.tooltipText,
        fontSize: 12,
        ...(overrides.textStyle || {}),
      },
      extraCssText: isDark
        ? 'box-shadow: 0 4px 16px rgba(0, 0, 0, 0.4); border-radius: 8px;'
        : 'box-shadow: 0 4px 14px rgba(11, 31, 58, 0.12); border-radius: 8px;',
      ...overrides,
    }),
    getGrid: (overrides = {}) => ({
      left: '4%',
      right: '4%',
      bottom: '8%',
      top: '16%',
      containLabel: true,
      ...overrides,
    }),
  }), [chart, isDark]);

  return {
    theme,
    isDark,
    tokens: themeTokens,
    colors,
    chart,
    palette: chart.palette,
    lifecycleColors: chart.lifecycle,
    primaryDot: chart.primaryDot,
    secondaryDot: chart.secondaryDot,
    labelColor: chart.text,
    headingColor: chart.title,
    axisLineColor: chart.axisLine,
    splitLineColor: chart.splitLine,
    tooltipBg: chart.tooltipBg,
    tooltipBorder: chart.tooltipBorder,
    tooltipText: chart.tooltipText,
    tooltipSubtext: chart.tooltipSubtext,
    ...helpers,
  };
}

export default useChartTheme;
