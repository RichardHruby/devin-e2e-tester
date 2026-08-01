from typing import Any

import httpx


class DevinClient:
    def __init__(self, api_key: str, base_url: str = "https://api.devin.ai"):
        self.client = httpx.AsyncClient(
            base_url=base_url, headers={"Authorization": f"Bearer {api_key}"}, timeout=30
        )

    async def create_session(self, prompt: str) -> dict[str, Any]:
        response = await self.client.post(
            "/v1/sessions",
            json={
                "prompt": prompt,
                "idempotent": True,
                "structured_output_schema": {
                    "type": "object",
                    "properties": {
                        "verdict": {"enum": ["pass", "bug_found", "error"]},
                        "bugs": {"type": "array"},
                        "summary": {"type": "string"},
                        "fix_pr_url": {"type": ["string", "null"]},
                    },
                    "required": ["verdict", "bugs", "summary", "fix_pr_url"],
                },
            },
        )
        response.raise_for_status()
        return response.json()

    async def get_session(self, session_id: str) -> dict[str, Any]:
        response = await self.client.get(f"/v1/sessions/{session_id}")
        response.raise_for_status()
        return response.json()

    async def close(self) -> None:
        await self.client.aclose()
