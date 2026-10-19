import type { IconName } from "@garment-counter/components/Icon";

export type WorkstationId = "sewing" | "rework" | "style-colour" | "size";

export type WorkstationAvailability = "available" | "integration-ready";

export interface WorkstationModule {
  id: WorkstationId;
  area: string;
  name: string;
  summary: string;
  icon: IconName;
  accent: "green" | "indigo" | "violet" | "blue";
  availability: WorkstationAvailability;
  features: readonly string[];
  componentCount: number;
  frontendEntry: string;
  backendDirectory: string;
  modelDirectory: string;
}

export const WORKSTATION_MODULES: readonly WorkstationModule[] = [
  // Display order on the landing page and workstation selector:
  // 01 Production Monitoring, 02 Rework Counter, 03 Style & Colour, 04 Size Detection.
  {
    id: "sewing",
    area: "SEWING AREA",
    name: "Production Monitoring",
    summary: "Count completed garment pieces and measure sewing-cycle performance in real time.",
    icon: "activity",
    accent: "indigo",
    availability: "available",
    features: ["Garment-piece counting", "Cycle-time analysis", "Operator IoT events"],
    componentCount: 1,
    frontendEntry: "frontend/garment-counter-frontend/SewingWorkspace.tsx",
    backendDirectory: "backend/garment-counter-backend/",
    modelDirectory: "models/garment-counter/",
  },
  {
    id: "rework",
    area: "QUALITY CHECKING",
    name: "Rework Counter",
    summary: "Count accepted and rework garments in real time at the quality-checking workstation.",
    icon: "shield",
    accent: "green",
    availability: "available",
    features: ["Good-piece counting", "Rework-piece counting"],
    componentCount: 1,
    frontendEntry: "frontend/garment-rework-frontend/ReworkWorkspace.tsx",
    backendDirectory: "backend/garment-rework-backend/",
    modelDirectory: "models/garment-rework/",
  },
  {
    id: "style-colour",
    area: "PACKING AREA",
    name: "Garment Style and Colour Detection",
    summary: "Recognise garment style and extract its dominant colours before packing.",
    icon: "layers",
    accent: "violet",
    availability: "available",
    features: ["Style detection", "Colour extraction", "Production analytics"],
    componentCount: 1,
    frontendEntry: "frontend/garment-style-colour-frontend/StyleColourWorkspace.tsx",
    backendDirectory: "backend/garment-style-colour-backend/",
    modelDirectory: "models/garment-style-colour/",
  },
  {
    id: "size",
    area: "PACKING AREA",
    name: "Garment Size Detection",
    summary: "Measure garments and classify their production size using marker-free vision.",
    icon: "scan",
    accent: "blue",
    availability: "available",
    features: ["Garment measurement", "Size classification", "Packing counts"],
    componentCount: 1,
    frontendEntry: "frontend/garment-size-frontend/SizeWorkspace.tsx",
    backendDirectory: "backend/garment-size-backend/",
    modelDirectory: "models/garment-size/",
  },
] as const;

export function getWorkstation(id: WorkstationId): WorkstationModule {
  const workstation = WORKSTATION_MODULES.find((candidate) => candidate.id === id);

  if (!workstation) {
    throw new Error(`Unknown workstation: ${id}`);
  }

  return workstation;
}

export function getResearchComponentCount(): number {
  return WORKSTATION_MODULES.reduce((total, workstation) => total + workstation.componentCount, 0);
}
