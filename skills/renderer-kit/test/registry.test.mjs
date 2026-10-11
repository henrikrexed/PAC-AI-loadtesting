// Registry: register / get / has / names / list, keyed by renderer name.
import { test } from 'node:test';
import assert from 'node:assert/strict';
import { RendererRegistry, createRegistry } from '../lib/registry.mjs';
import { defineRenderer, makeCapabilityReport } from '../lib/renderer.mjs';

function stub(name) {
  return defineRenderer({
    name,
    supports: () => makeCapabilityReport([]),
    render: () => ({ files: [{ path: `${name}/f`, content: '' }], warnings: [] }),
  });
}

test('register + get + has + names', () => {
  const reg = new RendererRegistry();
  reg.register(stub('k6')).register(stub('locust'));
  assert.ok(reg.has('k6'));
  assert.ok(reg.has('locust'));
  assert.equal(reg.get('k6').name, 'k6');
  assert.deepEqual(reg.names(), ['k6', 'locust']);
  assert.equal(reg.list().length, 2);
});

test('get throws a helpful error for an unknown tool', () => {
  const reg = createRegistry([stub('k6')]);
  assert.throws(() => reg.get('gatling'), /no renderer registered for "gatling".*known: k6/);
});

test('duplicate registration is refused', () => {
  const reg = createRegistry([stub('k6')]);
  assert.throws(() => reg.register(stub('k6')), /already registered/);
});

test('register validates renderer shape', () => {
  const reg = new RendererRegistry();
  assert.throws(() => reg.register({ name: 'bad' }), TypeError);
});

test('createRegistry pre-populates', () => {
  const reg = createRegistry([stub('k6'), stub('jmeter'), stub('locust'), stub('gatling')]);
  assert.deepEqual(reg.names(), ['k6', 'jmeter', 'locust', 'gatling']);
});
