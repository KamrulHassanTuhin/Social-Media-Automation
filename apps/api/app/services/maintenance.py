from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any


@dataclass(frozen=True)
class RetentionRun:
    workspace_id: str
    retention_days: int
    eligible_count: int
    deleted_count: int
    cutoff_at: str
    dry_run: bool


def run_audit_retention(workspace_repository: Any, *, dry_run: bool = True, actor_id: str = "system") -> list[RetentionRun]:
    """Run workspace-scoped audit retention for every workspace.

    The dry-run default keeps manual invocations safe. Production schedulers should
    call the command with --apply after migrations 001-006 are installed.
    """
    results: list[RetentionRun] = []
    for workspace_id in workspace_repository.list_workspace_ids():
        retention_days = workspace_repository.get_audit_retention(workspace_id)
        eligible_count, cutoff_at = workspace_repository.purge_audit(workspace_id, retention_days, dry_run=dry_run)
        if not dry_run and eligible_count:
            workspace_repository.record_audit(
                workspace_id,
                actor_id,
                "AUDIT_RETENTION_PURGED",
                "AUDIT_LOG",
                None,
                None,
                {"deleted_count": eligible_count, "retention_days": retention_days, "cutoff_at": cutoff_at},
            )
        results.append(RetentionRun(workspace_id, retention_days, eligible_count, eligible_count if not dry_run else 0, cutoff_at, dry_run))
    return results


def serialize_retention_runs(results: list[RetentionRun]) -> list[dict[str, Any]]:
    return [asdict(result) for result in results]
