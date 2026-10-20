const puppeteer = require('puppeteer');
const fs = require('fs');
const path = require('path');

const OUTPUT_DIR = '/Users/vinayksharma/.gemini/antigravity/brain/8b03f9e3-5aca-46a9-9b30-abe2f5add822/rendered_exports/ui_alignment';
const BASE_URL = 'http://localhost:5175';

if (!fs.existsSync(OUTPUT_DIR)) {
  fs.mkdirSync(OUTPUT_DIR, { recursive: true });
}

async function runCertification() {
  console.log('=== Starting HighView UI Alignment Browser Certification ===');
  const browser = await puppeteer.launch({
    headless: 'new',
    executablePath: '/Applications/Google Chrome.app/Contents/MacOS/Google Chrome',
    args: ['--no-sandbox', '--disable-setuid-sandbox']
  });

  try {
    const page = await browser.newPage();
    await page.setViewport({ width: 1440, height: 900 });

    // Ensure Light theme
    await page.goto(`${BASE_URL}/#explorer`, { waitUntil: 'networkidle0' });
    await page.evaluate(() => {
      localStorage.setItem('highview_theme', 'light');
      document.documentElement.setAttribute('data-theme', 'light');
      window.dispatchEvent(new CustomEvent('highview-theme-change', { detail: { theme: 'light' } }));
    });
    await new Promise(r => setTimeout(r, 400));

    // 1. Data Explorer - Source Mode
    console.log('1. Capturing Data Explorer Source Mode...');
    await page.goto(`${BASE_URL}/?dataset_id=sdr7_cert&tab=source#explorer`, { waitUntil: 'networkidle0' });
    await page.waitForSelector('.sdr-source-mode-container table', { timeout: 10000 });
    await new Promise(r => setTimeout(r, 500));
    await page.screenshot({ path: path.join(OUTPUT_DIR, '01_explorer_source_mode.png') });

    // 2. Data Explorer - Semantics Mode (Verified Populated from SDR)
    console.log('2. Capturing Data Explorer Semantics Mode...');
    await page.goto(`${BASE_URL}/?dataset_id=sdr7_cert&tab=semantics#explorer`, { waitUntil: 'networkidle0' });
    await page.waitForSelector('.sdr-semantics-mode-container table tbody tr', { timeout: 10000 });
    await new Promise(r => setTimeout(r, 500));
    await page.screenshot({ path: path.join(OUTPUT_DIR, '02_explorer_semantics_mode_populated.png') });

    // 3. Data Explorer - Relationships Mode
    console.log('3. Capturing Data Explorer Relationships Mode...');
    await page.goto(`${BASE_URL}/?dataset_id=sdr7_cert&tab=relationships#explorer`, { waitUntil: 'networkidle0' });
    await page.waitForSelector('.sdr-relationships-mode-container', { timeout: 10000 });
    await new Promise(r => setTimeout(r, 500));
    await page.screenshot({ path: path.join(OUTPUT_DIR, '03_explorer_relationships_mode.png') });

    // 4. Data Explorer - Analytical Views Mode
    console.log('4. Capturing Data Explorer Analytical Views Mode...');
    await page.goto(`${BASE_URL}/?dataset_id=sdr7_cert&tab=analytical-views#explorer`, { waitUntil: 'networkidle0' });
    await page.waitForSelector('.sdr-analytical-views-mode-container', { timeout: 10000 });
    await new Promise(r => setTimeout(r, 500));
    await page.screenshot({ path: path.join(OUTPUT_DIR, '04_explorer_analytical_views_mode.png') });

    // 5. Upload Modal - Step 1: Select File
    console.log('5. Capturing Upload Modal Step 1...');
    await page.goto(`${BASE_URL}/#upload`, { waitUntil: 'networkidle0' });
    await page.waitForSelector('.upload-modal-panel', { timeout: 10000 });
    await new Promise(r => setTimeout(r, 400));
    await page.screenshot({ path: path.join(OUTPUT_DIR, '05_upload_modal_step1_select.png') });

    // 6. Upload Modal - Step 2: Analysis Expectations
    console.log('6. Capturing Upload Modal Step 2...');
    // Create and attach a mock file
    const fileInput = await page.$('#modal-file-upload-input');
    const dummyFilePath = '/tmp/sample_workforce.csv';
    fs.writeFileSync(dummyFilePath, 'employee_id,name,department,salary\nE101,John Doe,Engineering,125000\nE102,Jane Smith,Product,130000\n');
    await fileInput.uploadFile(dummyFilePath);
    await page.waitForSelector('.upload-step-expectations', { timeout: 10000 });
    await new Promise(r => setTimeout(r, 400));
    await page.screenshot({ path: path.join(OUTPUT_DIR, '06_upload_modal_step2_expectations.png') });

    // 7. Upload Modal - Step 3: Ingestion & Profiling (Stage Progress)
    console.log('7. Triggering Step 3 Ingestion...');
    const submitBtn = await page.$('.btn-primary');
    await submitBtn.click();
    await page.waitForSelector('.ingestion-progress-card', { timeout: 10000 });
    await new Promise(r => setTimeout(r, 600));
    await page.screenshot({ path: path.join(OUTPUT_DIR, '07_upload_modal_step3_stages_progress.png') });

    // 8. Upload Modal - Step 3: Governed Completion Summary
    console.log('8. Waiting for Governed Completion Card...');
    await page.waitForSelector('.upload-minimal-success', { timeout: 35000 });
    await new Promise(r => setTimeout(r, 600));
    await page.screenshot({ path: path.join(OUTPUT_DIR, '08_upload_modal_completion_summary.png') });

    // 9. Dark Theme - Data Explorer Semantics
    console.log('9. Capturing Dark Theme Data Explorer Semantics...');
    await page.evaluate(() => {
      localStorage.setItem('highview_theme', 'dark');
      document.documentElement.setAttribute('data-theme', 'dark');
      window.dispatchEvent(new CustomEvent('highview-theme-change', { detail: { theme: 'dark' } }));
    });
    await page.goto(`${BASE_URL}/?dataset_id=sdr7_cert&tab=semantics#explorer`, { waitUntil: 'networkidle0' });
    await page.waitForSelector('.sdr-semantics-mode-container table tbody tr', { timeout: 10000 });
    await new Promise(r => setTimeout(r, 500));
    await page.screenshot({ path: path.join(OUTPUT_DIR, '09_dark_theme_semantics.png') });

    // 10. Mobile Viewport (375x812) - Upload Progress / Explorer
    console.log('10. Capturing Mobile Viewport...');
    await page.setViewport({ width: 375, height: 812, isMobile: true });
    await page.goto(`${BASE_URL}/?dataset_id=sdr7_cert&tab=source#explorer`, { waitUntil: 'networkidle0' });
    await page.waitForSelector('.sdr-source-mode-container table', { timeout: 10000 });
    await new Promise(r => setTimeout(r, 500));
    await page.screenshot({ path: path.join(OUTPUT_DIR, '10_mobile_source_mode.png') });

    console.log('=== Browser Certification Captured Successfully ===');
  } finally {
    await browser.close();
  }
}

runCertification().catch((err) => {
  console.error('Certification capture failed:', err);
  process.exit(1);
});
