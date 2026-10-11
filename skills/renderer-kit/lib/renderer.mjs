// renderer.mjs — the formal Renderer interface (research §4.3).
//
// A renderer is a PURE FUNCTION over an approved workload-model.json: no network,
// no mutation of the model, deterministic output for a given (model, opts). Each
// tool (k6 / jmeter / locust / gatling) ships one renderer that conforms to this
// contract so the agent/user can pick a target tool from the registry and get the
// same shape back regardless of tool.
//
//   interface Renderer {
//     name: string         // "k6" | "jmeter" | "locust" | "gatling"
//     targetTool: string   // human label, e.g. "Grafana k6"
//     schemaRange: string  // compatible §4 schema versions, e.g. ">=1.0 <2.0"
//     supports(model) -> CapabilityReport     // declared BEFORE rendering
//     render(model, opts) -> { files, warnings }
//   }
//
// CapabilityReport = {
//   ok: boolean,                       // true iff nothing is unsupported
//   unsupported: Array<{
//     feature: string,                 // the §4 construct not natively honored
//     reason: string,                  // why this tool can't honor it
//     approximation?: string           // what the renderer will do instead (if it still renders)
//   }>
// }
//
// RenderResult = {
//   files: Array<{ path: string, content: string }>,  // paths relative to an outDir
//   warnings: string[]
// }

/**
 * Build a well-formed capability report from a list of unsupported features.
 * `ok` is derived: a renderer that can honor everything returns `ok:true` with an
 * empty list; any entry flips `ok` to false so the agent warns the human at VALIDATE.
 */
export function makeCapabilityReport(unsupported = []) {
  const list = Array.isArray(unsupported) ? unsupported : [];
  return { ok: list.length === 0, unsupported: list };
}

/**
 * Validate the SHAPE of a capability report. Throws a TypeError on any violation.
 * This is the convention every renderer's `supports()` must satisfy; the shared
 * acceptance harness calls it so no renderer can return a malformed report.
 */
export function validateCapabilityReport(report, who = 'renderer') {
  if (!report || typeof report !== 'object') {
    throw new TypeError(`${who}.supports() must return an object, got ${typeof report}`);
  }
  if (typeof report.ok !== 'boolean') {
    throw new TypeError(`${who}.supports().ok must be a boolean`);
  }
  if (!Array.isArray(report.unsupported)) {
    throw new TypeError(`${who}.supports().unsupported must be an array`);
  }
  for (const [i, u] of report.unsupported.entries()) {
    if (!u || typeof u !== 'object') {
      throw new TypeError(`${who}.supports().unsupported[${i}] must be an object`);
    }
    if (typeof u.feature !== 'string' || !u.feature) {
      throw new TypeError(`${who}.supports().unsupported[${i}].feature must be a non-empty string`);
    }
    if (typeof u.reason !== 'string' || !u.reason) {
      throw new TypeError(`${who}.supports().unsupported[${i}].reason must be a non-empty string`);
    }
    if (u.approximation != null && typeof u.approximation !== 'string') {
      throw new TypeError(`${who}.supports().unsupported[${i}].approximation must be a string when present`);
    }
  }
  // the derived invariant: ok === (unsupported is empty)
  if (report.ok !== (report.unsupported.length === 0)) {
    throw new TypeError(`${who}.supports().ok (${report.ok}) is inconsistent with ${report.unsupported.length} unsupported features`);
  }
  return report;
}

/**
 * Validate the SHAPE of a render result. Throws a TypeError on any violation.
 */
export function validateRenderResult(result, who = 'renderer') {
  if (!result || typeof result !== 'object') {
    throw new TypeError(`${who}.render() must return an object, got ${typeof result}`);
  }
  if (!Array.isArray(result.files)) {
    throw new TypeError(`${who}.render().files must be an array`);
  }
  if (result.files.length === 0) {
    throw new TypeError(`${who}.render().files must contain at least one file`);
  }
  for (const [i, f] of result.files.entries()) {
    if (!f || typeof f !== 'object') throw new TypeError(`${who}.render().files[${i}] must be an object`);
    if (typeof f.path !== 'string' || !f.path) throw new TypeError(`${who}.render().files[${i}].path must be a non-empty string`);
    if (typeof f.content !== 'string') throw new TypeError(`${who}.render().files[${i}].content must be a string`);
  }
  if (!Array.isArray(result.warnings)) {
    throw new TypeError(`${who}.render().warnings must be an array`);
  }
  return result;
}

/**
 * Validate that an object conforms to the Renderer interface (static shape only —
 * does not invoke supports/render). Throws a TypeError on any violation.
 */
export function validateRenderer(renderer) {
  if (!renderer || typeof renderer !== 'object') {
    throw new TypeError('renderer must be an object');
  }
  for (const k of ['name', 'targetTool', 'schemaRange']) {
    if (typeof renderer[k] !== 'string' || !renderer[k]) {
      throw new TypeError(`renderer.${k} must be a non-empty string`);
    }
  }
  for (const k of ['supports', 'render']) {
    if (typeof renderer[k] !== 'function') {
      throw new TypeError(`renderer.${k} must be a function`);
    }
  }
  return renderer;
}

/**
 * Helper for authoring a renderer: fills defaults and validates the static shape.
 * Returns the frozen renderer object.
 */
export function defineRenderer(spec) {
  const renderer = {
    name: spec.name,
    targetTool: spec.targetTool || spec.name,
    schemaRange: spec.schemaRange || '>=1.0 <2.0',
    supports: spec.supports,
    render: spec.render,
  };
  validateRenderer(renderer);
  return Object.freeze(renderer);
}
