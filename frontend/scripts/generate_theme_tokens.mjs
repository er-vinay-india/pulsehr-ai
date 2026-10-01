import * as sass from 'sass';
import { readFile, writeFile } from 'node:fs/promises';
import { fileURLToPath } from 'node:url';
import { resolve } from 'node:path';

export const themeSource = fileURLToPath(new URL('../src/styles/_tokens.scss', import.meta.url));
const output = fileURLToPath(new URL('../src/theme/tokens.generated.js', import.meta.url));

// SCSS owns the palette. ECharts requires resolved colours rather than CSS var().
export async function generateThemeTokens() {
  const css = sass.compile(themeSource).css;
  const modes = { light: {}, dark: {} };
  for (const [, selector, body] of css.matchAll(/([^{}]+)\{([^{}]*)\}/g)) {
    const values = Object.fromEntries([...body.matchAll(/--([\w-]+):\s*([^;]+);/g)].map(([, key, value]) => [key, value.trim()]));
    if (selector.includes(':root')) {
      Object.assign(modes.light, values);
      Object.assign(modes.dark, values);
    } else if (/data-theme=["']?dark/.test(selector)) {
      Object.assign(modes.dark, values);
    }
  }
  const colourKeys = {
    page: 'color-bg-page', surface: 'color-bg-surface', elevated: 'color-bg-elevated',
    surfaceHover: 'color-bg-subtle', inset: 'surface-inset', mint: 'color-bg-soft-teal',
    softBlue: 'color-bg-soft-blue', softGold: 'color-bg-soft-gold', softError: 'color-bg-soft-error',
    border: 'color-border', borderSubtle: 'color-divider', borderStrong: 'color-border-strong', borderFocus: 'color-focus',
    textPrimary: 'color-text-primary', textSecondary: 'color-text-secondary', textMuted: 'color-text-muted',
    textOnDark: 'hv-text-on-dark', textOnBrand: 'fg-on-brand',
    brandPrimary: 'color-brand-primary', brandSecondary: 'color-brand-secondary', brandAccent: 'color-brand-accent',
    brandBlue: 'color-brand-blue', gold: 'color-gold', violet: 'color-violet',
    statusSuccess: 'color-success', statusWarning: 'color-warning', statusError: 'color-error', statusInfo: 'color-info'
  };
  const chartKeys = {
    text: 'chart-text', title: 'chart-title', axisLine: 'chart-axis-line', splitLine: 'chart-grid',
    tooltipBg: 'chart-tooltip-bg', tooltipBorder: 'chart-tooltip-border', tooltipText: 'chart-tooltip-text', tooltipSubtext: 'chart-tooltip-subtext',
    heatmapText: 'chart-heatmap-text'
  };
  const exports = [];
  for (const [mode, values] of Object.entries(modes)) {
    const resolve = (key, seen = []) => {
      if (seen.includes(key) || !values[key]) throw new Error(`Invalid ${mode} token: ${key}`);
      const ref = values[key].match(/^var\(--([\w-]+)\)$/);
      return ref ? resolve(ref[1], [...seen, key]) : values[key];
    };
    const palette = Array.from({ length: 8 }, (_, i) => resolve(`chart-series-${i + 1}`));
    const theme = {
      colors: Object.fromEntries(Object.entries(colourKeys).map(([key, cssKey]) => [key, resolve(cssKey)])),
      chart: {
        palette, primaryDot: palette[0], secondaryDot: palette[1],
        lifecycle: [palette[1], palette[4], palette[0], palette[3]],
        heatmapPalette: ['negative', 'neutral', 'positive'].map(key => resolve(`chart-heatmap-${key}`)),
        ...Object.fromEntries(Object.entries(chartKeys).map(([key, cssKey]) => [key, resolve(cssKey)]))
      }
    };
    exports.push(`export const ${mode}Tokens = ${JSON.stringify(theme, null, 2)};\n`);
  }
  const content = '// Generated from styles/_tokens.scss. Edit the SCSS palette, not this file.\n' + exports.join('\n');
  const current = await readFile(output, 'utf8').catch(error => { if (error.code === 'ENOENT') return ''; throw error; });
  if (current !== content) await writeFile(output, content);
}

if (process.argv[1] && fileURLToPath(import.meta.url) === resolve(process.argv[1])) {
  await generateThemeTokens();
}
