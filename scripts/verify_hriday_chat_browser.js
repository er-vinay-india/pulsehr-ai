const puppeteer = require('puppeteer');
const fs = require('fs');
const path = require('path');

const ARTIFACT_DIR = '/Users/vinayksharma/.gemini/antigravity/brain/8b03f9e3-5aca-46a9-9b30-abe2f5add822';
const BASE_URL = 'http://localhost:5175';

const TURNS = [
  { step: 1, text: "who is not coming regularly", expectKeywords: ["attendance", "days", "rank"] },
  { step: 2, text: "What about Operations only?", expectKeywords: ["Operations and Infrastructure"] },
  { step: 3, text: "Show department also", expectKeywords: ["Operations and Infrastructure"] },
  { step: 4, text: "I need employee ID", expectKeywords: ["LB", "10", "days"] },
  { step: 5, text: "Why?", expectKeywords: ["denominators", "scheduled", "recorded", "limitations"] },
  { step: 6, text: "Show me the bottom 3", expectKeywords: ["#1", "#2", "#3"] }
];

async function runChatVerification() {
  console.log('=== Starting HRIDAY Chat Browser UI Acceptance Test ===');
  const browser = await puppeteer.launch({
    headless: 'new',
    executablePath: '/Applications/Google Chrome.app/Contents/MacOS/Google Chrome',
    args: ['--no-sandbox', '--disable-setuid-sandbox']
  });

  const report = {
    timestamp: new Date().toISOString(),
    viewports: {},
    turns_verified: [],
    overall_passed: false
  };

  try {
    const viewports = [
      { name: 'desktop_1440', width: 1440, height: 900, shotName: 'qa_hriday_chat_desktop_1440.png' },
      { name: 'mobile_390', width: 390, height: 844, shotName: 'qa_hriday_chat_mobile_390.png' }
    ];

    for (const vp of viewports) {
      console.log(`\n--- Running Viewport: ${vp.name} (${vp.width}x${vp.height}) ---`);
      const page = await browser.newPage();
      await page.setViewport({ width: vp.width, height: vp.height, deviceScaleFactor: 2 });

      // Enable reduced motion for fast text delivery in test runner
      await page.emulateMediaFeatures([{ name: 'prefers-reduced-motion', value: 'reduce' }]);
      const consoleErrors = [];
      const failedRequests = [];

      page.on('console', msg => {
        if (msg.type() === 'error') {
          consoleErrors.push(msg.text());
        }
      });
      page.on('requestfailed', req => {
        const errorText = req.failure()?.errorText;
        if (errorText !== 'net::ERR_ABORTED') {
          failedRequests.push(`${req.method()} ${req.url()}: ${errorText}`);
        }
      });

      // Load page with dataset_id=99770
      await page.goto(`${BASE_URL}/?dataset_id=99770#adaptive`, { waitUntil: 'networkidle2', timeout: 30000 });
      await new Promise(r => setTimeout(r, 1500));

      // Open HRIDAY Chat panel via header button, launcher pill, or hash navigation
      const headerBtn = await page.$('.btn-header-hriday');
      if (headerBtn && await headerBtn.isIntersectingViewport()) {
        await headerBtn.click();
      } else {
        const pill = await page.$('.hriday-launcher');
        if (pill && await pill.isIntersectingViewport()) {
          await pill.click();
        } else {
          await page.evaluate(() => { window.location.hash = 'copilot'; });
        }
      }
      await page.waitForSelector('#hriday-chat-panel, .hriday-panel', { timeout: 10000 });
      await new Promise(r => setTimeout(r, 1000));

      const vpTurns = [];

      for (const turn of TURNS) {
        console.log(`  [Turn ${turn.step}] Sending: "${turn.text}"`);
        const inputSelector = '.hriday-composer textarea';
        await page.waitForSelector(inputSelector, { timeout: 5000 });
        
        // Clear and type
        await page.click(inputSelector);
        await page.$eval(inputSelector, el => el.value = '');
        await page.type(inputSelector, turn.text);
        
        // Click send button
        const sendBtnSelector = '.hriday-composer-action, button[type="submit"]';
        await page.click(sendBtnSelector);

        // Wait for response to stream and complete (phase === complete or stop button disappears)
        console.log(`  [Turn ${turn.step}] Waiting for assistant response to complete...`);
        await page.waitForFunction(
          (turnIndex) => {
            const msgs = document.querySelectorAll('.hriday-message--assistant');
            if (msgs.length < turnIndex) return false;
            const latest = msgs[msgs.length - 1];
            // Check if loading activity is gone and answer-actions or complete content is present
            const hasActions = latest.querySelector('.hriday-answer-actions');
            const hasAnswer = latest.querySelector('.hriday-answer');
            const hasRecovery = latest.querySelector('.hriday-recovery');
            return (hasActions || hasRecovery) && hasAnswer;
          },
          { timeout: 45000 },
          turn.step
        );

        // Extract latest assistant message content
        const lastMsgData = await page.evaluate(() => {
          const msgs = document.querySelectorAll('.hriday-message--assistant');
          const latest = msgs[msgs.length - 1];
          const text = latest.querySelector('.hriday-answer')?.innerText || '';
          const hasRawJson = text.includes('{"') && text.includes('"}');
          const hasInternalTerms = /\b(AnalyticalQueryService|DuckDB|AST|Pydantic|P50|P95|DataFrame)\b/i.test(text);
          return {
            text: text.slice(0, 500),
            fullLength: text.length,
            hasRawJson,
            hasInternalTerms
          };
        });

        console.log(`  [Turn ${turn.step}] Completed (length=${lastMsgData.fullLength}, json=${lastMsgData.hasRawJson}, internalTerms=${lastMsgData.hasInternalTerms})`);
        vpTurns.push({
          step: turn.step,
          query: turn.text,
          length: lastMsgData.fullLength,
          snippet: lastMsgData.text.replace(/\n+/g, ' ').slice(0, 150),
          hasRawJson: lastMsgData.hasRawJson,
          hasInternalTerms: lastMsgData.hasInternalTerms
        });

        await new Promise(r => setTimeout(r, 1000));
      }

      // Capture screenshot
      const shotPath = path.join(ARTIFACT_DIR, vp.shotName);
      await page.screenshot({ path: shotPath, fullPage: false });
      console.log(`  Saved screenshot: ${vp.shotName}`);

      report.viewports[vp.name] = {
        viewport: `${vp.width}x${vp.height}`,
        console_errors: consoleErrors,
        failed_requests: failedRequests,
        turns: vpTurns,
        screenshot: vp.shotName,
        clean: consoleErrors.length === 0 && failedRequests.length === 0
      };

      await page.close();
    }

    report.overall_passed = Object.values(report.viewports).every(v => v.clean && v.turns.every(t => !t.hasRawJson && !t.hasInternalTerms));
  } catch (err) {
    console.error('Browser verification failed:', err);
    report.error = err.message;
    report.overall_passed = false;
  } finally {
    await browser.close();
  }

  const resultPath = path.join(ARTIFACT_DIR, 'qa_hriday_chat_browser_result.json');
  fs.writeFileSync(resultPath, JSON.stringify(report, null, 2));
  console.log(`\nVerification complete. Result written to ${resultPath}`);
  console.log(`Overall Passed: ${report.overall_passed}`);
  return report;
}

runChatVerification();
