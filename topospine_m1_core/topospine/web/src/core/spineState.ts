/** User-controlled parameters of the spine view, with defaults. */

import { RadiusMode } from "./spine/links";
import { Saturation } from "./types";

export interface SpineParams {
  pLo: number;
  pHi: number;
  saturation: Saturation;
  dedupe: boolean;
  radiusMode: RadiusMode;
  glyphScale: number;
  minLevelGap: number; // fraction of the height range
  maxLevels: number;
  extraLevels: number; // evenly spaced pseudo-contours added to the critical values
  showSkeleton: boolean;
  showNodes: boolean;
}

export const DEFAULT_PARAMS: SpineParams = {
  pLo: 0,
  pHi: Infinity,
  saturation: "paper",
  dedupe: true,
  radiusMode: "sqrt",
  glyphScale: 0.5,
  minLevelGap: 0.03,
  maxLevels: 24,
  extraLevels: 6,
  showSkeleton: true,
  showNodes: true,
};
