from pathlib import Path

import pytest

from osip_dashboard.operations.backup import create_backup, inspect_backup, restore_backup


DATABASE_URL = "postgresql+psycopg://osip:secret@db.example:5432/osip"


class FakePostgresRunner:
    def __init__(self):
        self.commands = []
        self.passwords = []

    def __call__(self, command, *, env, check, capture_output, text):
        assert check and capture_output and text
        self.commands.append(command)
        self.passwords.append(env.get("PGPASSWORD"))
        if command[0] == "pg_dump":
            output = Path(next(item.split("=", 1)[1] for item in command if item.startswith("--file=")))
            output.write_bytes(b"fake-postgresql-custom-dump")


def test_backup_and_confirmed_restore_verify_both_stores(tmp_path):
    blobs = tmp_path / "blobs"
    source = blobs / "b9" / "b9-source.xls"
    source.parent.mkdir(parents=True)
    source.write_bytes(b"immutable workbook evidence")
    archive = tmp_path / "backup.tar.gz"
    runner = FakePostgresRunner()

    manifest = create_backup(
        database_url=DATABASE_URL,
        blob_root=blobs,
        destination=archive,
        runner=runner,
    )
    assert archive.is_file()
    assert manifest["database"]["size_bytes"] > 0
    assert "secret" not in " ".join(runner.commands[0])
    assert runner.passwords == ["secret"]

    inspection = tmp_path / "inspection"
    inspection.mkdir()
    assert inspect_backup(archive, inspection) == manifest

    source.write_bytes(b"content to replace")
    extra = blobs / "extra.bin"
    extra.write_bytes(b"not in backup")
    with pytest.raises(PermissionError):
        restore_backup(
            database_url=DATABASE_URL,
            blob_root=blobs,
            archive_path=archive,
            confirmed=False,
            runner=runner,
        )

    restored = restore_backup(
        database_url=DATABASE_URL,
        blob_root=blobs,
        archive_path=archive,
        confirmed=True,
        runner=runner,
    )
    assert restored == manifest
    assert source.read_bytes() == b"immutable workbook evidence"
    assert not extra.exists()
    assert runner.commands[-1][0] == "pg_restore"
    assert "secret" not in " ".join(runner.commands[-1])
    assert runner.passwords[-1] == "secret"


def test_backup_refuses_overwrite_and_non_postgresql_database(tmp_path):
    destination = tmp_path / "existing.tar.gz"
    destination.write_bytes(b"keep")
    with pytest.raises(FileExistsError):
        create_backup(
            database_url=DATABASE_URL,
            blob_root=tmp_path / "blobs",
            destination=destination,
            runner=FakePostgresRunner(),
        )
    with pytest.raises(ValueError, match="PostgreSQL"):
        create_backup(
            database_url="sqlite:///local.db",
            blob_root=tmp_path / "blobs",
            destination=tmp_path / "new.tar.gz",
            runner=FakePostgresRunner(),
        )
