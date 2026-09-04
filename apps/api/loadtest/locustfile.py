"""Locust load scenarios for FDrive API (Phase 17)."""

from __future__ import annotations

import os
import uuid

from locust import HttpUser, between, task


class DriveUser(HttpUser):
    wait_time = between(0.5, 2.0)

    def on_start(self) -> None:
        email = f"load-{uuid.uuid4().hex[:10]}@example.com"
        password = os.getenv("LOADTEST_PASSWORD", "securepass1")
        with self.client.post(
            "/api/v1/auth/register-account",
            json={
                "email": email,
                "password": password,
                "display_name": "Load User",
            },
            catch_response=True,
            name="auth.register-account",
        ) as response:
            if response.status_code not in {201, 409}:
                response.failure(f"register failed: {response.status_code}")
                return
            if response.status_code == 409:
                login = self.client.post(
                    "/api/v1/auth/login",
                    json={"email": email, "password": password},
                    name="auth.login",
                )
                token = login.json()["access_token"]
            else:
                token = response.json()["access_token"]
        self.headers = {"Authorization": f"Bearer {token}"}

    @task(3)
    def profile(self) -> None:
        self.client.get(
            "/api/v1/account/profile",
            headers=self.headers,
            name="account.profile",
        )

    @task(2)
    def list_root(self) -> None:
        self.client.get(
            "/api/v1/folders/list-folder-contents",
            headers=self.headers,
            name="folders.list-folder-contents",
        )

    @task(1)
    def storage_quota(self) -> None:
        self.client.get(
            "/api/v1/account/storage-quota",
            headers=self.headers,
            name="account.storage-quota",
        )

    @task(1)
    def search(self) -> None:
        self.client.get(
            "/api/v1/search/search-drive",
            params={"q": "a"},
            headers=self.headers,
            name="search.search-drive",
        )
