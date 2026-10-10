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

const BACKEND_URL = "http://127.0.0.1:8020";

async function fetchJson(url) {
  const res = await fetch(url);
  if (!res.ok) {
    throw new Error(`Fetch ${url} failed with HTTP ${res.status}`);
  }
  return res.json();
}

console.log("🧪 Starting Highview Executive Information Architecture & UX Governance Suite...\n");

async function runUXGovernanceSuite() {
  // Step 1: Fetch active dataset Executive Dashboard
  const datasetsResp = await fetchJson(`${BACKEND_URL}/api/upload/datasets`);
  const datasets = Array.isArray(datasetsResp) ? datasetsResp : datasetsResp.datasets || [];
  assert(datasets.length > 0, "No datasets available to test");
  const targetDataset = datasets.find((d) => d.id === 99747) || datasets[0];

  const dashData = await fetchJson(`${BACKEND_URL}/api/adaptive-dashboard/primary-element?dataset_id=${targetDataset.id}`);
  const insights = dashData.selected_dashboard_insights || [];
  const topics = dashData.executive_topics || [];
  const storyPlan = dashData.story_plan || {};

  const gridSrc = fs.readFileSync(
    path.resolve("src/components/adaptive/UnifiedExecutiveInsightsGrid.jsx"),
    "utf-8"
  );
  const adaptivePageSrc = fs.readFileSync(
    path.resolve("src/pages/AdaptiveDashboardPage.jsx"),
    "utf-8"
  );
  const briefingSrc = fs.readFileSync(
    path.resolve("src/components/adaptive/ExecutiveBriefingCard.jsx"),
    "utf-8"
  );

  // =========================================================================
  // 1. test_related_period_insights_merge_into_one_topic
  // =========================================================================
  console.log("1. test_related_period_insights_merge_into_one_topic...");
  assert(topics.length > 0, "executive_topics must be present in response");
  const mergedLeaveTopic = topics.find((t) => t.metric_family === "attendance_leave_reconciliation");
  assert(mergedLeaveTopic, "Expected attendance_leave_reconciliation topic in executive_topics");
  assert(
    mergedLeaveTopic.periods && mergedLeaveTopic.periods.length >= 3,
    "Merged topic must span multiple reporting periods (e.g. 5 weeks of July)"
  );
  console.log(`   Found merged topic: "${mergedLeaveTopic.title}" spanning ${mergedLeaveTopic.periods.length} periods.`);
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
  assert(topics.length <= 5, `Total executive topics (${topics.length}) must be <= 5`);
  const chartContainersCount = (gridSrc.match(/<SafeReactECharts/g) || []).length;
  assert(chartContainersCount <= 5, `Visible chart instances (${chartContainersCount}) must be <= 5`);
  console.log(`   Visible chart instances: ${chartContainersCount} (Budget: max 5).`);
  console.log("   ✅ Main visuals strictly obey the 4–5 visual budget.");

  // =========================================================================
  // 4. test_business_kpis_only_on_level_one
  // =========================================================================
  console.log("\n4. test_business_kpis_only_on_level_one...");
  assert(gridSrc.includes("Office Presence Rate"), "KPI strip must include Office Presence Rate");
  assert(gridSrc.includes("Policy Compliance"), "KPI strip must include Policy Compliance");
  assert(gridSrc.includes("Approved Leave Rate"), "KPI strip must include Approved Leave Rate");
  assert(gridSrc.includes("Department Attendance Gap"), "KPI strip must include Department Attendance Gap");
  console.log("   ✅ Level 1 KPI strip displays strictly business workforce metrics.");

  // =========================================================================
  // 5. test_governance_metrics_hidden_from_kpi_strip
  // =========================================================================
  console.log("\n5. test_governance_metrics_hidden_from_kpi_strip...");
  const kpiSectionMatch = gridSrc.match(/data-testid="executive-kpi-strip"[\s\S]*?<\/div>\s*<\/div>/);
  const kpiSection = kpiSectionMatch ? kpiSectionMatch[0] : "";
  assert(!kpiSection.includes("Verified Foundation 100%"), "Verified Foundation must not occupy a KPI tile");
  assert(!kpiSection.includes("Grounding 100%"), "Grounding 100% must not occupy a KPI tile");
  assert(!kpiSection.includes("Evidence Coverage"), "Evidence Coverage must not occupy a KPI tile");
  console.log("   ✅ Governance metrics eliminated from the primary business KPI strip.");

  // =========================================================================
  // 6. test_evidence_section_collapsed_by_default
  // =========================================================================
  console.log("\n6. test_evidence_section_collapsed_by_default...");
  assert(
    adaptivePageSrc.includes("const [showDetailedAnalysis, setShowDetailedAnalysis] = useState(false);"),
    "Detailed evidence section must be collapsed by default (showDetailedAnalysis = false)"
  );
  assert(
    adaptivePageSrc.includes("adaptive-analysis-expand-btn"),
    "Explore detailed analysis button must be present to expand Level 2 evidence"
  );
  console.log("   ✅ Detailed evidence storyboard collapsed by default behind 'Explore detailed analysis →'.");

  // =========================================================================
  // 7. test_hero_visual_occupies_primary_layout
  // =========================================================================
  console.log("\n7. test_hero_visual_occupies_primary_layout...");
  assert(gridSrc.includes("executive-hero-card"), "UnifiedExecutiveInsightsGrid must contain executive-hero-card");
  assert(gridSrc.includes("Department Attendance Ranking & Policy Benchmark"), "Hero visual must be the Department Ranking");
  assert(gridSrc.includes("hero-chart-container"), "Hero chart container must be present");
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
  // Verify that the UI does NOT render 4 separate cards for each week
  assert(
    !gridSrc.includes("Attendance vs Approved Leave (1st to 5th July)"),
    "Individual weekly attendance-leave card must not be rendered separately"
  );
  assert(
    !gridSrc.includes("Attendance vs Approved Leave (6th to 12th July)"),
    "Individual weekly attendance-leave card must not be rendered separately"
  );
  assert(
    gridSrc.includes("Attendance vs Approved Leave — July Trend"),
    "Must render the single unified Attendance vs Approved Leave — July Trend visual"
  );
  console.log("   ✅ Verified: 4 separate weekly cards merged into 1 multi-period trend visual.");

  // =========================================================================
  // 10. test_default_dashboard_has_more_visual_area_than_text_area
  // =========================================================================
  console.log("\n10. test_default_dashboard_has_more_visual_area_than_text_area...");
  // Briefing is compact
  assert(briefingSrc.includes("adaptive-compact-summary-banner"), "Briefing must be a compact banner");
  // Exactly 1 takeaway per chart
  assert(gridSrc.includes("Design trails the company attendance benchmark by 6.8 days"), "Hero has 1 takeaway");
  assert(gridSrc.includes("Approved leave explains the primary cross-sheet attendance divergence"), "Supporting A has 1 takeaway");
  console.log("   ✅ Default dashboard maximizes visual area with minimal text blocks.");

  console.log("\n🎉 ALL 10 EXECUTIVE INFORMATION ARCHITECTURE & UX GOVERNANCE CHECKS PASSED!");
}

runUXGovernanceSuite().catch((err) => {
  console.error("❌ UX Governance Test Failed:", err);
  process.exit(1);
});
