/**
 * Surface Guard - Text & Token Sanitization Engine
 *
 * Guaranteed Invariant:
 * Zero raw underscores, machine prefixes, or unformatted tokens ever render on UI surfaces.
 */

import { formatDisplayLabel, RECOGNIZED_ACRONYMS } from '../../utils/displayFormatters.js';

/**
 * Checks whether a text contains un-repaired machine underscores.
 * @param {any} text
 * @returns {boolean}
 */
export function hasUnderscores(text) {
  if (typeof text !== 'string') return false;
  return text.includes('_');
}

/**
 * Deeply sanitizes any label, metric, or column identifier into clean human English.
 * @param {any} raw
 * @returns {string}
 */
export function sanitizeText(raw) {
  if (raw === null || raw === undefined) return '';
  let str = String(raw).trim();
  if (!str) return '';

  // 1. Strip machine interaction / synthetic prefixes
  const prefixes = [
    'interact_mean_', 'interact_ratio_', 'interact_sum_', 'interact_count_', 'interact_',
    'interact mean ', 'interact ratio ', 'interact sum ', 'interact count ', 'interact ',
    'mean_', 'sum_', 'ratio_', 'log_', 'std_', 'diff_', 'pct_',
    'mean ', 'sum ', 'ratio ', 'log ', 'std ', 'diff ', 'pct '
  ];
  for (const p of prefixes) {
    if (str.toLowerCase().startsWith(p)) {
      str = str.slice(p.length).trim();
      break;
    }
  }

  // 2. Normalize compound tokens like _over_ and _by_
  str = str.replace(/_over_/gi, ' over ');
  str = str.replace(/_by_/gi, ' by ');

  // 3. Fallback to formatDisplayLabel for sentence casing and acronym preservation
  return formatDisplayLabel(str);
}

/**
 * Formats ISO date strings (e.g. 2026-10-04) to readable strings (e.g. Oct 4, 2026).
 * @param {string} dateStr
 * @returns {string}
 */
export function formatHumanDate(dateStr) {
  if (!dateStr || typeof dateStr !== 'string') return dateStr || '';
  const trimmed = dateStr.trim();
  const isoMatch = trimmed.match(/^(\d{4})-(\d{2})-(\d{2})$/);
  if (isoMatch) {
    const [, y, m, d] = isoMatch;
    const months = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec'];
    const monthIdx = parseInt(m, 10) - 1;
    if (monthIdx >= 0 && monthIdx < 12) {
      return `${months[monthIdx]} ${parseInt(d, 10)}, ${y}`;
    }
  }
  return trimmed;
}

/**
 * Sanitizes dashboard and card headlines (e.g. "Unusual interact_ratio_... in group A").
 * @param {string} rawTitle
 * @returns {string}
 */
export function sanitizeTitle(rawTitle) {
  if (!rawTitle || typeof rawTitle !== 'string') return '';
  let title = rawTitle.trim();

  // Pattern A: "Unusual <metric> in <segment>"
  const unusualMatch = title.match(/^Unusual\s+(.+?)\s+in\s+(.+)$/i);
  if (unusualMatch) {
    const [, metric, segment] = unusualMatch;
    const cleanMetric = sanitizeText(metric);
    const cleanSeg = sanitizeText(segment);
    return `Unusual ${cleanMetric.toLowerCase()} in ${cleanSeg}`;
  }

  // Pattern B: "Unusual period: <date>"
  if (title.startsWith('Unusual period: ')) {
    const rawDate = title.replace('Unusual period: ', '').trim();
    return `Unusual period: ${formatHumanDate(rawDate)}`;
  }

  // Generic sentence-case sanitation
  return sanitizeText(title);
}

/**
 * Formats a metric value with safe units, avoiding NaN or raw zeroes.
 * @param {number|string} val
 * @param {string} unit
 * @returns {string}
 */
export function sanitizeMetric(val, unit = '') {
  if (val === null || val === undefined || val === '') return '—';
  const num = typeof val === 'number' ? val : parseFloat(String(val).replace(/[^0-9.-]+/g, ''));
  if (Number.isNaN(num)) return String(val);

  let formatted = Math.abs(num) >= 1_000_000
    ? `${(num / 1_000_000).toFixed(1)}M`
    : Math.abs(num) >= 1_000
    ? `${(num / 1_000).toFixed(1)}K`
    : num.toLocaleString(undefined, { maximumFractionDigits: 2 });

  if (unit === '$') return `$${formatted}`;
  if (unit === '%') return `${formatted}%`;
  if (unit) return `${formatted} ${unit}`;
  return formatted;
}
