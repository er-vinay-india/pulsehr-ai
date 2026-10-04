/**
 * Deterministic Number & Label Formatters
 * Compact notation (1.2M, 45K) prevents axis tick collisions and label truncation.
 */

/**
 * Formats a numerical value into compact, readable notation curated up to 2 decimal places.
 * @param {number|string} val 
 * @param {string} [unit=''] 
 * @param {number} [maxDecimals=2] 
 * @returns {string}
 */
export function formatCompactNumber(val, unit = '', maxDecimals = 2) {
  if (val == null || val === '') return '—';
  const num = Number(val);
  if (Number.isNaN(num)) return String(val);

  const abs = Math.abs(num);
  let formatted = '';

  if (abs >= 1e9) {
    formatted = (num / 1e9).toFixed(maxDecimals).replace(/\.00$/, '').replace(/(\.\d)0$/, '$1') + 'B';
  } else if (abs >= 1e6) {
    formatted = (num / 1e6).toFixed(maxDecimals).replace(/\.00$/, '').replace(/(\.\d)0$/, '$1') + 'M';
  } else if (abs >= 1e3) {
    formatted = (num / 1e3).toFixed(maxDecimals).replace(/\.00$/, '').replace(/(\.\d)0$/, '$1') + 'K';
  } else if (abs % 1 !== 0) {
    formatted = num.toLocaleString('en-US', {
      minimumFractionDigits: 0,
      maximumFractionDigits: maxDecimals
    });
  } else {
    formatted = num.toLocaleString('en-US');
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
 * Formats a numerical value displaying its complete, unrounded decimal precision.
 * Used for tooltips and hover inspections when the user places their mouse on a number.
 * @param {number|string} val 
 * @param {string} [unit=''] 
 * @returns {string}
 */
export function formatFullNumber(val, unit = '') {
  if (val == null || val === '') return '—';
  const num = Number(val);
  if (Number.isNaN(num)) return String(val);

  const str = String(val).trim();
  let formatted = '';
  if (str.includes('.')) {
    const [intPart, decPart] = str.split('.');
    const intNum = Number(intPart);
    formatted = Number.isFinite(intNum) ? `${intNum.toLocaleString('en-US')}.${decPart}` : str;
  } else {
    formatted = num.toLocaleString('en-US');
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

