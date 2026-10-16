/**
 * Negative Verification Test: Test Environment Firewall
 * 
 * Verifies:
 * 1. Client-side guard REFUSES mutating operations against live server (localhost:8000).
 * 2. Server-side middleware BLOCKS test-marked mutating requests on live server with 403 Forbidden.
 * 3. Ephemeral isolated test backend ALLOWS test mutations cleanly.
 */

import assert from 'assert';
import {
  assertIsolatedTestTarget,
  LiveInstanceMutationBlockedError,
  spawnIsolatedTestBackend,
  getTestHeaders,
} from './test_environment_guard.mjs';

async function runNegativeVerification() {
  console.log('🧪 Starting Test Environment Firewall Negative Verification Suite...\n');

  // 1. Client-side guard negative checks
  console.log('1. Testing client-side guard against localhost:8000...');
  let refusedLocalhost = false;
  try {
    assertIsolatedTestTarget('http://localhost:8000', 'negative_test_upload');
  } catch (err) {
    if (err instanceof LiveInstanceMutationBlockedError) {
      refusedLocalhost = true;
    } else {
      throw err;
    }
  }
  assert.strictEqual(refusedLocalhost, true, 'Guard must refuse http://localhost:8000');
  console.log('   ✅ PASS: Refused mutation against http://localhost:8000 before network execution.');

  console.log('2. Testing client-side guard against 127.0.0.1:8000...');
  let refusedIp = false;
  try {
    assertIsolatedTestTarget('http://127.0.0.1:8000', 'negative_test_delete');
  } catch (err) {
    if (err instanceof LiveInstanceMutationBlockedError) {
      refusedIp = true;
    } else {
      throw err;
    }
  }
  assert.strictEqual(refusedIp, true, 'Guard must refuse http://127.0.0.1:8000');
  console.log('   ✅ PASS: Refused mutation against http://127.0.0.1:8000 before network execution.');

  // 3. Server-side firewall negative check against running live backend on port 8000
  console.log('3. Testing server-side firewall rejection on live server port 8000...');
  try {
    const liveRes = await fetch('http://127.0.0.1:8000/api/upload/datasets', {
      method: 'DELETE',
      headers: {
        ...getTestHeaders('negative-probe-live'),
      },
    });

    assert.strictEqual(
      liveRes.status,
      403,
      `Live server must return 403 Forbidden for mutating test run. Got HTTP ${liveRes.status}`
    );
    const body = await liveRes.json();
    assert.strictEqual(
      body.error,
      'FORBIDDEN_TEST_MUTATION_ON_LIVE_INSTANCE',
      'Live server must return FORBIDDEN_TEST_MUTATION_ON_LIVE_INSTANCE error code'
    );
    console.log('   ✅ PASS: Live server rejected test mutation with 403 Forbidden (FORBIDDEN_TEST_MUTATION_ON_LIVE_INSTANCE).');
  } catch (err) {
    if (err.code === 'ECONNREFUSED') {
      console.log('   ℹ️  (Live server port 8000 not currently running; skipping live HTTP probe)');
    } else {
      throw err;
    }
  }

  // 4. Positive check: Spawning ephemeral isolated test backend
  console.log('4. Testing allowed mutation on isolated test backend instance...');
  const isolated = await spawnIsolatedTestBackend();
  try {
    assertIsolatedTestTarget(isolated.baseUrl, 'isolated_test_mutation');
    console.log(`   ✅ PASS: Client-side guard permits isolated target ${isolated.baseUrl}`);

    const testRes = await fetch(`${isolated.baseUrl}/api/upload/datasets`, {
      method: 'DELETE',
      headers: {
        ...getTestHeaders('isolated-probe'),
      },
    });

    assert.strictEqual(testRes.status, 200, `Isolated backend must allow test mutations. Got HTTP ${testRes.status}`);
    const testJson = await testRes.json();
    assert.strictEqual(testJson.orphan_check, 'PASS', 'Isolated backend must handle clear operation with orphan_check: PASS');
    console.log('   ✅ PASS: Isolated backend processed mutation cleanly (orphan_check: PASS).');
  } finally {
    await isolated.teardown();
  }

  console.log('\n🎉 ALL TEST ENVIRONMENT FIREWALL VERIFICATIONS PASSED!\n');
}

runNegativeVerification().catch((err) => {
  console.error('\n❌ FIREWALL TEST FAILED:', err);
  process.exit(1);
});
