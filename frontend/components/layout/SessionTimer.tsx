// components/layout/SessionTimer.tsx
"use client";
import { useState, useEffect } from "react";
import { cn } from "@/lib/utils";

function formatElapsed(seconds: number): string {
  const h = Math.floor(seconds / 3600);
  const m = Math.floor((seconds % 3600) / 60);
  const s = seconds % 60;
  const pad = (n: number) => String(n).padStart(2, "0");
  if (h > 0) return `${h}:${pad(m)}:${pad(s)}`;
  return `${pad(m)}:${pad(s)}`;
}

interface SessionTimerProps {
  startTime: Date | null;
  showLabel?: boolean;
  className?: string;
}

export function SessionTimer({
  startTime,
  showLabel = true,
  className,
}: SessionTimerProps) {
  const [elapsed, setElapsed] = useState(0);

  useEffect(() => {
    if (!startTime) return;

    const start = new Date(startTime).getTime();
    const tick = () => {
      setElapsed(Math.floor((Date.now() - start) / 1000));
    };

    tick();
    const id = setInterval(tick, 1000);
    return () => clearInterval(id);
  }, [startTime]);

  if (!startTime) return null;

  return (
    <span className={cn("inline-flex items-center gap-1.5", className)}>
      {showLabel && (
        <span className="text-[10px] font-mono text-text-muted uppercase tracking-widest">
          Session
        </span>
      )}
      <span className="text-sm font-mono text-text-primary tabular-nums">
        {formatElapsed(elapsed)}
      </span>
    </span>
  );
}