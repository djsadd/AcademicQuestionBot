from __future__ import annotations

import unittest

from fastapi.testclient import TestClient

from backend.api.main import app
from backend.services.permissions import require_admin


class ApiTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        app.dependency_overrides[require_admin] = lambda: {"telegram_id": 1, "platonus_role": "admin"}
        cls.client = TestClient(app)

    @classmethod
    def tearDownClass(cls) -> None:
        app.dependency_overrides.clear()

    def test_liveness(self) -> None:
        response = self.client.get("/api/health")
        self.assertEqual(response.status_code, 200)
        self.assertIn("X-Request-ID", response.headers)

    def test_rag_search_route_is_not_shadowed_by_document_detail(self) -> None:
        # Previously GET /documents/search matched /documents/{document_id}.
        response = self.client.get("/api/rag/documents/search", params={"query": "стипендия"})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["query"], "стипендия")

    def test_upload_rejects_unsupported_extension(self) -> None:
        response = self.client.post(
            "/api/rag/documents/upload",
            files={"file": ("evil.exe", b"MZ...", "application/octet-stream")},
        )
        self.assertEqual(response.status_code, 415)

    def test_chat_rejects_empty_message(self) -> None:
        response = self.client.post("/api/chat/public/admission", json={"message": "   "})
        self.assertEqual(response.status_code, 422)


if __name__ == "__main__":
    unittest.main()
