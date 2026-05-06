"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { useWorkstationStore } from "@/store/workstationStore";
import { ROUTES } from "@/lib/constants";
import { Sidebar } from "./Sidebar";
import { TopBar } from "./TopBar";

export function DashboardShell({ children }: { children: React.ReactNode }) {
  const router = useRouter();
  const { isConfigured } = useWorkstationStore();
  const [mounted, setMounted] = useState(false);

  useEffect(() => {
    const id = window.setTimeout(() => setMounted(true), 0);
    return () => window.clearTimeout(id);
  }, []);

  useEffect(() => {
    if (mounted && !isConfigured) router.replace(ROUTES.SETUP);
  }, [isConfigured, mounted, router]);

  if (!mounted) {
    return (
      <main className="auth-page" style={{ alignItems: "center", justifyContent: "center" }}>
        <div className="status-pill info"><span className="dot" /> Starting local workstation</div>
      </main>
    );
  }

  if (!isConfigured) return null;

  return (
    <div className="workstation-shell">
      <Sidebar />
      <div className="shell-main">
        <TopBar />
        <main className="page">{children}</main>
      </div>
    </div>
  );
}
