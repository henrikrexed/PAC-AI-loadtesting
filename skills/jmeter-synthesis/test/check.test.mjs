// Unit tests for the own static check (check.mjs): the well-formedness scanner
// catches real malformation, and the gate fails closed on tampered artifacts.
import { test } from 'node:test';
import assert from 'node:assert/strict';
import path from 'node:path';
import { fileURLToPath } from 'node:url';
import { checkWellFormed, jmeterCheck } from '../lib/check.mjs';
import { buildArtifacts } from '../lib/synthesize.mjs';
import { loadModel } from '../lib/model.mjs';
import { buildDatasets } from '../lib/csv.mjs';

const HERE = path.dirname(fileURLToPath(import.meta.url));
const FIXTURE = path.join(HERE, 'fixtures', 'shop-checkout.workload-model.json');
const model = loadModel(FIXTURE);

test('well-formed scanner accepts balanced XML, rejects mismatches', () => {
  assert.equal(checkWellFormed('<a><b/></a>').ok, true);
  assert.equal(checkWellFormed('<a><b></a>').ok, false);
  assert.equal(checkWellFormed('<a>').ok, false);
  assert.equal(checkWellFormed('<a x="1"><!-- c --><![CDATA[ <x> ]]></a>').ok, true);
  assert.equal(checkWellFormed('<a x="1></a>').ok, false); // unbalanced quote
});

test('full gate passes on freshly rendered artifacts', () => {
  const { xml, datasets, files, meta } = buildArtifacts(model);
  const res = jmeterCheck({ model, xml, datasets, files, maxRate: meta.maxRate, totalThreads: meta.totalThreads });
  assert.equal(res.pass, true);
});

test('gate fails closed when synthetic baggage is stripped', () => {
  const { xml, datasets, files, meta } = buildArtifacts(model);
  const tampered = xml.replace(/synthetic=true/g, 'tampered');
  const res = jmeterCheck({ model, xml: tampered, datasets, files, maxRate: meta.maxRate, totalThreads: meta.totalThreads });
  assert.equal(res.pass, false);
  assert.equal(res.checks.find((c) => c.id === 'synthetic').pass, false);
});

test('gate fails closed when a CSV file is missing from the fileset', () => {
  const { xml, meta } = buildArtifacts(model);
  const datasets = buildDatasets(model);
  const res = jmeterCheck({ model, xml, datasets, files: [], maxRate: meta.maxRate, totalThreads: meta.totalThreads });
  assert.equal(res.pass, false);
  assert.equal(res.checks.find((c) => c.id === 'datasets').pass, false);
});

test('gate fails closed when declared load exceeds caps', () => {
  const { xml, datasets, files } = buildArtifacts(model);
  const res = jmeterCheck({ model, xml, datasets, files, maxRate: 9999, totalThreads: 9999 });
  assert.equal(res.pass, false);
  assert.equal(res.checks.find((c) => c.id === 'caps').pass, false);
});
