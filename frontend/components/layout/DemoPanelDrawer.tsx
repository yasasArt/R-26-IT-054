// components/layout/DemoPanelDrawer.tsx
"use client";
import { useEffect } from "react";
import { X, Zap, Keyboard } from "lucide-react";
import { cn } from "@/lib/utils";

interface DemoPanelDrawerProps {
  isOpen: boolean;
  onClose: () => void;
}

export function DemoPanelDrawer({ isOpen, onClose }: DemoPanelDrawerProps) {
  // Close on Escape
  useEffect(() => {
    const handler = (e: KeyboardEvent) => {
      if (e.key === "Escape" && isOpen) onClose();
    };
    window.addEventListener("keydown", handler);
    return () => window.removeEventListener("keydown", handler);
  }, [isOpen, onClose]);

  return (
    <>
      {/* Backdrop */}
      <div
        className={cn(
          "fixed inset-0 bg-black/50 z-40 transition-opacity duration-300",
          isOpen ? "opacity-100 pointer-events-auto" : "opacity-0 pointer-events-none"
        )}
        onClick={onClose}
      />

      {/* Drawer */}
      <div
        className={cn(
          "fixed top-0 right-0 h-full w-80 z-50",
          "bg-card border-l-2 border-orange",
          "transform transition-transform duration-300 ease-out",
          "flex flex-col",
          isOpen ? "translate-x-0" : "translate-x-full"
        )}
      >
        {/* Header */}
        <div className="h-14 border-b border-card-border px-4 flex items-center justify-between flex-shrink-0">
          <div className="flex items-center gap-2">
            <Zap size={14} className="text-orange" />
            <span className="text-[11px] font-mono font-bold text-orange uppercase tracking-[3px]">
              Demo Panel
            </span>
          </div>
          <button
            onClick={onClose}
            className="text-text-muted hover:text-text-primary transition-colors cursor-pointer p-1 rounded hover:bg-card-border"
          >
            <X size={15} />
          </button>
        </div>

        {/* Body — Phase 5 placeholder */}
        <div className="flex-1 flex flex-col items-center justify-center gap-4 p-6">
          <div className="w-14 h-14 rounded-2xl bg-orange/10 border border-orange/20 flex items-center justify-center">
            <Zap size={24} className="text-orange/60" />
          </div>
          <div className="text-center space-y-1">
            <div className="text-sm font-display font-semibold text-text-primary">
              Demo Control Panel
            </div>
            <div className="text-xs font-mono text-text-muted">
              Event injection & simulation
            </div>
            <div className="text-[10px] font-mono text-dim mt-2">
              Coming in Phase 5
            </div>
          </div>

          {/* Keyboard shortcut reminder */}
          <div className="mt-4 flex items-center gap-2 bg-surface border border-card-border rounded-badge px-3 py-2">
            <Keyboard size={11} className="text-text-muted" />
            <span className="text-[10px] font-mono text-text-muted">
              Toggle:{" "}
              <kbd className="text-text-primary bg-card-border rounded px-1 py-px">
                Ctrl
              </kbd>{" "}
              +{" "}
              <kbd className="text-text-primary bg-card-border rounded px-1 py-px">
                Shift
              </kbd>{" "}
              +{" "}
              <kbd className="text-text-primary bg-card-border rounded px-1 py-px">
                D
              </kbd>
            </span>
          </div>
        </div>
      </div>
    </>
  );
}