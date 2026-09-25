# -*- mode: python ; coding: utf-8 -*-
"""Build the offline production Python service as a platform-native directory."""

import os
from pathlib import Path

from PyInstaller.utils.hooks import collect_all, collect_submodules

backend_directory = Path(os.environ.get("GARMENT_COUNTER_BACKEND_ROOT", os.getcwd())).resolve()
packaging_directory = backend_directory / "packaging"

datas = []
binaries = []
hiddenimports = collect_submodules("app")

for package in (
    "fastapi",
    "starlette",
    "pydantic",
    "uvicorn",
    "openpyxl",
    "numpy",
    "cv2",
    "torch",
    "torchvision",
    "ultralytics",
):
    package_datas, package_binaries, package_imports = collect_all(package)
    datas.extend(package_datas)
    binaries.extend(package_binaries)
    hiddenimports.extend(package_imports)

hiddenimports.extend((
    "uvicorn.logging",
    "uvicorn.loops.auto",
    "uvicorn.protocols.http.auto",
    "uvicorn.protocols.websockets.auto",
    "uvicorn.lifespan.on",
    "sqlite3",
))

analysis = Analysis(
    [str(packaging_directory / "sidecar_entry.py")],
    pathex=[str(backend_directory)],
    binaries=binaries,
    datas=datas,
    hiddenimports=sorted(set(hiddenimports)),
    hookspath=[str(packaging_directory / "hooks")],
    hooksconfig={},
    runtime_hooks=[str(packaging_directory / "runtime_hook.py")],
    excludes=["pytest", "IPython", "tensorboard", "matplotlib.tests", "scipy.tests"],
    noarchive=False,
)

python_archive = PYZ(analysis.pure)

executable = EXE(
    python_archive,
    analysis.scripts,
    [],
    exclude_binaries=True,
    name="garment-counter-sidecar",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    console=True,
    disable_windowed_traceback=False,
)

COLLECT(
    executable,
    analysis.binaries,
    analysis.datas,
    strip=False,
    upx=False,
    name="garment-counter-sidecar",
)
