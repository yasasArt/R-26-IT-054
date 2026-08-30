const COLOR_MAP: Record<string, string> = {
  blue: "#3E6FD8",
  navy: "#1F3568",
  red: "#D6455A",
  black: "#22262A",
  white: "#F4F5F7",
  green: "#22A27E",
  olive: "#6B7A4F",
  amber: "#B97519",
  yellow: "#E8C24A",
  orange: "#DB7C3E",
  grey: "#8691A4",
  gray: "#8691A4",
  beige: "#D8C9A8",
  brown: "#8A6142",
  purple: "#765AC9",
  pink: "#D683A0",
  unknown: "#B3BFD1",
};

export function colorHex(name?: string) {
  if (!name) return "#B3BFD1";
  const cleanName = name.trim().replace(/[^a-zA-Z]/g, "").toLowerCase();
  return COLOR_MAP[cleanName] ?? "#B3BFD1";
}

interface FabricSwatchProps {
  label: string;
  hex: string;
}

export function FabricSwatch({ label, hex }: FabricSwatchProps) {
  const cleanLabel = label.replace(/[^a-zA-Z]/g, "");
  const isLight = ["white", "beige", "yellow"].includes(cleanLabel.toLowerCase());

  return (
    <div className="flex flex-col items-center gap-1.5">
      <div
        className="w-10 h-10 rounded-full shadow-sm"
        style={{
          backgroundColor: hex,
          border: isLight ? "1px solid var(--color-line)" : "1px solid rgba(0,0,0,0.06)",
        }}
      />
      <span className="font-mono text-[9px] uppercase tracking-wider text-ink-soft max-w-[56px] truncate text-center">
        {cleanLabel || "UNKNOWN"}
      </span>
    </div>
  );
}
