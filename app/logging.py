import json
import logging
import sys
from datetime import datetime, timezone
from typing import Any

logger = logging.getLogger("orchestrator")
handler = logging.StreamHandler(sys.stdout)
handler.setFormatter(logging.Formatter("%(message)s"))
logger.addHandler(handler)
logger.setLevel(logging.INFO)


def transition(review_id: int, pr_number: int, state: str, **fields: Any) -> None:
    payload = {
        "ts": datetime.now(timezone.utc).isoformat(),
        "level": "info",
        "event": "review_state_transition",
        "review_id": review_id,
        "pr_number": pr_number,
        "state": state,
        **fields,
    }
    logger.info(json.dumps(payload, default=str))
