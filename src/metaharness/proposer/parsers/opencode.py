from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from ...models import AgentEvent
from ..normalized_events import collect_changed_files, last_text_message


def parse_opencode_jsonl(path: Path) -> tuple[list[AgentEvent], str, list[str]]:
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
        if not isinstance(payload, dict):
            continue

        kind = str(payload.get("type", "unknown"))
        part = payload.get("part")
        text = _extract_text(payload, part)
        command = _extract_command(part)
        output = _extract_output(payload, part)
        tool_name = _extract_tool_name(part)
        file_changes = _extract_file_changes(tool_name, part)
        events.append(
            AgentEvent(
                ts=_coerce_timestamp(payload.get("timestamp")),
                kind=kind,
                text=text,
                command=command,
                output=output,
                file_changes=file_changes,
                tool_name=tool_name,
                raw=payload,
            )
        )

    return events, last_text_message(events), collect_changed_files(events)


def _coerce_timestamp(value: Any) -> str | None:
    if value is None:
        return None
    if isinstance(value, str) and value.strip():
        return value
    return str(value)


def _extract_text(payload: dict[str, Any], part: Any) -> str | None:
    if isinstance(part, dict) and part.get("type") in {"text", "reasoning"}:
        text = part.get("text")
        if isinstance(text, str) and text.strip():
            return text

    error = payload.get("error")
    if isinstance(error, dict):
        data = error.get("data")
        if isinstance(data, dict):
            message = data.get("message")
            if isinstance(message, str) and message.strip():
                return message
        name = error.get("name")
        if isinstance(name, str) and name.strip():
            return name

    return None


def _extract_command(part: Any) -> str | None:
    if not isinstance(part, dict):
        return None
    state = part.get("state")
    if not isinstance(state, dict):
        return None
    input_payload = state.get("input")
    if not isinstance(input_payload, dict):
        return None
    command = input_payload.get("command")
    if isinstance(command, str) and command.strip():
        return command
    return None


def _extract_output(payload: dict[str, Any], part: Any) -> str | None:
    if payload.get("type") == "error":
        return _extract_text(payload, part)

    if not isinstance(part, dict):
        return None
    state = part.get("state")
    if not isinstance(state, dict):
        return None

    for key in ("output", "error"):
        value = state.get(key)
        if isinstance(value, str) and value.strip():
            return value
    return None


def _extract_tool_name(part: Any) -> str | None:
    if not isinstance(part, dict):
        return None
    tool = part.get("tool")
    if isinstance(tool, str) and tool.strip():
        return tool
    return None


def _extract_file_changes(tool_name: str | None, part: Any) -> list[str]:
    if not _tool_likely_mutates_files(tool_name):
        return []
    if not isinstance(part, dict):
        return []
    state = part.get("state")
    if not isinstance(state, dict):
        return []

    input_payload = state.get("input")
    if not isinstance(input_payload, dict):
        return []

    changed: list[str] = []
    for key in (
        "filePath",
        "path",
        "newPath",
        "oldPath",
        "targetPath",
        "sourcePath",
    ):
        value = input_payload.get(key)
        if isinstance(value, str) and value.strip() and value not in changed:
            changed.append(value)
    return changed


def _tool_likely_mutates_files(tool_name: str | None) -> bool:
    if not tool_name:
        return False
    normalized = tool_name.strip().lower()
    return any(token in normalized for token in ("edit", "write", "create", "delete", "move", "rename"))
