# Required trained model files

This update already includes the verified Phase 8 classifier files:

- `best_model.pt` - the Phase 8 winning baseline `TemporalMobileNetV3Small` checkpoint
- `label_mapping.json` - maps index `0` to `IDLE_SETUP` and index `1` to `SEWING`

Before running live production inference, add the following project-specific file that was not present in the supplied archive:

- `best.pt` - your trained YOLO workstation detector

The production classifier intentionally does not receive `operation_type`. Collar, pocket, and sleeve are selected when a session is created and are used for cycle-time benchmarking, reporting, and UI status only.

Do not place the experimental operation-aware checkpoint in this folder under the name `best_model.pt`.
