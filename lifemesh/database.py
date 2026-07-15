from __future__ import annotations

import os
import fcntl
import hashlib
import json
import shutil
import sqlite3
import subprocess
import tempfile
import time
from contextlib import closing, contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .config import LifemeshConfig
from .migrations import (
    MIGRATION_CHECKSUM,
    apply_empty_schema,
    apply_legacy_schema,
    build_conservation_snapshot,
    build_preflight,
)


TARGET_MIGRATION_ID = "0001_unified_write_model"


class DatabaseError(RuntimeError):
    pass


class ClosingConnection(sqlite3.Connection):
    _lifemesh_lock_file: Any | None = None

    def attach_lock_file(self, lock_file: Any) -> None:
        self._lifemesh_lock_file = lock_file

    def close(self) -> None:
        lock_file = self._lifemesh_lock_file
        self._lifemesh_lock_file = None
        try:
            super().close()
        finally:
            if lock_file is not None:
                fcntl.flock(lock_file.fileno(), fcntl.LOCK_UN)
                lock_file.close()

    def __exit__(self, exc_type: Any, exc: Any, traceback: Any) -> bool:
        try:
            return bool(super().__exit__(exc_type, exc, traceback))
        finally:
            self.close()


class LifeMeshDatabase:
    def __init__(self, config: LifemeshConfig) -> None:
        self.config = config

    def status(self) -> dict[str, Any]:
        path = self.config.db_path
        if not path.exists():
            return {
                "database_path": str(path),
                "database_exists": False,
                "schema_status": "uninitialized",
                "applied_migrations": [],
                "target_migration_id": TARGET_MIGRATION_ID,
            }

        applied = self._read_applied_migrations(path)
        target = next(
            (item for item in applied if item["migration_id"] == TARGET_MIGRATION_ID),
            None,
        )
        if target is not None and target["checksum"] != MIGRATION_CHECKSUM:
            raise DatabaseError(
                f"Migration checksum mismatch for {TARGET_MIGRATION_ID}"
            )
        return {
            "database_path": str(path),
            "database_exists": True,
            "schema_status": "current" if target is not None else "legacy",
            "applied_migrations": applied,
            "target_migration_id": TARGET_MIGRATION_ID,
        }

    def connect(self) -> sqlite3.Connection:
        con = self._open_connection()
        try:
            row = con.execute(
                "SELECT checksum FROM schema_migrations WHERE migration_id = ?",
                (TARGET_MIGRATION_ID,),
            ).fetchone()
            if row is None:
                raise DatabaseError("Unified database migration is required; run `lifemesh db migrate --apply`")
            if str(row[0]) != MIGRATION_CHECKSUM:
                raise DatabaseError(f"Migration checksum mismatch for {TARGET_MIGRATION_ID}")
            return con
        except (sqlite3.Error, DatabaseError):
            con.close()
            raise

    def ensure_current_for_write(self) -> None:
        status = self.status()["schema_status"]
        if status == "uninitialized":
            self.migrate(apply=True)
            return
        if status != "current":
            raise DatabaseError(
                "Legacy LifeMesh database must be migrated before writing; run `lifemesh db migrate --apply`"
            )

    @contextmanager
    def transaction(self) -> Any:
        con = self.connect()
        try:
            con.execute("BEGIN IMMEDIATE")
            yield con
            con.commit()
        except Exception:
            con.rollback()
            raise
        finally:
            con.close()

    def migrate(self, *, apply: bool = False) -> dict[str, Any]:
        applied = self.status()["schema_status"] == "current"
        if apply:
            if applied:
                preflight = build_preflight(self.config.db_path)
                return {
                    "dry_run": False,
                    "migration_required": False,
                    "target_migration_id": TARGET_MIGRATION_ID,
                    "preflight": preflight,
                    "backup_manifest": None,
                    "postflight": self._postflight(),
                }
            if self.config.db_path.exists():
                self._ensure_private_home()
                with self._exclusive_lock():
                    self._assert_database_quiescent()
                    preflight = build_preflight(self.config.db_path)
                    guard = self._open_connection(acquire_lock=False)
                    try:
                        guard.execute("BEGIN IMMEDIATE")
                        manifest_path = self._online_backup(preflight)
                        apply_legacy_schema(guard, applied_at=_utc_now())
                        self._validate_migration_conservation(guard, preflight)
                        guard.commit()
                    except (sqlite3.Error, OSError, ValueError) as exc:
                        guard.rollback()
                        raise DatabaseError(f"Cannot migrate legacy database: {exc}") from exc
                    finally:
                        guard.close()
                os.chmod(self.config.db_path, 0o600)
                return {
                    "dry_run": False,
                    "migration_required": True,
                    "target_migration_id": TARGET_MIGRATION_ID,
                    "preflight": preflight,
                    "backup_manifest": str(manifest_path),
                    "postflight": self._postflight(preflight=preflight),
                }
            preflight = build_preflight(self.config.db_path)
            self._ensure_private_home()
            with self._exclusive_lock():
                con = self._open_connection(acquire_lock=False)
                try:
                    apply_empty_schema(con, applied_at=_utc_now())
                except sqlite3.Error as exc:
                    raise DatabaseError(f"Cannot initialize unified database: {exc}") from exc
                finally:
                    con.close()
            os.chmod(self.config.db_path, 0o600)
            return {
                "dry_run": False,
                "migration_required": True,
                "target_migration_id": TARGET_MIGRATION_ID,
                "preflight": preflight,
                "backup_manifest": None,
                "postflight": self._postflight(preflight=preflight),
            }
        if self.config.db_path.exists():
            self._ensure_private_home()
            with self._exclusive_lock():
                self._assert_database_quiescent()
                preflight = build_preflight(self.config.db_path)
        else:
            preflight = build_preflight(self.config.db_path)
        return {
            "dry_run": True,
            "migration_required": not applied,
            "target_migration_id": TARGET_MIGRATION_ID,
            "preflight": preflight,
        }

    def restore(self, manifest_path: Path, *, apply: bool = False) -> dict[str, Any]:
        if not apply:
            raise DatabaseError("Database restore requires explicit --apply")
        self._ensure_private_home()
        backup_dir = self.config.home / "backups"
        backup_dir.mkdir(parents=True, exist_ok=True)
        os.chmod(backup_dir, 0o700)
        stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
        forensic_dir = backup_dir / f"forensic-before-restore-{stamp}"
        forensic_path = forensic_dir / self.config.db_path.name
        replaced = False
        with self._exclusive_lock():
            manifest, resolved_manifest, backup_path = self._validate_restore_manifest(manifest_path)
            self._assert_database_quiescent()
            if not self.config.db_path.exists():
                raise DatabaseError("Cannot restore because the target database does not exist")
            forensic_dir.mkdir(mode=0o700)
            moved_paths = self._move_database_to_forensic(forensic_dir)
            forensic_manifest = forensic_dir / "forensic-manifest.json"
            forensic_manifest.write_text(
                json.dumps(
                    {
                        "created_at": _utc_now(),
                        "target_database": str(self.config.db_path),
                        "restore_manifest": str(resolved_manifest),
                        "moved_files": moved_paths,
                    },
                    ensure_ascii=False,
                    indent=2,
                )
                + "\n",
                encoding="utf-8",
            )
            os.chmod(forensic_manifest, 0o600)
            _fsync_path(forensic_manifest)
            _fsync_directory(forensic_dir)
            fd, temp_name = tempfile.mkstemp(prefix="lifemesh-restore-", suffix=".db", dir=self.config.home)
            os.close(fd)
            temp_path = Path(temp_name)
            try:
                _copy_validated_backup(
                    backup_path,
                    temp_path,
                    expected_size=int(manifest["backup_size"]),
                    expected_sha256=str(manifest["backup_sha256"]),
                )
                os.chmod(temp_path, 0o600)
                with closing(sqlite3.connect(f"file:{temp_path}?mode=ro", uri=True)) as con:
                    integrity = con.execute("PRAGMA integrity_check").fetchone()[0]
                if integrity != "ok":
                    raise DatabaseError("Restore backup integrity check failed")
                _fsync_path(temp_path)
                os.replace(temp_path, self.config.db_path)
                replaced = True
                os.chmod(self.config.db_path, 0o600)
                _fsync_directory(self.config.db_path.parent)
                self._remove_database_companions()
                restored_preflight = build_preflight(self.config.db_path)
                expected_digests = manifest.get("preflight", {}).get("identity_digests")
                restored_digests = restored_preflight.get("identity_digests", {})
                if expected_digests is not None and any(
                    restored_digests.get(key) != value
                    for key, value in expected_digests.items()
                ):
                    raise DatabaseError("Restored database does not match the backup preflight identity sets")
                with closing(sqlite3.connect(f"file:{self.config.db_path}?mode=ro", uri=True)) as con:
                    restored_integrity = con.execute("PRAGMA integrity_check").fetchone()[0]
                if restored_integrity != "ok":
                    raise DatabaseError("Restored database integrity check failed")
                self._restore_smoke_test()
            except Exception:
                if replaced:
                    failed_restore = forensic_dir / "failed-restore-attempt.db"
                    os.replace(self.config.db_path, failed_restore)
                    os.chmod(failed_restore, 0o600)
                self._restore_forensic_database(forensic_dir)
                raise
            finally:
                temp_path.unlink(missing_ok=True)
        return {
            "manifest_path": str(resolved_manifest),
            "backup_path": str(backup_path),
            "forensic_database_path": str(forensic_path),
            "forensic_directory": str(forensic_dir),
            "database_path": str(self.config.db_path),
            "integrity_check": "ok",
            "preflight": restored_preflight,
        }

    def reconcile_files(self, *, apply: bool = False) -> dict[str, Any]:
        with self.connect() as con:
            rows = con.execute(
                "SELECT * FROM file_operations WHERE status IN ('pending', 'failed') ORDER BY created_at, operation_id"
            ).fetchall()
        if not apply:
            return {
                "dry_run": True,
                "pending_count": len(rows),
                "completed_count": 0,
                "failed_count": sum(1 for row in rows if row["status"] == "failed"),
                "operations": [_file_operation_summary(row) for row in rows],
            }
        completed = 0
        failed = 0
        for row in rows:
            error: str | None = None
            try:
                self._apply_file_operation(row)
            except (OSError, DatabaseError) as exc:
                error = str(exc)
            with self.transaction() as con:
                if error is None:
                    con.execute(
                        "UPDATE file_operations SET status = 'completed', attempts = attempts + 1, last_error = NULL, completed_at = ? WHERE operation_id = ?",
                        (_utc_now(), row["operation_id"]),
                    )
                    completed += 1
                else:
                    con.execute(
                        "UPDATE file_operations SET status = 'failed', attempts = attempts + 1, last_error = ? WHERE operation_id = ?",
                        (error, row["operation_id"]),
                    )
                    failed += 1
        return {
            "dry_run": False,
            "pending_count": failed,
            "completed_count": completed,
            "failed_count": failed,
            "operations": [],
        }

    def _apply_file_operation(self, row: sqlite3.Row) -> None:
        operation_type = str(row["operation_type"])
        if operation_type == "delete_managed_asset":
            if not row["source_path"]:
                raise DatabaseError("delete_managed_asset is missing source_path")
            path = Path(str(row["source_path"])).expanduser().resolve(strict=False)
            root = self.config.raw_asset_dir.resolve(strict=False)
            if not path.is_relative_to(root):
                raise DatabaseError("managed asset operation escaped the private raw asset directory")
            path.unlink(missing_ok=True)
            return
        if operation_type == "promote_staged_asset":
            if not row["source_path"] or not row["target_path"]:
                raise DatabaseError("promote_staged_asset is missing a path")
            unresolved_source = Path(str(row["source_path"])).expanduser()
            if unresolved_source.is_symlink():
                raise DatabaseError("managed asset staging path cannot be a symlink")
            source = unresolved_source.resolve(strict=False)
            target = Path(str(row["target_path"])).resolve(strict=False)
            root = self.config.raw_asset_dir.resolve(strict=False)
            staging_root = (self.config.home / "staging").resolve(strict=False)
            if not source.is_relative_to(staging_root):
                raise DatabaseError("managed asset staging operation escaped the private staging directory")
            if not target.is_relative_to(root):
                raise DatabaseError("managed asset promotion escaped the private raw asset directory")
            if not source.exists():
                if target.exists():
                    return
                raise DatabaseError("managed asset staging file is missing")
            target.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
            current = target.parent
            while current.is_relative_to(root):
                os.chmod(current, 0o700)
                if current == root:
                    break
                current = current.parent
            os.replace(source, target)
            os.chmod(target, 0o600)
            return
        raise DatabaseError(f"Unsupported file operation: {operation_type}")

    def _validate_restore_manifest(self, manifest_path: Path) -> tuple[dict[str, Any], Path, Path]:
        backup_root = (self.config.home / "backups").resolve()
        unresolved_manifest = manifest_path.expanduser().absolute()
        if unresolved_manifest.is_symlink():
            raise DatabaseError("Symlink backup paths are not allowed")
        try:
            resolved_manifest = unresolved_manifest.resolve(strict=True)
        except FileNotFoundError as exc:
            raise DatabaseError(f"Backup manifest not found: {manifest_path}") from exc
        if not resolved_manifest.is_relative_to(backup_root):
            raise DatabaseError("Backup manifest must be inside the managed LifeMesh backup directory")
        data = json.loads(resolved_manifest.read_text(encoding="utf-8"))
        if Path(str(data.get("home", ""))).resolve() != self.config.home.resolve():
            raise DatabaseError("Backup manifest HOME does not match the current LifeMesh HOME")
        if Path(str(data.get("database_path", ""))).resolve() != self.config.db_path.resolve():
            raise DatabaseError("Backup manifest database path does not match the current target")
        try:
            unresolved_backup = Path(str(data["backup_path"])).expanduser().absolute()
            if unresolved_backup.is_symlink():
                raise DatabaseError("Symlink backup paths are not allowed")
            backup_path = unresolved_backup.resolve(strict=True)
        except (KeyError, FileNotFoundError) as exc:
            raise DatabaseError("Backup file referenced by manifest is missing") from exc
        if not backup_path.is_relative_to(backup_root):
            raise DatabaseError("Backup file must be inside the managed LifeMesh backup directory")
        if backup_path.stat().st_size != int(data.get("backup_size", -1)):
            raise DatabaseError("Backup size does not match manifest")
        if _sha256_file(backup_path) != data.get("backup_sha256"):
            raise DatabaseError("Backup hash does not match manifest")
        return data, resolved_manifest, backup_path

    def _assert_database_quiescent(self) -> None:
        watched = [self.config.db_path, *self._database_companions()]
        open_pids = _open_file_pids([path for path in watched if path.exists()])
        if open_pids:
            raise DatabaseError(
                "Database is in use by a process that does not honor the LifeMesh lock: "
                + ", ".join(str(pid) for pid in sorted(open_pids))
            )
        before = {
            path: (path.stat().st_ino, path.stat().st_size, path.stat().st_mtime_ns)
            for path in self._database_companions()
            if path.exists()
        }
        if before:
            time.sleep(0.05)
            after = {
                path: (path.stat().st_ino, path.stat().st_size, path.stat().st_mtime_ns)
                for path in self._database_companions()
                if path.exists()
            }
            if before != after:
                raise DatabaseError("Database WAL/SHM/journal changed during preflight")

    def _database_companions(self) -> list[Path]:
        return [Path(str(self.config.db_path) + suffix) for suffix in ("-wal", "-shm", "-journal")]

    def _remove_database_companions(self) -> None:
        for path in self._database_companions():
            path.unlink(missing_ok=True)

    def _move_database_to_forensic(self, forensic_dir: Path) -> list[dict[str, Any]]:
        moved: list[dict[str, Any]] = []
        for source in [self.config.db_path, *self._database_companions()]:
            if not source.exists():
                continue
            target = forensic_dir / source.name
            os.replace(source, target)
            moved.append(
                {
                    "original_path": str(source),
                    "forensic_path": str(target),
                    "size": target.stat().st_size,
                    "sha256": _sha256_file(target),
                }
            )
        _fsync_directory(forensic_dir)
        _fsync_directory(self.config.db_path.parent)
        return moved

    def _restore_forensic_database(self, forensic_dir: Path) -> None:
        self._remove_database_companions()
        for original in [self.config.db_path, *self._database_companions()]:
            saved = forensic_dir / original.name
            if saved.exists():
                shutil.copy2(saved, original)
        os.chmod(self.config.db_path, 0o600)
        _fsync_directory(self.config.db_path.parent)

    def _restore_smoke_test(self) -> None:
        with closing(sqlite3.connect(f"file:{self.config.db_path}?mode=ro", uri=True)) as con:
            table_count = int(
                con.execute("SELECT COUNT(*) FROM sqlite_master WHERE type IN ('table', 'view')").fetchone()[0]
            )
        if table_count == 0:
            raise DatabaseError("Restored database smoke test found no schema objects")

    def _ensure_private_home(self) -> None:
        self.config.home.mkdir(parents=True, exist_ok=True)
        os.chmod(self.config.home, 0o700)

    def _open_connection(self, *, acquire_lock: bool = True) -> ClosingConnection:
        lock_file = None
        if acquire_lock:
            lock_path = self.config.home / ".database.lock"
            lock_file = lock_path.open("a+b")
            os.chmod(lock_path, 0o600)
            fcntl.flock(lock_file.fileno(), fcntl.LOCK_SH)
        try:
            con = sqlite3.connect(self.config.db_path, factory=ClosingConnection)
        except Exception:
            if lock_file is not None:
                fcntl.flock(lock_file.fileno(), fcntl.LOCK_UN)
                lock_file.close()
            raise
        if lock_file is not None:
            con.attach_lock_file(lock_file)
        con.row_factory = sqlite3.Row
        con.execute("PRAGMA foreign_keys = ON")
        con.execute("PRAGMA busy_timeout = 5000")
        return con

    @contextmanager
    def _exclusive_lock(self) -> Any:
        lock_path = self.config.home / ".database.lock"
        with lock_path.open("a+b") as lock_file:
            os.chmod(lock_path, 0o600)
            fcntl.flock(lock_file.fileno(), fcntl.LOCK_EX)
            try:
                yield
            finally:
                fcntl.flock(lock_file.fileno(), fcntl.LOCK_UN)

    def _online_backup(self, preflight: dict[str, Any]) -> Path:
        backup_dir = self.config.home / "backups"
        backup_dir.mkdir(parents=True, exist_ok=True)
        os.chmod(backup_dir, 0o700)
        stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
        backup_path = backup_dir / f"lifemesh-before-{TARGET_MIGRATION_ID}-{stamp}.db"
        manifest_path = backup_path.with_suffix(".manifest.json")
        source_uri = f"file:{self.config.db_path}?mode=ro"
        with closing(sqlite3.connect(source_uri, uri=True)) as source, closing(
            sqlite3.connect(backup_path)
        ) as target:
            source.backup(target)
            integrity = target.execute("PRAGMA integrity_check").fetchone()[0]
        if integrity != "ok":
            raise DatabaseError("Backup integrity check failed")
        os.chmod(backup_path, 0o600)
        digest = _sha256_file(backup_path)
        manifest = {
            "schema_version": 1,
            "home": str(self.config.home.resolve()),
            "database_path": str(self.config.db_path.resolve()),
            "backup_path": str(backup_path.resolve()),
            "backup_sha256": digest,
            "backup_size": backup_path.stat().st_size,
            "target_migration_id": TARGET_MIGRATION_ID,
            "created_at": _utc_now(),
            "preflight": preflight,
        }
        manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        os.chmod(manifest_path, 0o600)
        return manifest_path

    def _postflight(self, *, preflight: dict[str, Any] | None = None) -> dict[str, Any]:
        with self._open_connection() as con:
            integrity = con.execute("PRAGMA integrity_check").fetchone()[0]
            foreign_keys = [list(row) for row in con.execute("PRAGMA foreign_key_check").fetchall()]
            counts = self._migration_counts(con)
            snapshot = build_conservation_snapshot(con) if preflight is not None else None
        if integrity != "ok" or foreign_keys:
            raise DatabaseError("Unified database postflight validation failed")
        conservation = None
        if preflight is not None:
            expected = preflight["expected"]
            conservation = "ok" if (
                counts == expected
                and snapshot is not None
                and snapshot["identity_digests"] == preflight.get("identity_digests", {})
                and snapshot["preserved_table_digests"] == preflight.get("preserved_table_digests", {})
            ) else "failed"
            if conservation != "ok":
                raise DatabaseError(
                    "Unified database conservation check failed after commit"
                )
        return {
            "integrity_check": integrity,
            "foreign_key_violations": foreign_keys,
            "migration_id": TARGET_MIGRATION_ID,
            "migration_checksum": MIGRATION_CHECKSUM,
            "candidate_count": counts["candidates"],
            "source_reference_count": counts["source_references"],
            "source_tombstone_count": counts["source_tombstones"],
            "canonical_object_count": counts["canonical_objects"],
            "review_item_count": counts["review_items"],
            "conservation_check": conservation,
        }

    def _validate_migration_conservation(
        self,
        con: sqlite3.Connection,
        preflight: dict[str, Any],
    ) -> None:
        integrity = con.execute("PRAGMA integrity_check").fetchone()[0]
        foreign_keys = con.execute("PRAGMA foreign_key_check").fetchall()
        if integrity != "ok" or foreign_keys:
            raise sqlite3.IntegrityError("migration integrity or foreign-key validation failed")
        expected = preflight["expected"]
        actual = self._migration_counts(con)
        if actual != expected:
            raise sqlite3.IntegrityError(
                f"migration conservation check failed: expected {expected}, got {actual}"
            )
        snapshot = build_conservation_snapshot(con)
        if snapshot["identity_digests"] != preflight.get("identity_digests", {}):
            raise sqlite3.IntegrityError("migration identity/link/audit conservation check failed")
        if snapshot["preserved_table_digests"] != preflight.get("preserved_table_digests", {}):
            raise sqlite3.IntegrityError("migration FTS/vector preservation check failed")

    @staticmethod
    def _migration_counts(con: sqlite3.Connection) -> dict[str, int]:
        return {
            "candidates": int(con.execute("SELECT COUNT(*) FROM knowledge_candidates").fetchone()[0]),
            "source_references": int(con.execute("SELECT COUNT(*) FROM source_references").fetchone()[0]),
            "source_tombstones": int(con.execute("SELECT COUNT(*) FROM source_tombstones").fetchone()[0]),
            "canonical_objects": int(con.execute("SELECT COUNT(*) FROM canonical_objects").fetchone()[0]),
            "review_items": int(con.execute("SELECT COUNT(*) FROM review_items").fetchone()[0]),
        }

    def _read_applied_migrations(self, path: Path) -> list[dict[str, Any]]:
        try:
            with closing(sqlite3.connect(f"file:{path}?mode=ro", uri=True)) as con:
                exists = con.execute(
                    "SELECT 1 FROM sqlite_master WHERE type='table' AND name='schema_migrations'"
                ).fetchone()
                if exists is None:
                    return []
                con.row_factory = sqlite3.Row
                return [
                    dict(row)
                    for row in con.execute(
                        "SELECT migration_id, name, checksum, applied_at FROM schema_migrations ORDER BY migration_id"
                    ).fetchall()
                ]
        except sqlite3.Error as exc:
            raise DatabaseError(f"Cannot inspect LifeMesh database: {exc}") from exc


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as file:
        for chunk in iter(lambda: file.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _open_file_pids(paths: list[Path]) -> set[int]:
    if not paths:
        return set()
    lsof = shutil.which("lsof")
    if lsof is not None:
        result = subprocess.run(
            [lsof, "-t", *[str(path) for path in paths]],
            check=False,
            capture_output=True,
            text=True,
        )
        return {
            int(line)
            for line in result.stdout.splitlines()
            if line.strip().isdigit() and int(line) != os.getpid()
        }
    proc = Path("/proc")
    if not proc.exists():
        return set()
    resolved = {path.resolve(strict=False) for path in paths}
    pids: set[int] = set()
    for process in proc.iterdir():
        if not process.name.isdigit() or int(process.name) == os.getpid():
            continue
        fd_dir = process / "fd"
        try:
            descriptors = list(fd_dir.iterdir())
        except (FileNotFoundError, PermissionError):
            continue
        for descriptor in descriptors:
            try:
                if descriptor.resolve(strict=True) in resolved:
                    pids.add(int(process.name))
                    break
            except (FileNotFoundError, PermissionError, OSError):
                continue
    return pids


def _fsync_path(path: Path) -> None:
    with path.open("rb") as handle:
        os.fsync(handle.fileno())


def _copy_validated_backup(
    source_path: Path,
    target_path: Path,
    *,
    expected_size: int,
    expected_sha256: str,
) -> None:
    flags = os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0)
    source_fd = os.open(source_path, flags)
    digest = hashlib.sha256()
    copied = 0
    try:
        with os.fdopen(source_fd, "rb", closefd=False) as source, target_path.open("wb") as target:
            for chunk in iter(lambda: source.read(1024 * 1024), b""):
                target.write(chunk)
                digest.update(chunk)
                copied += len(chunk)
            target.flush()
            os.fsync(target.fileno())
    finally:
        os.close(source_fd)
    if copied != expected_size or digest.hexdigest() != expected_sha256:
        target_path.unlink(missing_ok=True)
        raise DatabaseError("Backup changed after manifest validation")


def _fsync_directory(path: Path) -> None:
    fd = os.open(path, os.O_RDONLY)
    try:
        os.fsync(fd)
    finally:
        os.close(fd)


def _file_operation_summary(row: sqlite3.Row) -> dict[str, Any]:
    return {
        "operation_id": row["operation_id"],
        "operation_type": row["operation_type"],
        "status": row["status"],
        "attempts": row["attempts"],
        "last_error": row["last_error"],
    }
