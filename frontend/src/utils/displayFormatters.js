/**
 * Centralized Display-Label Formatter & Analytical Title Engine (Frontend)
 *
 * Formats column names, identifiers, and chart titles into consistent sentence case
 * while preserving recognized acronyms (HR, ID, KPI, CPI, etc.) and keeping raw
 * data keys intact for queries, joins, and row lookups.
 */

export const RECOGNIZED_ACRONYMS = new Set([
  'HR',
  'ID',
  'KPI',
  'FTE',
  'USD',
  'CPI',
  'OLS',
  'AI',
  'IT',
  'GE',
  'CEO',
  'CFO',
  'CPO',
  'CTO',
  'ROI',
  'YTD',
  'Q1',
  'Q2',
  'Q3',
  'Q4',
  'P&L',
  'SLA'
]);

export const SPECIAL_DISPLAY_OVERRIDES = {
  cpi: 'CPI',
  cpi_index: 'CPI index',
  weekly_sales: 'Weekly sales',
  holiday_flag: 'Holiday flag',
  fuel_price: 'Fuel price',
  unemployment: 'Unemployment',
  store: 'Store',
  date: 'Date',
  temperature: 'Temperature',
  dept: 'Department',
  department: 'Department',
  fte: 'FTE',
  kpi: 'KPI',
  ols: 'OLS'
};

/**
 * Formats a raw identifier or column name into a natural sentence-cased display label.
 * @param {string|any} rawName - Raw column name (e.g. "Weekly_Sales", "employeeID", "left.Fuel_Price")
 * @returns {string} Clean formatted display label (e.g. "Weekly sales", "Employee ID", "left Fuel price")
 */
export function formatDisplayLabel(rawName) {
  if (rawName == null) return '';
  let text = String(rawName).trim();
  if (!text) return '';

  // Handle prefixed names like 'left.Weekly_Sales' or 'right.Store'
  let prefix = '';
  if (text.includes('.') && !/^\d+\.\d+$/.test(text)) {
    const parts = text.split('.');
    prefix = parts[0] + ' ';
    text = parts.slice(1).join('.');
  }

  const lowerKey = text.toLowerCase().replace(/[\s-]+/g, '_');
  if (SPECIAL_DISPLAY_OVERRIDES[lowerKey]) {
    return `${prefix}${SPECIAL_DISPLAY_OVERRIDES[lowerKey]}`.trim();
  }

  // CamelCase splitting: "employeeID" -> "employee ID", "monthlySales" -> "monthly Sales"
  const s1 = text.replace(/([a-z0-9])([A-Z])/g, '$1 $2');
  const s2 = s1.replace(/([A-Z]+)([A-Z][a-z])/g, '$1 $2');

  // Replace underscores and hyphens with space
  const normalized = s2.replace(/[_\\-]+/g, ' ').trim();
  const tokens = normalized.split(/\s+/);
  if (!tokens.length) return text;

  const processedTokens = tokens.map((token) => {
    const cleanToken = token.replace(/^[.,:;()[\]]+|[.,:;()[\]]+$/g, '');
    const tokenUpper = cleanToken.toUpperCase();
    if (RECOGNIZED_ACRONYMS.has(tokenUpper)) {
      return token.replace(cleanToken, tokenUpper);
    }
    return token.toLowerCase();
  });

  const joined = processedTokens.join(' ');
  if (!joined) return text;

  // Sentence case: Capitalize the first character of the string unless first token is an acronym
  const firstTokenClean = tokens[0].replace(/^[.,:;()[\]]+|[.,:;()[\]]+$/g, '').toUpperCase();
  let finalStr = joined;
  if (!RECOGNIZED_ACRONYMS.has(firstTokenClean)) {
    finalStr = joined.charAt(0).toUpperCase() + joined.slice(1);
  }

  return `${prefix}${finalStr}`.trim();
}

/**
 * Generates an objective, natural analytical title and subtitle.
 * @param {string} calcType - Calculation type (e.g. "Average", "Summation", "Distribution")
 * @param {string} metricCol - Measured metric column (e.g. "Weekly_Sales")
 * @param {string} [groupCol] - Categorical grouping column (e.g. "Store", "Holiday_Flag")
 * @param {string} [comparisonType] - Special comparison type ('binary_flag', 'time_series', 'donut')
 * @param {number} [totalCount] - Number of entities or observation periods
 * @returns {{ title: string, subtitle: string }}
 */
export function formatAnalyticalTitle(calcType = 'Average', metricCol = '', groupCol = null, comparisonType = null, totalCount = null) {
  const mLabel = formatDisplayLabel(metricCol);
  const mLower = RECOGNIZED_ACRONYMS.has(mLabel) ? mLabel : mLabel.toLowerCase();

  // 1. Categorical Composition / Donut Chart
  if (comparisonType === 'donut' || /distribution|composition|share/i.test(calcType)) {
    if (groupCol && /holiday/i.test(groupCol)) {
      return {
        title: 'Distribution: Holiday vs non-holiday',
        subtitle: `Proportional composition across ${totalCount || 'all'} recorded periods`
      };
    }
    if (groupCol) {
      const gLabel = formatDisplayLabel(groupCol);
      return {
        title: `Distribution by ${gLabel.toLowerCase()}`,
        subtitle: `Proportional composition across ${totalCount || 'all'} recorded entities`
      };
    }
    return {
      title: `Distribution of ${mLower}`,
      subtitle: 'Proportional composition across recorded categories'
    };
  }

  // 2. Binary Flag Comparison (Holiday vs Regular)
  if (comparisonType === 'binary_flag' || (groupCol && /holiday|flag/i.test(groupCol))) {
    if (/holiday/i.test(groupCol || '')) {
      return {
        title: `Average ${mLower}: Holiday vs non-holiday`,
        subtitle: 'Average comparison between holiday and regular weeks'
      };
    }
    const gLabel = formatDisplayLabel(groupCol);
    return {
      title: `Average ${mLower}: ${gLabel} comparison`,
      subtitle: `Performance comparison segmented by ${gLabel.toLowerCase()}`
    };
  }

  // 3. Sequential Trend / Time-Series Line Chart
  if (comparisonType === 'time_series' || (groupCol && /date|time|week|month|year/i.test(groupCol))) {
    const isTotal = /total|sum/i.test(calcType);
    const aggDesc = isTotal ? 'Total network' : 'Average';
    return {
      title: `${aggDesc} ${mLower} over time`,
      subtitle: totalCount
        ? `Longitudinal progression across ${totalCount} recorded periods`
        : 'Longitudinal progression across recorded periods'
    };
  }

  // 4. Standard Categorical Bar Chart
  if (groupCol) {
    const gLabel = formatDisplayLabel(groupCol);
    const gLower = RECOGNIZED_ACRONYMS.has(gLabel) ? gLabel : gLabel.toLowerCase();
    const isTotal = /total|sum/i.test(calcType);
    const measureWord = isTotal ? 'Total' : 'Average';
    return {
      title: `${measureWord} ${mLower} by ${gLower}`,
      subtitle: totalCount
        ? `Ranked across ${totalCount} ${gLower} entities by ${measureWord.toLowerCase()} ${mLower}`
        : `Ranked by ${measureWord.toLowerCase()} ${mLower}`
    };
  }

  return {
    title: `${calcType} ${mLower}`,
    subtitle: `Calculated ${calcType.toLowerCase()} across evaluated records`
  };
}
