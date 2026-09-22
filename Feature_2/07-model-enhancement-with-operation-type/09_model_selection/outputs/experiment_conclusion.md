# Operation-Type Model Enhancement Experiment

## Final decision

The original TemporalMobileNetV3Small model remains the selected
deployment model.

## Test dataset

- Test clips: 1001
- Test videos: 9
- Operations: COLLAR, POCKET, SLEEVE

## Overall comparison

| Metric | Baseline | Operation-aware |
|---|---:|---:|
| Accuracy | 98.10% | 97.80% |
| Macro-F1 | 0.9776 | 0.9742 |
| Test loss | 0.0810 | Available in Phase 7 |
| Errors | 19 | 22 |

## Paired prediction comparison

- Both models correct: 977
- Baseline only correct: 5
- Operation-aware only correct: 2
- Both models wrong: 17
- Exact McNemar p-value: 0.453125

## Interpretation

Adding operation_type as a one-hot model input did not improve overall
state classification. It slightly improved sleeve performance, but
reduced collar and pocket performance. The overall difference was not
statistically significant at the 0.05 level.

The experiment does not support replacing the existing classifier.

Operation type will still be retained as session-level contextual
information for estimated cycle time, live status colours, reporting,
and performance analysis.

## Deployment choice

- Selected architecture: TemporalMobileNetV3Small
- Model input: video frames only
- State output: IDLE_SETUP or SEWING
- Session operation input: COLLAR, POCKET, or SLEEVE
- Estimated cycle time: entered during session creation
- Blue status: actual cycle time is less than or equal to estimated time
- Red status: actual cycle time is greater than estimated time
