// components/layout/NavLink.tsx
"use client";
import Link from "next/link";
import { usePathname } from "next/navigation";
import { cn } from "@/lib/utils";
import type { LucideIcon } from "lucide-react";

interface NavLinkProps {
  href: string;
  label: string;
  icon: LucideIcon;
  badge?: string;
  disabled?: boolean;
}

export function NavLink({ href, label, icon: Icon, badge, disabled }: NavLinkProps) {
  const pathname = usePathname();
  const isActive =
    pathname === href ||
    (href !== "/" && pathname.startsWith(href + "/")) ||
    (href.includes("/dashboard") && pathname.startsWith("/dashboard") && href.includes(pathname.split("/")[2]));

  if (disabled) {
    return (
      <span className="flex items-center gap-3 px-3 py-2.5 rounded-badge text-sm font-display text-dim cursor-not-allowed opacity-50">
        <Icon size={15} className="shrink-0" />
        <span className="flex-1">{label}</span>
      </span>
    );
  }

  return (
    <Link
      href={href}
      className={cn(
        "flex items-center gap-3 px-3 py-2.5 rounded-badge text-sm font-display",
        "transition-all duration-150 group relative",
        isActive
          ? "bg-accent/10 text-accent border border-accent/20"
          : "text-text-muted hover:text-text-primary hover:bg-card border border-transparent"
      )}
    >
      {isActive && (
        <span className="absolute left-0 top-1/2 -translate-y-1/2 w-0.5 h-5 bg-accent rounded-r-full" />
      )}
      <Icon
        size={15}
        className={cn(
          "shrink-0 transition-colors",
          isActive
            ? "text-accent"
            : "text-text-muted group-hover:text-text-primary"
        )}
      />
      <span className="flex-1">{label}</span>
      {badge && (
        <span className="text-[9px] font-mono bg-accent/15 text-accent border border-accent/20 rounded px-1.5 py-0.5">
          {badge}
        </span>
      )}
    </Link>
  );
}