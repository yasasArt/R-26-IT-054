from __future__ import annotations

import importlib.util
import sys
from pathlib import Path
from unittest.mock import patch


def test_frozen_sidecar_entrypoint_applies_multiprocessing_support_before_startup() -> None:
    entrypoint = Path(__file__).resolve().parents[1] / "packaging" / "sidecar_entry.py"
    specification = importlib.util.spec_from_file_location("garment_release_entry", entrypoint)
    assert specification is not None
    assert specification.loader is not None
    module = importlib.util.module_from_spec(specification)
    sys.modules[specification.name] = module
    specification.loader.exec_module(module)

    with patch("multiprocessing.freeze_support") as freeze_support, patch("app.main.run") as run:
        module.main()

    freeze_support.assert_called_once_with()
    run.assert_called_once_with()
