// components/layout/DashboardShell.tsx
"use client";
import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { useWorkstationStore } from "@/store/workstationStore";
import { Sidebar } from "./Sidebar";
import { TopBar } from "./TopBar";
import { DemoPanelDrawer } from "./DemoPanelDrawer";

interface DashboardShellProps {
  children: React.ReactNode;
}

export function DashboardShell({ children }: DashboardShellProps) {
  const { isConfigured } = useWorkstationStore();
  const router = useRouter();

  const [mounted, setMounted]         = useState(() => typeof window !== "undefined");
  const [demoPanelOpen, setDemoPanel] = useState(false);

  // Route guard — wait until mounted so Zustand has hydrated
  useEffect(() => {
    if (mounted && !isConfigured) {
      router.replace("/setup");
    }
  }, [mounted, isConfigured, router]);

  // Ctrl + Shift + D → demo panel
  useEffect(() => {
    const handler = (e: KeyboardEvent) => {
      if (e.ctrlKey && e.shiftKey && e.key === "D") {
        e.preventDefault();
        setDemoPanel((p) => !p);
      }
    };
    window.addEventListener("keydown", handler);
    return () => window.removeEventListener("keydown", handler);
  }, []);

  // Spinner while hydrating
  if (!mounted) {
    return (
      <div className="min-h-screen bg-bg flex items-center justify-center">
        <div className="flex flex-col items-center gap-3">
          <div className="w-6 h-6 border-2 border-accent/30 border-t-accent rounded-full animate-spin" />
          <span className="text-[10px] font-mono text-text-muted uppercase tracking-widest">
            Loading
          </span>
        </div>
      </div>
    );
  }

  // Blank while route guard redirect fires
  if (!isConfigured) return null;

  return (
    <div className="flex h-screen overflow-hidden bg-bg">
      <Sidebar />

      <div className="flex-1 flex flex-col min-w-0 overflow-hidden">
        <TopBar />
        <main className="flex-1 overflow-y-auto overflow-x-hidden p-6">
          {children}
        </main>
      </div>

      <DemoPanelDrawer
        isOpen={demoPanelOpen}
        onClose={() => setDemoPanel(false)}
      />
    </div>
  );
}