import puppeteer from 'puppeteer';
import path from 'path';

const ARTIFACT_DIR = '/Users/vinayksharma/.gemini/antigravity/brain/8b03f9e3-5aca-46a9-9b30-abe2f5add822';
const BASE_URL = 'http://localhost:5175';
const DATASET_ID = '99767';

async function run() {
  console.log('🚀 Starting Details Drawer Verification (Executive Summary & KPI)...');
  const browser = await puppeteer.launch({
    headless: 'new',
    executablePath: '/Applications/Google Chrome.app/Contents/MacOS/Google Chrome',
    args: ['--no-sandbox', '--disable-setuid-sandbox', '--window-size=1440,1000']
  });

  const page = await browser.newPage();
  await page.setViewport({ width: 1440, height: 1000, deviceScaleFactor: 2 });

  await page.goto(`${BASE_URL}/?dataset_id=${DATASET_ID}&theme=dark#dashboard`, { waitUntil: 'networkidle0' });
  await new Promise(r => setTimeout(r, 1200));

  // 1. Click Executive Summary details button
  console.log('📋 STEP 1: Clicking Executive Summary details (ⓘ) button...');
  const execSummaryBtn = await page.$('.adaptive-compact-summary-banner .hv-action-icon-btn[data-action-key="details"]');
  if (!execSummaryBtn) {
    throw new Error('Executive summary details button not found');
  }
  await execSummaryBtn.click();
  await new Promise(r => setTimeout(r, 600));

  const execDrawerCheck = await page.evaluate(() => {
    const panel = document.querySelector('.hv-sidepanel-panel');
    if (!panel) return { open: false };
    const rect = panel.getBoundingClientRect();
    const title = document.querySelector('.hv-sidepanel-title')?.innerText || '';
    const synthesisText = document.querySelector('.hv-sidepanel-body p')?.innerText || '';
    const claims = Array.from(document.querySelectorAll('.hv-sidepanel-body [style*="border-radius: 8px"]')).length;
    return {
      open: true,
      title,
      isRightAnchored: rect.right <= window.innerWidth + 5 && rect.left > window.innerWidth / 2,
      synthesisText,
      hasDetails: synthesisText.length > 20,
      claimsCount: claims
    };
  });

  console.log('  Executive Summary Drawer Open:', execDrawerCheck.open);
  console.log('  Title:', execDrawerCheck.title);
  console.log('  Right Anchored (Slid from right):', execDrawerCheck.isRightAnchored);
  console.log('  Has Details:', execDrawerCheck.hasDetails);
  console.log('  Synthesis excerpt:', execDrawerCheck.synthesisText.substring(0, 80) + '...');
  
  await page.screenshot({ path: path.join(ARTIFACT_DIR, 'qa_exec_summary_drawer_open.png') });
  console.log('  📸 Saved: qa_exec_summary_drawer_open.png');

  if (!execDrawerCheck.open || !execDrawerCheck.hasDetails) {
    throw new Error('Executive summary details drawer failed: empty or not open');
  }

  // Dismiss via Escape
  await page.keyboard.press('Escape');
  await new Promise(r => setTimeout(r, 400));

  // 2. Click KPI details button
  console.log('\n📋 STEP 2: Clicking KPI details (ⓘ) button...');
  const kpiDetailsBtn = await page.$('.kpi-card .hv-action-icon-btn[data-action-key="details"]');
  if (!kpiDetailsBtn) {
    throw new Error('KPI details button not found');
  }
  await kpiDetailsBtn.click();
  await new Promise(r => setTimeout(r, 600));

  const kpiDrawerCheck = await page.evaluate(() => {
    const panel = document.querySelector('.kpi-side-panel') || document.querySelector('.hv-sidepanel-panel');
    if (!panel) return { open: false };
    const rect = panel.getBoundingClientRect();
    const title = document.querySelector('.hv-sidepanel-title')?.innerText || '';
    const definition = document.querySelector('.hv-sidepanel-body p')?.innerText || '';
    const formula = document.querySelector('.hv-sidepanel-body pre')?.innerText || '';
    return {
      open: true,
      title,
      isRightAnchored: rect.right <= window.innerWidth + 5 && rect.left > window.innerWidth / 2,
      definition,
      formula
    };
  });

  console.log('  KPI Drawer Open:', kpiDrawerCheck.open);
  console.log('  Title:', kpiDrawerCheck.title);
  console.log('  Right Anchored (Slid from right):', kpiDrawerCheck.isRightAnchored);
  console.log('  Definition:', kpiDrawerCheck.definition);
  console.log('  Formula:', kpiDrawerCheck.formula);

  await page.screenshot({ path: path.join(ARTIFACT_DIR, 'qa_kpi_drawer_open.png') });
  console.log('  📸 Saved: qa_kpi_drawer_open.png');

  if (!kpiDrawerCheck.open || !kpiDrawerCheck.isRightAnchored) {
    throw new Error('KPI details drawer failed: not open or not right-anchored');
  }

  await browser.close();
  console.log('\n🎉 ALL DRAWER TESTS PASSED SUCCESSFULLY!');
}

run().catch(err => {
  console.error('❌ Test failed:', err);
  process.exit(1);
});
