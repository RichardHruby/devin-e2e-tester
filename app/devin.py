import json
import re
from typing import Any

import httpx

from .models import Verdict


def parse_verdict(session_json: dict[str, Any]) -> Verdict | None:
    candidate = session_json.get("structured_output")
    if isinstance(candidate, dict):
        data = candidate
    else:
        data = None
        for message in reversed(session_json.get("messages", [])):
            text = message.get("message", "") if isinstance(message, dict) else str(message)
            for raw in reversed(re.findall(r"\{[\s\S]*\}", text)):
                try:
                    parsed = json.loads(raw)
                except json.JSONDecodeError:
                    continue
                if isinstance(parsed, dict) and parsed.get("verdict") in {
                    "pass",
                    "bug_found",
                    "error",
                }:
                    data = parsed
                    break
            if data:
                break
    if not data or data.get("verdict") not in {"pass", "bug_found", "error"}:
        return None
    return Verdict(
        verdict=data["verdict"],
        bugs=data.get("bugs", []),
        summary=str(data.get("summary", "")),
        fix_pr_url=data.get("fix_pr_url"),
    )


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
