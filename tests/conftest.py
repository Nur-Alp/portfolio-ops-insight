from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from osip_dashboard.config import Settings
from osip_dashboard.main import create_app
from osip_dashboard.persistence import Base
from osip_dashboard.persistence.database import create_database_engine
from osip_dashboard.storage import LocalBlobStore


WORKBOOK_DIR = Path(__file__).resolve().parents[1] / "Portfolio operations"


@pytest.fixture()
def api(tmp_path):
    database_path = tmp_path / "test.sqlite3"
    engine = create_database_engine(f"sqlite:///{database_path}")
    Base.metadata.create_all(engine)
    settings = Settings(
        environment="test",
        database_url=f"sqlite:///{database_path}",
        blob_root=tmp_path / "blobs",
        reference_data_root=tmp_path / "reference-data",
        identity_provider="development",
    )
    app = create_app(
        settings=settings,
        engine=engine,
        blob_store=LocalBlobStore(settings.blob_root),
    )
    with TestClient(app) as client:
        yield client
    engine.dispose()


@pytest.fixture()
def source_first_api(tmp_path):
    """Local domain-owner app where parsed sources publish without DQ gates."""
    database_path = tmp_path / "source-first.sqlite3"
    engine = create_database_engine(f"sqlite:///{database_path}")
    Base.metadata.create_all(engine)
    settings = Settings(
        environment="test",
        database_url=f"sqlite:///{database_path}",
        blob_root=tmp_path / "blobs-source-first",
        reference_data_root=tmp_path / "reference-data-source-first",
        identity_provider="development",
        source_first_mode=True,
    )
    app = create_app(
        settings=settings,
        engine=engine,
        blob_store=LocalBlobStore(settings.blob_root),
    )
    with TestClient(app) as client:
        yield client
    engine.dispose()


DEMO_JWT_SECRET = "test-only-demo-jwt-secret-1234567890123456"


@pytest.fixture()
def demo_api(tmp_path):
    """App running the self-issued 'demo' identity provider."""
    database_path = tmp_path / "demo.sqlite3"
    engine = create_database_engine(f"sqlite:///{database_path}")
    Base.metadata.create_all(engine)
    settings = Settings(
        environment="test",
        database_url=f"sqlite:///{database_path}",
        blob_root=tmp_path / "blobs-demo",
        reference_data_root=tmp_path / "reference-data-demo",
        identity_provider="demo",
        demo_jwt_secret=DEMO_JWT_SECRET,
        demo_max_failed_attempts=3,
        demo_lockout_minutes=15,
    )
    app = create_app(
        settings=settings,
        engine=engine,
        blob_store=LocalBlobStore(settings.blob_root),
    )
    with TestClient(app) as client:
        yield client
    engine.dispose()


@pytest.fixture(scope="session")
def workbook_paths():
    """Real OSIP portfolio workbooks are never committed to this repo -
    they're a customer's live financial data, and the whole point of this
    app is that each deployment uses its own uploaded workbook, not a
    bundled sample. Drop a real SOBSTV/TABYS .xls pair into
    "Portfolio operations/" locally (gitignored - see .gitignore) to run
    the tests that depend on one; without it, they skip rather than fail.
    """
    sobstv = next(WORKBOOK_DIR.glob("*СОБСТВ*.xls"), None)
    tabys = next(WORKBOOK_DIR.glob("*TABYS*.xls"), None)
    if sobstv is None or tabys is None:
        pytest.skip("No local OSIP portfolio workbook - see this fixture's docstring")
    return {"SOBSTV": sobstv, "TABYS": tabys}
