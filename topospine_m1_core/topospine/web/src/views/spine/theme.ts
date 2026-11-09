/** Canvas colours read from the page's CSS tokens, so the spine follows light/dark mode. */

import * as THREE from "three";

export type RGB = [number, number, number];

export interface Theme {
  background: RGB;
  ink: RGB;
  paper: RGB;
}

function cssColor(name: string, fallback: string): RGB {
  const raw = getComputedStyle(document.documentElement).getPropertyValue(name).trim() || fallback;
  const c = new THREE.Color(raw);
  return [c.r, c.g, c.b];
}

export function readTheme(): Theme {
  return {
    background: cssColor("--canvas", "#f3f5f7"),
    ink: cssColor("--ink", "#1f2a36"),
    paper: cssColor("--paper", "#ffffff"),
  };
}
