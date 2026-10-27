import puppeteer from 'puppeteer';

const BASE_URL = 'http://localhost:5175';
const DATASET_ID = '99795';

async function runAudit() {
  console.log('🚀 Starting Comprehensive Frontend Defect Audit Across All Tabs...');
  
  const browser = await puppeteer.launch({
    headless: 'new',
    executablePath: '/Applications/Google Chrome.app/Contents/MacOS/Google Chrome',
    args: ['--no-sandbox', '--disable-setuid-sandbox', '--window-size=1440,1000']
  });

  const page = await browser.newPage();
  await page.setViewport({ width: 1440, height: 1000, deviceScaleFactor: 2 });

  const errors = [];
  const warnings = [];

  page.on('pageerror', err => {
    errors.push({ type: 'pageerror', message: err.message, stack: err.stack });
    console.error('❌ [PAGE ERROR]:', err.message);
  });

  page.on('console', msg => {
    const text = msg.text();
    if (msg.type() === 'error') {
      errors.push({ type: 'console.error', text });
      console.error('❌ [CONSOLE ERROR]:', text);
    } else if (msg.type() === 'warning') {
      if (!text.includes('React DevTools') && !text.includes('favicon')) {
        warnings.push({ type: 'console.warn', text });
        console.warn('⚠️ [CONSOLE WARN]:', text);
      }
    }
  });

  async function checkPageIntegrity(tabName) {
    const audit = await page.evaluate(() => {
      const allText = document.body.innerText || '';
      const hasNan = /\bNaN\b/.test(allText);
      const hasUndefined = /\bundefined\b/.test(allText);
      const hasObjectObject = /\[object Object\]/.test(allText);
      const hasNullPages = /null\.pages/.test(allText);

      const html = document.documentElement;
      const body = document.body;
      const scrollWidth = Math.max(body.scrollWidth, html.scrollWidth);
      const clientWidth = html.clientWidth;
      const hasHorizontalOverflow = scrollWidth > clientWidth + 2;

      // Check for broken images
      const brokenImages = Array.from(document.querySelectorAll('img'))
        .filter(img => !img.complete || img.naturalWidth === 0)
        .map(img => img.src);

      // Check for raw un-rendered template tags
      const hasRawTemplates = /\{\{[^}]+\}\}/.test(allText);

      return {
        hasNan,
        hasUndefined,
        hasObjectObject,
        hasNullPages,
        hasHorizontalOverflow,
        scrollWidth,
        clientWidth,
        brokenImagesCount: brokenImages.length,
        hasRawTemplates,
        bodyLength: allText.length,
      };
    });

    console.log(`  [Audit ${tabName}]: length=${audit.bodyLength}, NaN=${audit.hasNan}, undefined=${audit.hasUndefined}, [object Object]=${audit.hasObjectObject}, hOverflow=${audit.hasHorizontalOverflow}, brokenImgs=${audit.brokenImagesCount}`);
    return audit;
  }

  // 1. Executive Dashboard (Light Theme)
  console.log('\n--- 1. Testing Dashboard (Light) ---');
  await page.goto(`${BASE_URL}/?tab=dashboard&dataset_id=${DATASET_ID}&theme=light#adaptive`, { waitUntil: 'networkidle2', timeout: 30000 });
  await new Promise(r => setTimeout(r, 1200));
  await checkPageIntegrity('Dashboard-Light');

  // 2. Executive Dashboard (Dark Theme)
  console.log('\n--- 2. Testing Dashboard (Dark) ---');
  await page.evaluate(() => {
    document.documentElement.setAttribute('data-theme', 'dark');
    document.documentElement.classList.add('dark');
    localStorage.setItem('pulsehr_theme', 'dark');
  });
  await new Promise(r => setTimeout(r, 600));
  await checkPageIntegrity('Dashboard-Dark');

  // 3. Data Explorer (Overview)
  console.log('\n--- 3. Testing Data Explorer (Overview) ---');
  await page.goto(`${BASE_URL}/?tab=data-explorer&dataset_id=${DATASET_ID}#explorer`, { waitUntil: 'networkidle2', timeout: 30000 });
  await new Promise(r => setTimeout(r, 1200));
  await checkPageIntegrity('Explorer-Overview');

  // 4. Data Explorer (Data Grid Subtab)
  console.log('\n--- 4. Testing Data Explorer (Data Subtab) ---');
  await page.goto(`${BASE_URL}/?tab=data&dataset_id=${DATASET_ID}#explorer`, { waitUntil: 'networkidle2', timeout: 30000 });
  await new Promise(r => setTimeout(r, 1200));
  await checkPageIntegrity('Explorer-Data');

  // 5. Data Explorer (Profile Subtab)
  console.log('\n--- 5. Testing Data Explorer (Profile Subtab) ---');
  await page.goto(`${BASE_URL}/?tab=profile&dataset_id=${DATASET_ID}#explorer`, { waitUntil: 'networkidle2', timeout: 30000 });
  await new Promise(r => setTimeout(r, 1200));
  await checkPageIntegrity('Explorer-Profile');

  // 6. Data Explorer (Semantics Subtab)
  console.log('\n--- 6. Testing Data Explorer (Semantics Subtab) ---');
  await page.goto(`${BASE_URL}/?tab=semantics&dataset_id=${DATASET_ID}#explorer`, { waitUntil: 'networkidle2', timeout: 30000 });
  await new Promise(r => setTimeout(r, 1200));
  await checkPageIntegrity('Explorer-Semantics');

  // 7. Data Explorer (Relationships Subtab)
  console.log('\n--- 7. Testing Data Explorer (Relationships Subtab) ---');
  await page.goto(`${BASE_URL}/?tab=relationships&dataset_id=${DATASET_ID}#explorer`, { waitUntil: 'networkidle2', timeout: 30000 });
  await new Promise(r => setTimeout(r, 1200));
  await checkPageIntegrity('Explorer-Relationships');

  // 8. Data Explorer (Analysis Subtab)
  console.log('\n--- 8. Testing Data Explorer (Analysis Subtab) ---');
  await page.goto(`${BASE_URL}/?tab=analysis&dataset_id=${DATASET_ID}#explorer`, { waitUntil: 'networkidle2', timeout: 30000 });
  await new Promise(r => setTimeout(r, 1200));
  await checkPageIntegrity('Explorer-Analysis');

  // 9. Data Explorer (Evidence Subtab)
  console.log('\n--- 9. Testing Data Explorer (Evidence Subtab) ---');
  await page.goto(`${BASE_URL}/?tab=evidence&dataset_id=${DATASET_ID}#explorer`, { waitUntil: 'networkidle2', timeout: 30000 });
  await new Promise(r => setTimeout(r, 1200));
  await checkPageIntegrity('Explorer-Evidence');

  // 10. Scenarios View
  console.log('\n--- 10. Testing Scenarios View ---');
  await page.goto(`${BASE_URL}/?tab=scenarios&dataset_id=${DATASET_ID}#adaptive`, { waitUntil: 'networkidle2', timeout: 30000 });
  await new Promise(r => setTimeout(r, 1200));
  await checkPageIntegrity('Scenarios');

  // 11. Presentation Studio
  console.log('\n--- 11. Testing Presentation Studio ---');
  await page.goto(`${BASE_URL}/?dataset_id=${DATASET_ID}#presentation`, { waitUntil: 'networkidle2', timeout: 30000 });
  await new Promise(r => setTimeout(r, 1500));
  await checkPageIntegrity('Presentation-Studio');

  // 12. HRIDAY Copilot Widget Toggle
  console.log('\n--- 12. Testing HRIDAY Copilot Widget ---');
  await page.goto(`${BASE_URL}/?tab=dashboard&dataset_id=${DATASET_ID}#adaptive`, { waitUntil: 'networkidle2', timeout: 30000 });
  await new Promise(r => setTimeout(r, 1000));
  
  // Click copilot toggle button in header
  const copilotBtn = await page.$('.btn-header-hriday, .hriday-launcher');
  if (copilotBtn) {
    await copilotBtn.click();
    await new Promise(r => setTimeout(r, 600));
    const copilotOpen = await page.evaluate(() => {
      const panel = document.querySelector('#hriday-chat-panel, .hriday-panel');
      return !!panel;
    });
    console.log('  HRIDAY Copilot Widget Open:', copilotOpen);
    if (!copilotOpen) throw new Error('HRIDAY chat panel failed to open');
    
    // Test closing it via Escape
    await page.keyboard.press('Escape');
    await new Promise(r => setTimeout(r, 400));
    const copilotClosed = await page.evaluate(() => {
      const panel = document.querySelector('#hriday-chat-panel, .hriday-panel');
      return !panel;
    });
    console.log('  HRIDAY Copilot Widget Closed via Escape:', copilotClosed);
  } else {
    console.log('  Copilot trigger button not found');
  }

  // 13. Upload Modal
  console.log('\n--- 13. Testing Upload Modal ---');
  const uploadBtn = await page.$('.btn-header-upload');
  if (uploadBtn) {
    await uploadBtn.click();
    await new Promise(r => setTimeout(r, 500));
    const modalVisible = await page.evaluate(() => {
      return !!document.querySelector('.upload-modal, [role="dialog"]');
    });
    console.log('  Upload Modal Open:', modalVisible);
    // Dismiss
    await page.keyboard.press('Escape');
    await new Promise(r => setTimeout(r, 300));
  }

  await browser.close();

  console.log('\n================ AUDIT SUMMARY ================');
  console.log(`Total Errors Logged:   ${errors.length}`);
  console.log(`Total Warnings Logged: ${warnings.length}`);
  
  if (errors.length > 0) {
    console.log('\n🔴 Errors details:');
    errors.forEach((e, idx) => console.log(`  ${idx + 1}. [${e.type}] ${e.text || e.message}`));
  }
  if (warnings.length > 0) {
    console.log('\n🟡 Warnings details:');
    warnings.slice(0, 10).forEach((w, idx) => console.log(`  ${idx + 1}. [${w.type}] ${w.text}`));
  }
  console.log('===============================================\n');
}

runAudit().catch(err => {
  console.error('Audit fatal error:', err);
  process.exit(1);
});
