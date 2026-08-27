import json
from decimal import Decimal

from alembic import command
from alembic.autogenerate import compare_metadata
from alembic.config import Config
from alembic.migration import MigrationContext
from sqlalchemy import create_engine, inspect, text
from sqlalchemy.orm import Session

from osip_dashboard.persistence import Base
from osip_dashboard.persistence.models import ImportBatch, Portfolio, SourceRow


def test_formula_carrying_price_migration_backfills_cached_blank(tmp_path):
    database_path = tmp_path / "formula-carrying-price.sqlite3"
    config = Config("alembic.ini")
    config.set_main_option("sqlalchemy.url", f"sqlite:///{database_path}")
    command.upgrade(config, "0012_backfill_carrying_price_native")

    values = [""] * 58
    values[11] = 1000
    values[16] = 99
    values[26] = 99068.31
    values[56] = 1
    values[57] = 2

    engine = create_engine(f"sqlite:///{database_path}")
    with engine.begin() as connection:
        connection.execute(text("INSERT INTO portfolios (code, name, reporting_currency, created_at) VALUES ('TEST', 'Test', 'KZT', CURRENT_TIMESTAMP)"))
        connection.execute(text("""INSERT INTO import_batches
            (id, portfolio_code, source_sha256, original_filename, storage_key,
             parser_version, status, uploader_id, created_at, updated_at)
            VALUES ('00000000000000000000000000000031', 'TEST', :sha,
             'source.xls', 'sha256/source.xls', 'test', 'validated', 'tester',
             CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
        """), {"sha": "d" * 64})
        connection.execute(text("""INSERT INTO source_rows
            (id, import_id, workbook_name, sheet_name, row_number, row_kind,
             parser_version, raw_values)
            VALUES ('00000000000000000000000000000032',
             '00000000000000000000000000000031', 'source.xls', 'Temp', 5,
             'position', 'test', :raw_values)
        """), {"raw_values": json.dumps(values)})
        connection.execute(text("""INSERT INTO instruments
            (isin, security_code, issuer, raw_security_type,
             normalized_asset_class, instrument_currency, raw_sector,
             first_seen_at)
            VALUES ('TESTISIN', 'TEST', 'Test issuer', 'Bond', 'Bonds', 'KZT',
             '', CURRENT_TIMESTAMP)
        """))
        connection.execute(text("""INSERT INTO portfolio_snapshots
            (id, import_id, portfolio_code, report_date, version, value_label,
             position_count, unique_isin_count, raw_settlement_count,
             settlement_count, purchase_amount_kzt,
             derived_carrying_value_kzt, cash_kzt,
             derived_operational_total_kzt, total_fees_kzt, total_reserves_kzt,
             created_at)
            VALUES ('00000000000000000000000000000033',
             '00000000000000000000000000000031', 'TEST', '2026-07-27', 1,
             'test', 1, 1, 0, 0, 0, 0, 0, 0, 0, 0, CURRENT_TIMESTAMP)
        """))
        connection.execute(text("""INSERT INTO position_lots
            (id, snapshot_id, source_row_id, source_section, security_code,
             isin, raw_security_type, issuer, valuation_method,
             instrument_currency, raw_sector, rating_sp, rating_moodys,
             rating_fitch, listing_rating, quantity, carrying_price_native,
             unavailable_fields)
            VALUES ('00000000000000000000000000000034',
             '00000000000000000000000000000033',
             '00000000000000000000000000000032', 'Temp', 'TEST', 'TESTISIN',
             'Bond', 'Test issuer', 'test', 'KZT', '', '', '', '', '', 99,
             NULL, '[]')
        """))
    engine.dispose()

    command.upgrade(config, "head")
    engine = create_engine(f"sqlite:///{database_path}")
    with engine.connect() as connection:
        price = connection.execute(text("SELECT carrying_price_native FROM position_lots")).scalar_one()
        assert Decimal(str(price)).quantize(Decimal("0.0001")) == Decimal("100.0690")
    engine.dispose()


def test_source_upload_hash_is_scoped_to_uploader(tmp_path):
    database_path = tmp_path / "source-upload-ownership.sqlite3"
    config = Config("alembic.ini")
    config.set_main_option("sqlalchemy.url", f"sqlite:///{database_path}")
    command.upgrade(config, "head")

    engine = create_engine(f"sqlite:///{database_path}")
    with engine.begin() as connection:
        for identifier, uploader in (("00000000000000000000000000000041", "operator-a"), ("00000000000000000000000000000042", "operator-b")):
            connection.execute(text("""INSERT INTO source_uploads
                (id, source_sha256, original_filename, storage_key, file_format,
                 detected_source_type, detection, uploader_id, created_at)
                VALUES (:id, :sha, 'risk.xls', 'aa/blob.xls', 'xls',
                 'risk_limits_sobstv', '{}', :uploader, CURRENT_TIMESTAMP)
            """), {"id": identifier, "sha": "e" * 64, "uploader": uploader})
        assert connection.execute(text("SELECT COUNT(*) FROM source_uploads WHERE source_sha256 = :sha"), {"sha": "e" * 64}).scalar_one() == 2
    engine.dispose()

def test_empty_database_upgrades_to_head(tmp_path):
    database_path = tmp_path / "migration.sqlite3"
    config = Config("alembic.ini")
    config.set_main_option("sqlalchemy.url", f"sqlite:///{database_path}")
    command.upgrade(config, "head")

    engine = create_engine(f"sqlite:///{database_path}")
    inspector = inspect(engine)
    tables = set(inspector.get_table_names())
    assert {
        "portfolios",
        "import_batches",
        "portfolio_snapshots",
        "position_lots",
        "cash_balances",
        "settlement_events",
        "data_quality_issues",
        "audit_events",
    } <= tables
    import_indexes = {
        index["name"]: index for index in inspector.get_indexes("import_batches")
    }
    assert import_indexes["uq_published_import_per_portfolio_date"]["unique"] == 1
    assert import_indexes["uq_active_import_source_portfolio"]["unique"] == 1
    snapshot_columns = {
        column["name"]: column
        for column in inspector.get_columns("portfolio_snapshots")
    }
    assert snapshot_columns["cash_kzt"]["type"].precision == 38
    assert snapshot_columns["cash_kzt"]["type"].scale == 12
    lot_columns = {column["name"]: column for column in inspector.get_columns("position_lots")}
    assert lot_columns["current_ytm"]["type"].precision == 38
    assert lot_columns["current_ytm"]["type"].scale == 12
    foreign_keys = inspector.get_foreign_keys("position_lots")
    assert {tuple(key["constrained_columns"]) for key in foreign_keys} >= {
        ("snapshot_id",),
        ("source_row_id",),
    }
    with engine.connect() as connection:
        schema_diff = compare_metadata(MigrationContext.configure(connection), Base.metadata)
    assert schema_diff == []
    engine.dispose()

def test_baseline_migration_downgrades_cleanly(tmp_path):
    database_path = tmp_path / "downgrade.sqlite3"
    config = Config("alembic.ini")
    config.set_main_option("sqlalchemy.url", f"sqlite:///{database_path}")
    command.upgrade(config, "head")
    command.downgrade(config, "base")

    engine = create_engine(f"sqlite:///{database_path}")
    assert set(inspect(engine).get_table_names()) <= {"alembic_version"}
    engine.dispose()


def test_assignment_scoped_source_migration_preserves_existing_evidence(tmp_path):
    database_path = tmp_path / "assignment-scope.sqlite3"
    config = Config("alembic.ini")
    config.set_main_option("sqlalchemy.url", f"sqlite:///{database_path}")
    command.upgrade(config, "0001_versioned_imports")

    engine = create_engine(f"sqlite:///{database_path}")
    # Insert using the historical 0001 schema rather than the current ORM model.
    # This proves that the migration upgrades data created by the old release.
    with engine.begin() as connection:
        connection.execute(text("INSERT INTO portfolios (code, name, reporting_currency, created_at) VALUES ('OLD', 'Old', 'KZT', CURRENT_TIMESTAMP)"))
        connection.execute(text("""INSERT INTO import_batches
            (id, portfolio_code, source_sha256, original_filename, storage_key, parser_version, status, uploader_id, created_at, updated_at)
            VALUES ('00000000000000000000000000000001', 'OLD', :sha, 'source.xls', 'sha256/a.xls', 'test', 'withdrawn', 'tester', CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
        """), {"sha": "a" * 64})
        connection.execute(text("""INSERT INTO source_rows
            (id, import_id, workbook_name, sheet_name, row_number, row_kind, parser_version, raw_values)
            VALUES ('00000000000000000000000000000002', '00000000000000000000000000000001', 'source.xls', 'Temp', 1, 'metadata', 'test', '[]')
        """))
    engine.dispose()

    command.upgrade(config, "head")
    engine = create_engine(f"sqlite:///{database_path}")
    with Session(engine) as session:
        assert session.query(ImportBatch).count() == 1
        assert session.query(SourceRow).count() == 1
        batch = session.query(ImportBatch).one()
        assert batch.source_upload_id is not None
    engine.dispose()


def test_osip_business_date_migration_repairs_filename_derived_date(tmp_path):
    database_path = tmp_path / "business-date.sqlite3"
    config = Config("alembic.ini")
    config.set_main_option("sqlalchemy.url", f"sqlite:///{database_path}")
    command.upgrade(config, "0008_client_identity_resolutions")

    engine = create_engine(f"sqlite:///{database_path}")
    with engine.begin() as connection:
        connection.execute(text("INSERT INTO portfolios (code, name, reporting_currency, created_at) VALUES ('SOBSTV', 'Own', 'KZT', CURRENT_TIMESTAMP)"))
        connection.execute(text("""INSERT INTO import_batches
            (id, portfolio_code, source_sha256, original_filename, storage_key,
             parser_version, status, uploader_id, created_at, updated_at,
             dataset_type, source_report_date, business_date)
            VALUES ('00000000000000000000000000000011', 'SOBSTV', :sha,
             'source 19.07.2026.xls', 'sha256/source.xls', 'test', 'validated',
             'tester', CURRENT_TIMESTAMP, CURRENT_TIMESTAMP,
             'portfolio_snapshot', '2026-07-20', '2026-07-19')
        """), {"sha": "b" * 64})
    engine.dispose()


    command.upgrade(config, "head")
    engine = create_engine(f"sqlite:///{database_path}")
    with engine.connect() as connection:
        row = connection.execute(text("SELECT source_report_date, business_date FROM import_batches WHERE id = '00000000000000000000000000000011'")).one()
        assert str(row.source_report_date) == "2026-07-20"
        assert str(row.business_date) == "2026-07-20"
    engine.dispose()


def test_accounting_landing_migration_clears_untrusted_inferred_dates(tmp_path):
    database_path = tmp_path / "accounting-date.sqlite3"
    config = Config("alembic.ini")
    config.set_main_option("sqlalchemy.url", f"sqlite:///{database_path}")
    command.upgrade(config, "0009_osip_business_date")

    engine = create_engine(f"sqlite:///{database_path}")
    with engine.begin() as connection:
        connection.execute(text("""INSERT INTO source_uploads
            (id, source_sha256, original_filename, storage_key, file_format,
             detected_source_type, detection, uploader_id, created_at)
            VALUES ('00000000-0000-0000-0000-000000000021', :sha,
             'accounting.xls', 'sha256/accounting.xls', 'xls',
             'accounting_portfolio_landing', '{}', 'tester', CURRENT_TIMESTAMP)
        """), {"sha": "c" * 64})
        connection.execute(text("""INSERT INTO dataset_versions
            (id, source_upload_id, dataset_type, detected_key, scope_type,
             scope_code, source_report_date, business_date, parser_version,
             version, status, summary, uploader_id, created_at)
            VALUES ('00000000-0000-0000-0000-000000000022',
             '00000000-0000-0000-0000-000000000021', 'accounting_landing',
             'portfolio', 'business_domain', 'ACCOUNTING', '2028-05-15',
             '2028-05-15', 'old-parser', 1, 'validated', '{}', 'tester',
             CURRENT_TIMESTAMP)
        """))
        connection.execute(text("""INSERT INTO dataset_issues
            (id, dataset_id, code, severity, message, affected_fields, source_refs)
            VALUES ('00000000-0000-0000-0000-000000000023',
             '00000000-0000-0000-0000-000000000022', 'ACCOUNTING-02', 'medium',
             'old inferred date conflict', '[]', '[]')
        """))
    engine.dispose()

    command.upgrade(config, "head")
    engine = create_engine(f"sqlite:///{database_path}")
    with engine.connect() as connection:
        row = connection.execute(text("""SELECT source_report_date, business_date
            FROM dataset_versions WHERE dataset_type = 'accounting_landing'""")).one()
        assert row.source_report_date is None
        assert row.business_date is None
        assert connection.execute(text("SELECT COUNT(*) FROM dataset_issues WHERE code = 'ACCOUNTING-02'")).scalar_one() == 0
    engine.dispose()
