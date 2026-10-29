import assert from 'node:assert/strict';
import { bulkDeleteDatasets, deleteDataset, deleteAllDatasets } from '../src/api/client.js';

const originalFetch = globalThis.fetch;
try {
  for (const remove of [() => bulkDeleteDatasets([7, 20]), () => deleteDataset(7), deleteAllDatasets]) {
    for (const [body, status] of [['Internal Server Error', 500], ['<html>Bad Gateway</html>', 502], ['', 200]]) {
      globalThis.fetch = async () => new Response(body, { status });
      await assert.rejects(remove, /Could not confirm workbook deletion/);
    }
    globalThis.fetch = async () => Response.json({ detail: 'Workbook storage is read-only.' }, { status: 503 });
    await assert.rejects(remove, /Workbook storage is read-only/);
    const result = { deleted_count: 2, cleanup_pending: false };
    globalThis.fetch = async () => Response.json(result);
    assert.deepEqual(await remove(), result);
  }
} finally {
  globalThis.fetch = originalFetch;
}
console.log('Deletion response tests passed.');
