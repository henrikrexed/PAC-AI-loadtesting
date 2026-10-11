// model-access: §4 v1.1 (G-R1/G-P1) accessors with pre-v1.1 back-compat.
import { test } from 'node:test';
import assert from 'node:assert/strict';
import {
  parseOperation,
  resolveRequest,
  methodHasBody,
  resolveFieldTarget,
  partitionDrivableSteps,
} from '../lib/model-access.mjs';

test('parseOperation splits method + path', () => {
  assert.deepEqual(parseOperation('GET /api/products/{id}'), { method: 'GET', pathTemplate: '/api/products/{id}' });
  assert.deepEqual(parseOperation('/no/method'), { method: 'GET', pathTemplate: '/no/method' });
});

test('resolveRequest (pre-v1.1): string-parses operation, falls back to payloadRef', () => {
  const step = { operation: 'POST /api/cart', payloadRef: 'cartItem' };
  const r = resolveRequest(step);
  assert.equal(r.method, 'POST');
  assert.equal(r.pathTemplate, '/api/cart');
  assert.deepEqual(r.queryParams, {});
  assert.deepEqual(r.headers, {});
  assert.equal(r.bodyPayloadRef, 'cartItem');
});

test('resolveRequest (v1.1 G-R1): prefers structured request fields', () => {
  const step = {
    operation: 'POST /api/cart',
    request: {
      method: 'PUT',
      pathTemplate: '/api/cart/{cartId}',
      queryParams: { dryRun: 'true' },
      headers: { 'X-Api-Version': '2' },
      bodyPayloadRef: 'cartUpdate',
    },
  };
  const r = resolveRequest(step);
  assert.equal(r.method, 'PUT');
  assert.equal(r.pathTemplate, '/api/cart/{cartId}');
  assert.deepEqual(r.queryParams, { dryRun: 'true' });
  assert.deepEqual(r.headers, { 'X-Api-Version': '2' });
  assert.equal(r.bodyPayloadRef, 'cartUpdate');
});

test('resolveRequest (v1.1 partial): structured request inherits method from operation', () => {
  const step = { operation: 'GET /api/x', request: { pathTemplate: '/api/x/{id}' } };
  const r = resolveRequest(step);
  assert.equal(r.method, 'GET'); // inherited from operation
  assert.equal(r.pathTemplate, '/api/x/{id}');
});

test('methodHasBody', () => {
  assert.equal(methodHasBody('POST'), true);
  assert.equal(methodHasBody('put'), true);
  assert.equal(methodHasBody('GET'), false);
});

test('resolveFieldTarget (pre-v1.1): defaults to body_field under field name', () => {
  assert.deepEqual(resolveFieldTarget({ name: 'email' }), { into: 'body_field', as: 'email' });
});

test('resolveFieldTarget (v1.1 G-P1): honors explicit target', () => {
  assert.deepEqual(
    resolveFieldTarget({ name: 'q', target: { into: 'query_param', as: 'search' } }),
    { into: 'query_param', as: 'search' }
  );
  // target without `as` falls back to field name
  assert.deepEqual(resolveFieldTarget({ name: 'id', target: { into: 'path_param' } }), { into: 'path_param', as: 'id' });
});

test('partitionDrivableSteps separates http edge steps from topology steps (G-X1)', () => {
  const j = {
    steps: [
      { id: 'a', callType: 'http' },
      { id: 'b', callType: 'db' },
      { id: 'c', callType: 'http' },
      { id: 'd', callType: 'grpc' },
    ],
  };
  const { driven, undriven } = partitionDrivableSteps(j);
  assert.deepEqual(driven.map((s) => s.id), ['a', 'c']);
  assert.deepEqual(undriven.map((s) => s.id), ['b', 'd']);
});
