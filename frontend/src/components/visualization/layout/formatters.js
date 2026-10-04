/**
 * Deterministic Number & Label Formatters
 * Compact notation (1.2M, 45K) prevents axis tick collisions and label truncation.
 */

/**
 * Formats a numerical value into compact, readable notation.
 * @param {number|string} val 
 * @param {string} [unit=''] 
 * @param {number} [maxDecimals=1] 
 * @returns {string}
 */
export function formatCompactNumber(val, unit = '', maxDecimals = 1) {
  if (val == null || val === '') return '—';
  const num = Number(val);
  if (Number.isNaN(num)) return String(val);

  const abs = Math.abs(num);
  let formatted = '';

  if (abs >= 1e9) {
    formatted = (num / 1e9).toFixed(maxDecimals).replace(/\.0$/, '') + 'B';
  } else if (abs >= 1e6) {
    formatted = (num / 1e6).toFixed(maxDecimals).replace(/\.0$/, '') + 'M';
  } else if (abs >= 1e3) {
    formatted = (num / 1e3).toFixed(maxDecimals).replace(/\.0$/, '') + 'K';
  } else if (abs % 1 !== 0) {
    formatted = num.toFixed(maxDecimals).replace(/\.0$/, '');
  } else {
    formatted = num.toLocaleString();
  }

  if (!unit) return formatted;
  if (unit === '$' || unit === '£' || unit === '€' || unit === '₹') {
    return `${unit}${formatted}`;
  }
  if (unit === '%') {
    return `${formatted}%`;
  }
  return `${formatted} ${unit}`;
}

/**
 * Clamps text to a max character length with an ellipsis.
 * @param {string} text 
 * @param {number} maxChars 
 * @returns {string}
 */
export function clampText(text, maxChars = 28) {
  if (!text || typeof text !== 'string') return '';
  if (text.length <= maxChars) return text;
  return text.slice(0, maxChars - 1).trim() + '…';
}

/**
 * Humanizes raw machine tokens, column names, and snake_case strings into clean business English.
 * Replaces underscores with spaces, removes synthetic prefixes (mean_, sum_, interact_, etc.),
 * and properly title-cases while preserving common acronyms (HR, FTE, KPI, ID, US, UK, etc.).
 * @param {string|any} text
 * @returns {string}
 */
export function humanizeLabel(text) {
  if (text == null) return '';
  let s = String(text).trim();
  if (!s) return '';

  // Remove common machine prefixes
  const prefixes = [
    'interact_mean_', 'interact_ratio_', 'interact_sum_', 'interact_count_', 'interact_',
    'mean_', 'sum_', 'ratio_', 'log_', 'std_', 'diff_', 'pct_'
  ];
  for (const prefix of prefixes) {
    if (s.toLowerCase().startsWith(prefix)) {
      s = s.slice(prefix.length);
    }
  }

  // Handle _by_ or _vs_
  if (s.includes('_by_')) {
    return s.split('_by_').map(humanizeLabel).join(' by ');
  }
  if (s.includes('_vs_')) {
    return s.split('_vs_').map(humanizeLabel).join(' vs ');
  }

  if (s.includes('_')) {
    s = s.replace(/_+/g, ' ').trim();
  }

  const acronyms = new Set(['hr', 'fte', 'kpi', 'id', 'us', 'uk', 'cpi', 'ols', 'usd', 'eur', 'gbp', 'inr', 'roi', 'ai', 'qa']);

  return s.split(/\s+/).map((word, idx) => {
    const lower = word.toLowerCase();
    if (acronyms.has(lower)) return lower.toUpperCase();
    if (idx > 0 && ['by', 'vs', 'and', 'of', 'in', 'on', 'at', 'to', 'for', 'with'].includes(lower)) {
      return lower;
    }
    return word.charAt(0).toUpperCase() + word.slice(1);
  }).join(' ');
}

