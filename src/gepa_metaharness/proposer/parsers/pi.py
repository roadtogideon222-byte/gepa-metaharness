from __future__ import annotations

import json
from collections.abc import Iterable
from pathlib import Path
from typing import Any

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
        if not isinstance(payload, dict):
            continue
        kind = str(payload.get("type", "unknown"))
        text = _extract_text(payload)
        command = _extract_command(payload)
        output = _extract_output(payload)
        tool_name = _extract_tool_name(payload)
        file_changes = _extract_file_changes(payload, tool_name)
        events.append(
            AgentEvent(
                ts=payload.get("timestamp"),
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


def _extract_text(payload: dict[str, Any]) -> str | None:
    assistant_event = payload.get("assistantMessageEvent")
    if isinstance(assistant_event, dict):
        for key in ("delta", "text"):
            value = assistant_event.get(key)
            if isinstance(value, str) and value.strip():
                return value

    message = payload.get("message")
    if isinstance(message, dict):
        content = message.get("content")
        rendered = _extract_message_content(content)
        if rendered:
            return rendered

    if "content" in payload and isinstance(payload["content"], str) and payload["content"].strip():
        return payload["content"]
    return None


def _extract_command(payload: dict[str, Any]) -> str | None:
    args = payload.get("args")
    if isinstance(args, dict):
        command = args.get("command")
        if isinstance(command, str) and command.strip():
            return command
    partial = payload.get("partialResult")
    if isinstance(partial, dict):
        command = partial.get("command")
        if isinstance(command, str) and command.strip():
            return command
    return None


def _extract_output(payload: dict[str, Any]) -> str | None:
    for key in ("content",):
        value = payload.get(key)
        if isinstance(value, str) and value.strip():
            return value

    partial = payload.get("partialResult")
    if isinstance(partial, dict):
        for key in ("output", "stdout", "stderr", "message"):
            value = partial.get(key)
            if isinstance(value, str) and value.strip():
                return value

    result = payload.get("result")
    if isinstance(result, dict):
        for key in ("output", "stdout", "stderr", "message"):
            value = result.get(key)
            if isinstance(value, str) and value.strip():
                return value
    return None


def _extract_tool_name(payload: dict[str, Any]) -> str | None:
    for key in ("toolName", "tool_name", "tool"):
        value = payload.get(key)
        if isinstance(value, str) and value.strip():
            return value
    return None


def _extract_file_changes(payload: dict[str, Any], tool_name: str | None) -> list[str]:
    changed: list[str] = []

    for source_key in ("args", "partialResult", "result"):
        source = payload.get(source_key)
        if isinstance(source, dict) and _tool_likely_mutates_files(tool_name):
            for candidate in _iter_candidate_paths(source):
                if candidate not in changed:
                    changed.append(candidate)

    return changed


def _iter_candidate_paths(payload: dict[str, Any]) -> Iterable[str]:
    for key in (
        "filePath",
        "file_path",
        "path",
        "targetPath",
        "target_path",
        "newPath",
        "new_path",
        "oldPath",
        "old_path",
    ):
        value = payload.get(key)
        if isinstance(value, str) and value.strip():
            yield value


def _tool_likely_mutates_files(tool_name: str | None) -> bool:
    if not tool_name:
        return False
    normalized = tool_name.strip().lower()
    return any(token in normalized for token in ("write", "edit", "replace", "delete", "move", "rename", "create"))


def _extract_message_content(content: Any) -> str | None:
    if isinstance(content, str) and content.strip():
        return content
    if not isinstance(content, list):
        return None

    parts: list[str] = []
    for item in content:
        if not isinstance(item, dict):
            continue
        if item.get("type") == "text":
            text = item.get("text")
            if isinstance(text, str) and text.strip():
                parts.append(text)
    if not parts:
        return None
    return "".join(parts)
