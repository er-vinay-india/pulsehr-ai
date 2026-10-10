import puppeteer from "puppeteer";

async function run() {
  console.log("🧪 Testing Visual Decision Intelligence Inspect Modal & Drilldown...");
  const browser = await puppeteer.launch({
    headless: "new",
    executablePath: "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
    args: ["--no-sandbox", "--disable-setuid-sandbox"],
  });

  const page = await browser.newPage();
  await page.setViewport({ width: 1440, height: 1100 });

  const errors = [];
  page.on("console", (msg) => {
    if (msg.type() === "error") {
      errors.push(msg.text());
    }
  });

  let activeDatasetId = 99750;
  try {
    const dsRes = await fetch("http://localhost:5175/api/upload/datasets");
    if (dsRes.ok) {
      const dsList = await dsRes.json();
      if (dsList && dsList.length > 0) {
        activeDatasetId = dsList[0].id;
      }
    }
  } catch (e) {
    console.warn("Using fallback datasetId 99750:", e.message);
  }

  await page.goto(`http://localhost:5175/?dataset_id=${activeDatasetId}#adaptive`, { waitUntil: "networkidle2" });
  await new Promise((r) => setTimeout(r, 2500));

  // 1. Verify Topic 2 card exists
  const topic2Card = await page.$('[data-testid="supporting-card-attendance-leave"]');
  if (!topic2Card) {
    throw new Error("Topic 2 reconciliation card not found!");
  }
  console.log("  ✅ Topic 2 Reconciliation card found.");

  // Capture screenshot of the 100% Stacked Bar (Macro view with all 3 components)
  await page.evaluate((el) => el.scrollIntoView({ behavior: "instant", block: "center" }), topic2Card);
  await new Promise((r) => setTimeout(r, 400));
  await topic2Card.screenshot({ path: "/Users/vinayksharma/.gemini/antigravity-ide/brain/9cd70832-7bbd-449d-b18c-68954cd00123/executive_capacity_100_percent_stacked_bar.png" });
  console.log("  📸 Saved 100% Stacked Bar card screenshot: executive_capacity_100_percent_stacked_bar.png");

  // 2. Test toggling between 100% Stacked and Waterfall Gap
  const waterfallBtn = await page.evaluateHandle(() => {
    const buttons = Array.from(document.querySelectorAll("button"));
    return buttons.find((b) => b.textContent.includes("Waterfall Gap"));
  });
  const btnEl = waterfallBtn?.asElement ? waterfallBtn.asElement() : null;
  if (btnEl) {
    await btnEl.click();
    await new Promise((r) => setTimeout(r, 500));
    console.log("  ✅ Successfully toggled to Waterfall Gap drilldown.");
  }

  // 3. Click Inspect on Topic 2
  const inspectBtn = await page.evaluateHandle(() => {
    const card = document.querySelector('[data-testid="supporting-card-attendance-leave"]');
    if (!card) return null;
    const buttons = Array.from(card.querySelectorAll("button"));
    return buttons.find((b) => b.textContent.includes("Inspect"));
  });

  const inspectEl = inspectBtn?.asElement ? inspectBtn.asElement() : inspectBtn;
  if (!inspectEl) {
    throw new Error("Inspect button on Topic 2 not found!");
  }
  await inspectEl.click();
  await new Promise((r) => setTimeout(r, 800));

  // 4. Verify Inspect Modal is open
  const modal = await page.$(".adaptive-inspect-dialog");
  if (!modal) {
    throw new Error("Inspect dialog modal did not open!");
  }
  console.log("  ✅ Inspect dialog modal opened successfully.");

  // 5. Verify Visual Decision Intelligence Audit block exists in modal
  const auditCard = await page.$('[data-testid="visual-decision-audit-card"]');
  if (!auditCard) {
    throw new Error("visual-decision-audit-card not found in modal!");
  }
  console.log("  ✅ Visual Decision Intelligence Audit block verified inside inspect modal.");

  // 6. Verify audit content details
  const auditText = await page.evaluate((el) => el.textContent, auditCard);
  if (!auditText.includes("Visual Decision Intelligence Audit")) {
    throw new Error("Audit title missing!");
  }
  if (!auditText.includes("COMPOSITION")) {
    throw new Error("Analytical Intent 'COMPOSITION' missing from audit!");
  }
  if (!auditText.includes("employee-days") && !auditText.includes("employee_day")) {
    throw new Error(`Governed metric unit 'employee-days' or 'employee_day' missing from audit! Found: ${auditText}`);
  }
  if (!auditText.includes("100_percent_stacked_bar")) {
    throw new Error("Selected chart '100_percent_stacked_bar' missing from audit!");
  }
  if (!auditText.includes("Denominator") || !auditText.includes("RECONCILED")) {
    throw new Error(`Denominator Integrity contract missing from audit! Found: ${auditText}`);
  }
  console.log("  ✅ Verified audit contents: Intent COMPOSITION, Unit employee-days, Selected 100_percent_stacked_bar, DenominatorIntegrity RECONCILED.");

  // 7. Verify secondary drill-down visual in modal
  const drilldownHeading = await page.evaluate(() => {
    const h = Array.from(document.querySelectorAll("span")).find(s => s.textContent.includes("Supporting Drill-Down Visual"));
    return !!h;
  });
  if (!drilldownHeading) {
    throw new Error("Secondary drilldown visual header missing in modal!");
  }
  console.log("  ✅ Secondary Drilldown Waterfall Visual rendered inside inspect modal.");

  // 8. Capture high-res screenshot
  const screenshotPath = "/Users/vinayksharma/.gemini/antigravity-ide/brain/9cd70832-7bbd-449d-b18c-68954cd00123/executive_inspect_modal_visual_decision_audit.png";
  await page.screenshot({ path: screenshotPath });
  console.log(`  📸 Saved screenshot: ${screenshotPath}`);

  // 9. Close modal
  const closeBtn = await page.$(".modal-close-btn");
  if (closeBtn) {
    await closeBtn.click();
    await new Promise((r) => setTimeout(r, 400));
    console.log("  ✅ Inspect modal closed cleanly.");
  }

  if (errors.length > 0) {
    console.error("Browser console errors:", errors);
    throw new Error(`Encountered ${errors.length} browser errors during test`);
  }

  await browser.close();
  console.log("🎉 ALL VISUAL DECISION INTELLIGENCE AUDIT CHECKS PASSED!");
}

run().catch((err) => {
  console.error("Test failed:", err);
  process.exit(1);
});
