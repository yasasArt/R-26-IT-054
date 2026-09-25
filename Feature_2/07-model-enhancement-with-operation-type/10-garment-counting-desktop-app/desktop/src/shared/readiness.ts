import type {
  ModelResourceAvailability,
  ReadinessComponent,
  SystemReadiness,
} from "./types";

export function createPhaseOneReadiness(
  resources: ModelResourceAvailability,
  checkedAt = new Date().toISOString(),
): SystemReadiness {
  const components: ReadinessComponent[] = [
    {
      id: "desktop",
      label: "Desktop runtime",
      description: "Electron main, preload, and React renderer",
      status: "ready",
      detail: "Secure desktop shell is active.",
    },
    {
      id: "backend",
      label: "Python backend",
      description: "FastAPI session and inference sidecar",
      status: "pending",
      detail: "Automatic backend startup is scheduled for Phase 2.",
      actionLabel: "Phase 2",
    },
    {
      id: "workstation_detector",
      label: "Workstation detector",
      description: "YOLOv8n · workstation · 640 × 640",
      status: resources.workstationCheckpointExists ? "attention" : "blocked",
      detail: resources.workstationCheckpointExists
        ? "Checkpoint present. Runtime loading and test inference are pending."
        : "The workstation checkpoint best.pt is missing.",
      actionLabel: resources.workstationCheckpointExists ? "Phase 3" : "Add model",
    },
    {
      id: "garment_classifier",
      label: "Garment classifier",
      description: "Temporal MobileNetV3 · 8 frames · 224 × 224",
      status: resources.classifierCheckpointExists ? "attention" : "blocked",
      detail: resources.classifierCheckpointExists
        ? "Checkpoint present. Runtime loading and test inference are pending."
        : "The garment checkpoint best_model.pt is missing.",
      actionLabel: resources.classifierCheckpointExists ? "Phase 3" : "Add model",
    },
    {
      id: "camera",
      label: "Sewing camera",
      description: "Camera permissions and live workstation view",
      status: "pending",
      detail: "Camera capture becomes available with the Python sidecar.",
      actionLabel: "Check camera",
    },
    {
      id: "iot_controller",
      label: "IoT controller",
      description: "ESP32-C3 · BLE · rework / downtime",
      status: "pending",
      detail: "Connect the physical ESP32-C3 controller after the local service starts.",
      actionLabel: "Connect controller",
    },
  ];

  const readyCount = components.filter((component) => component.status === "ready").length;

  return {
    checkedAt,
    components,
    productionReady: components.every((component) => component.status === "ready"),
    completionPercent: Math.round((readyCount / components.length) * 100),
  };
}
