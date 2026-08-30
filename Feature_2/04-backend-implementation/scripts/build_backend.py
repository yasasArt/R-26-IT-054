from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
REQUIRED_MODEL_FILES = (
    PROJECT_ROOT / "models" / "final_idle_cycle" / "best_model.pt",
    PROJECT_ROOT / "models" / "final_idle_cycle" / "label_mapping.json",
    PROJECT_ROOT / "models" / "workstation_detector" / "best.pt",
)


def main() -> None:
    parser = argparse.ArgumentParser(description="Build the packaged backend")
    parser.add_argument(
        "--allow-missing-models",
        action="store_true",
        help="Build a diagnostic package without real .pt checkpoints",
    )
    arguments = parser.parse_args()
    missing = [path for path in REQUIRED_MODEL_FILES if not path.is_file()]
    if missing and not arguments.allow_missing_models:
        names = "\n".join(f"- {path.relative_to(PROJECT_ROOT)}" for path in missing)
        raise SystemExit(f"Required model assets are missing:\n{names}")

    command = [
        sys.executable,
        "-m",
        "PyInstaller",
        "--clean",
        "--noconfirm",
        "backend.spec",
    ]
    subprocess.run(command, cwd=PROJECT_ROOT, check=True)
    executable = PROJECT_ROOT / "dist" / "garment-counter-backend"
    if sys.platform == "win32":
        executable = executable.with_suffix(".exe")
    if not executable.is_file():
        raise SystemExit(f"Build completed but executable was not found: {executable}")
    print(f"Packaged backend: {executable}")


if __name__ == "__main__":
    main()

