# Trained Model Resources

- `best_model.pt`: `TemporalMobileNetV3Small`, two labels (`IDLE_SETUP`,
  `SEWING`), eight frames, 224 × 224 input, exact `576 → 1024 → 2` classifier
  head, `Hardswish` activation, and strict checkpoint loading.
- `best.pt`: YOLOv8n workstation detector, one label (`workstation`),
  640 × 640 input.
- `data.yaml`: workstation detector dataset/class configuration.
- `label_mapping.json`: production classifier label/index mapping.

These checkpoints are application resources and must never be written into the
per-user database directory. Phase 3 loads, warms, and runs both actual supplied
checkpoints; missing or incompatible resources block AI readiness.
