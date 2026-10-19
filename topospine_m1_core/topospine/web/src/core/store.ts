/**
 * Tiny observable store: the single place user-controlled state lives.
 * UI and pickers call `set`; views subscribe. No framework needed for one canvas and a panel.
 */

export type Listener<S> = (state: S, previous: S) => void;

export class Store<S extends object> {
  private state: S;
  private readonly listeners = new Set<Listener<S>>();

  constructor(initial: S) {
    this.state = { ...initial };
  }

  get(): Readonly<S> {
    return this.state;
  }

  set(patch: Partial<S>): void {
    const prev = this.state;
    const next = { ...prev, ...patch };
    if ((Object.keys(patch) as (keyof S)[]).every((k) => Object.is(prev[k], next[k]))) return; // no-op
    this.state = next;
    for (const fn of this.listeners) fn(next, prev);
  }

  subscribe(fn: Listener<S>): () => void {
    this.listeners.add(fn);
    return () => this.listeners.delete(fn);
  }
}
