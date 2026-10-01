import assert from 'node:assert/strict';
import { fileURLToPath } from 'node:url';
import * as sass from 'sass';
import { lightTokens, darkTokens } from '../src/theme/tokens.js';

// WCAG relative luminance. Compare raw ratios, never rounded thresholds.
const rgb = hex => hex.slice(1).match(/.{2}/g).map(v => parseInt(v, 16));
const luminance = hex => rgb(hex).map(v => {
  const s = v / 255;
  return s <= 0.04045 ? s / 12.92 : ((s + 0.055) / 1.055) ** 2.4;
}).reduce((sum, v, i) => sum + v * [0.2126, 0.7152, 0.0722][i], 0);
const contrast = (a, b) => {
  const [low, high] = [luminance(a), luminance(b)].sort((x, y) => x - y);
  return (high + 0.05) / (low + 0.05);
};

const css = sass.compile(fileURLToPath(new URL('../src/styles/_tokens.scss', import.meta.url))).css;
const modes = { light: {}, dark: {} };
for (const [, selector, body] of css.matchAll(/([^{}]+)\{([^{}]*)\}/g)) {
  const values = Object.fromEntries([...body.matchAll(/--([\w-]+):\s*([^;]+);/g)].map(([, key, value]) => [key, value.trim()]));
  if (selector.includes(':root')) {
    Object.assign(modes.light, values);
    Object.assign(modes.dark, values);
  } else if (selector.includes('data-theme=dark') || selector.includes('data-theme="dark"')) {
    Object.assign(modes.dark, values);
  }
}
function resolve(mode, key, seen = []) {
  assert(!seen.includes(key), `Circular token: ${key}`);
  const value = modes[mode][key];
  assert(value, `Missing ${mode} token: ${key}`);
  const ref = value.match(/^var\(--([\w-]+)\)$/);
  return ref ? resolve(mode, ref[1], [...seen, key]) : value;
}

let checks = 0;
let lowestText = { light: Infinity, dark: Infinity };
function check(mode, label, foreground, background, minimum = 7) {
  const ratio = contrast(foreground, background);
  assert(ratio >= minimum, `${mode}: ${label}: ${ratio.toFixed(3)}:1 < ${minimum}:1 (${foreground} on ${background})`);
  if (minimum === 7) lowestText[mode] = Math.min(lowestText[mode], ratio);
  checks++;
}

const parity = {
  page: 'color-bg-page', surface: 'color-bg-surface', elevated: 'color-bg-elevated',
  surfaceHover: 'color-bg-subtle', inset: 'surface-inset', mint: 'color-bg-soft-teal',
  softBlue: 'color-bg-soft-blue', softGold: 'color-bg-soft-gold', softError: 'color-bg-soft-error',
  border: 'color-border', borderSubtle: 'color-divider', borderStrong: 'color-border-strong', borderFocus: 'color-focus',
  textPrimary: 'color-text-primary', textSecondary: 'color-text-secondary', textMuted: 'color-text-muted',
  textOnDark: 'hv-text-on-dark', textOnBrand: 'fg-on-brand',
  brandPrimary: 'color-brand-primary', brandSecondary: 'color-brand-secondary', brandAccent: 'color-brand-accent',
  brandBlue: 'color-brand-blue', gold: 'color-gold', violet: 'color-violet',
  statusSuccess: 'color-success', statusWarning: 'color-warning', statusError: 'color-error', statusInfo: 'color-info',
};

// Check the component's actual rules, so a hardcoded foreground regression
// (white on the dark theme's mint active badge) cannot pass palette-only tests.
const uploadCSS = sass.compile(fileURLToPath(new URL('../src/styles/refinements.scss', import.meta.url))).css;
const uploadRules = Object.fromEntries([...uploadCSS.matchAll(/([^{}]+)\{([^{}]*)\}/g)]
  .filter(([, selector]) => selector.trim().startsWith('.upload-modal'))
  .map(([, selector, body]) => [selector.trim(), Object.fromEntries([...body.matchAll(/([\w-]+):\s*([^;]+);/g)].map(([, key, value]) => [key, value.trim()]))]));

for (const [mode, theme] of Object.entries({ light: lightTokens, dark: darkTokens })) {
  const token = key => resolve(mode, key);
  const colour = value => {
    assert(value, 'Missing upload step colour');
    const reference = value.match(/^var\(--([\w-]+)(?:,\s*[^)]+)?\)$/);
    return reference ? token(reference[1]) : value;
  };
  for (const state of ['', '.active']) {
    const badge = uploadRules[`.upload-modal-steps-indicator .step-badge${state}`];
    assert(badge, `Missing upload badge state: ${state || 'pending'}`);
    check(mode, `upload badge ${state || 'pending'}`, colour(badge.color), colour(badge.background));
  }
  check(mode, 'upload step arrow', colour(uploadRules['.upload-modal-steps-indicator .step-arrow'].color), colour(uploadRules['.upload-modal-header'].background));
  for (const [key, cssKey] of Object.entries(parity)) assert.equal(theme.colors[key], token(cssKey), `${mode}: CSS/JS mismatch for ${key}`);
  const surfaces = ['color-bg-page', 'color-bg-surface', 'color-bg-elevated', 'color-bg-subtle', 'color-bg-soft-blue', 'color-bg-soft-teal', 'color-bg-soft-gold', 'color-bg-soft-error'];
  const text = ['color-text-primary', 'color-text-secondary', 'color-text-muted', 'fg-disabled', 'color-brand-primary', 'color-brand-secondary', 'color-brand-accent', 'color-brand-blue', 'color-gold', 'color-violet', 'color-success', 'color-info', 'color-warning', 'color-error', 'brand-400', 'brand-500'];
  for (const bg of surfaces) {
    for (const fg of text) check(mode, `${fg} / ${bg}`, token(fg), token(bg));
    check(mode, `control boundary / ${bg}`, token('border-input'), token(bg), 3);
    check(mode, `focus / ${bg}`, token('border-focus'), token(bg), 3);
    for (const colour of [...theme.chart.palette, ...theme.chart.lifecycle, theme.chart.primaryDot, theme.chart.secondaryDot]) {
      check(mode, `chart / ${bg}`, colour, token(bg));
    }
  }
  theme.chart.palette.forEach((colour, i) => assert.equal(colour, token(`chart-series-${i + 1}`), `${mode}: chart palette drift`));
  for (const [key, cssKey] of Object.entries({ text: 'chart-text', title: 'chart-title', axisLine: 'chart-axis-line', splitLine: 'chart-grid', tooltipBg: 'chart-tooltip-bg', tooltipBorder: 'chart-tooltip-border', tooltipText: 'chart-tooltip-text', tooltipSubtext: 'chart-tooltip-subtext' })) {
    assert.equal(theme.chart[key], token(cssKey), `${mode}: chart ${key} drift`);
  }
  for (const kind of ['primary', 'secondary']) {
    for (const state of ['bg', 'hover']) check(mode, `${kind} button ${state}`, token(`btn-${kind}-fg`), token(`btn-${kind}-${state}`));
  }
  check(mode, 'legacy filled accent', token('fg-on-brand'), token('bg-brand'));
  check(mode, 'active navigation', token('nav-active-fg'), token('nav-active-bg'));
  for (const bg of ['hriday-surface', 'hriday-bg-soft', 'hriday-bg-cream']) {
    for (const fg of ['hriday-text', 'hriday-text-secondary', 'hriday-text-muted', 'hriday-secondary', 'hriday-accent', 'hriday-warm']) check(mode, `${fg} / ${bg}`, token(fg), token(bg));
  }
  // Heatmap labels must remain legible throughout both interpolated segments.
  for (let segment = 0; segment < theme.chart.heatmapPalette.length - 1; segment++) {
    const from = rgb(theme.chart.heatmapPalette[segment]);
    const to = rgb(theme.chart.heatmapPalette[segment + 1]);
    for (let i = 0; i <= 100; i++) {
      const bg = '#' + from.map((v, channel) => Math.round(v + (to[channel] - v) * i / 100).toString(16).padStart(2, '0')).join('');
      check(mode, `heatmap label segment ${segment} ${i}%`, theme.chart.heatmapText, bg);
    }
  }
  // Test every point in the launcher's sRGB gradient, including hover.
  for (const key of ['hriday-gradient', 'hriday-gradient-hover']) {
    const endpoints = token(key).match(/#[\da-f]{6}/gi).map(rgb);
    for (let i = 0; i <= 100; i++) {
      const mix = endpoints[0].map((v, channel) => Math.round(v + (endpoints[1][channel] - v) * i / 100));
      const bg = '#' + mix.map(v => v.toString(16).padStart(2, '0')).join('');
      check(mode, `${key} ${i}%`, '#FFFFFF', bg);
    }
  }
}
console.log(`${checks} contrast checks passed; CSS/JS palettes match.`);
for (const mode of ['light', 'dark']) console.log(`${mode}: minimum tested text contrast ${lowestText[mode].toFixed(2)}:1 (AAA >= 7:1).`);
