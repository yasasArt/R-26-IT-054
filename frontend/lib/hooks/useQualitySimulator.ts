// lib/hooks/useQualitySimulator.ts
"use client";
import { useEffect, useRef } from "react";
import { useQualityStore } from "@/store/qualityStore";
import { generateGarmentAnalysis, resetGarmentIndex } from "@/lib/mock/quality.mock";
import { SIMULATION } from "@/lib/constants";

export type SimSpeed = keyof typeof SIMULATION.SPEEDS;

export function useQualitySimulator(speed: SimSpeed = "1x") {
  const intervalRef = useRef<ReturnType<typeof setInterval> | null>(null);
  const timerRefs   = useRef<ReturnType<typeof setTimeout>[]>([]);
  const seeded      = useRef(false);

  function addTimer(t: ReturnType<typeof setTimeout>) {
    timerRefs.current.push(t);
  }

  function clearAll() {
    if (intervalRef.current) clearInterval(intervalRef.current);
    timerRefs.current.forEach(clearTimeout);
    timerRefs.current = [];
  }

  // ── Seed 8 past inspections on first mount ───────────────────
  useEffect(() => {
    if (seeded.current) return;
    seeded.current = true;
    if (useQualityStore.getState().inspectionLog.length > 0) return;

    resetGarmentIndex();
    for (let i = 0; i < 8; i++) {
      useQualityStore.getState().recordInspection(generateGarmentAnalysis());
    }
    useQualityStore.getState().setCameraStatus("live");
    useQualityStore.getState().setCalibration({
      status:          "calibrated",
      lastCalibratedAt: new Date(),
    });
  }, []);

  // ── Main simulation loop ─────────────────────────────────────
  useEffect(() => {
    clearAll();
    if (speed === "manual") return;

    const ms = SIMULATION.SPEEDS[speed];

    intervalRef.current = setInterval(() => {
      const analysis = generateGarmentAnalysis();

      // Start scanning
      useQualityStore.getState().setIsAnalysing(true);
      useQualityStore.getState().setCurrentGarment(analysis);

      // Record result after scan animation (40% of interval, max 2s)
      const scanDuration = Math.min(ms * 0.4, 2000);
      addTimer(setTimeout(() => {
        useQualityStore.getState().recordInspection(analysis);
      }, scanDuration));
    }, ms);

    return clearAll;
  }, [speed]);

  function triggerInspection() {
    const analysis = generateGarmentAnalysis();
    useQualityStore.getState().setIsAnalysing(true);
    useQualityStore.getState().setCurrentGarment(analysis);
    addTimer(setTimeout(() => {
      useQualityStore.getState().recordInspection(analysis);
    }, 1800));
  }

  return { triggerInspection };
}