import assert from 'node:assert/strict';
import { validateChartSpec, SchemaErrorCode } from '../src/components/visualization/schema/chartSchema.js';
import { VISUAL_POLICY, requiresHorizontalOrientation } from '../src/components/visualization/policy/visualPolicy.js';
import { calculateChartLayout } from '../src/components/visualization/layout/calculateChartLayout.js';
import { calculateMargins } from '../src/components/visualization/layout/calculateMargins.js';
import { formatCompactNumber } from '../src/components/visualization/layout/formatters.js';
import { normalizeChartSpec } from '../src/components/visualization/normalize/normalizeChartSpec.js';
import { repairChartLayout, RepairAction } from '../src/components/visualization/repair/repairChartLayout.js';

console.log('🧪 Starting Visual Guard & Presentation Engine Tests...\n');

// 1. Schema Validation Tests
console.log('1. Testing Schema Validation...');
{
  // Rejects null / non-object
  const res1 = validateChartSpec(null);
  assert.equal(res1.isValid, false);
  assert.equal(res1.errors[0].code, SchemaErrorCode.INVALID_INPUT);

  // Rejects empty series
  const res2 = validateChartSpec({ chart_type: 'bar', categories: ['A', 'B'], series: [] });
  assert.equal(res2.isValid, false);
  assert.equal(res2.errors[0].code, SchemaErrorCode.EMPTY_SERIES);

  // Rejects missing categories on Cartesian
  const res3 = validateChartSpec({ chart_type: 'bar', series: [{ name: 'V', data: [1, 2] }] });
  assert.equal(res3.isValid, false);
  assert.equal(res3.errors[0].code, SchemaErrorCode.MISSING_CATEGORIES);

  // Accepts valid column chart
  const res4 = validateChartSpec({
    chart_type: 'column',
    categories: ['Engineering', 'Sales', 'Marketing'],
    series: [{ name: 'Headcount', data: [120, 85, 45] }]
  });
  assert.equal(res4.isValid, true);
  assert.equal(res4.cleanType, 'column');

  // Accepts breakdown tree
  const res5 = validateChartSpec({
    type: 'breakdown_tree',
    tree_data: { name: 'Total Headcount', value: 250, children: [] }
  });
  assert.equal(res5.isValid, true);
  assert.equal(res5.cleanType, 'breakdown_tree');
}
console.log('   ✅ Schema validation tests passed.');

// 2. Pre-Render Layout & Orientation Tests
console.log('2. Testing Pre-Render Layout & Orientation Rules...');
{
  // < 10 categories + short labels -> Vertical bar
  const shortCats = ['Q1', 'Q2', 'Q3', 'Q4'];
  assert.equal(requiresHorizontalOrientation(shortCats.length, 2), false);
  const layout1 = calculateChartLayout({
    type: 'column',
    categories: shortCats,
    series: [{ name: 'Rev', data: [100, 120, 140, 160] }]
  });
  assert.equal(layout1.isVertical, true);

  // > 10 categories -> Automatic Flip to Horizontal Bar
  const manyCats = Array.from({ length: 14 }, (_, i) => `Dept ${i + 1}`);
  assert.equal(requiresHorizontalOrientation(manyCats.length, 6), true);
  const layout2 = calculateChartLayout({
    type: 'column',
    categories: manyCats,
    series: [{ name: 'Count', data: manyCats.map((_, i) => (i + 1) * 10) }]
  });
  assert.equal(layout2.isVertical, false, 'Should flip to horizontal bar when > 10 categories');

  // Long category labels (>16 chars) -> Automatic Flip to Horizontal Bar
  const longCats = ['Customer Support & Operations', 'Talent Acquisition & HR', 'Finance & Accounting'];
  const maxLen = Math.max(...longCats.map(c => c.length));
  assert.equal(requiresHorizontalOrientation(longCats.length, maxLen), true);
  const layout3 = calculateChartLayout({
    type: 'column',
    categories: longCats,
    series: [{ name: 'Budget', data: [500000, 320000, 410000] }]
  });
  assert.equal(layout3.isVertical, false, 'Should flip to horizontal bar when label chars > 16');

  // > 25 categories -> Automatic Top-N Consolidation
  const largeCats = Array.from({ length: 30 }, (_, i) => `Cat ${i + 1}`);
  const largeData = largeCats.map((_, i) => (i + 1) * 5);
  const layout4 = calculateChartLayout({
    type: 'column',
    categories: largeCats,
    series: [{ name: 'Metric', data: largeData }]
  });
  assert.equal(layout4.isConsolidated, true);
  assert.equal(layout4.hiddenCount, 20);
  assert.equal(layout4.categories.length, 11); // Top 10 + 1 Other
  assert.ok(layout4.categories[10].includes('Other (20 items)'));
}
console.log('   ✅ Pre-render layout & orientation tests passed.');

// 3. Dynamic Margins & Number Formatters Tests
console.log('3. Testing Dynamic Margins & Number Formatting...');
{
  // Number compaction
  assert.equal(formatCompactNumber(1250000), '1.3M');
  assert.equal(formatCompactNumber(45000), '45K');
  assert.equal(formatCompactNumber(1000000000), '1B');
  assert.equal(formatCompactNumber(85.5, '%'), '85.5%');
  assert.equal(formatCompactNumber(54000, '$'), '$54K');

  // Dynamic Margins for long labels
  const longCats = ['Enterprise Customer Success Operations', 'Supply Chain Global Logistics'];
  const margins = calculateMargins({
    categories: longCats,
    isVertical: false,
    hasLegend: true
  });
  assert.ok(margins.left >= 150, `Left margin should be >= 150px, got ${margins.left}`);
  assert.ok(margins.bottom >= 64, `Bottom margin should account for legend, got ${margins.bottom}`);
}
console.log('   ✅ Dynamic margin and number formatting tests passed.');

// 4. Normalizer Output Verification
console.log('4. Testing Visualization Normalizer...');
{
  const rawSpec = {
    title: 'Department Productivity',
    chart_type: 'column',
    unit: '$',
    categories: ['Engineering', 'Marketing', 'Sales'],
    series: [{ name: 'Spend', data: [1200000, 450000, 800000] }]
  };

  const norm = normalizeChartSpec(rawSpec);
  assert.equal(norm.isValid, true);
  assert.ok(norm.option.grid);
  assert.ok(norm.option.xAxis);
  assert.ok(norm.option.yAxis);
  assert.equal(norm.option.yAxis.axisLabel.fontSize, VISUAL_POLICY.MIN_AXIS_FONT_SIZE);
  assert.equal(norm.option.title.textStyle.fontSize, VISUAL_POLICY.MIN_TITLE_FONT_SIZE);
}
console.log('   ✅ Visualization Normalizer tests passed.');

// 5. Deterministic Auto-Repair Cascade Tests
console.log('5. Testing Deterministic Auto-Repair Priority Chain...');
{
  const baseOption = {
    grid: { left: 48, right: 24, bottom: 40, top: 36 },
    xAxis: { type: 'category', data: ['A', 'B', 'C'] },
    yAxis: { type: 'value' }
  };

  // 1. Repair Y-Axis Clipping
  const repair1 = repairChartLayout(baseOption, { yAxisClipped: true });
  assert.ok(repair1.repairsApplied.length > 0);
  assert.equal(repair1.repairsApplied[0].action, RepairAction.EXPAND_LEFT_MARGIN);
  assert.equal(repair1.repairedOption.grid.left, 72);

  // 2. Repair X-Axis Label Crowding
  const repair2 = repairChartLayout(baseOption, { xAxisCrowded: true });
  assert.ok(repair2.repairsApplied.length > 0);
  assert.equal(repair2.repairsApplied[0].action, RepairAction.ROTATE_X_LABELS);
  assert.equal(repair2.repairedOption.xAxis.axisLabel.rotate, 45);
  assert.equal(repair2.repairedOption.grid.bottom, 60);

  // 3. Repair Vertical Overflow
  const repair3 = repairChartLayout(baseOption, { hasVerticalOverflow: true });
  assert.ok(repair3.repairsApplied.length > 0);
  assert.equal(repair3.repairedOption.grid.top, 20);
}
console.log('   ✅ Deterministic Auto-Repair tests passed.');

// 6. Label Humanization & Underscore Auto-Repair Tests
console.log('6. Testing Label Humanization & Underscore Auto-Repair...');
{
  const { humanizeLabel } = await import('../src/components/visualization/layout/formatters.js');
  const { detectUnderscoresInOption } = await import('../src/components/visualization/observers/useVisualQA.js');

  // Test humanizeLabel transforms
  assert.equal(humanizeLabel('turnover_rate'), 'Turnover Rate');
  assert.equal(humanizeLabel('interact_mean_department_name'), 'Department Name');
  assert.equal(humanizeLabel('employee_hr_id'), 'Employee HR ID');
  assert.equal(humanizeLabel('annual_fte_count'), 'Annual FTE Count');
  assert.equal(humanizeLabel('turnover_by_department'), 'Turnover by Department');
  assert.equal(humanizeLabel('actual_vs_target'), 'Actual vs Target');
  assert.equal(humanizeLabel('department_name: software_engineer'), 'Department Name: Software Engineer');

  // Test detectUnderscoresInOption
  assert.equal(detectUnderscoresInOption({ xAxis: { data: ['Clean A', 'Clean B'] } }), false);
  assert.equal(detectUnderscoresInOption({ xAxis: { data: ['dirty_a', 'dirty_b'] } }), true);
  assert.equal(detectUnderscoresInOption({ series: [{ name: 'dirty_metric', data: [1, 2] }] }), true);

  // Test normalizeChartSpec automatically cleans underscore tokens
  const normWithUnderscores = normalizeChartSpec({
    title: 'employee_attrition_rate',
    chart_type: 'column',
    categories: ['sales_dept', 'eng_dept', 'hr_ops'],
    series: [{ name: 'attrition_count', data: [12, 18, 5] }]
  });
  assert.equal(normWithUnderscores.isValid, true);
  assert.equal(normWithUnderscores.option.title.text, 'Employee Attrition Rate');
  assert.deepEqual(normWithUnderscores.option.xAxis.data, ['Sales Dept', 'Eng Dept', 'HR Ops']);
  assert.equal(normWithUnderscores.option.series[0].name, 'Attrition Count');

  // Test repairChartLayout repairs underscores when detected
  const unhumanizedOption = {
    title: { text: 'gross_margin_variance' },
    xAxis: { data: ['product_a', 'product_b'] },
    series: [{ name: 'revenue_leakage', data: [{ name: 'item_one', value: 100 }] }]
  };
  const repair4 = repairChartLayout(unhumanizedOption, { hasUnderscoreLabels: true });
  assert.ok(repair4.repairsApplied.some(r => r.action === RepairAction.HUMANIZE_LABELS));
  assert.equal(repair4.repairedOption.title.text, 'Gross Margin Variance');
  assert.deepEqual(repair4.repairedOption.xAxis.data, ['Product A', 'Product B']);
  assert.equal(repair4.repairedOption.series[0].name, 'Revenue Leakage');
  assert.equal(repair4.repairedOption.series[0].data[0].name, 'Item One');
}
console.log('   ✅ Label Humanization & Underscore Auto-Repair tests passed.');

console.log('\n🎉 ALL VISUAL GUARD & PRESENTATION ENGINE TESTS PASSED!\n');
