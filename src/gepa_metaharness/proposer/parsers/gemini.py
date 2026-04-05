from __future__ import annotations

import json
from collections.abc import Iterable
from pathlib import Path
from typing import Any

from ...models import AgentEvent
from ..normalized_events import collect_changed_files, last_text_message


def parse_gemini_json(path: Path) -> tuple[list[AgentEvent], str, list[str]]:
    events: list[AgentEvent] = []
    if not path.exists():
        return events, "", []

    payloads = _load_payloads(path)
    for payload in payloads:
        event = _parse_payload(payload)
        if event is not None:
            events.append(event)
    return events, last_text_message(events), collect_changed_files(events)


def _load_payloads(path: Path) -> list[dict[str, Any]]:
    text = path.read_text(encoding="utf-8").strip()
    if not text:
        return []

    payloads: list[dict[str, Any]] = []
    for raw_line in text.splitlines():
        line = raw_line.strip()
        if not line:
            continue
        try:
            payload = json.loads(line)
        except json.JSONDecodeError:
            continue
        if isinstance(payload, dict):
            payloads.append(payload)

    if payloads:
        return payloads

    try:
        payload = json.loads(text)
    except json.JSONDecodeError:
        return []
    if not isinstance(payload, dict):
        return []
    return [payload]


def _parse_payload(payload: dict[str, Any]) -> AgentEvent | None:
    kind = str(payload.get("type", "unknown"))
    text = _extract_text(payload)
    command = _extract_command(payload)
    output = _extract_output(payload)
    tool_name = _extract_tool_name(payload)
    file_changes = _extract_file_changes(payload, tool_name)
    return AgentEvent(
        ts=_as_str(payload.get("timestamp")),
        kind=kind,
        text=text,
        command=command,
        output=output,
        file_changes=file_changes,
        tool_name=tool_name,
        raw=payload,
    )


def _extract_text(payload: dict[str, Any]) -> str | None:
    for key in ("content", "text", "message", "response", "value"):
        value = payload.get(key)
        if isinstance(value, str) and value.strip():
            return value
    response = payload.get("response")
    if isinstance(response, dict):
        nested = response.get("content") or response.get("text")
        if isinstance(nested, str) and nested.strip():
            return nested
    return None


def _extract_command(payload: dict[str, Any]) -> str | None:
    command = payload.get("command")
    if isinstance(command, str) and command.strip():
        return command

    parameters = payload.get("parameters")
    if isinstance(parameters, dict):
        nested = parameters.get("command")
        if isinstance(nested, str) and nested.strip():
            return nested
    return None


def _extract_output(payload: dict[str, Any]) -> str | None:
    output = payload.get("output")
    if isinstance(output, str) and output.strip():
        return output
    error = payload.get("error")
    if isinstance(error, dict):
        message = error.get("message")
        if isinstance(message, str) and message.strip():
            return message
    return None


def _extract_tool_name(payload: dict[str, Any]) -> str | None:
    for key in ("tool_name", "toolName", "tool"):
        value = payload.get(key)
        if isinstance(value, str) and value.strip():
            return value
    return None


def _extract_file_changes(payload: dict[str, Any], tool_name: str | None) -> list[str]:
    changed: list[str] = []
    for item in payload.get("fileChanges", []) or []:
        if isinstance(item, str) and item not in changed:
            changed.append(item)
        elif isinstance(item, dict):
            for key in ("path", "file_path", "target_path", "new_path", "old_path"):
                value = item.get(key)
                if isinstance(value, str) and value not in changed:
                    changed.append(value)

    parameters = payload.get("parameters")
    if isinstance(parameters, dict) and _tool_likely_mutates_files(tool_name):
        for candidate in _iter_candidate_paths(parameters):
            if candidate not in changed:
                changed.append(candidate)
    return changed


def _iter_candidate_paths(payload: dict[str, Any]) -> Iterable[str]:
    for key in (
        "file_path",
        "path",
        "target_path",
        "new_path",
        "old_path",
        "destination_path",
        "source_path",
    ):
        value = payload.get(key)
        if isinstance(value, str) and value.strip():
            yield value


def _tool_likely_mutates_files(tool_name: str | None) -> bool:
    if not tool_name:
        return False
    normalized = tool_name.strip().lower()
    return any(token in normalized for token in ("write", "edit", "replace", "delete", "move", "rename", "create"))


def _as_str(value: Any) -> str | None:
    return value if isinstance(value, str) else None
