import os

import pytest
from alembic import command
from alembic.config import Config
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, inspect

from osip_dashboard.config import Settings
from osip_dashboard.main import create_app
from osip_dashboard.storage import LocalBlobStore


POSTGRES_URL = os.getenv("OSIP_TEST_POSTGRES_URL")
pytestmark = [
    pytest.mark.postgres,
    pytest.mark.skipif(not POSTGRES_URL, reason="OSIP_TEST_POSTGRES_URL is not configured"),
]


def test_postgres_migration_and_real_workbook_imports(tmp_path, workbook_paths):
    config = Config("alembic.ini")
    config.set_main_option("sqlalchemy.url", POSTGRES_URL)
    command.upgrade(config, "head")

    engine = create_engine(POSTGRES_URL)
    inspector = inspect(engine)
    amount = next(
        column
        for column in inspector.get_columns("portfolio_snapshots")
        if column["name"] == "derived_operational_total_kzt"
    )
    assert amount["type"].precision == 38
    assert amount["type"].scale == 12
    published_index = next(
        index
        for index in inspector.get_indexes("import_batches")
        if index["name"] == "uq_published_import_per_portfolio_date"
    )
    assert published_index["unique"] is True

    settings = Settings(
        environment="test",
        database_url=POSTGRES_URL,
        blob_root=tmp_path / "postgres-blobs",
        identity_provider="development",
    )
    app = create_app(
        settings=settings,
        engine=engine,
        blob_store=LocalBlobStore(settings.blob_root),
    )
    headers = {
        "X-Actor-Id": "postgres-uploader",
        "X-Actor-Roles": "uploader,reader",
    }
    with TestClient(app) as client:
        results = []
        for path in workbook_paths.values():
            response = client.post(
                "/api/v1/imports",
                files={"file": (path.name, path.read_bytes(), "application/vnd.ms-excel")},
                data={"portfolio_code": "SOBSTV" if "СОБСТВ" in path.name.upper() else "TABYS"},
                headers=headers,
            )
            assert response.status_code == 201, response.text
            results.append(response.json())
    assert {result["portfolio"] for result in results} == {"SOBSTV", "TABYS"}
    assert {result["summary"]["position_count"] for result in results} == {19, 15}
    engine.dispose()
