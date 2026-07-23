import unittest

from fastapi import HTTPException

from app.auth.dependencies import CurrentUser
from app.auth.permissions import permissions_for, require_permission


class PermissionRulesTest(unittest.TestCase):
    def test_reviewer_can_approve_but_cannot_publish(self) -> None:
        permissions = permissions_for(("REVIEWER",))
        self.assertIn("APPROVE_CONTENT", permissions)
        self.assertNotIn("PUBLISH_CONTENT", permissions)

    def test_read_only_is_denied_mutation(self) -> None:
        user = CurrentUser("user_read", "read@axis.local", ("ws_demo",), ("READ_ONLY",))
        with self.assertRaises(HTTPException) as error:
            require_permission(("ws_demo", user), "CREATE_CONTENT")
        self.assertEqual(error.exception.status_code, 403)


if __name__ == "__main__":
    unittest.main()
