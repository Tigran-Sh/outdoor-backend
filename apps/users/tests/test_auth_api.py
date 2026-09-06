from apps.users.constants import Role
from apps.users.tests.base import (
    DEFAULT_PASSWORD,
    BaseAPITestCase,
    make_user,
)

LOGIN_URL = "/api/v1/auth/login/"
ADMIN_LOGIN_URL = "/api/v1/auth/admin/login/"
REFRESH_URL = "/api/v1/auth/refresh/"
LOGOUT_URL = "/api/v1/auth/logout/"
ME_URL = "/api/v1/auth/me/"
CHANGE_PASSWORD_URL = "/api/v1/auth/change-password/"


class LoginTests(BaseAPITestCase):
    def setUp(self):
        self.user = make_user("owner@example.com", role=Role.CLUB_OWNER)

    def test_login_success_returns_tokens_and_user(self):
        res = self.client.post(
            LOGIN_URL,
            {"email": "owner@example.com", "password": DEFAULT_PASSWORD},
            format="json",
        )
        self.assertEqual(res.status_code, 200)
        data = res.json()
        self.assertIn("access", data)
        self.assertIn("refresh", data)
        self.assertEqual(data["user"]["role"], Role.CLUB_OWNER.value)

    def test_login_response_excludes_password(self):
        res = self.client.post(
            LOGIN_URL,
            {"email": "owner@example.com", "password": DEFAULT_PASSWORD},
            format="json",
        )
        self.assertNotIn("password", res.json()["user"])

    def test_login_wrong_password(self):
        res = self.client.post(
            LOGIN_URL,
            {"email": "owner@example.com", "password": "wrong-pass-123"},
            format="json",
        )
        self.assertEqual(res.status_code, 400)
        self.assertIn("error", res.json())

    def test_login_unknown_email_same_error(self):
        res = self.client.post(
            LOGIN_URL,
            {"email": "ghost@example.com", "password": DEFAULT_PASSWORD},
            format="json",
        )
        self.assertEqual(res.status_code, 400)

    def test_inactive_user_cannot_login(self):
        self.user.is_active = False
        self.user.save(update_fields=["is_active"])
        res = self.client.post(
            LOGIN_URL,
            {"email": "owner@example.com", "password": DEFAULT_PASSWORD},
            format="json",
        )
        self.assertEqual(res.status_code, 400)


class AdminLoginTests(BaseAPITestCase):
    """The Admin Panel login accepts staff only."""

    def _login(self, email):
        return self.client.post(
            ADMIN_LOGIN_URL,
            {"email": email, "password": DEFAULT_PASSWORD},
            format="json",
        )

    def test_staff_roles_can_log_in(self):
        staff = [
            Role.CLUB_OWNER,
            Role.GUIDE,
            Role.INTERNAL_ADMIN,
            Role.PLATFORM_ADMIN,
        ]
        for role in staff:
            email = f"{role.value}@example.com"
            make_user(email, role=role)
            res = self._login(email)
            self.assertEqual(res.status_code, 200, role)
            self.assertIn("access", res.json())

    def test_participant_is_rejected(self):
        make_user("p@example.com", role=Role.PARTICIPANT)
        res = self._login("p@example.com")
        self.assertEqual(res.status_code, 403)
        self.assertEqual(
            res.json()["error"]["code"], "permission_denied"
        )

    def test_rejected_participant_gets_no_tokens(self):
        make_user("p2@example.com", role=Role.PARTICIPANT)
        body = self._login("p2@example.com").json()
        self.assertNotIn("access", body)
        self.assertNotIn("refresh", body)

    def test_participant_can_still_use_the_client_login(self):
        make_user("p3@example.com", role=Role.PARTICIPANT)
        res = self.client.post(
            LOGIN_URL,
            {"email": "p3@example.com", "password": DEFAULT_PASSWORD},
            format="json",
        )
        self.assertEqual(res.status_code, 200)
        self.assertIn("access", res.json())

    def test_bad_credentials_still_generic(self):
        make_user("p4@example.com", role=Role.PARTICIPANT)
        res = self.client.post(
            ADMIN_LOGIN_URL,
            {"email": "p4@example.com", "password": "wrong-pass-123"},
            format="json",
        )
        self.assertEqual(res.status_code, 400)

    def test_inactive_staff_cannot_log_in(self):
        user = make_user("inactive@example.com", role=Role.CLUB_OWNER)
        user.is_active = False
        user.save(update_fields=["is_active"])
        self.assertEqual(self._login("inactive@example.com").status_code, 400)


class MeTests(BaseAPITestCase):
    def setUp(self):
        self.user = make_user("guide@example.com", role=Role.GUIDE)

    def test_me_requires_authentication(self):
        self.assertEqual(self.client.get(ME_URL).status_code, 401)

    def test_me_returns_profile_with_capabilities(self):
        self.auth(self.user)
        res = self.client.get(ME_URL)
        self.assertEqual(res.status_code, 200)
        data = res.json()
        self.assertEqual(data["email"], "guide@example.com")
        self.assertEqual(data["role"], Role.GUIDE.value)
        self.assertIn("qr_check_in", data["capabilities"])
        self.assertNotIn("password", data)


class RefreshLogoutTests(BaseAPITestCase):
    def setUp(self):
        self.user = make_user("u@example.com", role=Role.PLATFORM_ADMIN)
        self.tokens = self.client.post(
            LOGIN_URL,
            {"email": "u@example.com", "password": DEFAULT_PASSWORD},
            format="json",
        ).json()

    def test_refresh_returns_new_access(self):
        res = self.client.post(
            REFRESH_URL, {"refresh": self.tokens["refresh"]}, format="json"
        )
        self.assertEqual(res.status_code, 200)
        self.assertIn("access", res.json())

    def test_logout_blacklists_refresh(self):
        self.client.credentials(
            HTTP_AUTHORIZATION=f"Bearer {self.tokens['access']}"
        )
        out = self.client.post(
            LOGOUT_URL, {"refresh": self.tokens["refresh"]}, format="json"
        )
        self.assertEqual(out.status_code, 205)
        reused = self.client.post(
            REFRESH_URL, {"refresh": self.tokens["refresh"]}, format="json"
        )
        self.assertEqual(reused.status_code, 401)

    def test_logout_invalid_token(self):
        self.client.credentials(
            HTTP_AUTHORIZATION=f"Bearer {self.tokens['access']}"
        )
        res = self.client.post(
            LOGOUT_URL, {"refresh": "not-a-token"}, format="json"
        )
        self.assertEqual(res.status_code, 400)


class ChangePasswordTests(BaseAPITestCase):
    def setUp(self):
        self.user = make_user("cp@example.com", role=Role.CLUB_OWNER)
        self.auth(self.user)

    def test_wrong_current_password(self):
        res = self.client.post(
            CHANGE_PASSWORD_URL,
            {"current_password": "nope", "new_password": "NewStrong123!"},
            format="json",
        )
        self.assertEqual(res.status_code, 400)

    def test_weak_new_password_rejected(self):
        res = self.client.post(
            CHANGE_PASSWORD_URL,
            {"current_password": DEFAULT_PASSWORD, "new_password": "123"},
            format="json",
        )
        self.assertEqual(res.status_code, 400)

    def test_success_changes_password(self):
        res = self.client.post(
            CHANGE_PASSWORD_URL,
            {
                "current_password": DEFAULT_PASSWORD,
                "new_password": "BrandNew456!",
            },
            format="json",
        )
        self.assertEqual(res.status_code, 200)

        self.logout()
        old = self.client.post(
            LOGIN_URL,
            {"email": "cp@example.com", "password": DEFAULT_PASSWORD},
            format="json",
        )
        self.assertEqual(old.status_code, 400)
        new = self.client.post(
            LOGIN_URL,
            {"email": "cp@example.com", "password": "BrandNew456!"},
            format="json",
        )
        self.assertEqual(new.status_code, 200)
