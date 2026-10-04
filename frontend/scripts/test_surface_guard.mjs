import assert from 'node:assert/strict';
import {
  sanitizeText,
  sanitizeTitle,
  sanitizeMetric,
  hasUnderscores
} from '../src/components/guard/surfaceSanitizer.js';

console.log('🧪 Testing SurfaceGuard Sanitization Engine...\n');

// Test 1: Title Sanitization for the User's Exact Problem Case
{
  const dirtyTitle = "Unusual interact_ratio_math score + reading score_over_math score / writing score in group A";
  const cleanTitle = sanitizeTitle(dirtyTitle);
  console.log(`Input:  ${dirtyTitle}`);
  console.log(`Output: ${cleanTitle}`);
  assert.equal(hasUnderscores(cleanTitle), false, "Clean title must contain 0 underscores");
  assert.ok(cleanTitle.startsWith("Unusual "), "Must preserve 'Unusual' prefix");
  assert.ok(cleanTitle.includes(" in Group a") || cleanTitle.includes(" in group A") || cleanTitle.includes(" in Group A"), "Must preserve group suffix");
  assert.ok(!cleanTitle.includes("interact_"), "Must eliminate 'interact_' prefix");
  assert.ok(!cleanTitle.includes("_over_"), "Must eliminate '_over_' delimiter");
  console.log('✅ Test 1 Passed: User complaint case sanitized with 0 underscores\n');
}

// Test 2: Machine Group Mean Sanitization
{
  const dirtyGroupMean = "interact_mean_math_score_by_gender";
  const clean = sanitizeText(dirtyGroupMean);
  console.log(`Input:  ${dirtyGroupMean}`);
  console.log(`Output: ${clean}`);
  assert.equal(hasUnderscores(clean), false, "Group mean must contain 0 underscores");
  assert.ok(clean.toLowerCase().includes("math score by gender"), "Must cleanly describe calculation");
  console.log('✅ Test 2 Passed: Group mean sanitized with 0 underscores\n');
}

// Test 3: Standard snake_case and Acronym Preservation
{
  const colWithAcronym = "weekly_sales_cpi_index";
  const clean = sanitizeText(colWithAcronym);
  console.log(`Input:  ${colWithAcronym}`);
  console.log(`Output: ${clean}`);
  assert.equal(hasUnderscores(clean), false);
  assert.ok(clean.includes("CPI"), "Acronym CPI must be preserved in uppercase");
  console.log('✅ Test 3 Passed: Acronyms preserved\n');
}

// Test 4: Unusual Period Date Title
{
  const dateTitle = "Unusual period: 2026-10-04";
  const clean = sanitizeTitle(dateTitle);
  console.log(`Input:  ${dateTitle}`);
  console.log(`Output: ${clean}`);
  assert.equal(clean, "Unusual period: Oct 4, 2026");
  console.log('✅ Test 4 Passed: Date titles handled\n');
}

// Test 5: Metric Value Sanitizer
{
  assert.equal(sanitizeMetric(1250000, "$"), "$1.3M");
  assert.equal(sanitizeMetric(45200, ""), "45.2K");
  assert.equal(sanitizeMetric(12.5, "%"), "12.5%");
  assert.equal(sanitizeMetric(null), "—");
  console.log('✅ Test 5 Passed: Compact metric values formatted\n');
}

console.log('🎉 All SurfaceGuard tests passed cleanly!\n');
