from pathlib import Path
from string import Template

TEMPLATE = Path(__file__).resolve().parent.parent / "prompts" / "e2e_review.md"


def render_prompt(pr: dict) -> str:
    return Template(TEMPLATE.read_text()).substitute(
        pr_url=pr.get("html_url", ""),
        title=pr.get("title", ""),
        body=pr.get("body") or "(no description provided)",
        head_branch=pr["head"]["ref"],
        repo=f"{pr['base']['repo']['full_name']}",
        head_sha=pr["head"]["sha"],
    )


def parse_verdict(session_json: dict) -> object | None:
    import json
    import re

    from .models import Verdict

    candidate = session_json.get("structured_output")
    if isinstance(candidate, dict):
        data = candidate
    else:
        data = None
        messages = session_json.get("messages", [])
        for message in reversed(messages):
            text = message.get("message", "") if isinstance(message, dict) else str(message)
            matches = re.findall(r"\{[\s\S]*\}", text)
            for raw in reversed(matches):
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
