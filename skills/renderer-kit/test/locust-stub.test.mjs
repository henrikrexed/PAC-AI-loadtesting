// locust-stub: proves the trivial non-k6 renderer conforms to the interface,
// returns an honest capability report, and runs the shared acceptance harness.
import { test } from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';
import { locustStub } from '../lib/renderers/locust-stub.mjs';
import { assertRendererConformance } from '../lib/acceptance.mjs';
import { createRegistry } from '../lib/registry.mjs';

const HERE = path.dirname(fileURLToPath(import.meta.url));
const FIXTURE = path.join(HERE, 'fixtures', 'shop-checkout.workload-model.json');
const model = JSON.parse(readFileSync(FIXTURE, 'utf8'));

test('locust-stub passes the shared renderer acceptance harness', () => {
  const { supports, render } = assertRendererConformance(locustStub, model);
  // open-arrival fixture => Locust must report the G-O1 approximation
  assert.equal(supports.ok, false);
  assert.ok(supports.unsupported.some((u) => u.feature === 'arrivalProfile.model=open'));
  // render produced a locustfile
  assert.ok(render.files.some((f) => f.path === 'locust/shop-checkout.py'));
});

test('locust-stub capability report flags empirical-free fixture correctly', () => {
  // shop-checkout uses exponential/uniform/constant think-times -> no empirical flag
  const report = locustStub.supports(model);
  assert.ok(!report.unsupported.some((u) => u.feature === 'thinkTime.distribution=empirical'));
});

test('locust-stub reports empirical think-time + grpc as unsupported when present', () => {
  const m = JSON.parse(JSON.stringify(model));
  m.spec.journeys[0].steps[0].thinkTime = { distribution: 'empirical', samples: [10, 20] };
  m.spec.journeys[0].steps.push({ id: 'cache-read', service: 's', operation: 'GET x', callType: 'cache' });
  const report = locustStub.supports(m);
  assert.ok(report.unsupported.some((u) => u.feature === 'thinkTime.distribution=empirical'));
  assert.ok(report.unsupported.some((u) => u.feature.startsWith('callType in')));
});

test('locustfile warnings mirror the capability report', () => {
  const { warnings } = locustStub.render(model);
  const report = locustStub.supports(model);
  assert.equal(warnings.length, report.unsupported.length);
});

test('locust-stub uses G-R1 structured request when present', () => {
  const m = JSON.parse(JSON.stringify(model));
  m.spec.journeys[0].steps[0].request = { method: 'POST', pathTemplate: '/api/search' };
  const file = m.spec.journeys[0] && locustStub.render(m).files[0].content;
  assert.ok(file.includes("self.client.post('/api/search'"));
});

test('locust-stub registers and resolves from a registry alongside other tools', () => {
  const reg = createRegistry([locustStub]);
  assert.equal(reg.get('locust').name, 'locust');
  assert.ok(reg.names().includes('locust'));
});
