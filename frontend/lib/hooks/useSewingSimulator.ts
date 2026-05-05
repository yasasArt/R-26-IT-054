// lib/hooks/useSewingSimulator.ts
"use client";
import { useEffect, useRef } from "react";
import { useSewingStore } from "@/store/sewingStore";
import { generateDetectionEvent, generateSeedDetections } from "@/lib/mock/sewing.mock";
import { randomBetween } from "@/lib/utils";
import { SIMULATION } from "@/lib/constants";

export type SimSpeed = keyof typeof SIMULATION.SPEEDS;

export function useSewingSimulator(speed: SimSpeed = "1x") {
  const intervalRef   = useRef<ReturnType<typeof setInterval> | null>(null);
  const timerRefs     = useRef<ReturnType<typeof setTimeout>[]>([]);
  const seeded        = useRef(false);

  function addTimer(t: ReturnType<typeof setTimeout>) {
    timerRefs.current.push(t);
  }

  function clearAll() {
    if (intervalRef.current) clearInterval(intervalRef.current);
    timerRefs.current.forEach(clearTimeout);
    timerRefs.current = [];
  }

  // Seed 20 past detections on first mount
  useEffect(() => {
    if (seeded.current) return;
    seeded.current = true;
    if (useSewingStore.getState().pieceCount > 0) return;

    const seeds = generateSeedDetections(20);
    seeds.forEach(({ id: _id, ...rest }) => {
      useSewingStore.getState().incrementPiece(rest);
    });
    useSewingStore.getState().setCameraStatus("live");
    useSewingStore.getState().setIoTStatus("connected");
    useSewingStore.getState().setOperatorStatus("active");
  }, []);

  // Main loop
  useEffect(() => {
    clearAll();
    if (speed === "manual") return;

    const ms = SIMULATION.SPEEDS[speed];

    intervalRef.current = setInterval(() => {
      const st = useSewingStore.getState();
      if (st.downtimeActive || st.reworkActive) return;

      const next      = st.pieceCount + 1;
      const cycleTime = randomBetween(33, 68);

      addTimer(setTimeout(() => useSewingStore.getState().setSignalA(true), 0));
      addTimer(setTimeout(() => useSewingStore.getState().setSignalB(true), 420));
      addTimer(setTimeout(() => {
        const { id: _id, ...rest } = generateDetectionEvent(next, { cycleTimeSeconds: cycleTime });
        useSewingStore.getState().incrementPiece(rest);
      }, 940));
      addTimer(setTimeout(() => {
        useSewingStore.getState().setSignalA(false);
        useSewingStore.getState().setSignalB(false);
      }, 2100));

      const rand = Math.random();
      if (rand < 0.05) {
        addTimer(setTimeout(() => {
          useSewingStore.getState().startRework();
          addTimer(setTimeout(() => useSewingStore.getState().endRework(), randomBetween(4000, 9000)));
        }, ms * 0.55));
      } else if (rand < 0.075) {
        addTimer(setTimeout(() => {
          useSewingStore.getState().startDowntime();
          addTimer(setTimeout(() => useSewingStore.getState().endDowntime(), randomBetween(7000, 16000)));
        }, ms * 0.65));
      }
    }, ms);

    return clearAll;
  }, [speed]);

  function triggerPiece() {
    const st   = useSewingStore.getState();
    const next = st.pieceCount + 1;
    const { id: _id, ...rest } = generateDetectionEvent(next);

    useSewingStore.getState().setSignalA(true);
    addTimer(setTimeout(() => useSewingStore.getState().setSignalB(true), 420));
    addTimer(setTimeout(() => {
      useSewingStore.getState().incrementPiece({ ...rest, pieceNumber: next, timestamp: new Date() });
    }, 940));
    addTimer(setTimeout(() => {
      useSewingStore.getState().setSignalA(false);
      useSewingStore.getState().setSignalB(false);
    }, 2100));
  }

  return { triggerPiece };
}