"""Verified PostgreSQL and immutable-blob backup/restore primitives."""

from __future__ import annotations

from collections.abc import Callable, Sequence
from datetime import UTC, datetime
from hashlib import sha256
import json
import os
from pathlib import Path, PurePosixPath
import shutil
import subprocess
import tarfile
import tempfile
from typing import Any
from uuid import uuid4

from sqlalchemy.engine import URL, make_url


Runner = Callable[..., subprocess.CompletedProcess[Any]]
MANIFEST_VERSION = 1


def file_sha256(path: Path) -> str:
    digest = sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _postgres_command_environment(database_url: str) -> tuple[str, dict[str, str]]:
    url = make_url(database_url)
    if not url.drivername.startswith("postgresql"):
        raise ValueError("Backup and restore require a PostgreSQL database URL")
    command_url = URL.create(
        drivername="postgresql",
        username=url.username,
        host=url.host,
        port=url.port,
        database=url.database,
        query=url.query,
    )
    environment = os.environ.copy()
    if url.password:
        environment["PGPASSWORD"] = url.password
    return command_url.render_as_string(hide_password=False), environment


def _run(runner: Runner, command: Sequence[str], environment: dict[str, str]) -> None:
    runner(list(command), env=environment, check=True, capture_output=True, text=True)


def _safe_extract(archive: tarfile.TarFile, destination: Path) -> None:
    for member in archive.getmembers():
        name = PurePosixPath(member.name)
        if name.is_absolute() or ".." in name.parts or member.issym() or member.islnk():
            raise ValueError(f"Unsafe archive member: {member.name}")
    archive.extractall(destination, filter="data")


def create_backup(
    *,
    database_url: str,
    blob_root: Path,
    destination: Path,
    runner: Runner = subprocess.run,
) -> dict[str, Any]:
    """Create an atomic, checksummed archive without exposing DB credentials."""
    if destination.exists():
        raise FileExistsError(f"Backup already exists: {destination}")
    destination.parent.mkdir(parents=True, exist_ok=True)
    command_url, environment = _postgres_command_environment(database_url)

    with tempfile.TemporaryDirectory(prefix="osip-backup-", dir=destination.parent) as raw:
        workspace = Path(raw)
        database_dump = workspace / "database.dump"
        blob_archive = workspace / "blobs.tar.gz"
        _run(
            runner,
            [
                "pg_dump",
                "--format=custom",
                "--no-owner",
                f"--file={database_dump}",
                f"--dbname={command_url}",
            ],
            environment,
        )

        with tarfile.open(blob_archive, "w:gz") as archive:
            if blob_root.exists():
                archive.add(blob_root, arcname="source-files", recursive=True)
            else:
                empty = tarfile.TarInfo("source-files")
                empty.type = tarfile.DIRTYPE
                empty.mode = 0o750
                archive.addfile(empty)

        manifest = {
            "manifest_version": MANIFEST_VERSION,
            "created_at": datetime.now(UTC).isoformat(),
            "database": {
                "filename": database_dump.name,
                "sha256": file_sha256(database_dump),
                "size_bytes": database_dump.stat().st_size,
            },
            "blobs": {
                "filename": blob_archive.name,
                "sha256": file_sha256(blob_archive),
                "size_bytes": blob_archive.stat().st_size,
            },
        }
        manifest_path = workspace / "manifest.json"
        manifest_path.write_text(
            json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8"
        )

        temporary_archive = workspace / "backup.tar.gz"
        with tarfile.open(temporary_archive, "w:gz") as archive:
            for path in (manifest_path, database_dump, blob_archive):
                archive.add(path, arcname=path.name, recursive=False)
        os.replace(temporary_archive, destination)
    return manifest


def inspect_backup(archive_path: Path, destination: Path) -> dict[str, Any]:
    """Extract and verify a backup into a caller-owned temporary directory."""
    with tarfile.open(archive_path, "r:gz") as archive:
        _safe_extract(archive, destination)
    manifest_path = destination / "manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    if manifest.get("manifest_version") != MANIFEST_VERSION:
        raise ValueError("Unsupported backup manifest version")
    for section in ("database", "blobs"):
        metadata = manifest[section]
        artifact = destination / metadata["filename"]
        if artifact.stat().st_size != metadata["size_bytes"]:
            raise ValueError(f"Backup {section} size does not match manifest")
        if file_sha256(artifact) != metadata["sha256"]:
            raise ValueError(f"Backup {section} checksum does not match manifest")
    return manifest


def restore_backup(
    *,
    database_url: str,
    blob_root: Path,
    archive_path: Path,
    confirmed: bool,
    runner: Runner = subprocess.run,
) -> dict[str, Any]:
    """Verify then restore both stores; callers must stop application writes first."""
    if not confirmed:
        raise PermissionError("Restore requires explicit destructive confirmation")
    command_url, environment = _postgres_command_environment(database_url)
    blob_root.parent.mkdir(parents=True, exist_ok=True)

    with tempfile.TemporaryDirectory(prefix="osip-restore-", dir=blob_root.parent) as raw:
        workspace = Path(raw)
        manifest = inspect_backup(archive_path, workspace)
        database_dump = workspace / manifest["database"]["filename"]
        packed_blobs = workspace / manifest["blobs"]["filename"]
        replacement_parent = workspace / "replacement"
        replacement_parent.mkdir()
        with tarfile.open(packed_blobs, "r:gz") as archive:
            _safe_extract(archive, replacement_parent)
        replacement = replacement_parent / "source-files"
        if not replacement.is_dir():
            raise ValueError("Backup blob archive has no source-files root")

        _run(
            runner,
            [
                "pg_restore",
                "--clean",
                "--if-exists",
                "--no-owner",
                f"--dbname={command_url}",
                str(database_dump),
            ],
            environment,
        )

        previous = blob_root.with_name(f".{blob_root.name}.pre-restore-{uuid4().hex}")
        if blob_root.exists():
            os.replace(blob_root, previous)
        try:
            os.replace(replacement, blob_root)
        except Exception:
            if previous.exists():
                os.replace(previous, blob_root)
            raise
        if previous.exists():
            shutil.rmtree(previous)
    return manifest
