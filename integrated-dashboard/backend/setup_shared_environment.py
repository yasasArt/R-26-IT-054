"""Create and verify the single Python 3.12 environment shared by every feature."""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import subprocess
import sys
import venv


BACKEND_ROOT = Path(__file__).resolve().parent
ENVIRONMENT = BACKEND_ROOT / ".venv"
REQUIRED_MODULES = (
    "fastapi",
    "uvicorn",
    "pydantic",
    "openpyxl",
    "numpy",
    "cv2",
    "torch",
    "torchvision",
    "ultralytics",
    "flask",
    "flask_cors",
    "requests",
    "supervision",
    "multipart",
)


def environment_python() -> Path:
    if os.name == "nt":
        return ENVIRONMENT / "Scripts" / "python.exe"
    return ENVIRONMENT / "bin" / "python"


def run(command: list[str]) -> None:
    subprocess.run(command, cwd=BACKEND_ROOT, check=True)


def verify_environment(python: Path) -> bool:
    if not python.exists():
        print(f"Shared Python environment does not exist: {python}", file=sys.stderr)
        return False

    probe = subprocess.run(
        [
            str(python),
            "-c",
            (
                "import importlib.util,json,platform;"
                f"modules={REQUIRED_MODULES!r};"
                "print(json.dumps({'python':platform.python_version(),"
                "'missing':[name for name in modules "
                "if importlib.util.find_spec(name) is None]}))"
            ),
        ],
        cwd=BACKEND_ROOT,
        check=False,
        capture_output=True,
        text=True,
    )
    if probe.returncode != 0:
        print(probe.stderr.strip() or "The shared environment could not be checked.", file=sys.stderr)
        return False

    report = json.loads(probe.stdout)
    if report["missing"]:
        print("Missing shared Python packages: " + ", ".join(report["missing"]), file=sys.stderr)
        return False

    print(f"Shared Python {report['python']} environment is ready: {python}")
    print("All four feature backends can use the same installed dependencies.")
    return True


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true", help="Only verify the existing shared environment.")
    arguments = parser.parse_args()

    if sys.version_info[:2] != (3, 12):
        print(
            f"Python 3.12 is required; this interpreter is {sys.version.split()[0]}. "
            "Run python3.12 backend/setup_shared_environment.py.",
            file=sys.stderr,
        )
        return 1

    python = environment_python()
    if arguments.check:
        return 0 if verify_environment(python) else 1

    if not python.exists():
        print(f"Creating the shared Python environment at {ENVIRONMENT}")
        venv.create(ENVIRONMENT, with_pip=True)

    run([str(python), "-m", "pip", "install", "--upgrade", "pip", "setuptools", "wheel"])
    run([str(python), "-m", "pip", "install", "-r", str(BACKEND_ROOT / "requirements.txt")])
    return 0 if verify_environment(python) else 1


if __name__ == "__main__":
    raise SystemExit(main())
