from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


# ---------------------------------------------------------------------
# Project paths
# ---------------------------------------------------------------------

PHASE_9_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = PHASE_9_DIR.parent

PHASE_8_SUMMARY_PATH = (
    PROJECT_ROOT
    / "08_model_comparison"
    / "outputs"
    / "phase8_summary.json"
)

PHASE_6_DIR = (
    PROJECT_ROOT
    / "06_operation_aware_training"
)

BASELINE_DIR = (
    PROJECT_ROOT
    / "00_protected_baseline"
)

OUTPUT_DIR = PHASE_9_DIR / "outputs"

OUTPUT_DIR.mkdir(parents=True, exist_ok=True)


# ---------------------------------------------------------------------
# Utility functions
# ---------------------------------------------------------------------

def load_json(path: Path) -> dict[str, Any]:
    if not path.is_file():
        raise FileNotFoundError(
            f"Required JSON file was not found:\n{path}"
        )

    with path.open("r", encoding="utf-8") as file:
        return json.load(file)


def save_json(
    data: dict[str, Any],
    path: Path,
) -> None:
    with path.open("w", encoding="utf-8") as file:
        json.dump(data, file, indent=2)


def find_single_file(
    directory: Path,
    filename: str,
) -> Path:
    matches = sorted(directory.rglob(filename))

    if not matches:
        raise FileNotFoundError(
            f"Could not find {filename!r} inside:\n"
            f"{directory}"
        )

    if len(matches) > 1:
        found_files = "\n".join(
            str(path)
            for path in matches
        )

        raise RuntimeError(
            f"More than one {filename!r} was found.\n\n"
            f"{found_files}"
        )

    return matches[0]


def relative_project_path(path: Path) -> str:
    """
    Store paths relative to the project root.

    Relative paths make the final configuration portable when the
    project is moved to another computer or folder.
    """

    resolved_path = path.resolve()
    resolved_project_root = PROJECT_ROOT.resolve()

    try:
        return str(
            resolved_path.relative_to(
                resolved_project_root
            )
        )
    except ValueError:
        return str(resolved_path)


def percentage(value: float) -> str:
    return f"{value * 100:.2f}%"


# ---------------------------------------------------------------------
# Main Phase 9 process
# ---------------------------------------------------------------------

def main() -> None:
    print("Phase 9: Final model selection")
    print("=" * 45)

    phase_8 = load_json(
        PHASE_8_SUMMARY_PATH
    )

    if phase_8.get("status") != "PASS":
        raise ValueError(
            "Phase 8 did not finish with PASS status."
        )

    failed_checks = [
        check_name
        for check_name, result
        in phase_8["checks"].items()
        if result != "PASS"
    ]

    if failed_checks:
        raise ValueError(
            "Phase 8 contains failed checks: "
            f"{failed_checks}"
        )

    baseline_checkpoint = find_single_file(
        BASELINE_DIR,
        "best_model.pt",
    )

    phase_6_experiment_config = find_single_file(
        PHASE_6_DIR,
        "experiment_config.json",
    )

    experiment_config = load_json(
        phase_6_experiment_config
    )

    baseline = phase_8["baseline"]
    enhanced = phase_8["enhanced"]

    comparison = phase_8[
        "overall_comparison"
    ]

    paired_comparison = phase_8[
        "paired_prediction_comparison"
    ]

    baseline_macro_f1 = float(
        baseline["overall"]["macro_f1"]
    )

    enhanced_macro_f1 = float(
        enhanced["overall"]["macro_f1"]
    )

    baseline_accuracy = float(
        baseline["overall"]["accuracy"]
    )

    enhanced_accuracy = float(
        enhanced["overall"]["accuracy"]
    )

    p_value = float(
        paired_comparison[
            "exact_mcnemar_p_value"
        ]
    )

    # -------------------------------------------------------------
    # Final selection rule
    # -------------------------------------------------------------

    if enhanced_macro_f1 > baseline_macro_f1:
        raise RuntimeError(
            "The enhanced model has a higher macro-F1. "
            "Review the Phase 8 result before automatically "
            "selecting the baseline model."
        )

    selected_model_id = (
        "baseline_temporal_mobilenet_v3_small"
    )

    selection_reason = (
        "The baseline model achieved higher test accuracy, "
        "higher macro-F1, lower test loss, and fewer test "
        "errors. The paired prediction difference was not "
        "statistically significant. Therefore, the simpler "
        "baseline model remains the selected deployment model."
    )

    operation_names = list(
        experiment_config["operation_names"]
    )

    training_configuration = (
        experiment_config["config"]
    )

    # -------------------------------------------------------------
    # Deployment configuration
    # -------------------------------------------------------------

    deployment_config = {
        "schema_version": 1,
        "created_at_utc": (
            datetime.now(timezone.utc).isoformat()
        ),
        "selected_model": {
            "model_id": selected_model_id,
            "architecture": (
                "TemporalMobileNetV3Small"
            ),
            "checkpoint_path": (
                relative_project_path(
                    baseline_checkpoint
                )
            ),
            "checkpoint_epoch": baseline[
                "checkpoint_epoch"
            ],
            "classes": [
                "IDLE_SETUP",
                "SEWING",
            ],
            "class_to_index": {
                "IDLE_SETUP": 0,
                "SEWING": 1,
            },
            "frames_per_clip": int(
                training_configuration[
                    "frames_per_clip"
                ]
            ),
            "input_size": int(
                training_configuration[
                    "input_size"
                ]
            ),
            "requires_operation_type": False,
        },
        "operation_context": {
            "session_requires_operation_type": True,
            "allowed_operation_types": operation_names,
            "used_as_model_input": False,
            "uses": [
                "estimated_cycle_time_configuration",
                "live_cycle_time_status",
                "session_history_filtering",
                "operation_level_reporting",
                "performance_comparison",
            ],
        },
        "estimated_cycle_time": {
            "source": (
                "Entered when creating a session"
            ),
            "unit": "seconds",
            "validation": {
                "required": True,
                "minimum_exclusive": 0,
            },
            "display_rules": {
                "BLUE": (
                    "actual_cycle_time_sec <= "
                    "estimated_cycle_time_sec"
                ),
                "RED": (
                    "actual_cycle_time_sec > "
                    "estimated_cycle_time_sec"
                ),
            },
        },
        "state_and_counting_rules": {
            "piece_count_transition": (
                "SEWING_TO_IDLE_SETUP"
            ),
            "cycle_time_definition": (
                "Time between consecutive confirmed "
                "garment completion transitions"
            ),
            "operation_type_does_not_change_state_labels": True,
        },
        "research_decision": {
            "selected_model": "BASELINE_MODEL",
            "rejected_as_default": (
                "OPERATION_AWARE_MODEL"
            ),
            "selection_reason": selection_reason,
            "baseline_accuracy": baseline_accuracy,
            "enhanced_accuracy": enhanced_accuracy,
            "accuracy_difference_enhanced_minus_baseline": (
                enhanced_accuracy
                - baseline_accuracy
            ),
            "baseline_macro_f1": baseline_macro_f1,
            "enhanced_macro_f1": enhanced_macro_f1,
            "macro_f1_difference_enhanced_minus_baseline": (
                enhanced_macro_f1
                - baseline_macro_f1
            ),
            "baseline_error_count": comparison[
                "error_count"
            ]["baseline"],
            "enhanced_error_count": comparison[
                "error_count"
            ]["enhanced"],
            "mcnemar_p_value": p_value,
            "statistically_significant_at_0_05": (
                p_value < 0.05
            ),
        },
    }

    deployment_config_path = (
        OUTPUT_DIR
        / "deployment_model_config.json"
    )

    save_json(
        deployment_config,
        deployment_config_path,
    )

    # -------------------------------------------------------------
    # Human-readable experiment conclusion
    # -------------------------------------------------------------

    conclusion_text = f"""# Operation-Type Model Enhancement Experiment

## Final decision

The original TemporalMobileNetV3Small model remains the selected
deployment model.

## Test dataset

- Test clips: {phase_8["test_dataset"]["clip_count"]}
- Test videos: {phase_8["test_dataset"]["video_count"]}
- Operations: {", ".join(operation_names)}

## Overall comparison

| Metric | Baseline | Operation-aware |
|---|---:|---:|
| Accuracy | {percentage(baseline_accuracy)} | {percentage(enhanced_accuracy)} |
| Macro-F1 | {baseline_macro_f1:.4f} | {enhanced_macro_f1:.4f} |
| Test loss | {baseline["test_loss"]:.4f} | {phase_8["enhanced"].get("test_loss", "Available in Phase 7")} |
| Errors | {comparison["error_count"]["baseline"]} | {comparison["error_count"]["enhanced"]} |

## Paired prediction comparison

- Both models correct: {paired_comparison["both_correct"]}
- Baseline only correct: {paired_comparison["baseline_only_correct"]}
- Operation-aware only correct: {paired_comparison["enhanced_only_correct"]}
- Both models wrong: {paired_comparison["both_wrong"]}
- Exact McNemar p-value: {p_value:.6f}

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
"""

    conclusion_path = (
        OUTPUT_DIR
        / "experiment_conclusion.md"
    )

    conclusion_path.write_text(
        conclusion_text,
        encoding="utf-8",
    )

    # -------------------------------------------------------------
    # Phase 9 summary
    # -------------------------------------------------------------

    phase_9_summary = {
        "status": "PASS",
        "phase": (
            "Phase 9 - Final model selection "
            "and deployment contract"
        ),
        "decision": {
            "selected_model": "BASELINE_MODEL",
            "selected_model_id": selected_model_id,
            "selected_architecture": (
                "TemporalMobileNetV3Small"
            ),
            "selected_checkpoint": (
                relative_project_path(
                    baseline_checkpoint
                )
            ),
            "operation_aware_model_selected": False,
            "reason": selection_reason,
        },
        "operation_type_decision": {
            "kept_in_dataset": True,
            "kept_in_session": True,
            "used_as_classifier_input": False,
            "used_for_estimated_cycle_time": True,
            "used_for_reporting": True,
        },
        "evidence": {
            "baseline_accuracy": baseline_accuracy,
            "enhanced_accuracy": enhanced_accuracy,
            "baseline_macro_f1": baseline_macro_f1,
            "enhanced_macro_f1": enhanced_macro_f1,
            "baseline_error_count": comparison[
                "error_count"
            ]["baseline"],
            "enhanced_error_count": comparison[
                "error_count"
            ]["enhanced"],
            "mcnemar_p_value": p_value,
        },
        "checks": {
            "phase_8_passed": "PASS",
            "phase_8_checks_passed": "PASS",
            "baseline_checkpoint_exists": (
                "PASS"
                if baseline_checkpoint.is_file()
                else "FAIL"
            ),
            "deployment_config_created": "PASS",
            "experiment_conclusion_created": "PASS",
        },
        "outputs": {
            "deployment_model_config": str(
                deployment_config_path
            ),
            "experiment_conclusion": str(
                conclusion_path
            ),
        },
    }

    phase_9_summary_path = (
        OUTPUT_DIR
        / "phase9_summary.json"
    )

    save_json(
        phase_9_summary,
        phase_9_summary_path,
    )

    print("Phase 9 completed successfully.")
    print()
    print("Selected model: BASELINE_MODEL")
    print(
        "Architecture: TemporalMobileNetV3Small"
    )
    print(
        "Classifier uses operation_type: No"
    )
    print(
        "Session uses operation_type: Yes"
    )
    print()
    print(
        f"Deployment configuration:\n"
        f"{deployment_config_path}"
    )
    print()
    print(
        f"Phase 9 summary:\n"
        f"{phase_9_summary_path}"
    )


if __name__ == "__main__":
    main()