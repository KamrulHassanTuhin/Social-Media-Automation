import unittest
from datetime import datetime, timedelta, timezone

from app.repositories.workspace import AuditRecord, InMemoryWorkspaceRepository
from app.services.maintenance import run_audit_retention


class MaintenanceTest(unittest.TestCase):
    def test_retention_command_previews_then_deletes_old_records(self) -> None:
        repository = InMemoryWorkspaceRepository()
        old_timestamp = (datetime.now(timezone.utc) - timedelta(days=400)).isoformat()
        repository._audit.append(AuditRecord("old-audit", "ws_demo", "user_demo", "PROJECT_UPDATED", "PROJECT", "project_demo", None, None, old_timestamp))

        preview = run_audit_retention(repository)
        self.assertEqual(preview[0].eligible_count, 1)
        self.assertEqual(preview[0].deleted_count, 0)
        self.assertTrue(any(record.id == "old-audit" for record in repository._audit))

        applied = run_audit_retention(repository, dry_run=False)
        self.assertEqual(applied[0].deleted_count, 1)
        self.assertFalse(any(record.id == "old-audit" for record in repository._audit))
        self.assertTrue(any(record.action == "AUDIT_RETENTION_PURGED" for record in repository._audit))


if __name__ == "__main__":
    unittest.main()
