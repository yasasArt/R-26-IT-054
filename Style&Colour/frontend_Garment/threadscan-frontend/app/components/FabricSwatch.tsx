// Renders a detected color as a pinking-shear fabric snippet rather than a plain dot —
// ties the visual language back to the actual garment/textile domain.

const COLOR_MAP: Record<string, string> = {
  blue: "#3E6FD8",
  navy: "#1F3568",
  red: "#FF6B5E",
  black: "#22262A",
  white: "#EDEEEA",
  green: "#3FE0A1",
  olive: "#6B7A4F",
  amber: "#F5B24A",
  yellow: "#F0D264",
  orange: "#E8925A",
  grey: "#7C877F",
  gray: "#7C877F",
  beige: "#D8C9A8",
  brown: "#8A6142",
  purple: "#8A6BC9",
  pink: "#E893B0",
};

export function colorHex(name?: string) {
  if (!name) return "#8B9990";
  return COLOR_MAP[name.trim().toLowerCase()] ?? "#8B9990";
}

const PINKED_EDGE =
  "polygon(0% 12%, 8% 0%, 16% 12%, 24% 0%, 32% 12%, 40% 0%, 48% 12%, 56% 0%, 64% 12%, 72% 0%, 80% 12%, 88% 0%, 96% 12%, 100% 0%, 100% 100%, 0% 100%)";

export function FabricSwatch({ label, hex }: { label: string; hex: string }) {
  return (
    <div className="flex flex-col items-center gap-1.5">
      <div
        className="w-10 h-11 border border-white/15 shadow-[inset_0_0_6px_rgba(0,0,0,0.4)]"
        style={{ backgroundColor: hex, clipPath: PINKED_EDGE }}
      />
      <span className="font-mono text-[9px] uppercase tracking-wider text-textDim max-w-[56px] truncate text-center">
        {label}
      </span>
    </div>
  );
}
