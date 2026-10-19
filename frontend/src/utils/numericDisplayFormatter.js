/**
 * HighView Unified Semantic-Aware Numeric Display Formatter (Frontend)
 * 
 * Provides single shared display contract for compact, executive-grade number formatting
 * across Dashboard, Presentation Studio, and Export surfaces.
 * 
 * Invariants:
 * - Underlying raw governed values remain 100% untouched.
 * - Semantic hashes and analytical provenance continue to use raw governed numbers.
 * - Non-aggregatable entities (IDs, years, postal codes, phone numbers, percentages) are NEVER compacted.
 * - Exact full values are preserved for accessible hover tooltips and audit inspection.
 */

// Canonical Currency Symbol Mapping
const CURRENCY_SYMBOLS = {
  USD: '$',
  '$': '$',
  EUR: '€',
  '€': '€',
  GBP: '£',
  '£': '£',
  INR: '₹',
  '₹': '₹',
  JPY: '¥',
  '¥': '¥',
  CNY: '¥',
  AUD: 'A$',
  CAD: 'CA$',
  CHF: 'CHF',
  AED: 'AED',
  SGD: 'SGD',
  HKD: 'HK$',
  NZD: 'NZ$',
  BRL: 'R$',
  SEK: 'kr',
  ZAR: 'R',
};

// Measure classes that strictly forbid K/M/B/T compaction
const FORBIDDEN_COMPACT_CLASSES = new Set([
  'IDENTIFIER',
  'ENTITY_IDENTIFIER',
  'YEAR',
  'DATE',
  'TIME',
  'CODE',
  'POSTAL_CODE',
  'PHONE_NUMBER',
  'PERCENTAGE',
  'DURATION',
  'SCORE',
  'INDEX',
]);

const IDENTIFIER_TOKENS = new Set([
  'id', 'identifier', 'code', 'zip', 'postal', 'phone', 'ssn', 'ein', 'itin',
  'uuid', 'guid', 'pin', 'account_no', 'acc_no', 'sheet_id', 'dataset_id', 'evid'
]);
const YEAR_TOKENS = new Set(['year', 'yr', 'fiscal_year', 'fy', 'calendar_year']);
const PERCENT_TOKENS = new Set([
  'pct', 'percent', 'percentage', 'rate', 'ratio', 'compliance',
  'utilization', 'yield', 'margin', 'share', 'proportion'
]);
const DURATION_TOKENS = new Set([
  'duration', 'hours', 'hrs', 'minutes', 'mins', 'seconds', 'secs',
  'days', 'weeks', 'months', 'years_of_service', 'tenure'
]);
const SCORE_TOKENS = new Set(['score', 'rating', 'grade', 'rank', 'index', 'plddt', 'confidence', 'probability']);

/**
 * Normalizes input value to a JavaScript number if finite.
 * Returns null for missing/null/undefined/NaN/Infinity.
 */
export function parseGovernedNumber(val) {
  if (val == null || val === '') return null;
  if (typeof val === 'number') {
    return Number.isFinite(val) ? val : null;
  }
  let cleanStr = String(val).replace(/,/g, '').trim();
  if (
    cleanStr === '' ||
    cleanStr.toLowerCase() === 'nan' ||
    cleanStr.toLowerCase() === 'infinity' ||
    cleanStr.toLowerCase() === '-infinity' ||
    cleanStr.toLowerCase() === 'none' ||
    cleanStr.toLowerCase() === 'null' ||
    cleanStr.toLowerCase() === 'unavailable' ||
    cleanStr === '—'
  ) {
    return null;
  }

  // Strip currency symbol or percent suffix if present
  cleanStr = cleanStr.replace(/^[\$€£₹¥]\s*/, '').replace(/%\s*$/, '').trim();

  const num = Number(cleanStr);
  return Number.isFinite(num) ? num : null;
}

/**
 * Checks if unit or options represents a currency.
 */
export function isCurrency(unit = '', options = {}) {
  const u = String(options.currency || unit || '').toUpperCase().trim();
  if (!u) return false;
  return Boolean(CURRENCY_SYMBOLS[u]) || ['USD', 'EUR', 'GBP', 'INR', 'JPY', 'CNY', 'AUD', 'CAD', 'CHF', 'AED', 'SGD', '$', '€', '£', '₹', '¥'].includes(u);
}

/**
 * Resolves currency symbol or prefix for a given currency code or unit.
 */
export function resolveCurrencyFormat(unit = '', options = {}) {
  const rawCode = String(options.currency || unit || '').trim();
  const upperCode = rawCode.toUpperCase();

  const sym = CURRENCY_SYMBOLS[upperCode] || CURRENCY_SYMBOLS[rawCode];
  if (sym) {
    const isCode = sym.length >= 3 && /^[A-Za-z]+$/.test(sym);
    return { symbol: sym, isPrefix: true, isCode };
  }

  // Fallback: If 3-letter currency code like AED, BRL, SGD, prefix with code and space
  if (/^[A-Z]{3}$/.test(upperCode)) {
    return { symbol: upperCode, isPrefix: true, isCode: true };
  }
  return { symbol: rawCode, isPrefix: false, isCode: false };
}

/**
 * Determines whether a measure is semantically eligible for compact K/M/B/T notation.
 */
export function isCompactAllowed(val, options = {}) {
  const {
    unit = '',
    measure_class = '',
    semantic_role = '',
    metric_id = '',
    label = '',
    column_name = '',
    allow_compact = null,
  } = options;

  // 1. Explicit caller override
  if (allow_compact === false) return false;

  // 2. Explicit measure class check
  const mClass = String(measure_class || '').toUpperCase().trim();
  if (FORBIDDEN_COMPACT_CLASSES.has(mClass)) return false;

  // 3. Unit-based exclusions (Percentages)
  const u = String(unit || '').trim();
  if (u === '%' || u.includes('%')) return false;

  // 4. Role-based exclusions
  const role = String(semantic_role || '').toLowerCase().trim();
  if (role === 'identifier' || role === 'dimension' || role === 'year' || role === 'date' || role === 'code') {
    return false;
  }

  // 5. Token-based inspection
  const combined = `${metric_id} ${label} ${column_name}`.trim().toLowerCase();
  const tokens = new Set(combined ? combined.split(/[\s_\-]+/) : []);

  for (const t of tokens) {
    if (IDENTIFIER_TOKENS.has(t)) return false;
  }

  // Year heuristics: integer in range 1800-2200 with year token in name or unit
  const num = typeof val === 'number' ? val : Number(val);
  if (Number.isFinite(num) && Number.isInteger(num) && num >= 1800 && num <= 2200) {
    if (u.toLowerCase() === 'year' || u.toLowerCase() === 'yr') return false;
    for (const t of tokens) {
      if (YEAR_TOKENS.has(t)) return false;
    }
  }

  // Percentage / Duration / Score tokens when not currency
  const hasCurr = isCurrency(u, options);
  if (!hasCurr) {
    for (const t of tokens) {
      if (PERCENT_TOKENS.has(t)) return false;
      if (DURATION_TOKENS.has(t)) return false;
      if (SCORE_TOKENS.has(t)) return false;
    }
  }

  return true;
}

/**
 * Strips unnecessary trailing zeros after decimal point, rounding half up.
 */
function formatCleanDecimal(val, maxDecimals) {
  // Use round-half-up
  const factor = Math.pow(10, maxDecimals);
  const rounded = Math.round((val + Number.EPSILON) * factor) / factor;
  const s = rounded.toFixed(maxDecimals);
  return s.replace(/\.0+$/, '').replace(/(\.[0-9]*[1-9])0+$/, '$1');
}

/**
 * Formats a number in compact K/M/B/T notation.
 * Preserves up to 2 decimal places, stripping unnecessary trailing zeros.
 * Handles rollovers (e.g. 999,999 -> 1M).
 */
function formatCompactMantissa(num, maxDecimals = 2) {
  const abs = Math.abs(num);

  const TIERS = [
    { threshold: 1e12, suffix: 'T', divisor: 1e12 },
    { threshold: 1e9,  suffix: 'B', divisor: 1e9 },
    { threshold: 1e6,  suffix: 'M', divisor: 1e6 },
    { threshold: 1e3,  suffix: 'K', divisor: 1e3 },
  ];

  for (let i = 0; i < TIERS.length; i++) {
    const tier = TIERS[i];
    if (abs >= tier.divisor) {
      const scaled = abs / tier.divisor;
      const mantissa = formatCleanDecimal(scaled, maxDecimals);

      // Check if rounded mantissa pushed to 1000 (e.g. 999.999 -> 1000)
      if (parseFloat(mantissa) >= 1000 && i > 0) {
        const nextTier = TIERS[i - 1];
        const nextScaled = abs / nextTier.divisor;
        return {
          mantissa: formatCleanDecimal(nextScaled, maxDecimals),
          suffix: nextTier.suffix,
        };
      }

      return { mantissa, suffix: tier.suffix };
    }
  }

  // Check rollover for values just below 1e3 (e.g. 999.999)
  const scaled = abs / 1e3;
  const mantissa = formatCleanDecimal(scaled, maxDecimals);
  if (parseFloat(mantissa) >= 1.0) {
    return { mantissa, suffix: 'K' };
  }

  // < 1000: normal number with clean decimals
  const formatted = (abs % 1 === 0)
    ? abs.toLocaleString('en-US')
    : formatCleanDecimal(abs, maxDecimals);
  return { mantissa: formatted, suffix: '' };
}

/**
 * Attaches currency symbol or unit cleanly without space collision.
 */
function applyCurrencyAndUnit(coreStr, sign, unit, currencyInfo, options = {}) {
  const { symbol, isPrefix, isCode } = currencyInfo;

  if (isPrefix) {
    if (isCode || (symbol.length >= 3 && /^[A-Za-z]+$/.test(symbol))) {
      return `${sign}${symbol} ${coreStr}`;
    }
    return `${sign}${symbol}${coreStr}`;
  }

  const u = String(unit || '').trim();
  if (u.toLowerCase() === 'year' || u.toLowerCase() === 'yr') {
    return `${sign}${coreStr}`;
  }
  if (u === '%') {
    return `${sign}${coreStr}%`;
  }
  if (u) {
    return `${sign}${coreStr} ${u}`;
  }
  return `${sign}${coreStr}`;
}

/**
 * Formats a governed numeric value into executive-grade display notation.
 * 
 * @param {number|string|null} value - Raw governed numeric value
 * @param {Object|string} [options={}] - Options or unit string
 * @param {string} [options.unit=''] - Unit of measurement (e.g. '$', 'USD', '%', 'INR', 'employees')
 * @param {string} [options.currency=''] - Currency code override (e.g. 'USD', 'EUR')
 * @param {string} [options.measure_class=''] - FINANCIAL, QUANTITY, HEADCOUNT, PERCENTAGE, etc.
 * @param {string} [options.semantic_role=''] - identifier, dimension, measure, etc.
 * @param {string} [options.metric_id=''] - Diagnostic metric ID (e.g. 'KPI-001', 'employee_id')
 * @param {string} [options.label=''] - User-facing label (e.g. 'Office Attendance', 'Year')
 * @param {string} [options.column_name=''] - Schema column name
 * @param {number} [options.max_decimals=2] - Maximum decimal places for compact form (default: 2)
 * @param {boolean} [options.allow_compact=null] - Explicit override to allow/disallow K/M/B/T
 * @param {string} [options.unavailable_label='—'] - Placeholder for missing/null/invalid values
 * @returns {string} Formatted string (e.g. '$58M', '1.25K', '84.2%', '2026')
 */
export function formatGovernedNumber(value, options = {}) {
  const opts = typeof options === 'string' ? { unit: options } : (options || {});
  const {
    unit = '',
    unavailable_label = '—',
    max_decimals = 2,
  } = opts;

  const num = parseGovernedNumber(value);
  if (num === null) {
    return unavailable_label;
  }

  const sign = num < 0 ? '-' : '';
  const absNum = Math.abs(num);

  const currencyInfo = resolveCurrencyFormat(unit, opts);
  const eligible = isCompactAllowed(num, { ...opts, unit });

  if (!eligible || absNum < 1000) {
    let formattedNumber = '';
    const combined = `${opts.metric_id || ''} ${opts.label || ''} ${opts.column_name || ''}`.trim().toLowerCase();
    const tokens = new Set(combined ? combined.split(/[\s_\-]+/) : []);

    let isYearToken = false;
    for (const t of tokens) {
      if (YEAR_TOKENS.has(t)) { isYearToken = true; break; }
    }

    if (absNum % 1 === 0) {
      const isYearOrId = (
        opts.measure_class === 'YEAR' ||
        opts.measure_class === 'IDENTIFIER' ||
        opts.measure_class === 'POSTAL_CODE' ||
        String(unit).toLowerCase().trim() === 'year' ||
        String(unit).toLowerCase().trim() === 'yr' ||
        (absNum >= 1800 && absNum <= 2200 && isYearToken)
      );
      formattedNumber = isYearOrId ? String(absNum) : absNum.toLocaleString('en-US');
    } else {
      formattedNumber = formatCleanDecimal(absNum, max_decimals);
    }

    return applyCurrencyAndUnit(formattedNumber, sign, unit, currencyInfo, opts);
  }

  // Compact K/M/B/T formatting
  const { mantissa, suffix } = formatCompactMantissa(absNum, max_decimals);
  const compactStr = `${mantissa}${suffix}`;
  return applyCurrencyAndUnit(compactStr, sign, unit, currencyInfo, opts);
}

/**
 * Formats a governed value in full, unrounded/exact notation with standard thousands separators.
 * Used for accessible hover tooltips (e.g. title attributes) and audit inspection.
 * 
 * @param {number|string|null} value - Raw governed numeric value
 * @param {Object|string} [options={}] - Options or unit string
 * @returns {string} Exact formatted string (e.g. '$58,000,000', '1,250', '84.2%')
 */
export function formatExactMeasure(value, options = {}) {
  const opts = typeof options === 'string' ? { unit: options } : (options || {});
  const {
    unit = '',
    unavailable_label = '—',
  } = opts;

  const num = parseGovernedNumber(value);
  if (num === null) {
    return unavailable_label;
  }

  const sign = num < 0 ? '-' : '';
  const absNum = Math.abs(num);
  const strVal = String(absNum).trim();

  let formattedNumber = '';
  if (absNum % 1 === 0) {
    const combined = `${opts.metric_id || ''} ${opts.label || ''} ${opts.column_name || ''}`.trim().toLowerCase();
    const tokens = new Set(combined ? combined.split(/[\s_\-]+/) : []);
    let isYearToken = false;
    for (const t of tokens) {
      if (YEAR_TOKENS.has(t)) { isYearToken = true; break; }
    }

    const isYearOrPostal = (
      opts.measure_class === 'YEAR' ||
      opts.measure_class === 'POSTAL_CODE' ||
      String(unit).toLowerCase().trim() === 'year' ||
      String(unit).toLowerCase().trim() === 'yr' ||
      (absNum >= 1800 && absNum <= 2200 && isYearToken)
    );
    formattedNumber = isYearOrPostal ? String(absNum) : absNum.toLocaleString('en-US');
  } else if (strVal.includes('.')) {
    const [intPart, decPart] = strVal.split('.');
    const intNum = Number(intPart);
    formattedNumber = Number.isFinite(intNum) ? `${intNum.toLocaleString('en-US')}.${decPart}` : strVal;
  } else {
    formattedNumber = absNum.toLocaleString('en-US');
  }

  const currencyInfo = resolveCurrencyFormat(unit, opts);
  return applyCurrencyAndUnit(formattedNumber, sign, unit, currencyInfo, opts);
}

// Backward-compatible alias matching historical signature
export function formatCompactNumber(val, unit = '', maxDecimals = 2, options = {}) {
  const mergedOpts = typeof options === 'object' ? { ...options, unit, max_decimals: maxDecimals } : { unit, max_decimals: maxDecimals };
  return formatGovernedNumber(val, mergedOpts);
}

// Backward-compatible alias matching historical signature
export function formatFullNumber(val, unit = '', options = {}) {
  const mergedOpts = typeof options === 'object' ? { ...options, unit } : { unit };
  return formatExactMeasure(val, mergedOpts);
}
