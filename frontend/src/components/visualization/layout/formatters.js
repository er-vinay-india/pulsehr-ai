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
