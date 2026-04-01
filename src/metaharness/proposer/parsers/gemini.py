from __future__ import annotations

import json
from pathlib import Path

from ...models import AgentEvent
from ..normalized_events import collect_changed_files, last_text_message


def parse_gemini_json(path: Path) -> tuple[list[AgentEvent], str, list[str]]:
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
        text = payload.get("text") or payload.get("value") or payload.get("message")
        command = payload.get("command")
        output = payload.get("output")
        tool_name = payload.get("tool") or payload.get("toolName")
        file_changes = [str(item) for item in payload.get("fileChanges", []) or []]
        events.append(
            AgentEvent(
                ts=payload.get("timestamp"),
                kind=kind,
                text=text if isinstance(text, str) else None,
                command=command if isinstance(command, str) else None,
                output=output if isinstance(output, str) else None,
                file_changes=file_changes,
                tool_name=tool_name if isinstance(tool_name, str) else None,
                raw=payload,
            )
        )
    return events, last_text_message(events), collect_changed_files(events)
