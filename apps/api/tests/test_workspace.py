import unittest
from uuid import uuid4

from fastapi.testclient import TestClient

from app.main import app
from app.jobs.outbox import notification_outbox


class WorkspaceAdminWorkflowTest(unittest.TestCase):
    def setUp(self) -> None:
        self.client = TestClient(app)
        self.headers = {"X-Workspace-ID": "ws_demo"}

    def test_admin_writes_are_audited(self) -> None:
        project = self.client.post("/api/v1/workspace/projects", headers=self.headers, json={"name": "Test Workspace Project"})
        self.assertEqual(project.status_code, 201)
        project_id = project.json()["data"]["id"]
        archived = self.client.patch(f"/api/v1/workspace/projects/{project_id}", headers=self.headers, json={"name": "Test Workspace Project", "slug": "test-workspace-project", "status": "ARCHIVED"})
        self.assertEqual(archived.status_code, 200)
        invite = self.client.post("/api/v1/workspace/members/invite", headers=self.headers, json={"email": "test.member@axis.local", "role": "REVIEWER"})
        self.assertEqual(invite.status_code, 202)
        notifications = self.client.get("/api/v1/notifications/outbox", headers=self.headers)
        self.assertEqual(notifications.status_code, 200)
        self.assertTrue(any(item["event_type"] == "EMAIL" for item in notifications.json()["data"]))
        role = self.client.patch("/api/v1/workspace/members/user_writer/role", headers=self.headers, json={"role": "MANAGER"})
        self.assertEqual(role.status_code, 200)
        disabled = self.client.patch("/api/v1/workspace/members/user_writer/status", headers=self.headers, json={"status": "DISABLED"})
        self.assertEqual(disabled.status_code, 200)
        reactivated = self.client.patch("/api/v1/workspace/members/user_writer/status", headers=self.headers, json={"status": "ACTIVE"})
        self.assertEqual(reactivated.status_code, 200)
        preview = self.client.post("/api/v1/workspace/invitations/preview", headers=self.headers, json={"email": "preview@axis.local"})
        self.assertEqual(preview.status_code, 200)
        self.assertIn("subject", preview.json()["data"])
        audit = self.client.get("/api/v1/workspace/audit-log", headers=self.headers)
        self.assertEqual(audit.status_code, 200)
        self.assertGreaterEqual(len(audit.json()["data"]), 6)
        exported = self.client.get("/api/v1/workspace/audit-log.csv", headers=self.headers)
        self.assertEqual(exported.status_code, 200)
        self.assertIn("text/csv", exported.headers["content-type"])
        archived_projects = self.client.get("/api/v1/workspace/projects?include_archived=true", headers=self.headers)
        self.assertTrue(any(item["id"] == project_id and item["status"] == "ARCHIVED" for item in archived_projects.json()["data"]))

    def test_admin_cannot_change_own_role(self) -> None:
        response = self.client.patch("/api/v1/workspace/members/user_demo/role", headers=self.headers, json={"role": "READ_ONLY"})
        self.assertEqual(response.status_code, 409)

    def test_email_webhook_updates_delivery_state_and_analytics(self) -> None:
        event = notification_outbox.enqueue("ws_demo", "EMAIL", {"to": "bounce-test@axis.local", "subject": "Test"}, f"webhook-test:{uuid4()}")
        notification_outbox.mark_sent(event, "provider-test-message")
        response = self.client.post("/api/v1/notifications/webhook/email", json={"type": "email.bounced", "data": {"email_id": "provider-test-message", "reason": "hard_bounce"}})
        self.assertEqual(response.status_code, 202)
        self.assertTrue(response.json()["data"]["matched"])
        self.assertEqual(event.status, "BOUNCED")
        analytics = self.client.get("/api/v1/notifications/analytics", headers=self.headers)
        self.assertEqual(analytics.status_code, 200)
        self.assertGreaterEqual(analytics.json()["data"]["BOUNCED"], 1)

    def test_audit_retention_is_admin_gated_and_dry_run_by_default(self) -> None:
        current = self.client.get("/api/v1/workspace/audit-retention", headers=self.headers)
        self.assertEqual(current.status_code, 200)
        self.assertGreaterEqual(current.json()["data"]["retention_days"], 30)
        invalid = self.client.patch("/api/v1/workspace/audit-retention", headers=self.headers, json={"retention_days": 7})
        self.assertEqual(invalid.status_code, 422)
        preview = self.client.post("/api/v1/workspace/audit-log/retention/purge", headers=self.headers, json={"confirm": False})
        self.assertEqual(preview.status_code, 200)
        self.assertTrue(preview.json()["data"]["dry_run"])
        self.assertEqual(preview.json()["data"]["deleted_count"], 0)


if __name__ == "__main__":
    unittest.main()
