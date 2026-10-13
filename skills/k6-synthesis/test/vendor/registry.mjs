// registry.mjs — tool registry keyed by renderer name (research §4.3).
//
// The agent/user picks a target tool by name ("k6" | "jmeter" | "locust" |
// "gatling"); the registry returns the renderer. Renderers register themselves
// (or are registered by the host) so JMeter/Locust/Gatling can be built in
// separate packages and plugged in without the registry knowing about them.

import { validateRenderer } from '../../lib/vendor/renderer.mjs';

export class RendererRegistry {
  constructor() {
    this._byName = new Map();
  }

  /** Register a renderer. Validates its shape; refuses duplicate names. */
  register(renderer) {
    validateRenderer(renderer);
    if (this._byName.has(renderer.name)) {
      throw new Error(`renderer "${renderer.name}" is already registered`);
    }
    this._byName.set(renderer.name, renderer);
    return this;
  }

  has(name) {
    return this._byName.has(name);
  }

  /** Get a renderer by name. Throws a clear error listing known tools if absent. */
  get(name) {
    const r = this._byName.get(name);
    if (!r) {
      throw new Error(`no renderer registered for "${name}" (known: ${this.names().join(', ') || 'none'})`);
    }
    return r;
  }

  /** All registered renderer names, in registration order. */
  names() {
    return [...this._byName.keys()];
  }

  /** All registered renderers, in registration order. */
  list() {
    return [...this._byName.values()];
  }
}

/** Build a registry pre-populated with the given renderers. */
export function createRegistry(renderers = []) {
  const reg = new RendererRegistry();
  for (const r of renderers) reg.register(r);
  return reg;
}
