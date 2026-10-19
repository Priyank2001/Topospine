/** Composition root: find the DOM elements, start the App, clean up on hot reload. */

import "./styles.css";
import { App } from "./app/App";

const byId = <T extends HTMLElement>(id: string) => {
  const el = document.getElementById(id);
  if (!el) throw new Error(`#${id} missing from index.html`);
  return el as T;
};

const app = new App({
  canvas: byId<HTMLCanvasElement>("spine-canvas"),
  plot: byId<HTMLCanvasElement>("persistence-plot"),
  panel: byId("panel"),
  stats: byId("stats"),
  status: byId("status"),
  datasetLine: byId("dataset-line"),
});
app.start().catch((err) => {
  byId("status").textContent = `Startup failed: ${(err as Error).message}`;
  console.error(err);
});

if (import.meta.hot) import.meta.hot.dispose(() => app.dispose()); // no GPU leaks during development
