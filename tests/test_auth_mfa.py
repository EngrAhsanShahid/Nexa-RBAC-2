import copy
import unittest
from types import SimpleNamespace
from bson import ObjectId
from unittest.mock import patch, MagicMock

from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.db.session import get_db
from app.features.auth import api as auth_api
from app.features.auth.api import router as auth_router
from app.features.auth.security import get_password_hash


class FakeCollection:
    def __init__(self, docs=None):
        self.docs = docs or []
        self.indexes = []

    def create_index(self, keys, **kwargs):
        self.indexes.append((keys, kwargs))
        return str(keys)

    def find_one(self, query):
        for doc in self.docs:
            if all(doc.get(key) == value for key, value in query.items()):
                return copy.deepcopy(doc)
        return None

    def insert_one(self, doc):
        self.docs.append(copy.deepcopy(doc))
        return SimpleNamespace(inserted_id=doc.get("_id"))

    def delete_one(self, query):
        for index, doc in enumerate(self.docs):
            if all(doc.get(key) == value for key, value in query.items()):
                self.docs.pop(index)
                return SimpleNamespace(deleted_count=1)
        return SimpleNamespace(deleted_count=0)

    def update_one(self, query, update):
        for index, doc in enumerate(self.docs):
            if all(doc.get(key) == value for key, value in query.items()):
                updated = copy.deepcopy(doc)
                if "$set" in update:
                    updated.update(update["$set"])
                self.docs[index] = updated
                return SimpleNamespace(matched_count=1, modified_count=1)
        return SimpleNamespace(matched_count=0, modified_count=0)


class FakeDatabase:
    def __init__(self, users, mfa_challenges=None):
        self.users = FakeCollection(users)
        self.mfa_challenges = FakeCollection(mfa_challenges)


class AuthMfaTests(unittest.TestCase):
    def setUp(self):
        auth_api._MFA_INDEXES_READY = False
        self.user_id = ObjectId()
        self.db = FakeDatabase([
            {
                "_id": self.user_id,
                "email": "user@example.com",
                "full_name": "Regular User",
                "hashed_password": get_password_hash("user123"),
                "role": "User",
                "is_active": True,
                "tenant_id": "tenant_1",
            }
        ])

        auth_api.settings.GMAIL_EMAIL = "lambdatheta123@gmail.com"
        auth_api.settings.GMAIL_APP_PASSWORD = "app-password"
        auth_api.settings.GMAIL_FROM_EMAIL = "lambdatheta123@gmail.com"
        auth_api.settings.GMAIL_SMTP_HOST = "smtp.gmail.com"
        auth_api.settings.GMAIL_SMTP_PORT = 465

        self.app = FastAPI()
        self.app.include_router(auth_router, prefix="/api/v1/auth", tags=["auth"])
        self.app.dependency_overrides[get_db] = lambda: self.db

        self.generate_otp_patch = patch("app.features.auth.api._generate_otp", return_value="123456")
        self.smtp_patch = patch("app.features.auth.api.smtplib.SMTP_SSL")
        self.generate_otp_patch.start()
        self.smtp_mock = self.smtp_patch.start()
        smtp_context = MagicMock()
        self.smtp_mock.return_value.__enter__.return_value = smtp_context
        self.smtp_context = smtp_context

        self.client = TestClient(self.app)

    def tearDown(self):
        self.generate_otp_patch.stop()
        self.smtp_patch.stop()
        self.app.dependency_overrides.clear()

    def test_login_returns_mfa_challenge_instead_of_jwt(self):
        response = self.client.post(
            "/api/v1/auth/login",
            json={"username": "user@example.com", "password": "user123"},
        )

        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertTrue(body["mfa_required"])
        self.assertTrue(body["challenge_id"])
        self.assertEqual(body["expires_in_seconds"], 300)
        self.assertEqual(len(self.db.mfa_challenges.docs), 1)
        self.smtp_context.login.assert_called_once()
        self.smtp_context.send_message.assert_called_once()

    def test_verify_mfa_issues_jwt_and_clears_challenge(self):
        login = self.client.post(
            "/api/v1/auth/login",
            json={"username": "user@example.com", "password": "user123"},
        )
        challenge_id = login.json()["challenge_id"]

        verify = self.client.post(
            "/api/v1/auth/verify-mfa",
            json={"challenge_id": challenge_id, "otp": "123456"},
        )

        self.assertEqual(verify.status_code, 200)
        self.assertIn("access_token", verify.json())
        self.assertEqual(len(self.db.mfa_challenges.docs), 0)
        self.assertIn("access_token=", verify.headers.get("set-cookie", ""))

    def test_verify_mfa_rejects_wrong_otp(self):
        login = self.client.post(
            "/api/v1/auth/login",
            json={"username": "user@example.com", "password": "user123"},
        )

        verify = self.client.post(
            "/api/v1/auth/verify-mfa",
            json={"challenge_id": login.json()["challenge_id"], "otp": "000000"},
        )

        self.assertEqual(verify.status_code, 401)


if __name__ == "__main__":
    unittest.main()