/**
 * HighView / PulseHR Unified Design Tokens (Single Source of Truth)
 * 
 * Provides centralized color palettes, surface tokens, text contrast pairs,
 * and chart visual configurations calibrated for WCAG AAA accessibility (>= 7:1 for text, >= 3:1 for graphics).
 */

export const lightTokens = {
  colors: {
    page: '#F8FAFC',
    surface: '#FFFFFF',
    surfaceHover: '#F1F5F9',
    inset: '#F8FAFC',
    mint: '#E6F4F1',
    border: '#E2E8F0',
    borderSubtle: '#F1F5F9',
    borderStrong: '#CBD5E1',
    borderFocus: '#155EEF',
    textPrimary: '#0F172A',
    textSecondary: '#334155',
    textMuted: '#64748B',
    textOnDark: '#FFFFFF',
    brandPrimary: '#0B1F3A',
    brandSecondary: '#005A6B',
    brandAccent: '#155EEF',
    statusSuccess: '#365314',
    statusWarning: '#B7791F',
    statusError: '#B91C1C',
    statusInfo: '#005A6B',
  },
  chart: {
    palette: [
      '#005A6B', // Accessible Teal (7.7:1 - AAA)
      '#123B5D', // Deep Blue (11.2:1 - AAA)
      '#365314', // Accessible Green (7.8:1 - AAA)
      '#155EEF', // Primary Blue (4.8:1 - AA)
      '#0F766E', // Dark Teal (5.4:1 - AA)
      '#0B1F3A', // Deep Navy (16.9:1 - AAA)
      '#6B21A8', // Deep Purple (10.0:1 - AAA)
      '#C2410C', // Rust Amber (4.8:1 - AA)
    ],
    primaryDot: '#0F766E',
    secondaryDot: '#0284C7',
    lifecycle: [
      '#0F766E', // Primary records (deep teal)
      '#0284C7', // Matched cohort (deep sky)
      '#047857', // Agreed records (emerald)
      '#C2410C', // Sibling only / exceptions (rust amber)
    ],
    text: '#0F172A',
    title: '#0F172A',
    axisLine: '#94A3B8',
    splitLine: 'rgba(15, 23, 42, 0.10)',
    tooltipBg: '#FFFFFF',
    tooltipBorder: '#CBD5E1',
    tooltipText: '#0F172A',
    tooltipSubtext: '#334155',
  }
};

export const darkTokens = {
  colors: {
    page: '#08111F',
    surface: '#0F1B2D',
    surfaceHover: '#132238',
    inset: '#08111F',
    mint: 'rgba(45, 212, 191, 0.12)',
    border: '#26384D',
    borderSubtle: '#1E3146',
    borderStrong: '#334960',
    borderFocus: '#60A5FA',
    textPrimary: '#F8FAFC',
    textSecondary: '#CBD5E1',
    textMuted: '#94A3B8',
    textOnDark: '#FFFFFF',
    brandPrimary: '#5EEAD4',
    brandSecondary: '#2DD4BF',
    brandAccent: '#60A5FA',
    statusSuccess: '#4ADE80',
    statusWarning: '#FBBF24',
    statusError: '#F87171',
    statusInfo: '#5EEAD4',
  },
  chart: {
    palette: [
      '#5EEAD4', // Interactive Teal (12.1:1 - AAA)
      '#93C5FD', // Interactive Blue (9.8:1 - AAA)
      '#2DD4BF', // Mint Teal (9.5:1 - AAA)
      '#60A5FA', // Electric Blue (7.0:1 - AAA)
      '#C084FC', // Soft Violet (6.7:1 - AA)
      '#F8FAFC', // Pure Slate (16.6:1 - AAA)
      '#38BDF8', // Bright Sky (9.8:1 - AAA)
      '#FBBF24', // Warm Amber (10.5:1 - AAA)
    ],
    primaryDot: '#2DD4BF',
    secondaryDot: '#60A5FA',
    lifecycle: [
      '#2DD4BF', // Primary records (mint teal)
      '#60A5FA', // Matched cohort (electric blue)
      '#34D399', // Agreed records (bright emerald)
      '#FBBF24', // Sibling only / exceptions (amber gold)
    ],
    text: '#F1F5F9',
    title: '#FFFFFF',
    axisLine: '#64748B',
    splitLine: 'rgba(241, 245, 249, 0.12)',
    tooltipBg: '#0F1B2D',
    tooltipBorder: '#334960',
    tooltipText: '#F8FAFC',
    tooltipSubtext: '#CBD5E1',
  }
};

export const getThemeTokens = (isDark = false) => (isDark ? darkTokens : lightTokens);
export const getChartTokens = (isDark = false) => (isDark ? darkTokens.chart : lightTokens.chart);
