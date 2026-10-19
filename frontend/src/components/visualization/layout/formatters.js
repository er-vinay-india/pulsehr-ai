/**
 * Deterministic Number & Label Formatters
 * Compact notation (1.2M, 45K) prevents axis tick collisions and label truncation.
 */

import {
  formatGovernedNumber,
  formatExactMeasure,
  formatCompactNumber,
  formatFullNumber,
  isCompactAllowed,
  parseGovernedNumber,
} from '../../../utils/numericDisplayFormatter.js';

export {
  formatGovernedNumber,
  formatExactMeasure,
  formatCompactNumber,
  formatFullNumber,
  isCompactAllowed,
  parseGovernedNumber,
};

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

  // Remove common machine prefixes (supporting both underscore and space-separated variants)
  const prefixes = [
    'interact_mean_', 'interact_ratio_', 'interact_sum_', 'interact_count_', 'interact_',
    'interact mean ', 'interact ratio ', 'interact sum ', 'interact count ', 'interact ',
    'mean_', 'sum_', 'ratio_', 'log_', 'std_', 'diff_', 'pct_',
    'mean ', 'sum ', 'ratio ', 'log ', 'std ', 'diff ', 'pct '
  ];
  for (const prefix of prefixes) {
    if (s.toLowerCase().startsWith(prefix)) {
      s = s.slice(prefix.length).trim();
      break;
    }
  }

  // Normalize underscores to spaces for unified matching
  const normalizedS = s.replace(/_+/g, ' ').trim();

  // Detect and collapse duplicated metric patterns like:
  // "math score by test preparation course math score lift" -> "test preparation course math score lift"
  const duplicateByMatch = normalizedS.match(/^(.+?)\s+by\s+(.+?)\s+\1\s*(.*)$/i);
  if (duplicateByMatch) {
    const [, metric, category, remainder] = duplicateByMatch;
    s = `${category} ${metric} ${remainder}`.trim();
  } else {
    s = normalizedS;
  }

  // Handle ' by ' or ' vs ' or ' over '
  if (s.includes(' by ')) {
    return s.split(' by ').map(humanizeLabel).join(' by ');
  }
  if (s.includes(' vs ')) {
    return s.split(' vs ').map(humanizeLabel).join(' vs ');
  }
  if (s.includes(' over ')) {
    return s.split(' over ').map(humanizeLabel).join(' / ');
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

