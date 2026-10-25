import assert from 'node:assert/strict';
import { mkdtemp, writeFile, rm, readFile } from 'node:fs/promises';
import { tmpdir } from 'node:os';
import path from 'node:path';
import { createRequire } from 'node:module';
import { fileURLToPath } from 'node:url';
import { build } from 'esbuild';

const temporary = await mkdtemp(path.join(tmpdir(), 'dashboard-error-'));
try {
  const output = path.join(temporary, 'boundary.cjs');
  const bundle = await build({
    stdin: {
      contents: `export {default as React} from 'react';
        export {renderToStaticMarkup} from 'react-dom/server';
        export {default as Boundary} from './src/components/adaptive/EmptyDashboardBoundary.jsx';
        export {resolveDashboardState} from './src/contracts/DashboardStateContract.js';
        export {sanitizeError} from './src/contracts/ProductErrorSanitizer.js';`,
      resolveDir: fileURLToPath(new URL('../', import.meta.url)), loader: 'jsx',
    },
    bundle: true, write: false, platform: 'node', format: 'cjs',
    loader: { '.scss': 'empty' },
  });
  await writeFile(output, bundle.outputFiles[0].text);
  const { React, renderToStaticMarkup, Boundary, resolveDashboardState, sanitizeError } = createRequire(import.meta.url)(output);
  for (const failure of ['Failed to fetch', 'Server responded with status 500']) {
    const error = sanitizeError(new Error(failure));
    for (const [sourcesError, calcError] of [[error, error], [error, null], [null, error]]) {
      const state = resolveDashboardState({ sources: [{ id: 'one' }], selectedDatasetId: 'one', sourcesError, calcError });
      const html = renderToStaticMarkup(React.createElement(Boundary, {
        dashboardState: state, error: sourcesError || calcError,
      }, React.createElement('div', null, 'Analysis content')));
      assert.equal((html.match(/role="alert"/g) || []).length, 1);
      assert.equal((html.match(/<button/g) || []).length, 1);
      assert.ok(html.includes('Dashboard couldn’t be loaded'));
      assert.ok(html.includes('Check that the server is available, then try again.'));
      assert.ok(html.includes('explorer-empty-state'));
      assert.ok(html.includes('Try again'));
      assert.ok(!html.includes('Analysis content'));
      assert.ok(!html.includes('uploading a fresh copy'));
    }
  }
  const page = await readFile(new URL('../src/pages/AdaptiveDashboardPage.jsx', import.meta.url), 'utf8');
  assert.ok(!page.includes('{sourcesError.message}') && !page.includes('{calcError.message}'), 'request errors must only render through the boundary');
  assert.ok(!page.includes('type: "error"'), 'failed refreshes must not add an error toast');
  console.log('Dashboard errors: one notice and retry for source, analysis, and combined outages.');
} finally {
  await rm(temporary, { recursive: true, force: true });
}
