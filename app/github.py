import hashlib
import hmac
from typing import Any

import httpx


class GitHubClient:
    def __init__(self, token: str, base_url: str = "https://api.github.com"):
        self.client = httpx.AsyncClient(
            base_url=base_url,
            headers={"Authorization": f"Bearer {token}", "Accept": "application/vnd.github+json"},
            timeout=30,
        )

    async def get_pr(self, repo: str, number: int) -> dict[str, Any]:
        response = await self.client.get(f"/repos/{repo}/pulls/{number}")
        response.raise_for_status()
        return response.json()

    async def create_commit_status(
        self, repo: str, sha: str, state: str, target_url: str | None, description: str
    ) -> None:
        response = await self.client.post(
            f"/repos/{repo}/statuses/{sha}",
            json={
                "state": state,
                "context": "devin/e2e-review",
                "target_url": target_url,
                "description": description[:140],
            },
        )
        response.raise_for_status()

    async def create_issue_comment(self, repo: str, number: int, body: str) -> str | None:
        response = await self.client.post(
            f"/repos/{repo}/issues/{number}/comments", json={"body": body}
        )
        response.raise_for_status()
        return response.json().get("html_url")

    async def create_issue(self, repo: str, title: str, body: str, label: str) -> str:
        payload = {"title": title, "body": body, "labels": [label]}
        response = await self.client.post(f"/repos/{repo}/issues", json=payload)
        if response.status_code == 422 and label:
            response = await self.client.post(
                f"/repos/{repo}/issues", json={"title": title, "body": body}
            )
        response.raise_for_status()
        return response.json()["html_url"]

    async def close(self) -> None:
        await self.client.aclose()


def verify_signature(body: bytes, signature: str | None, secret: str) -> bool:
    if not signature or not signature.startswith("sha256="):
        return False
    expected = "sha256=" + hmac.new(secret.encode(), body, hashlib.sha256).hexdigest()
    return hmac.compare_digest(expected, signature)
