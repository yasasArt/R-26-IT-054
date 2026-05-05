// components/layout/DashboardShell.tsx
"use client";
import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { useWorkstationStore } from "@/store/workstationStore";
import { Sidebar } from "./Sidebar";
import { TopBar } from "./TopBar";

export function DashboardShell({ children }: { children: React.ReactNode }) {
  const { isConfigured } = useWorkstationStore();
  const router = useRouter();
  const [mounted, setMounted] = useState(false);

  useEffect(() => {
    const timeout = window.setTimeout(() => {
      setMounted(true);
    }, 0);

    return () => {
      window.clearTimeout(timeout);
    };
  }, []);

  useEffect(() => {
    if (mounted && !isConfigured) router.replace("/setup");
  }, [mounted, isConfigured, router]);

  if (!mounted) {
    return (
      <div
        className="min-h-screen flex items-center justify-center"
        style={{ background: "#0B1017" }}
      >
        <div className="flex flex-col items-center gap-3">
          <div
            className="animate-spin rounded-full"
            style={{
              width: 24, height: 24,
              border: "2px solid #243044",
              borderTopColor: "#3B82F6",
            }}
          />
          <span className="font-mono text-text-muted" style={{ fontSize: 10, letterSpacing: "0.14em" }}>
            LOADING
          </span>
        </div>
      </div>
    );
  }

  if (!isConfigured) return null;

  return (
    <div
      className="flex overflow-hidden"
      style={{ height: "100vh", background: "#0B1017" }}
    >
      <Sidebar />
      <div className="flex flex-col flex-1 min-w-0 overflow-hidden">
        <TopBar />
        <main
          className="flex-1 overflow-y-auto overflow-x-hidden"
          style={{ padding: "20px 24px 32px" }}
        >
          {children}
        </main>
      </div>
    </div>
  );
}