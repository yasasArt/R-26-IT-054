// lib/mock/quality.mock.ts
import type {
  IGarmentAnalysis,
  IColourDetection,
  ISizeMeasurement,
  IStyleDetection,
  ISpecMatchResult,
  IDemoScriptStep,
} from "@/lib/types";
import { generateId, randomFloat } from "@/lib/utils";
import { COLOUR_LIBRARY, PRODUCTION_SPECS, SIZE_THRESHOLDS } from "@/lib/constants";

// ─────────────────────────────────────────
// SAMPLE GARMENTS
// ─────────────────────────────────────────

/** Pre-defined garment samples for demo cycling */
export const SAMPLE_GARMENTS: Omit<IGarmentAnalysis, "id" | "timestamp" | "frameCapturedAt">[] = [
  // PASS — T-Shirt M Navy
  {
    sizeMeasurement: {
      widthCm: 48.2,
      heightCm: 67.5,
      detectedSize: "M",
      pixelPerCmRatio: 18.4,
      confidenceScore: 0.94,
    },
    styleDetection: { style: "T-Shirt", confidenceScore: 0.91 },
    colourDetections: [
      { id: "c1", name: "Navy Blue", hex: "#1E3A5F", percentage: 95, },
    ],
    decision: "PASS",
    specMatchResults: [
      { attribute: "size",   label: "Size",   expected: "M",         detected: "M",         isMatch: true  },
      { attribute: "style",  label: "Style",  expected: "T-Shirt",   detected: "T-Shirt",   isMatch: true  },
      { attribute: "colour", label: "Colour", expected: "Navy Blue", detected: "Navy Blue", isMatch: true  },
      { attribute: "width",  label: "Width",  expected: "46–52 cm",  detected: "48.2 cm",   isMatch: true  },
      { attribute: "height", label: "Height", expected: "65–70 cm",  detected: "67.5 cm",   isMatch: true  },
    ],
    overallConfidence: 0.93,
  },

  // MISMATCH — Wrong colour
  {
    sizeMeasurement: {
      widthCm: 49.1,
      heightCm: 68.0,
      detectedSize: "M",
      pixelPerCmRatio: 18.4,
      confidenceScore: 0.92,
    },
    styleDetection: { style: "T-Shirt", confidenceScore: 0.89 },
    colourDetections: [
      { id: "c2", name: "Sky Blue", hex: "#4FA3D1", percentage: 80 },
      { id: "c3", name: "White",    hex: "#F8F8F8", percentage: 20 },
    ],
    decision: "MISMATCH",
    specMatchResults: [
      { attribute: "size",   label: "Size",   expected: "M",         detected: "M",        isMatch: true  },
      { attribute: "style",  label: "Style",  expected: "shorts",   detected: "shorts",  isMatch: true  },
      { attribute: "colour", label: "Colour", expected: "Navy Blue", detected: "Sky Blue", isMatch: false },
      { attribute: "width",  label: "Width",  expected: "46–52 cm",  detected: "49.1 cm",  isMatch: true  },
      { attribute: "height", label: "Height", expected: "65–70 cm",  detected: "68.0 cm",  isMatch: true  },
    ],
    overallConfidence: 0.62,
  },

  // REWORK — Wrong size
  {
    sizeMeasurement: {
      widthCm: 54.8,
      heightCm: 71.2,
      detectedSize: "L",
      pixelPerCmRatio: 18.4,
      confidenceScore: 0.88,
    },
    styleDetection: { style: "Pants", confidenceScore: 0.90 },
    colourDetections: [
      { id: "c4", name: "Navy Blue", hex: "#1E3A5F", percentage: 96 },
    ],
    decision: "REWORK",
    specMatchResults: [
      { attribute: "size",   label: "Size",   expected: "M",        detected: "L",        isMatch: false },
      { attribute: "style",  label: "Style",  expected: "pants",  detected: "pants",  isMatch: true  },
      { attribute: "colour", label: "Colour", expected: "Navy Blue",detected: "Navy Blue",isMatch: true  },
      { attribute: "width",  label: "Width",  expected: "46–52 cm", detected: "54.8 cm",  isMatch: false },
      { attribute: "height", label: "Height", expected: "65–70 cm", detected: "71.2 cm",  isMatch: false },
    ],
    overallConfidence: 0.74,
  },

  // PASS — T-Shirt L White
  {
    sizeMeasurement: {
      widthCm: 55.3,
      heightCm: 70.8,
      detectedSize: "L",
      pixelPerCmRatio: 18.4,
      confidenceScore: 0.96,
    },
    styleDetection: { style: "T-Shirt", confidenceScore: 0.94 },
    colourDetections: [
      { id: "c5", name: "White", hex: "#F8F8F8", percentage: 98 },
    ],
    decision: "PASS",
    specMatchResults: [
      { attribute: "size",   label: "Size",   expected: "L",     detected: "L",     isMatch: true },
      { attribute: "style",  label: "Style",  expected: "T-Shirt",detected: "T-Shirt",isMatch: true },
      { attribute: "colour", label: "Colour", expected: "White", detected: "White", isMatch: true },
      { attribute: "width",  label: "Width",  expected: "52–58 cm",detected: "55.3 cm",isMatch: true },
      { attribute: "height", label: "Height", expected: "68–74 cm",detected: "70.8 cm",isMatch: true },
    ],
    overallConfidence: 0.95,
  },

  // MISMATCH — Wrong style
  {
    sizeMeasurement: {
      widthCm: 47.5,
      heightCm: 66.2,
      detectedSize: "M",
      pixelPerCmRatio: 18.4,
      confidenceScore: 0.91,
    },
    styleDetection: {
      style: "T-Shirt",
      confidenceScore: 0.85,
      alternativeStyle: "Pants",
      alternativeScore: 0.61,
    },
    colourDetections: [
      { id: "c6", name: "Navy Blue", hex: "#1E3A5F", percentage: 94 },
    ],
    decision: "MISMATCH",
    specMatchResults: [
      { attribute: "size",   label: "Size",   expected: "M",        detected: "M",        isMatch: true  },
      { attribute: "style",  label: "Style",  expected: "Pants",    detected: "T-Shirt",  isMatch: false },
      { attribute: "colour", label: "Colour", expected: "Navy Blue",detected: "Navy Blue",isMatch: true  },
      { attribute: "width",  label: "Width",  expected: "46–52 cm", detected: "47.5 cm",  isMatch: true  },
      { attribute: "height", label: "Height", expected: "65–70 cm", detected: "66.2 cm",  isMatch: true  },
    ],
    overallConfidence: 0.70,
  },
];

// ─────────────────────────────────────────
// GENERATOR
// ─────────────────────────────────────────

let garmentIndex = 0;

export function generateGarmentAnalysis(): IGarmentAnalysis {
  const template = SAMPLE_GARMENTS[garmentIndex % SAMPLE_GARMENTS.length];
  garmentIndex++;

  return {
    ...template,
    id: generateId("gmt"),
    timestamp: new Date(),
    frameCapturedAt: new Date(),
    sizeMeasurement: {
      ...template.sizeMeasurement,
      // Add small variance to measurements each time
      widthCm: parseFloat(
        (template.sizeMeasurement.widthCm + (Math.random() * 1.2 - 0.6)).toFixed(1)
      ),
      heightCm: parseFloat(
        (template.sizeMeasurement.heightCm + (Math.random() * 1.4 - 0.7)).toFixed(1)
      ),
    },
  };
}

export function resetGarmentIndex() {
  garmentIndex = 0;
}

// ─────────────────────────────────────────
// DEMO SCRIPTS
// ─────────────────────────────────────────

export const QUALITY_DEMO_SCRIPT_NORMAL: IDemoScriptStep[] = [
  { id: "q1", delay: 0,    action: "inspectGarment", label: "Scan garment #1 → PASS" },
  { id: "q2", delay: 5000, action: "inspectGarment", label: "Scan garment #2 → MISMATCH (wrong colour)" },
  { id: "q3", delay: 5000, action: "inspectGarment", label: "Scan garment #3 → REWORK (size L vs M)" },
  { id: "q4", delay: 5000, action: "inspectGarment", label: "Scan garment #4 → PASS" },
  { id: "q5", delay: 5000, action: "inspectGarment", label: "Scan garment #5 → MISMATCH (wrong style)" },
];

export const QUALITY_DEMO_SCRIPT_CALIBRATION: IDemoScriptStep[] = [
  { id: "c1", delay: 0,    action: "setCalibrationError", label: "Camera calibration lost" },
  { id: "c2", delay: 3000, action: "recalibrate",          label: "Recalibrating camera..." },
  { id: "c3", delay: 4000, action: "calibrationSuccess",   label: "Calibration restored — ratio 18.4 px/cm" },
  { id: "c4", delay: 2000, action: "inspectGarment",       label: "First scan after recalibration → PASS" },
];
