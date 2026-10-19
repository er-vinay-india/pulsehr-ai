/**
 * Comprehensive Unit & Boundary Test Suite for HighView Display Formatting (Frontend).
 * 
 * Verifies:
 * - Standard compact thresholds (K, M, B, T) and rollovers.
 * - Multi-currency symbol mapping (USD, INR, EUR, AED, GBP, JPY).
 * - Semantic exclusions: IDs, Years, Percentages, Durations, Scores.
 * - Graceful null/NaN/Infinity handling.
 * - Full unrounded exact measure formatting.
 * - Invariance: raw values and semantic hashes remain untouched.
 */

import {
  formatGovernedNumber,
  formatExactMeasure,
  isCompactAllowed,
  parseGovernedNumber,
} from '../src/utils/numericDisplayFormatter.js';
import crypto from 'crypto';

let totalTests = 0;
let passedTests = 0;

function assert(condition, message) {
  totalTests++;
  if (!condition) {
    console.error(`❌ FAILED: ${message}`);
    throw new Error(message);
  }
  passedTests++;
}

console.log('🧪 Starting HighView Compact Number Formatter Test Suite...');

// 1. Standard Compact Boundaries
const boundaries = [
  [0, '0'],
  [1, '1'],
  [950, '950'],
  [999, '999'],
  [1000, '1K'],
  [1001, '1K'],
  [1250, '1.25K'],
  [12500, '12.5K'],
  [999499, '999.5K'],
  [999999, '1M'],
  [1000000, '1M'],
  [1250000, '1.25M'],
  [58000000, '58M'],
  [999999999, '1B'],
  [1000000000, '1B'],
  [1250000000, '1.25B'],
  [2400000000000, '2.4T'],
];

for (const [val, expected] of boundaries) {
  const res = formatGovernedNumber(val);
  assert(res === expected, `Boundary ${val} expected "${expected}", got "${res}"`);
}
console.log('  ✓ 17/17 boundary tests passed');

// 2. Multi-Currency Formatting
const currencies = [
  [58000000, { currency: 'USD' }, '$58M'],
  [58000000, { unit: '$' }, '$58M'],
  [1250000, { currency: 'INR' }, '₹1.25M'],
  [923500, { currency: 'EUR' }, '€923.5K'],
  [50000000, { currency: 'AED' }, 'AED 50M'],
  [1500000, { currency: 'GBP' }, '£1.5M'],
  [80000000, { currency: 'JPY' }, '¥80M'],
];

for (const [val, opts, expected] of currencies) {
  const res = formatGovernedNumber(val, opts);
  assert(res === expected, `Currency ${val} expected "${expected}", got "${res}"`);
}
console.log('  ✓ 7/7 currency tests passed');

// 3. Negatives & Decimals
assert(formatGovernedNumber(-1250) === '-1.25K', 'Negative compact');
assert(formatGovernedNumber(-58000000, { currency: 'USD' }) === '-$58M', 'Negative currency');
assert(formatGovernedNumber(-450, { unit: '$' }) === '-$450', 'Negative small currency');
assert(formatGovernedNumber(58.00) === '58', 'Decimal trailing zeros stripped');
assert(formatGovernedNumber(58.10) === '58.1', 'Decimal single trailing zero stripped');
assert(formatGovernedNumber(58.125) === '58.13', 'Decimal half-up rounded');
console.log('  ✓ 6/6 negative and decimal tests passed');

// 4. Semantic Exclusions (Never Compacted)
assert(formatGovernedNumber(10523, { metric_id: 'employee_id' }) === '10,523', 'Employee ID not compacted');
assert(formatGovernedNumber(94105, { measure_class: 'POSTAL_CODE' }) === '94105', 'Postal code no comma');
assert(formatGovernedNumber(883492, { label: 'Account ID' }) === '883,492', 'Account ID not compacted');
assert(formatGovernedNumber(2026, { label: 'Fiscal Year' }) === '2026', 'Fiscal Year 2026 no comma');
assert(formatGovernedNumber(2024, { unit: 'year' }) === '2024', 'Year unit no comma no suffix');
assert(formatGovernedNumber(72.4, { unit: '%' }) === '72.4%', 'Percentage unit');
assert(formatGovernedNumber(88.5, { label: 'compliance_rate' }) === '88.5', 'Rate token not compacted');
assert(formatGovernedNumber(3600, { label: 'duration_seconds' }) === '3,600', 'Duration not compacted');
assert(formatGovernedNumber(1500, { label: 'performance_score' }) === '1,500', 'Score not compacted');
console.log('  ✓ 9/9 semantic exclusion tests passed');

// 5. Graceful Missing / Null Handling
assert(formatGovernedNumber(null) === '—', 'Null value');
assert(formatGovernedNumber(undefined) === '—', 'Undefined value');
assert(formatGovernedNumber('') === '—', 'Empty string');
assert(formatGovernedNumber('nan') === '—', 'NaN string');
assert(formatGovernedNumber('NaN') === '—', 'NaN case string');
assert(formatGovernedNumber(NaN) === '—', 'NaN number');
assert(formatGovernedNumber(Infinity) === '—', 'Infinity');
assert(formatGovernedNumber('unavailable') === '—', 'Unavailable string');
assert(formatGovernedNumber(null, { unavailable_label: 'N/A' }) === 'N/A', 'Custom placeholder');
console.log('  ✓ 9/9 graceful missing/invalid tests passed');

// 6. Format Exact Measure (Hover Tooltip Inspection)
assert(formatExactMeasure(58000000, { currency: 'USD' }) === '$58,000,000', 'Exact currency');
assert(formatExactMeasure(1250) === '1,250', 'Exact integer');
assert(formatExactMeasure(72.4, { unit: '%' }) === '72.4%', 'Exact percentage');
assert(formatExactMeasure(2026, { measure_class: 'YEAR' }) === '2026', 'Exact year');
assert(formatExactMeasure(1234567.89, { unit: '$' }) === '$1,234,567.89', 'Exact decimal currency');
console.log('  ✓ 5/5 exact measure hover tests passed');

// 7. Semantic Hash & Raw Value Invariance
const rawFact = {
  fact_id: 'FACT-REV-01',
  metric: 'gross_revenue',
  raw_value: 58000000,
  unit: 'USD',
  grain: 'store_id',
  denominator: 'all_stores',
};

const preJson = JSON.stringify(rawFact, Object.keys(rawFact).sort());
const preHash = crypto.createHash('sha256').update(preJson).digest('hex');

const displayStr = formatGovernedNumber(rawFact.raw_value, { currency: rawFact.unit });
const exactHover = formatExactMeasure(rawFact.raw_value, { currency: rawFact.unit });

assert(displayStr === '$58M', 'Display formatted correctly');
assert(exactHover === '$58,000,000', 'Hover formatted correctly');
assert(rawFact.raw_value === 58000000, 'Raw value remained untouched');

const postJson = JSON.stringify(rawFact, Object.keys(rawFact).sort());
const postHash = crypto.createHash('sha256').update(postJson).digest('hex');
assert(preHash === postHash, 'Semantic hash strictly invariant');
console.log('  ✓ Semantic hash and raw value invariance verified');

console.log(`\n🎉 ALL ${passedTests}/${totalTests} TESTS PASSED!`);
