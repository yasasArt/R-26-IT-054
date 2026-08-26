from app.config import get_settings
from app.db.migrations import initialize_database


def main() -> None:
    settings = get_settings()
    settings.ensure_directories()
    assert settings.database_path is not None

    version = initialize_database(settings.database_path)
    print(f"Database: {settings.database_path}")
    print(f"Schema version: {version}")
    print("Database initialization completed successfully.")


if __name__ == "__main__":
    main()
