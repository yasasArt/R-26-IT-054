from app.config import get_settings
from app.db.connection import connect_database
from app.db.migrations import apply_migrations
from app.db.transaction import transaction
from app.time_utils import utc_now_iso


def main() -> None:
    settings = get_settings()
    if settings.environment == "production":
        raise RuntimeError("Development readiness simulation is disabled in production")

    settings.ensure_directories()
    assert settings.database_path is not None
    connection = connect_database(settings.database_path)
    try:
        apply_migrations(connection)
        with transaction(connection):
            connection.execute(
                """
                UPDATE device_configuration
                SET camera_index = 0,
                    camera_label = 'Development Camera',
                    camera_tested = 1,
                    controller_device_id = 'development-controller',
                    controller_name = 'Development Garment Controller',
                    controller_connected = 1,
                    updated_at = ?
                WHERE id = 1
                """,
                (utc_now_iso(),),
            )
    finally:
        connection.close()

    print("Development camera and controller readiness enabled.")
    print("Do not use this simulation in a production installation.")


if __name__ == "__main__":
    main()
