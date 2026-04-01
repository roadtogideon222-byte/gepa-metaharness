from __future__ import annotations

import json
from pathlib import Path

from ...models import AgentEvent
from ..normalized_events import collect_changed_files, last_text_message


def parse_pi_jsonl(path: Path) -> tuple[list[AgentEvent], str, list[str]]:
    events: list[AgentEvent] = []
    if not path.exists():
        return events, "", []

    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line:
            continue
        try:
            payload = json.loads(line)
        except json.JSONDecodeError:
            continue
        kind = str(payload.get("type", "unknown"))
        text = None
        if kind == "message_update":
            assistant_event = payload.get("assistantMessageEvent", {})
            text = assistant_event.get("delta") or assistant_event.get("text")
        if "content" in payload and isinstance(payload["content"], str):
            text = payload["content"]
        events.append(
            AgentEvent(
                ts=payload.get("timestamp"),
                kind=kind,
                text=text,
                raw=payload,
            )
        )
    return events, last_text_message(events), collect_changed_files(events)
