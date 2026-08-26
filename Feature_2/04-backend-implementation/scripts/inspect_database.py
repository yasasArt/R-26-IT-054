from app.config import get_settings
from app.db.connection import connect_database
from app.db.migrations import current_schema_version


def main() -> None:
    settings = get_settings()
    assert settings.database_path is not None

    connection = connect_database(settings.database_path)
    try:
        tables = connection.execute(
            """
            SELECT name
            FROM sqlite_master
            WHERE type = 'table' AND name NOT LIKE 'sqlite_%'
            ORDER BY name
            """
        ).fetchall()

        print(f"Database: {settings.database_path}")
        print(f"Schema version: {current_schema_version(connection)}")
        print("Tables:")
        for table in tables:
            print(f"- {table['name']}")
    finally:
        connection.close()


if __name__ == "__main__":
    main()
