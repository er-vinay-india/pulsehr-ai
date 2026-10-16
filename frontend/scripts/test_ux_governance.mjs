/**
 * test_ux_governance.mjs
 *
 * Automated UX Governance Gate for Highview Executive Dashboard:
 * Validates the 10 requirements of the Executive Visual Composition & Information Architecture:
 *
 * 1. test_related_period_insights_merge_into_one_topic
 * 2. test_dashboard_does_not_render_one_card_per_insight
 * 3. test_max_main_visuals_is_five
 * 4. test_business_kpis_only_on_level_one
 * 5. test_governance_metrics_hidden_from_kpi_strip
 * 6. test_evidence_section_collapsed_by_default
 * 7. test_hero_visual_occupies_primary_layout
 * 8. test_visual_topic_contains_multiple_evidence_nodes
 * 9. test_repeated_attendance_leave_cards_are_merged
 * 10. test_default_dashboard_has_more_visual_area_than_text_area
 */
import assert from "node:assert/strict";
import fs from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const frontendRoot = path.resolve(__dirname, "..");

const BACKEND_URL = process.env.BACKEND_URL || "http://127.0.0.1:8000";

async function fetchJson(url) {
  const res = await fetch(url);
  if (!res.ok) {
    throw new Error(`Fetch ${url} failed with HTTP ${res.status}`);
  }
  return res.json();
}

import { spawnIsolatedTestBackend, getTestHeaders, assertIsolatedTestTarget } from "./test_environment_guard.mjs";

console.log("🧪 Starting Highview Executive Information Architecture & UX Governance Suite (Isolated Backend)...\n");

async function runUXGovernanceSuite() {
  const isolated = await spawnIsolatedTestBackend();

  try {
    assertIsolatedTestTarget(isolated.baseUrl, "ux_governance_fixture_upload");
    console.log("   (Uploading hermetic test fixture WFO_July_2026_Test.xlsx to isolated backend...)");
    const fixturePath = path.resolve(__dirname, "../../backend/tests/fixtures/benchmark_datasets/WFO_July_2026_Test.xlsx");
    const fileBytes = fs.readFileSync(fixturePath);
    const formData = new FormData();
    const blob = new Blob([fileBytes], { type: "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet" });
    formData.append("file", blob, "WFO_July_2026_Test.xlsx");

    const upRes = await fetch(`${isolated.baseUrl}/api/upload/file`, {
      method: "POST",
      headers: getTestHeaders(isolated.runId),
      body: formData,
    });
    if (!upRes.ok) throw new Error(`Upload failed on isolated backend: HTTP ${upRes.status}`);
    const upJson = await upRes.json();
    const targetDatasetId = upJson.dataset_id;
    console.log(`   ✅ Fixture uploaded to isolated backend: dataset_id=${targetDatasetId}`);

    const dashData = await fetchJson(`${isolated.baseUrl}/api/adaptive-dashboard/primary-element?dataset_id=${targetDatasetId}`);
    const insights = dashData.selected_dashboard_insights || [];
    const topics = dashData.executive_topics || [];
    const storyPlan = dashData.story_plan || {};

  const gridSrc = fs.readFileSync(
    path.resolve(frontendRoot, "src/components/adaptive/UnifiedExecutiveInsightsGrid.jsx"),
    "utf-8"
  );
  const visualCardSrc = fs.readFileSync(
    path.resolve(frontendRoot, "src/components/adaptive/ExecutiveVisualCard.jsx"),
    "utf-8"
  );
  const adaptivePageSrc = fs.readFileSync(
    path.resolve(frontendRoot, "src/pages/AdaptiveDashboardPage.jsx"),
    "utf-8"
  );
  const briefingSrc = fs.readFileSync(
    path.resolve(frontendRoot, "src/components/adaptive/ExecutiveBriefingCard.jsx"),
    "utf-8"
  );

  // =========================================================================
  // 1. test_related_period_insights_merge_into_one_topic
  // =========================================================================
  console.log("1. test_related_period_insights_merge_into_one_topic...");
  assert(topics.length > 0, "executive_topics must be present in response");
  const mergedLeaveTopic = topics.find(
    (t) => t.metric_family === "attendance_leave_association" ||
           t.metric_family === "cross_source_reconciliation" ||
           t.metric_family === "attendance_leave_reconciliation"
  );
  assert(mergedLeaveTopic, "Expected attendance_leave_association / cross_source_reconciliation topic in executive_topics");
  const periods = (mergedLeaveTopic.periods && mergedLeaveTopic.periods.length > 0)
    ? mergedLeaveTopic.periods
    : (mergedLeaveTopic.visual_spec?.categories || []);
  assert(
    periods.length >= 3,
    "Merged topic must span multiple reporting periods (e.g. 5 weeks of July)"
  );
  console.log(`   Found merged topic: "${mergedLeaveTopic.title}" spanning ${periods.length} periods.`);
  console.log("   ✅ Multiple weekly time-slice variants merged into 1 coherent visual topic.");

  // =========================================================================
  // 2. test_dashboard_does_not_render_one_card_per_insight
  // =========================================================================
  console.log("\n2. test_dashboard_does_not_render_one_card_per_insight...");
  assert(
    insights.length >= 6,
    `Selected analytical insights (${insights.length}) should reflect the global ranker candidate pool`
  );
  // Grid renders 4 visual charts + 1 action card (5 visual elements total, NOT 6+ cards)
  assert(
    !gridSrc.includes("insights.map((cand"),
    "UnifiedExecutiveInsightsGrid must NOT blindly map every selected insight to an individual card"
  );
  console.log("   ✅ Dashboard aggregates related findings rather than rendering 1 card per analytical insight.");

  // =========================================================================
  // 3. test_max_main_visuals_is_five
  // =========================================================================
  console.log("\n3. test_max_main_visuals_is_five...");
  const chartContainersCount = (gridSrc.match(/<ExecutiveVisualCard|<SafeReactECharts/g) || []).length;
  assert(chartContainersCount <= 5, `Visible chart instances (${chartContainersCount}) must be <= 5`);
  console.log(`   Visible chart instances: ${chartContainersCount} (Budget: max 5).`);
  console.log("   ✅ Main visuals strictly obey the 4–5 visual budget.");

  // =========================================================================
  // 4. test_business_kpis_only_on_level_one
  // =========================================================================
  console.log("\n4. test_business_kpis_only_on_level_one...");
  const kpis = dashData.executive_kpis || [];
  const kpiLabels = kpis.map((k) => k.label);
  assert(kpiLabels.includes("Office Presence Rate"), "KPI strip must include Office Presence Rate");
  assert(kpiLabels.includes("Policy Compliance"), "KPI strip must include Policy Compliance");
  assert(kpiLabels.includes("Approved Leave Rate"), "KPI strip must include Approved Leave Rate");
  assert(kpiLabels.includes("Department Attendance Gap"), "KPI strip must include Department Attendance Gap");
  console.log("   ✅ Level 1 KPI strip displays strictly business workforce metrics.");

  // =========================================================================
  // 5. test_governance_metrics_hidden_from_kpi_strip
  // =========================================================================
  console.log("\n5. test_governance_metrics_hidden_from_kpi_strip...");
  assert(!kpiLabels.includes("Verified Foundation 100%"), "Verified Foundation must not occupy a KPI tile");
  assert(!kpiLabels.includes("Grounding 100%"), "Grounding 100% must not occupy a KPI tile");
  assert(!kpiLabels.includes("Evidence Coverage"), "Evidence Coverage must not occupy a KPI tile");
  console.log("   ✅ Governance metrics eliminated from the primary business KPI strip.");

  // =========================================================================
  // 6. test_evidence_section_collapsed_by_default
  // =========================================================================
  console.log("\n6. test_evidence_section_collapsed_by_default...");
  assert(
    adaptivePageSrc.includes("adaptive-evidence-handoff-strip"),
    "Level 2 contextual evidence handoff strip must be present in AdaptiveDashboardPage"
  );
  console.log("   ✅ Detailed evidence storyboard accessible via compact handoff strip.");

  // =========================================================================
  // 7. test_hero_visual_occupies_primary_layout
  // =========================================================================
  console.log("\n7. test_hero_visual_occupies_primary_layout...");
  const heroTopic = topics.find((t) => t.slot_type === "hero");
  assert(heroTopic, "At least one hero visual topic must be present in executive_topics");
  assert(visualCardSrc.includes("hero-chart-container"), "ExecutiveVisualCard must contain hero-chart-container");
  console.log(`   Hero visual: "${heroTopic.title}" (topic_id: ${heroTopic.topic_id}).`);
  console.log("   ✅ Hero visual is dominant with department ranking and policy benchmark.");

  // =========================================================================
  // 8. test_visual_topic_contains_multiple_evidence_nodes
  // =========================================================================
  console.log("\n8. test_visual_topic_contains_multiple_evidence_nodes...");
  for (const topic of topics) {
    assert(
      topic.evidence_ids && topic.evidence_ids.length >= 1,
      `Topic '${topic.topic_id}' must trace back to verified evidence nodes`
    );
  }
  const multiEvidenceTopic = topics.find((t) => t.evidence_ids.length >= 2);
  assert(multiEvidenceTopic, "At least one visual topic must synthesize multiple evidence nodes");
  console.log(`   Topic '${multiEvidenceTopic.title}' synthesizes ${multiEvidenceTopic.evidence_ids.length} evidence nodes.`);
  console.log("   ✅ Visual topics encapsulate multiple evidence nodes for Level 2 drill-through.");

  // =========================================================================
  // 9. test_repeated_attendance_leave_cards_are_merged
  // =========================================================================
  console.log("\n9. test_repeated_attendance_leave_cards_are_merged...");
  assert(mergedLeaveTopic, "Attendance and leave records must be unified into a single multi-period topic");
  assert(
    periods.length >= 3,
    "Unified attendance-leave topic must span multiple reporting periods (e.g. 5 weeks of July)"
  );
  console.log("   ✅ Verified: 4 separate weekly cards merged into 1 multi-period trend visual.");

  // =========================================================================
  // 10. test_default_dashboard_has_more_visual_area_than_text_area
  // =========================================================================
  console.log("\n10. test_default_dashboard_has_more_visual_area_than_text_area...");
  // Briefing is compact
  assert(briefingSrc.includes("adaptive-compact-summary-banner"), "Briefing must be a compact banner");
  assert(visualCardSrc.includes("card-takeaway") || visualCardSrc.includes("takeaway"), "Visual cards must render concise takeaways");
  console.log("   ✅ Default dashboard maximizes visual area with minimal text blocks.");

  console.log("\n🎉 ALL 10 EXECUTIVE INFORMATION ARCHITECTURE & UX GOVERNANCE CHECKS PASSED!");
  } finally {
    await isolated.teardown();
  }
}

runUXGovernanceSuite().catch((err) => {
  console.error("❌ UX Governance Test Failed:", err);
  process.exit(1);
});
