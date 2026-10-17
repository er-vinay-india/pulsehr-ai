/**
 * Test Environment Firewall Guard
 * 
 * Enforces the non-negotiable architectural invariant:
 * "NO TEST OR QA PROCESS MAY MUTATE USER APPLICATION STATE THROUGH ANY CHANNEL."
 * 
 * Specifically:
 * 1. Blocks any test script from targeting the normal running development backend (localhost:8000)
 *    when performing mutations (POST, PUT, DELETE).
 * 2. Provides lifecycle management for isolated, ephemeral backend instances backed by
 *    isolated temporary databases in /tmp/highview-test-<id>/.
 */

import net from 'net';
import { spawn } from 'child_process';
import fs from 'fs';
import path from 'path';
import os from 'os';
import crypto from 'crypto';

export class LiveInstanceMutationBlockedError extends Error {
  constructor(message) {
    super(message);
    this.name = 'LiveInstanceMutationBlockedError';
  }
}

const FORBIDDEN_LIVE_PORTS = new Set(['8000', '8020']);
const FORBIDDEN_LIVE_HOSTS = [
  'localhost:8000',
  '127.0.0.1:8000',
  '0.0.0.0:8000',
  'localhost:8020',
  '127.0.0.1:8020',
];

/**
 * Validates that a target URL is an isolated test instance and NOT the normal user/dev instance.
 * Throws LiveInstanceMutationBlockedError BEFORE any network mutation is executed.
 */
export function assertIsolatedTestTarget(targetUrl, operationName = 'mutation') {
  if (!targetUrl) {
    throw new LiveInstanceMutationBlockedError(
      `CRITICAL TEST FIREWALL VIOLATION: Missing target URL for test operation "${operationName}". ` +
      `Tests that perform mutations MUST explicitly specify an isolated test backend.`
    );
  }

  let parsed;
  try {
    parsed = new URL(targetUrl);
  } catch (err) {
    throw new LiveInstanceMutationBlockedError(
      `CRITICAL TEST FIREWALL VIOLATION: Invalid target URL "${targetUrl}" for test operation "${operationName}".`
    );
  }

  const hostWithPort = parsed.host;
  const port = parsed.port;

  if (FORBIDDEN_LIVE_HOSTS.includes(hostWithPort) || FORBIDDEN_LIVE_PORTS.has(port)) {
    throw new LiveInstanceMutationBlockedError(
      `CRITICAL TEST FIREWALL VIOLATION: Test operation "${operationName}" attempted mutation against live/development server at "${targetUrl}". ` +
      `Mutating tests are strictly prohibited from touching the user's running HighView instance. ` +
      `You MUST spawn an isolated ephemeral test backend on an isolated port with APP_ENV=test.`
    );
  }

  return true;
}

/**
 * Returns standard test headers required for test-runtime authentication with the backend firewall.
 */
export function getTestHeaders(runId = null) {
  const id = runId || `test-${crypto.randomUUID()}`;
  return {
    'X-HighView-Test-Run': id,
    'X-Test-Execution': 'isolated-suite',
  };
}

/**
 * Finds a free port on localhost.
 */
export function getAvailablePort() {
  return new Promise((resolve, reject) => {
    const server = net.createServer();
    server.unref();
    server.on('error', reject);
    server.listen(0, '127.0.0.1', () => {
      const port = server.address().port;
      server.close(() => resolve(port));
    });
  });
}

/**
 * Spawns an isolated backend instance running on an ephemeral port
 * backed by a dedicated temporary directory structure in /tmp.
 */
export async function spawnIsolatedTestBackend(options = {}) {
  const runId = options.runId || crypto.randomUUID().slice(0, 8);
  const tmpDir = path.join(os.tmpdir(), `highview-test-${runId}`);
  
  const testDb = path.join(tmpDir, 'test.sqlite3');
  const datasetsDir = path.join(tmpDir, 'datasets');
  const uploadsDir = path.join(tmpDir, 'uploads');
  const exportsDir = path.join(tmpDir, 'exports');
  const dataDir = path.join(tmpDir, 'data');
  const presentationDir = path.join(dataDir, 'presentation_qa');

  // Create isolated directories
  fs.mkdirSync(tmpDir, { recursive: true });
  fs.mkdirSync(datasetsDir, { recursive: true });
  fs.mkdirSync(uploadsDir, { recursive: true });
  fs.mkdirSync(exportsDir, { recursive: true });
  fs.mkdirSync(dataDir, { recursive: true });
  fs.mkdirSync(presentationDir, { recursive: true });

  const port = options.port || await getAvailablePort();
  const baseUrl = `http://127.0.0.1:${port}`;

  const repoRoot = path.resolve(process.cwd(), path.join(import.meta.dirname, '../../'));
  const backendPython = path.join(repoRoot, 'backend/.venv/bin/python');

  console.log(`[TestFirewall] Spawning isolated test backend on port ${port}...`);
  console.log(`[TestFirewall] Isolated storage root: ${tmpDir}`);

  const env = {
    ...process.env,
    PYTHONPATH: path.join(repoRoot, 'backend'),
    APP_ENV: 'test',
    HIGHVIEW_ENVIRONMENT: 'test',
    TESTING: 'true',
    PORT: String(port),
    HIGHVIEW_PORT: String(port),
    DATABASE_PATH: testDb,
    HIGHVIEW_DB_PATH: testDb,
    PARQUET_STORAGE_DIR: datasetsDir,
    HIGHVIEW_PARQUET_STORAGE_DIR: datasetsDir,
    UPLOAD_DIR: uploadsDir,
    UPLOADS_DIR: uploadsDir,
    HIGHVIEW_UPLOADS_DIR: uploadsDir,
    DATA_DIR: dataDir,
    HIGHVIEW_DATA_DIR: dataDir,
    EXPORTS_DIR: exportsDir,
    HIGHVIEW_EXPORTS_DIR: exportsDir,
  };

  const proc = spawn(
    backendPython,
    ['-m', 'uvicorn', 'app.main:app', '--host', '127.0.0.1', '--port', String(port), '--log-level', 'warning'],
    {
      cwd: path.join(repoRoot, 'backend'),
      env,
      stdio: ['ignore', 'pipe', 'pipe'],
    }
  );

  let outputLog = '';
  proc.stdout.on('data', (d) => { outputLog += d.toString(); });
  proc.stderr.on('data', (d) => { outputLog += d.toString(); });

  // Poll /api/health until ready
  const startTime = Date.now();
  let isReady = false;
  while (Date.now() - startTime < 15000) {
    try {
      const res = await fetch(`${baseUrl}/api/health`);
      if (res.ok) {
        isReady = true;
        break;
      }
    } catch (e) {
      // Waiting for socket
    }
    await new Promise((r) => setTimeout(r, 200));
  }

  if (!isReady) {
    proc.kill('SIGKILL');
    fs.rmSync(tmpDir, { recursive: true, force: true });
    throw new Error(`Isolated test backend failed to start within 15s on port ${port}.\nLogs:\n${outputLog}`);
  }

  console.log(`[TestFirewall] Isolated test backend is healthy at ${baseUrl}`);

  const teardown = async () => {
    console.log(`[TestFirewall] Stopping isolated test backend (port ${port})...`);
    proc.kill('SIGTERM');
    await new Promise((r) => setTimeout(r, 500));
    try {
      proc.kill('SIGKILL');
    } catch (_) {}
    
    // Purge temporary isolated directories
    try {
      fs.rmSync(tmpDir, { recursive: true, force: true });
      console.log(`[TestFirewall] Destroyed temporary test storage: ${tmpDir}`);
    } catch (err) {
      console.warn(`[TestFirewall] Warning cleaning up ${tmpDir}:`, err.message);
    }
  };

  return {
    port,
    baseUrl,
    tmpDir,
    testDb,
    runId,
    teardown,
  };
}

/**
 * Captures an immutable snapshot of the user's live development environment:
 * - pulsehr.sqlite3 file size and SHA256 hash
 * - backend/data/datasets/ file tree
 * - backend/data/uploads/ file tree
 */
export function captureUserEnvironmentSnapshot(repoRoot) {
  const liveDbPath = path.resolve(repoRoot, 'backend/data/db/pulsehr.sqlite3');
  const datasetsDir = path.resolve(repoRoot, 'backend/data/datasets');
  const uploadsDir = path.resolve(repoRoot, 'backend/data/uploads');

  let dbSize = 0;
  let dbHash = null;

  if (fs.existsSync(liveDbPath)) {
    const stat = fs.statSync(liveDbPath);
    dbSize = stat.size;
    const buf = fs.readFileSync(liveDbPath);
    dbHash = crypto.createHash('sha256').update(buf).digest('hex');
  }

  const listFiles = (dir) => {
    if (!fs.existsSync(dir)) return [];
    const files = [];
    const walk = (d, rel = '') => {
      for (const item of fs.readdirSync(d)) {
        const full = path.join(d, item);
        const subRel = rel ? `${rel}/${item}` : item;
        const s = fs.statSync(full);
        if (s.isDirectory()) {
          walk(full, subRel);
        } else {
          files.push(`${subRel}:${s.size}`);
        }
      }
    };
    walk(dir);
    return files.sort();
  };

  return {
    timestamp: new Date().toISOString(),
    liveDb: {
      path: liveDbPath,
      size: dbSize,
      sha256: dbHash,
    },
    datasets: listFiles(datasetsDir),
    uploads: listFiles(uploadsDir),
  };
}

/**
 * Asserts that two environment snapshots are identical.
 */
export function assertEnvironmentSnapshotsIdentical(pre, post, contextLabel = 'Test Execution') {
  if (pre.liveDb.sha256 !== post.liveDb.sha256) {
    throw new Error(
      `[${contextLabel}] CRITICAL ENVIRONMENT MUTATION DETECTED: pulsehr.sqlite3 was modified during test run!\n` +
      `  Pre SHA256:  ${pre.liveDb.sha256} (${pre.liveDb.size} bytes)\n` +
      `  Post SHA256: ${post.liveDb.sha256} (${post.liveDb.size} bytes)`
    );
  }

  const preDs = JSON.stringify(pre.datasets);
  const postDs = JSON.stringify(post.datasets);
  if (preDs !== postDs) {
    throw new Error(
      `[${contextLabel}] CRITICAL ENVIRONMENT MUTATION DETECTED: backend/data/datasets was modified during test run!\n` +
      `  Pre:  ${preDs}\n` +
      `  Post: ${postDs}`
    );
  }

  const preUp = JSON.stringify(pre.uploads);
  const postUp = JSON.stringify(post.uploads);
  if (preUp !== postUp) {
    throw new Error(
      `[${contextLabel}] CRITICAL ENVIRONMENT MUTATION DETECTED: backend/data/uploads was modified during test run!\n` +
      `  Pre:  ${preUp}\n` +
      `  Post: ${postUp}`
    );
  }

  return true;
}

/**
 * Automatically discovers Chrome/Chromium executable path across OS environments.
 * Respects CHROME_PATH and CHROME_BIN environment variables.
 */
export function resolveChromeExecutablePath() {
  if (process.env.CHROME_PATH && fs.existsSync(process.env.CHROME_PATH)) {
    return process.env.CHROME_PATH;
  }
  if (process.env.CHROME_BIN && fs.existsSync(process.env.CHROME_BIN)) {
    return process.env.CHROME_BIN;
  }
  const macPaths = [
    '/Applications/Google Chrome.app/Contents/MacOS/Google Chrome',
    '/Applications/Chromium.app/Contents/MacOS/Chromium',
  ];
  for (const mp of macPaths) {
    if (fs.existsSync(mp)) return mp;
  }
  const linuxPaths = [
    '/usr/bin/google-chrome',
    '/usr/bin/google-chrome-stable',
    '/usr/bin/chromium-browser',
    '/usr/bin/chromium',
    '/snap/bin/chromium',
  ];
  for (const lp of linuxPaths) {
    if (fs.existsSync(lp)) return lp;
  }
  const winPaths = [
    'C:\\Program Files\\Google\\Chrome\\Application\\chrome.exe',
    'C:\\Program Files (x86)\\Google\\Chrome\\Application\\chrome.exe',
  ];
  for (const wp of winPaths) {
    if (fs.existsSync(wp)) return wp;
  }
  return undefined;
}

