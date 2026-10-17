/**
 * test_progress.mjs
 *
 * Lightweight, zero-dependency real-time CLI progress bar & spinner
 * for long-running Puppeteer & integration test suites.
 *
 * Supports:
 * - Live animated spinner & step progress bar in TTY terminals
 * - Clean milestone progress lines in non-TTY/CI environments
 * - Elapsed duration tracking
 * - Sub-step status updates
 */

const SPINNER_FRAMES = ["⠋", "⠙", "⠹", "⠸", "⠼", "⠴", "⠦", "⠧", "⠇", "⠏"];

export class ProgressBar {
  constructor({ total = 10, title = "Test Progress", width = 24 } = {}) {
    this.total = Math.max(1, total);
    this.current = 0;
    this.title = title;
    this.width = width;
    this.statusMessage = "";
    this.startTime = Date.now();
    this.spinnerIndex = 0;
    this.timer = null;
    this.isTTY = Boolean(process.stdout.isTTY);

    if (this.isTTY) {
      this.timer = setInterval(() => {
        this.spinnerIndex = (this.spinnerIndex + 1) % SPINNER_FRAMES.length;
        this.render();
      }, 80);
    }
  }

  step(message) {
    this.current = Math.min(this.total, this.current + 1);
    this.statusMessage = message || "";
    if (this.isTTY) {
      this.render();
    } else {
      const elapsed = ((Date.now() - this.startTime) / 1000).toFixed(1);
      const pct = Math.round((this.current / this.total) * 100);
      console.log(`[PROGRESS ${this.current}/${this.total}] (${pct}%) ${this.statusMessage} (${elapsed}s)`);
    }
  }

  substep(message) {
    this.statusMessage = message || "";
    if (this.isTTY) {
      this.render();
    }
  }

  render() {
    if (!this.isTTY) return;

    const elapsed = ((Date.now() - this.startTime) / 1000).toFixed(1);
    const pct = Math.min(100, Math.round((this.current / this.total) * 100));
    const filledLen = Math.round((this.width * this.current) / this.total);
    const emptyLen = Math.max(0, this.width - filledLen);

    const bar = "█".repeat(filledLen) + "░".repeat(emptyLen);
    const spinner = SPINNER_FRAMES[this.spinnerIndex];

    // Truncate status message if terminal width is limited
    const cols = process.stdout.columns || 80;
    const prefix = `\r[${this.title}] [${bar}] ${pct}% (${this.current}/${this.total}) ${spinner} `;
    const suffix = ` [${elapsed}s]`;
    const avail = Math.max(10, cols - prefix.length - suffix.length - 2);

    let msg = this.statusMessage;
    if (msg.length > avail) {
      msg = msg.slice(0, avail - 3) + "...";
    }

    process.stdout.write(`${prefix}${msg}${suffix}`);
  }

  complete(message = "Done!") {
    if (this.timer) {
      clearInterval(this.timer);
      this.timer = null;
    }
    const elapsed = ((Date.now() - this.startTime) / 1000).toFixed(1);
    if (this.isTTY) {
      process.stdout.write(`\r\x1b[K`); // Clear current line
    }
    console.log(`\n✅ [${this.title}] Completed in ${elapsed}s — ${message}\n`);
  }

  fail(error) {
    if (this.timer) {
      clearInterval(this.timer);
      this.timer = null;
    }
    if (this.isTTY) {
      process.stdout.write(`\r\x1b[K`);
    }
    console.error(`\n❌ [${this.title}] FAILED: ${error?.message || error}\n`);
  }
}

export function createProgressBar(options) {
  return new ProgressBar(options);
}
