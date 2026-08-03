"""SQLite runtime storage — metadata only; RDF remains semantic authority."""

from __future__ import annotations

import hashlib
import json
import sqlite3
import threading
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from kg_mnp_demo.application.errors import ApplicationError, ErrorCode
from kg_mnp_demo.application.serializers import json_safe, to_iso_utc
from kg_mnp_demo.loader import project_root

_LOCK = threading.Lock()

SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS executions (
    execution_id TEXT PRIMARY KEY,
    case_id TEXT NOT NULL,
    assessment_time TEXT NOT NULL,
    created_at TEXT NOT NULL,
    input_hash TEXT NOT NULL,
    decision TEXT,
    publication_status TEXT,
    publishable INTEGER NOT NULL DEFAULT 0,
    blocking_reason_count INTEGER NOT NULL DEFAULT 0,
    artifact_directory TEXT,
    schema_version TEXT NOT NULL,
    input_json TEXT,
    result_json TEXT
);

CREATE UNIQUE INDEX IF NOT EXISTS idx_executions_idempotent
ON executions(case_id, assessment_time, input_hash);

CREATE INDEX IF NOT EXISTS idx_executions_case_created
ON executions(case_id, created_at DESC);
"""


def default_db_path() -> Path:
    return project_root() / "runtime_data" / "kg_mnp.sqlite3"


def default_artifact_root() -> Path:
    return project_root() / "runtime_data" / "executions"


def compute_input_hash(payload: dict[str, Any]) -> str:
    canonical = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


class Database:
    def __init__(self, path: Path | str | None = None) -> None:
        self.path = Path(path) if path else default_db_path()
        try:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            self._conn = sqlite3.connect(str(self.path), check_same_thread=False)
            self._conn.row_factory = sqlite3.Row
            self._conn.execute("PRAGMA journal_mode=WAL;")
            self.migrate()
        except sqlite3.Error as exc:
            raise ApplicationError(
                ErrorCode.STORAGE_ERROR,
                message="无法初始化 SQLite 数据库。",
                details=[str(exc)],
                retryable=True,
            ) from exc
        except OSError as exc:
            raise ApplicationError(
                ErrorCode.STORAGE_ERROR,
                message="数据库路径不可写。",
                details=[str(exc)],
                retryable=True,
            ) from exc

    def migrate(self) -> None:
        with _LOCK:
            self._conn.executescript(SCHEMA_SQL)
            self._conn.commit()

    @property
    def connection(self) -> sqlite3.Connection:
        return self._conn

    def close(self) -> None:
        self._conn.close()


class AssessmentRepository:
    """Persist assessment execution metadata and JSON snapshots."""

    def __init__(self, db: Database | None = None) -> None:
        self.db = db or Database()

    def find_idempotent_execution(
        self,
        case_id: str,
        assessment_time: str,
        input_hash: str,
    ) -> dict[str, Any] | None:
        row = self.db.connection.execute(
            """
            SELECT * FROM executions
            WHERE case_id = ? AND assessment_time = ? AND input_hash = ?
            """,
            (case_id, assessment_time, input_hash),
        ).fetchone()
        if not row:
            return None
        return self._row_to_record(row)

    def count_by_decision(self) -> dict[str, int]:
        rows = self.db.connection.execute(
            """
            SELECT decision, COUNT(*) AS n FROM executions GROUP BY decision
            """
        ).fetchall()
        out = {"total": 0, "eligible": 0, "blocked": 0, "manual_review": 0, "other": 0}
        for row in rows:
            n = int(row["n"])
            out["total"] += n
            d = row["decision"]
            if d == "ELIGIBLE":
                out["eligible"] += n
            elif d == "BLOCKED":
                out["blocked"] += n
            elif d == "MANUAL_REVIEW":
                out["manual_review"] += n
            else:
                out["other"] += n
        return out

    def latest_case_decision_counts(self) -> dict[str, int]:
        rows = self.db.connection.execute(
            """
            SELECT e.case_id, e.decision
            FROM executions e
            INNER JOIN (
                SELECT case_id, MAX(created_at) AS max_created
                FROM executions
                GROUP BY case_id
            ) t ON e.case_id = t.case_id AND e.created_at = t.max_created
            """
        ).fetchall()
        out = {"total": 0, "eligible": 0, "blocked": 0, "manual_review": 0, "other": 0}
        seen: set[str] = set()
        for row in rows:
            if row["case_id"] in seen:
                continue
            seen.add(row["case_id"])
            out["total"] += 1
            d = row["decision"]
            if d == "ELIGIBLE":
                out["eligible"] += 1
            elif d == "BLOCKED":
                out["blocked"] += 1
            elif d == "MANUAL_REVIEW":
                out["manual_review"] += 1
            else:
                out["other"] += 1
        return out

    def find_affected_by_rule_version(
        self,
        *,
        rule_id: str,
        old_version: str,
        new_version: str | None = None,
        case_id: str | None = None,
    ) -> list[dict[str, Any]]:
        items: list[dict[str, Any]] = []
        summaries = self.list_executions(case_id=case_id, limit=5000, offset=0)
        for summary in summaries:
            record = self.get_execution(summary["execution_id"])
            result = record.get("result") or {}
            rules = result.get("rule_results") or []
            used_old = any(
                r.get("rule_id") == rule_id
                and str(r.get("version") or r.get("rule_version")) == str(old_version)
                for r in rules
            )
            if not used_old:
                continue
            items.append(
                {
                    "execution_id": record["execution_id"],
                    "case_id": record["case_id"],
                    "assessment_time": record["assessment_time"],
                    "requires_reassessment": True,
                    "rule_id": rule_id,
                    "old_version": old_version,
                    "new_version": new_version,
                }
            )
        return json_safe(items)

    def save_execution(
        self,
        *,
        execution_id: str,
        case_id: str,
        assessment_time: str,
        input_payload: dict[str, Any],
        result: dict[str, Any],
        artifact_directory: str | None = None,
        force_recompute: bool = False,
    ) -> dict[str, Any]:
        input_hash = compute_input_hash(input_payload)
        created_at = to_iso_utc(datetime.now(timezone.utc))
        publication = result.get("publication") or {}
        row = {
            "execution_id": execution_id,
            "case_id": case_id,
            "assessment_time": assessment_time,
            "created_at": created_at,
            "input_hash": input_hash,
            "decision": result.get("decision"),
            "publication_status": publication.get("status"),
            "publishable": 1 if publication.get("publishable") else 0,
            "blocking_reason_count": len(result.get("blocking_reasons") or []),
            "artifact_directory": artifact_directory,
            "schema_version": result.get("schema_version") or "1.0",
            "input_json": json.dumps(json_safe(input_payload), ensure_ascii=False),
            "result_json": json.dumps(json_safe(result), ensure_ascii=False),
        }

        with _LOCK:
            if not force_recompute:
                existing = self.db.connection.execute(
                    """
                    SELECT * FROM executions
                    WHERE case_id = ? AND assessment_time = ? AND input_hash = ?
                    """,
                    (case_id, assessment_time, input_hash),
                ).fetchone()
                if existing:
                    return self._row_to_record(existing)
            else:
                self.db.connection.execute(
                    """
                    DELETE FROM executions
                    WHERE case_id = ? AND assessment_time = ? AND input_hash = ?
                    """,
                    (case_id, assessment_time, input_hash),
                )

            try:
                self.db.connection.execute(
                    """
                    INSERT INTO executions (
                        execution_id, case_id, assessment_time, created_at, input_hash,
                        decision, publication_status, publishable, blocking_reason_count,
                        artifact_directory, schema_version, input_json, result_json
                    ) VALUES (
                        :execution_id, :case_id, :assessment_time, :created_at, :input_hash,
                        :decision, :publication_status, :publishable, :blocking_reason_count,
                        :artifact_directory, :schema_version, :input_json, :result_json
                    )
                    """,
                    row,
                )
                self.db.connection.commit()
            except sqlite3.IntegrityError:
                # Concurrent idempotent insert — return original
                existing = self.db.connection.execute(
                    """
                    SELECT * FROM executions
                    WHERE case_id = ? AND assessment_time = ? AND input_hash = ?
                    """,
                    (case_id, assessment_time, input_hash),
                ).fetchone()
                if existing:
                    return self._row_to_record(existing)
                raise ApplicationError(
                    ErrorCode.STORAGE_ERROR,
                    message="写入执行记录失败。",
                    details=["integrity error"],
                )
            except sqlite3.Error as exc:
                raise ApplicationError(
                    ErrorCode.STORAGE_ERROR,
                    message="写入执行记录失败。",
                    details=[str(exc)],
                ) from exc

        return self.get_execution(execution_id)

    def get_execution(self, execution_id: str) -> dict[str, Any]:
        row = self.db.connection.execute(
            "SELECT * FROM executions WHERE execution_id = ?",
            (execution_id,),
        ).fetchone()
        if not row:
            raise ApplicationError(
                ErrorCode.EXECUTION_NOT_FOUND,
                details=[execution_id],
            )
        return self._row_to_record(row)

    def list_executions(
        self,
        *,
        case_id: str | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> list[dict[str, Any]]:
        if case_id:
            rows = self.db.connection.execute(
                """
                SELECT * FROM executions WHERE case_id = ?
                ORDER BY created_at DESC LIMIT ? OFFSET ?
                """,
                (case_id, limit, offset),
            ).fetchall()
        else:
            rows = self.db.connection.execute(
                """
                SELECT * FROM executions
                ORDER BY created_at DESC LIMIT ? OFFSET ?
                """,
                (limit, offset),
            ).fetchall()
        return [self._row_to_summary(r) for r in rows]

    def list_case_history(self, case_id: str) -> list[dict[str, Any]]:
        return self.list_executions(case_id=case_id, limit=1000, offset=0)

    def get_latest_case_execution(self, case_id: str) -> dict[str, Any]:
        rows = self.list_executions(case_id=case_id, limit=1)
        if not rows:
            raise ApplicationError(ErrorCode.CASE_NOT_FOUND, details=[case_id])
        return self.get_execution(rows[0]["execution_id"])

    def compare_executions(self, left_id: str, right_id: str) -> dict[str, Any]:
        from kg_mnp_demo.application.comparison import (
            compare_evidence,
            compare_reasons,
            compare_rule_results,
        )

        left = self.get_execution(left_id)
        right = self.get_execution(right_id)
        left_result = left.get("result") or {}
        right_result = right.get("result") or {}
        reason_diff = compare_reasons(
            left_result.get("blocking_reasons"),
            right_result.get("blocking_reasons"),
        )
        rule_diff = compare_rule_results(
            left_result.get("rule_results"),
            right_result.get("rule_results"),
        )
        return json_safe(
            {
                "decision_changed": left_result.get("decision") != right_result.get("decision"),
                "before": {
                    "execution_id": left_id,
                    "decision": left_result.get("decision"),
                    "case_id": left.get("case_id"),
                },
                "after": {
                    "execution_id": right_id,
                    "decision": right_result.get("decision"),
                    "case_id": right.get("case_id"),
                },
                "added_blocking_reasons": reason_diff["added"],
                "removed_blocking_reasons": reason_diff["removed"],
                "changed_rule_versions": [
                    {
                        "rule_id": r["rule_id"],
                        "version_before": r.get("version_before"),
                        "version_after": r.get("version_after"),
                    }
                    for r in rule_diff
                    if r.get("changed")
                ],
                "changed_evidence": compare_evidence(
                    left_result.get("evidence"),
                    right_result.get("evidence"),
                ),
                "rule_changes": rule_diff,
            }
        )

    def delete_runtime_execution(self, execution_id: str) -> None:
        with _LOCK:
            cur = self.db.connection.execute(
                "DELETE FROM executions WHERE execution_id = ?",
                (execution_id,),
            )
            self.db.connection.commit()
            if cur.rowcount == 0:
                raise ApplicationError(
                    ErrorCode.EXECUTION_NOT_FOUND,
                    details=[execution_id],
                )

    def _row_to_record(self, row: sqlite3.Row) -> dict[str, Any]:
        data = dict(row)
        result = json.loads(data.pop("result_json") or "{}")
        input_payload = json.loads(data.pop("input_json") or "{}")
        # Never expose absolute paths
        art = data.get("artifact_directory")
        if art:
            data["artifact_directory"] = Path(art).name
        return json_safe(
            {
                **data,
                "publishable": bool(data.get("publishable")),
                "input": input_payload,
                "result": result,
            }
        )

    def _row_to_summary(self, row: sqlite3.Row) -> dict[str, Any]:
        data = dict(row)
        art = data.get("artifact_directory")
        return json_safe(
            {
                "execution_id": data["execution_id"],
                "case_id": data["case_id"],
                "assessment_time": data["assessment_time"],
                "created_at": data["created_at"],
                "decision": data["decision"],
                "publication_status": data["publication_status"],
                "publishable": bool(data["publishable"]),
                "blocking_reason_count": data["blocking_reason_count"],
                "artifact_directory": Path(art).name if art else None,
                "schema_version": data["schema_version"],
                "input_hash": data["input_hash"],
            }
        )


class ArtifactRepository:
    def __init__(self, root: Path | None = None) -> None:
        self.root = root or default_artifact_root()

    def execution_dir(self, execution_id: str) -> Path:
        path = self.root / execution_id
        path.mkdir(parents=True, exist_ok=True)
        return path

    def cleanup_execution_dir(self, execution_id: str) -> None:
        """Remove a newly created artifact directory for a failed/orphaned write."""
        import shutil

        path = self.root / execution_id
        if path.exists() and path.is_dir():
            shutil.rmtree(path, ignore_errors=True)

    def relative_artifacts(self, names: dict[str, str]) -> dict[str, str]:
        return {k: Path(v).name for k, v in names.items()}
