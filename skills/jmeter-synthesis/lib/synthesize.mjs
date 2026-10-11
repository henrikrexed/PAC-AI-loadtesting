// synthesize.mjs — orchestrator: approved workload-model.json -> jmeter/*.jmx +
// jmeter/data/*.csv + a manifest, then run the own static check (check.mjs).
//
// buildArtifacts() is the PURE in-memory core (deterministic, no network, no disk)
// shared by synthesize() (writes + checks) and the formal Renderer adapter
// (renderer.mjs, §4.3) so the on-disk layout and the renderer files[] never drift
// — exactly the pattern the k6 renderer uses.

import { mkdirSync, writeFileSync } from 'node:fs';
import path from 'node:path';
import { loadModel, assertApproved } from './model.mjs';
import { buildDatasets } from './csv.mjs';
import { generateJmx } from './jmx.mjs';
import { jmeterCheck } from './check.mjs';
import { capabilityReport } from './capability.mjs';

/**
 * Build all JMeter artifacts IN MEMORY from an approved model.
 * Returns { files, warnings, datasets, jmx, meta } where files is
 * [{ path, content }] with paths relative to an outDir:
 *   jmeter/<name>.jmx, jmeter/data/<pool>.csv, jmeter/<name>.manifest.json
 */
export function buildArtifacts(model) {
  const name = model.metadata.name;
  const datasets = buildDatasets(model);
  const { xml, warnings, maxRate, totalThreads, isOpen } = generateJmx(model, datasets);

  const files = [];
  files.push({ path: path.posix.join('jmeter', `${name}.jmx`), content: xml });
  for (const ds of Object.values(datasets)) {
    files.push({ path: path.posix.join('jmeter', 'data', ds.filename), content: ds.content });
  }

  const report = capabilityReport(model);
  const manifest = {
    tool: 'jmeter',
    generatedBy: 'jmeter-synthesis (ISI-5656)',
    model: { name, revision: model.status.revision, targetService: model.metadata.targetService || null },
    synthetic: { header: 'baggage', value: 'synthetic=true', note: 'stamped on every request via the test-plan Header Manager' },
    otel: {
      note: 'W3C trace-context + span export requires the JMeter OpenTelemetry listener plugin at EXECUTE; baggage synthetic=true is carried natively here.',
    },
    executor: isOpen
      ? 'Concurrency Thread Group + Throughput Shaping Timer (open model)'
      : 'Thread Group (closed model)',
    load: { maxRate, totalThreads, caps: model.spec.caps || null },
    datasets: Object.values(datasets).map((ds) => ({
      id: ds.id,
      kind: ds.kind,
      file: `data/${ds.filename}`,
      variables: ds.variableNames,
      ...(ds.kind === 'cache-key'
        ? { keyField: ds.keyField, sampleRows: ds.sampleRows, cacheProfile: ds.cacheProfile }
        : { recordCount: ds.recordCount, pii: ds.pii }),
    })),
    capability: report,
    plugins: ['jp@gc - Concurrency Thread Group', 'jp@gc - Throughput Shaping Timer'],
  };
  files.push({
    path: path.posix.join('jmeter', `${name}.manifest.json`),
    content: JSON.stringify(manifest, null, 2) + '\n',
  });

  return { files, warnings, datasets, xml, meta: { maxRate, totalThreads, isOpen } };
}

/**
 * Run the full synthesis: build, write every artifact to disk, run the static
 * check. Throws on the V1 gate (unapproved model) before writing anything.
 * Returns { model, outDir, files, warnings, check, meta }.
 */
export function synthesize(modelPathOrObj, outDir) {
  const model = loadModel(modelPathOrObj);
  assertApproved(model); // V1 gate — refuse unapproved models (common contract)

  const { files, warnings, datasets, xml, meta } = buildArtifacts(model);
  for (const f of files) {
    const abs = path.join(outDir, f.path);
    mkdirSync(path.dirname(abs), { recursive: true });
    writeFileSync(abs, f.content);
  }

  const check = jmeterCheck({
    model,
    xml,
    datasets,
    files,
    maxRate: meta.maxRate,
    totalThreads: meta.totalThreads,
  });

  return { model, outDir, files, warnings, check, meta };
}
