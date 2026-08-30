import json

from app.config import get_settings
from app.vision.model_registry import ModelRegistry


def main() -> int:
    settings = get_settings()
    registry = ModelRegistry(settings)
    status = registry.load_all()
    print(json.dumps(status.model_dump(mode="json"), indent=2))
    registry.unload()
    return 0 if status.ready else 1


if __name__ == "__main__":
    raise SystemExit(main())
