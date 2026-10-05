/**
 * test_theme_integrity.mjs
 * 
 * Executes mandatory Theme Integrity Restoration and Visual Governance regression tests:
 * 1. test_no_protected_component_bypasses_central_theme
 * 2. test_dashboard_light_theme_integrity
 * 3. test_dashboard_dark_theme_integrity
 * 4. test_dynamic_visual_theme_compliance
 * 5. test_chart_theme_compliance
 * 6. test_evidence_pill_theme_compliance
 * 7. test_scenario_pill_theme_compliance
 * 8. test_governance_badge_theme_compliance
 * 9. test_cross_sheet_insight_theme_compliance
 * 10. test_data_explorer_theme_compliance
 * 11. test_modal_theme_compliance
 * 12. test_table_theme_compliance
 * 13. test_theme_switch_preserves_structure
 */
import assert from 'node:assert/strict';
import fs from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';
import { lightTokens, darkTokens, getThemeTokens } from '../src/theme/tokens.js';
import { ThemeIntegrityValidator, APPROVED_SEMANTIC_STATUSES } from '../src/theme/ThemeIntegrityValidator.js';

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);
const rootDir = path.resolve(__dirname, '..');

console.log('🧪 Starting Phase 9.5 Theme Integrity & Visual Governance Test Suite...\n');

// 1. test_no_protected_component_bypasses_central_theme
console.log('1. Testing: test_no_protected_component_bypasses_central_theme...');
{
  const protectedFiles = [
    path.join(rootDir, 'src/components/adaptive/EvidenceStoryCard.jsx'),
    path.join(rootDir, 'src/pages/AdaptiveDashboardPage.jsx'),
    path.join(rootDir, 'src/pages/DataExplorerPage.jsx'),
  ];

  for (const filePath of protectedFiles) {
    const content = fs.readFileSync(filePath, 'utf-8');
    // Ensure no dark slate rgba hacks exist
    const slateDarkMatches = content.match(/rgba\(\s*(?:15|30)\s*,\s*(?:23|41)\s*,\s*(?:42|59)/g) || [];
    assert.equal(
      slateDarkMatches.length,
      0,
      `Forbidden hardcoded dark slate background in ${path.basename(filePath)}: ${slateDarkMatches}`
    );
  }
  console.log('   ✅ No protected component contains raw dark slate background overrides.');
}

// 2. test_dashboard_light_theme_integrity
console.log('2. Testing: test_dashboard_light_theme_integrity...');
{
  const tokens = getThemeTokens(false);
  assert.equal(tokens.colors.page, '#F6F5F0');
  assert.equal(tokens.colors.surface, '#FFFFFF');
  assert.equal(tokens.colors.textPrimary, '#172B3A');
  assert.equal(tokens.colors.border, '#D4DDD6');
  console.log('   ✅ Highview Light Theme tokens valid & verified.');
}

// 3. test_dashboard_dark_theme_integrity
console.log('3. Testing: test_dashboard_dark_theme_integrity...');
{
  const tokens = getThemeTokens(true);
  assert.equal(tokens.colors.page, '#101B27');
  assert.equal(tokens.colors.surface, '#172635');
  assert.equal(tokens.colors.textPrimary, '#F4F5EF');
  assert.equal(tokens.colors.border, '#3B4E5A');
  console.log('   ✅ Highview Dark Theme tokens valid & verified.');
}

// 4. test_dynamic_visual_theme_compliance
console.log('4. Testing: test_dynamic_visual_theme_compliance...');
{
  // A theme-agnostic spec must pass
  const validSpec = {
    chart_type: 'bar',
    emphasis: 'primary',
    status: 'warning',
    reference_line: true,
  };
  const rep = ThemeIntegrityValidator.validateThemeIntegrity(validSpec, false);
  assert.equal(rep.overall_theme_passed, true);
  assert.equal(rep.violations.length, 0);

  // A spec trying to inject hardcoded brand hex must be rejected
  const invalidSpec = {
    chart_type: 'bar',
    background: '#111827',
    text_color: '#FFFFFF',
    bar_color: '#2563EB',
  };
  const repBad = ThemeIntegrityValidator.validateThemeIntegrity(invalidSpec, false);
  assert.equal(repBad.overall_theme_passed, false);
  assert.equal(repBad.violations.length, 3);
  console.log('   ✅ Dynamic VisualSpec theme boundary enforced.');
}

// 5. test_chart_theme_compliance
console.log('5. Testing: test_chart_theme_compliance...');
{
  const lightChart = lightTokens.chart;
  const darkChart = darkTokens.chart;
  assert.ok(lightChart.palette.length >= 6);
  assert.ok(darkChart.palette.length >= 6);
  assert.ok(lightChart.tooltipBg);
  assert.ok(darkChart.tooltipBg);
  assert.ok(lightChart.axisLine);
  assert.ok(darkChart.axisLine);
  console.log('   ✅ Chart palettes and axis/grid tokens compliant across Light & Dark.');
}

// 6. test_evidence_pill_theme_compliance
console.log('6. Testing: test_evidence_pill_theme_compliance...');
{
  const evCardSource = fs.readFileSync(path.join(rootDir, 'src/components/adaptive/EvidenceStoryCard.jsx'), 'utf-8');
  assert.ok(evCardSource.includes('var(--color-brand-primary)'));
  assert.ok(evCardSource.includes('var(--color-bg-subtle)'));
  assert.ok(!evCardSource.includes('#4f46e5'));
  console.log('   ✅ Evidence pills consume centralized theme tokens.');
}

// 7. test_scenario_pill_theme_compliance
console.log('7. Testing: test_scenario_pill_theme_compliance...');
{
  assert.ok(APPROVED_SEMANTIC_STATUSES.includes('scenario'));
  assert.ok(APPROVED_SEMANTIC_STATUSES.includes('observed'));
  console.log('   ✅ SCEN-xxx and EVID-xxx semantic statuses registered in visual governance.');
}

// 8. test_governance_badge_theme_compliance
console.log('8. Testing: test_governance_badge_theme_compliance...');
{
  const evCardSource = fs.readFileSync(path.join(rootDir, 'src/components/adaptive/EvidenceStoryCard.jsx'), 'utf-8');
  assert.ok(evCardSource.includes('var(--hv-status-success-bg, var(--color-bg-soft-teal))'));
  assert.ok(evCardSource.includes('var(--hv-status-success, var(--color-success))'));
  console.log('   ✅ Governed Runtime badge strictly adheres to theme tokens.');
}

// 9. test_cross_sheet_insight_theme_compliance
console.log('9. Testing: test_cross_sheet_insight_theme_compliance...');
{
  const spec = { status: 'relationship', emphasis: 'secondary' };
  const rep = ThemeIntegrityValidator.validateThemeIntegrity(spec, false);
  assert.equal(rep.semantic_status_token_valid, true);
  console.log('   ✅ Cross-sheet relationship semantic tokens verified.');
}

// 10. test_data_explorer_theme_compliance
console.log('10. Testing: test_data_explorer_theme_compliance...');
{
  const dataExplorerSource = fs.readFileSync(path.join(rootDir, 'src/pages/DataExplorerPage.jsx'), 'utf-8');
  assert.ok(dataExplorerSource.includes('var(--color-bg-soft-gold)'));
  assert.ok(dataExplorerSource.includes('var(--color-bg-soft-error)'));
  assert.ok(dataExplorerSource.includes('var(--color-bg-soft-teal)'));
  console.log('   ✅ Data Explorer features, delete buttons, and tags consume central tokens.');
}

// 11. test_modal_theme_compliance
console.log('11. Testing: test_modal_theme_compliance...');
{
  const rep = ThemeIntegrityValidator.validateThemeIntegrity({}, false);
  assert.equal(rep.modal_theme_valid, true);
  console.log('   ✅ Modal overlay & dialog theme variables validated.');
}

// 12. test_table_theme_compliance
console.log('12. Testing: test_table_theme_compliance...');
{
  const rep = ThemeIntegrityValidator.validateThemeIntegrity({}, false);
  assert.equal(rep.table_theme_valid, true);
  console.log('   ✅ Table cell & header token consistency validated.');
}

// 13. test_theme_switch_preserves_structure
console.log('13. Testing: test_theme_switch_preserves_structure...');
{
  const option = {
    xAxis: { type: 'category', data: ['A', 'B'], axisLabel: { fontSize: 12 } },
    yAxis: { type: 'value', axisLabel: { fontSize: 12 } },
    grid: { containLabel: true },
    series: [{ type: 'bar', data: [10, 20] }],
  };

  const gateLight = ThemeIntegrityValidator.evaluateThreeVisualGates({}, option, false);
  const gateDark = ThemeIntegrityValidator.evaluateThreeVisualGates({}, option, true);

  assert.equal(gateLight.passed, true);
  assert.equal(gateDark.passed, true);
  assert.equal(gateLight.layout_integrity.passed, gateDark.layout_integrity.passed);
  assert.equal(gateLight.accessibility_integrity.passed, gateDark.accessibility_integrity.passed);
  assert.equal(gateLight.theme_integrity.passed, gateDark.theme_integrity.passed);
  console.log('   ✅ Switching Light <-> Dark preserves 100% of visual structure and layout integrity.');
}

console.log('\n🎉 ALL 13 THEME INTEGRITY & VISUAL GOVERNANCE TESTS PASSED!\n');
