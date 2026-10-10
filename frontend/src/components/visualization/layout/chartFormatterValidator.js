/**
 * Chart Formatter Validator and Token Sanitization Engine (Frontend).
 *
 * Guarantees that:
 * 1. No raw template tokens ({value}, {name}, {series}, {percent}) leak into rendered charts.
 * 2. Axis formatters evaluate dynamically rather than returning literal string templates.
 * 3. Tooltips and annotations are presentation-safe.
 */

const UNRESOLVED_TOKEN_REGEX = /\{[a-zA-Z0-9_]+\}/g;

/**
 * Validates an ECharts option for unresolved formatter template tokens.
 * @param {object} option
 * @returns {{ passed: boolean, violations: string[] }}
 */
export function validateChartFormatters(option) {
  if (!option || typeof option !== 'object') {
    return { passed: true, violations: [] };
  }

  const violations = [];

  // Check axes
  const checkAxis = (axis, key) => {
    if (!axis) return;
    const axes = Array.isArray(axis) ? axis : [axis];
    axes.forEach((ax, idx) => {
      const fmt = ax?.axisLabel?.formatter;
      if (typeof fmt === 'string' && UNRESOLVED_TOKEN_REGEX.test(fmt)) {
        violations.push(`${key}[${idx}].axisLabel.formatter contains unresolved token: "${fmt}"`);
      }
    });
  };

  checkAxis(option.xAxis, 'xAxis');
  checkAxis(option.yAxis, 'yAxis');

  // Check tooltip
  const ttFmt = option.tooltip?.formatter;
  if (typeof ttFmt === 'string') {
    const tokens = ttFmt.match(UNRESOLVED_TOKEN_REGEX) || [];
    const invalidTokens = tokens.filter(t => !['{a}', '{b}', '{c}', '{d}', '{e}'].includes(t));
    if (invalidTokens.length > 0) {
      violations.push(`tooltip.formatter contains unresolved tokens: ${invalidTokens.join(', ')}`);
    }
  }

  // Check series labels and markLines
  (option.series || []).forEach((s, sIdx) => {
    const sFmt = s?.label?.formatter;
    if (typeof sFmt === 'string' && UNRESOLVED_TOKEN_REGEX.test(sFmt)) {
      violations.push(`series[${sIdx}].label.formatter contains unresolved token: "${sFmt}"`);
    }
    (s?.markLine?.data || []).forEach((ml, mlIdx) => {
      const mlFmt = ml?.label?.formatter;
      if (typeof mlFmt === 'string' && UNRESOLVED_TOKEN_REGEX.test(mlFmt)) {
        violations.push(`series[${sIdx}].markLine.data[${mlIdx}].label.formatter contains unresolved token: "${mlFmt}"`);
      }
    });
  });

  return {
    passed: violations.length === 0,
    violations,
  };
}

/**
 * Deeply resolves any string template into a deterministic formatter function.
 * Specifically converts "{value}%" or "{value} units" to an actual evaluation function.
 * @param {Function|string|undefined} formatter
 * @param {string} [unitFallback='']
 * @returns {Function}
 */
export function resolveAxisFormatter(formatter, unitFallback = '') {
  if (typeof formatter === 'function') {
    return (val, idx) => {
      try {
        const result = formatter(val, idx);
        if (typeof result === 'string' && UNRESOLVED_TOKEN_REGEX.test(result)) {
          return String(val != null ? val : '') + unitFallback;
        }
        return result;
      } catch (e) {
        return val != null ? `${val}${unitFallback}` : '';
      }
    };
  }

  if (typeof formatter === 'string') {
    return (val) => {
      if (formatter.includes('{value}')) {
        return formatter.replace(/\{value\}/g, val != null ? String(val) : '');
      }
      // If it's a static string template token that was not interpolated
      if (UNRESOLVED_TOKEN_REGEX.test(formatter)) {
        return val != null ? `${val}${unitFallback}` : '';
      }
      return `${val != null ? val : ''} ${formatter}`.trim();
    };
  }

  return (val) => (val != null ? `${val}${unitFallback}` : '');
}

/**
 * Recursively sanitizes an ECharts option tree to prevent literal string token leak.
 * Preserves function references without stringifying them.
 * @param {object} option
 * @returns {object} Sanitized clone of option
 */
export function sanitizeOptionFormatters(option) {
  if (!option || typeof option !== 'object') return option;

  // Shallow copy root, shallow copy axes to preserve function references!
  const clone = { ...option };

  const sanitizeSingleAxis = (ax) => {
    if (!ax || typeof ax !== 'object') return ax;
    const axClone = { ...ax };
    if (axClone.axisLabel) {
      axClone.axisLabel = { ...axClone.axisLabel };
      const fmt = axClone.axisLabel.formatter;
      if (typeof fmt === 'string') {
        if (fmt.includes('{value}')) {
          const suffix = fmt.replace('{value}', '').trim();
          axClone.axisLabel._unit_suffix = suffix;
          delete axClone.axisLabel.formatter;
        } else if (/^(\(.*\)|function|[a-zA-Z0-9_]+)\s*=>/.test(fmt)) {
          // If a stringified function ever appears, delete it
          delete axClone.axisLabel.formatter;
        }
      }
    }
    return axClone;
  };

  const sanitizeAxis = (axis) => {
    if (!axis) return axis;
    if (Array.isArray(axis)) {
      return axis.map(sanitizeSingleAxis);
    }
    return sanitizeSingleAxis(axis);
  };

  if (clone.xAxis) clone.xAxis = sanitizeAxis(clone.xAxis);
  if (clone.yAxis) clone.yAxis = sanitizeAxis(clone.yAxis);

  return clone;
}
