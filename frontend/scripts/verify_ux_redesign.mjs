import puppeteer from 'puppeteer';
import path from 'path';

const ARTIFACT_DIR = '/Users/vinayksharma/.gemini/antigravity/brain/98708ce3-6bc0-44d2-8c5c-f7a790e87154';

async function run() {
  const browser = await puppeteer.launch({
    headless: 'new',
    executablePath: '/Applications/Google Chrome.app/Contents/MacOS/Google Chrome',
    args: ['--no-sandbox', '--disable-setuid-sandbox']
  });

  const page = await browser.newPage();
  await page.setViewport({ width: 1440, height: 900 });

  console.log('Navigating to http://localhost:5175...');
  await page.goto('http://localhost:5175', { waitUntil: 'networkidle2', timeout: 30000 });

  // 1. Capture Header & Executive Overview
  console.log('Capturing Executive Overview & Header...');
  await page.screenshot({
    path: path.join(ARTIFACT_DIR, 'verify_ux_header_overview.png'),
    fullPage: false
  });

  // 2. Click Data Explorer tab
  console.log('Navigating to Data Explorer...');
  const explorerTab = await page.waitForSelector('button.nav-segment:nth-child(2)', { timeout: 5000 });
  await explorerTab.click();
  await new Promise(r => setTimeout(r, 2000));

  // Capture Data Explorer Page (compact toolbar, minimal delete, no bulky card)
  console.log('Capturing Data Explorer with Compact Command Bar...');
  await page.screenshot({
    path: path.join(ARTIFACT_DIR, 'verify_ux_explorer_toolbar.png'),
    fullPage: false
  });

  // 3. Test Minimal Delete consent modal trigger
  console.log('Testing minimal delete button...');
  const deleteBtn = await page.$('.btn-minimal-delete');
  if (deleteBtn) {
    await deleteBtn.click();
    await new Promise(r => setTimeout(r, 800));
    await page.screenshot({
      path: path.join(ARTIFACT_DIR, 'verify_ux_explorer_delete_modal.png'),
      fullPage: false
    });

    // Close modal by clicking cancel
    const cancelBtn = await page.$('.btn-cancel');
    if (cancelBtn) {
      await cancelBtn.click();
      await new Promise(r => setTimeout(r, 500));
    }
  }

  // 4. Test Header Upload Button & Modal
  console.log('Testing Header Upload Button...');
  const uploadBtn = await page.$('.btn-header-upload');
  if (uploadBtn) {
    await uploadBtn.click();
    await new Promise(r => setTimeout(r, 800));
    await page.screenshot({
      path: path.join(ARTIFACT_DIR, 'verify_ux_upload_modal.png'),
      fullPage: false
    });

    // Close the upload modal
    const closeBtn = await page.$('.upload-modal-close-btn');
    if (closeBtn) {
      await closeBtn.click();
      await new Promise(r => setTimeout(r, 600));
    }
  }

  // 5. Check Mobile layout
  console.log('Checking Mobile 390px layout...');
  await page.setViewport({ width: 390, height: 844 });
  await new Promise(r => setTimeout(r, 800));
  await page.screenshot({
    path: path.join(ARTIFACT_DIR, 'verify_ux_mobile_explorer.png'),
    fullPage: false
  });

  await browser.close();
  console.log('Verification finished successfully!');
}

run().catch(err => {
  console.error(err);
  process.exit(1);
});
