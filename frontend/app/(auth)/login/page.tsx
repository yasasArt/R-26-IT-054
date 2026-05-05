// app/(auth)/login/page.tsx
"use client";

import { useState, useRef, useEffect } from "react";
import { useRouter } from "next/navigation";
import {
  Eye, ChevronDown, AlertCircle, CheckCircle2, Wifi, Server,
} from "lucide-react";
import { useWorkstationStore } from "@/store/workstationStore";
import { cn } from "@/lib/utils";
import { AVAILABLE_STATIONS, DEMO_PIN, DEMO_SERVER_URL, ROUTES, APP_NAME } from "@/lib/constants";
import { format } from "date-fns";

// ── System status items shown in the top-bar ─────────────────────
const SYS_ITEMS = [
  { label: "YOLOv8",  ok: true  },
  { label: "Pose",    ok: true  },
  { label: "Camera",  ok: true  },
  { label: "IoT",     ok: false },
] as const;

export default function LoginPage() {
  const router = useRouter();
  const { setConfig } = useWorkstationStore();

  const [station, setStation] = useState(AVAILABLE_STATIONS[0]);
  const [dropOpen, setDropOpen] = useState(false);
  const [pin, setPin]           = useState(["", "", "", ""]);
  const [shaking, setShaking]   = useState(false);
  const [error, setError]       = useState<string | null>(null);
  const [success, setSuccess]   = useState(false);
  const [loading, setLoading]   = useState(false);
  const [clock, setClock]       = useState("");

  const r0 = useRef<HTMLInputElement>(null);
  const r1 = useRef<HTMLInputElement>(null);
  const r2 = useRef<HTMLInputElement>(null);
  const r3 = useRef<HTMLInputElement>(null);
  const refs = [r0, r1, r2, r3];

  useEffect(() => {
    const tick = () => setClock(format(new Date(), "HH:mm:ss"));
    tick();
    const id = setInterval(tick, 1000);
    return () => clearInterval(id);
  }, []);

  useEffect(() => { r0.current?.focus(); }, []);

  function doLogin(full: string) {
    if (full === DEMO_PIN) {
      setSuccess(true);
      setLoading(true);
      setConfig({ stationId: station.id, stationLabel: station.label });
      setTimeout(() => router.push(ROUTES.SETUP), 800);
    } else {
      setShaking(true);
      setError("Invalid PIN — use 1234 for demo");
      setPin(["", "", "", ""]);
      setTimeout(() => {
        setShaking(false);
        setError(null);
        r0.current?.focus();
      }, 500);
    }
  }

  function handleDigit(i: number, val: string) {
    if (!/^\d?$/.test(val)) return;
    setError(null);
    const next = [...pin];
    next[i] = val;
    setPin(next);
    if (val && i < 3) refs[i + 1].current?.focus();
    if (val && i === 3 && next.every(d => d !== "")) doLogin(next.join(""));
  }

  function handleKey(i: number, e: React.KeyboardEvent<HTMLInputElement>) {
    if (e.key === "Backspace" && !pin[i] && i > 0) {
      const next = [...pin];
      next[i - 1] = "";
      setPin(next);
      refs[i - 1].current?.focus();
    }
    if (e.key === "Enter" && pin.every(d => d !== "")) doLogin(pin.join(""));
  }

  const filled = pin.filter(Boolean).length;

  return (
    <main
      className="min-h-screen flex flex-col"
      style={{ background: "#0B1017" }}
    >
      {/* ── Background texture ─────────────────────────────── */}
      <div
        className="fixed inset-0 pointer-events-none"
        style={{
          backgroundImage:
            "radial-gradient(circle, rgba(59,130,246,0.09) 1px, transparent 1px)",
          backgroundSize: "44px 44px",
        }}
      />
      <div
        className="fixed inset-0 pointer-events-none"
        style={{
          background:
            "radial-gradient(ellipse 80% 60% at 50% 40%, rgba(59,130,246,0.05) 0%, transparent 70%)",
        }}
      />

      {/* ═══════════════════════════════════════════════════════
          TOP BAR
      ═══════════════════════════════════════════════════════ */}
      <header
        className="relative z-10 flex items-center justify-between flex-shrink-0"
        style={{
          height: 60,
          padding: "0 40px",
          background: "rgba(19,27,38,0.8)",
          borderBottom: "1px solid #243044",
          backdropFilter: "blur(12px)",
        }}
      >
        {/* Brand */}
        <div className="flex items-center gap-3">
          <div
            className="flex items-center justify-center flex-shrink-0"
            style={{
              width: 34, height: 34, borderRadius: 9,
              background: "rgba(59,130,246,0.12)",
              border: "1px solid rgba(59,130,246,0.3)",
            }}
          >
            <Eye size={16} className="text-accent" />
          </div>
          <div>
            <div
              className="font-display font-bold text-text-primary"
              style={{ fontSize: 14, lineHeight: 1.2 }}
            >
              {APP_NAME}
            </div>
            <div
              className="font-mono text-text-muted uppercase"
              style={{ fontSize: 8, letterSpacing: "0.14em", marginTop: 1 }}
            >
              Apparel Manufacturing Workstation
            </div>
          </div>
        </div>

        {/* Status indicators + clock */}
        <div className="flex items-center gap-6">
          {/* Per-module dots */}
          <div className="hidden md:flex items-center gap-4">
            {SYS_ITEMS.map(s => (
              <div key={s.label} className="flex items-center gap-1.5">
                <div
                  className={cn("rounded-full", s.ok && "animate-pulse-slow")}
                  style={{
                    width: 5, height: 5,
                    background: s.ok ? "#22C55E" : "#FACC15",
                    boxShadow: s.ok ? "0 0 5px #22C55E" : "0 0 5px #FACC15",
                  }}
                />
                <span className="font-mono text-text-muted" style={{ fontSize: 10 }}>
                  {s.label}
                </span>
              </div>
            ))}
          </div>

          {/* Divider */}
          <div style={{ width: 1, height: 18, background: "#243044" }} className="hidden md:block" />

          {/* Server */}
          <div className="hidden lg:flex items-center gap-1.5">
            <Server size={11} className="text-text-muted" />
            <span className="font-mono text-text-muted" style={{ fontSize: 10 }}>
              {DEMO_SERVER_URL}
            </span>
          </div>

          {/* Clock */}
          <div style={{ width: 1, height: 18, background: "#243044" }} className="hidden lg:block" />
          <span
            className="font-mono font-semibold text-text-primary tabular-nums"
            style={{ fontSize: 16, letterSpacing: "0.04em" }}
          >
            {clock || "──:──:──"}
          </span>
        </div>
      </header>

      {/* ═══════════════════════════════════════════════════════
          MAIN CONTENT — centered card
      ═══════════════════════════════════════════════════════ */}
      <div className="flex-1 flex items-center justify-center relative z-10 p-6">
        <div
          className="w-full animate-fade-in"
          style={{ maxWidth: 460 }}
        >
          {/* Page heading */}
          <div className="text-center mb-10">
            <h1
              className="font-display font-bold text-text-primary"
              style={{ fontSize: 30, marginBottom: 10 }}
            >
              Station Login
            </h1>
            <p
              className="font-display text-text-muted"
              style={{ fontSize: 14, lineHeight: 1.6, maxWidth: 360, margin: "0 auto" }}
            >
              Select your assigned workstation and enter your 4-digit PIN to begin the session.
            </p>
          </div>

          {/* ── Login card ── */}
          <div
            className={cn(shaking && "animate-shake")}
            style={{
              background: "#1A2536",
              border: `1px solid ${success ? "rgba(34,197,94,0.5)" : error ? "rgba(239,68,68,0.5)" : "#243044"}`,
              borderRadius: 18,
              padding: "36px 40px",
              boxShadow: success
                ? "0 24px 60px rgba(0,0,0,0.5), 0 0 44px rgba(34,197,94,0.1)"
                : "0 24px 60px rgba(0,0,0,0.5)",
              transition: "border-color 0.25s, box-shadow 0.35s",
            }}
          >
            {/* Workstation selector */}
            <div style={{ marginBottom: 28 }}>
              <label
                className="font-mono text-text-muted uppercase block"
                style={{ fontSize: 10, letterSpacing: "0.15em", marginBottom: 10 }}
              >
                Workstation
              </label>

              <div className="relative">
                <button
                  type="button"
                  onClick={() => setDropOpen(p => !p)}
                  className="w-full flex items-center justify-between font-display text-text-primary cursor-pointer transition-all duration-150"
                  style={{
                    height: 48,
                    padding: "0 16px",
                    background: "#0B1017",
                    border: `1px solid ${dropOpen ? "#3B82F6" : "#2A3A52"}`,
                    borderRadius: 10,
                    fontSize: 14,
                    boxShadow: dropOpen ? "0 0 0 3px rgba(59,130,246,0.12)" : "none",
                  }}
                >
                  <span>{station.label}</span>
                  <ChevronDown
                    size={14}
                    className={cn(
                      "text-text-muted transition-transform duration-200",
                      dropOpen && "rotate-180"
                    )}
                  />
                </button>

                {dropOpen && (
                  <div
                    className="absolute left-0 right-0 z-30 overflow-hidden animate-fade-in"
                    style={{
                      top: "calc(100% + 6px)",
                      background: "#131B26",
                      border: "1px solid #2A3A52",
                      borderRadius: 10,
                      boxShadow: "0 20px 48px rgba(0,0,0,0.65)",
                    }}
                  >
                    {AVAILABLE_STATIONS.map((s, i) => (
                      <button
                        key={s.id}
                        type="button"
                        onClick={() => { setStation(s); setDropOpen(false); }}
                        className="w-full text-left font-display cursor-pointer block transition-colors duration-100"
                        style={{
                          padding: "13px 16px",
                          fontSize: 14,
                          color: s.id === station.id ? "#3B82F6" : "#E8ECF1",
                          background: s.id === station.id ? "rgba(59,130,246,0.08)" : "transparent",
                          borderBottom:
                            i < AVAILABLE_STATIONS.length - 1 ? "1px solid #243044" : "none",
                        }}
                        onMouseEnter={e => {
                          if (s.id !== station.id)
                            (e.currentTarget as HTMLElement).style.background =
                              "rgba(255,255,255,0.03)";
                        }}
                        onMouseLeave={e => {
                          if (s.id !== station.id)
                            (e.currentTarget as HTMLElement).style.background = "transparent";
                        }}
                      >
                        {s.label}
                      </button>
                    ))}
                  </div>
                )}
              </div>
            </div>

            {/* PIN section */}
            <div style={{ marginBottom: 28 }}>
              <label
                className="font-mono text-text-muted uppercase block"
                style={{ fontSize: 10, letterSpacing: "0.15em", marginBottom: 14 }}
              >
                PIN Code
              </label>

              {/* PIN boxes */}
              <div className="flex gap-3 justify-center" style={{ marginBottom: 12 }}>
                {pin.map((d, i) => (
                  <input
                    key={i}
                    ref={refs[i]}
                    type="password"
                    inputMode="numeric"
                    maxLength={1}
                    value={d}
                    onChange={e => handleDigit(i, e.target.value)}
                    onKeyDown={e => handleKey(i, e)}
                    className="text-center font-mono font-bold caret-transparent focus:outline-none transition-all duration-150"
                    style={{
                      width: 76,
                      height: 80,
                      fontSize: 32,
                      background: "#0B1017",
                      borderRadius: 12,
                      border: `2px solid ${
                        success ? "#22C55E"
                        : error ? "#EF4444"
                        : d ? "#3B82F6"
                        : "#2A3A52"
                      }`,
                      color: success ? "#22C55E" : error ? "#EF4444" : "#E8ECF1",
                      transform: d ? "scale(1.04)" : "scale(1)",
                      boxShadow:
                        success ? "0 0 20px rgba(34,197,94,0.35)"
                        : error ? "0 0 16px rgba(239,68,68,0.25)"
                        : d ? "0 0 20px rgba(59,130,246,0.25)"
                        : "none",
                    }}
                  />
                ))}
              </div>

              {/* Fill indicators */}
              <div className="flex gap-3 justify-center">
                {pin.map((d, i) => (
                  <div
                    key={i}
                    style={{
                      width: 72,
                      height: 2,
                      borderRadius: 2,
                      background:
                        success ? "#22C55E"
                        : error ? "#EF4444"
                        : d ? "#3B82F6"
                        : "#243044",
                      boxShadow:
                        d && !error && !success ? "0 0 7px rgba(59,130,246,0.45)" : "none",
                      transition: "background 0.2s, box-shadow 0.2s",
                    }}
                  />
                ))}
              </div>
            </div>

            {/* Feedback */}
            <div
              className="flex items-center justify-center"
              style={{ height: 26, marginBottom: 20 }}
            >
              {success && (
                <div
                  className="flex items-center gap-2 text-success font-mono animate-fade-in"
                  style={{ fontSize: 12 }}
                >
                  <CheckCircle2 size={14} />
                  Access granted — loading session…
                </div>
              )}
              {error && !success && (
                <div
                  className="flex items-center gap-2 text-danger font-mono"
                  style={{ fontSize: 12 }}
                >
                  <AlertCircle size={14} />
                  {error}
                </div>
              )}
            </div>

            {/* Submit button */}
            <button
              type="button"
              disabled={filled < 4 || success || loading}
              onClick={() => filled === 4 && doLogin(pin.join(""))}
              className="w-full font-display font-semibold transition-all duration-200 disabled:cursor-not-allowed"
              style={{
                height: 52,
                borderRadius: 12,
                border: "none",
                fontSize: 15,
                cursor: filled === 4 && !success ? "pointer" : "not-allowed",
                background:
                  filled === 4 && !error ? "#3B82F6" : "rgba(59,130,246,0.15)",
                color: filled === 4 && !error ? "white" : "#4A5A6A",
                boxShadow:
                  filled === 4 && !error ? "0 0 32px rgba(59,130,246,0.4)" : "none",
              }}
            >
              {loading ? "Accessing Station…" : "Access Station"}
            </button>
          </div>

          {/* Demo hint */}
          <div
            className="mt-5 flex items-center justify-center gap-4 font-mono text-dim"
            style={{
              fontSize: 11,
              padding: "11px 20px",
              background: "rgba(19,27,38,0.7)",
              border: "1px solid #243044",
              borderRadius: 10,
            }}
          >
            <span>Demo mode</span>
            <span style={{ color: "#3A4A5C" }}>·</span>
            <span>Station <span className="text-text-muted">WS-01</span></span>
            <span style={{ color: "#3A4A5C" }}>·</span>
            <span>
              PIN{" "}
              <span className="text-text-muted" style={{ letterSpacing: "0.25em" }}>
                {DEMO_PIN}
              </span>
            </span>
          </div>
        </div>
      </div>

      {/* ── FOOTER ─────────────────────────────────────────── */}
      <footer
        className="relative z-10 flex items-center justify-between flex-shrink-0"
        style={{
          height: 48,
          padding: "0 40px",
          background: "rgba(19,27,38,0.6)",
          borderTop: "1px solid #243044",
        }}
      >
        <div className="flex items-center gap-2">
          <div
            className="rounded-full animate-pulse-slow"
            style={{
              width: 5, height: 5,
              background: "#22C55E",
              boxShadow: "0 0 5px #22C55E",
            }}
          />
          <span className="font-mono text-text-muted" style={{ fontSize: 10 }}>
            Local server connected · {DEMO_SERVER_URL}
          </span>
        </div>
        <span className="font-mono text-dim" style={{ fontSize: 10 }}>
          AI Vision System · v1.0.0-prototype · Research Build
        </span>
      </footer>
    </main>
  );
}