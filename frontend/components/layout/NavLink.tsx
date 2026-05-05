// components/layout/NavLink.tsx
"use client";
import Link from "next/link";
import { usePathname } from "next/navigation";
import type { LucideIcon } from "lucide-react";
import { cn } from "@/lib/utils";

interface NavLinkProps {
  href: string;
  label: string;
  icon: LucideIcon;
}

export function NavLink({ href, label, icon: Icon }: NavLinkProps) {
  const pathname = usePathname();
  const isActive =
    href.includes("dashboard")
      ? pathname.startsWith("/dashboard")
      : pathname === href || pathname.startsWith(href + "/");

  return (
    <Link
      href={href}
      className={cn(
        "relative flex items-center gap-3 px-3 py-2.5 rounded-lg font-display text-[13px] transition-colors duration-150",
        isActive
          ? "bg-accent/10 text-accent"
          : "text-text-muted hover:text-text-primary hover:bg-white/4"
      )}
    >
      {isActive && (
        <span
          className="absolute left-0 top-2 bottom-2 rounded-r-full"
          style={{ width: 3, background: "#3B82F6" }}
        />
      )}
      <Icon size={15} className="shrink-0" />
      <span className="flex-1">{label}</span>
    </Link>
  );
}