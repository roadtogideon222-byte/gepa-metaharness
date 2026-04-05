from __future__ import annotations

import json
from pathlib import Path

from ...models import AgentEvent
from ..normalized_events import collect_changed_files, last_text_message


def parse_codex_jsonl(path: Path) -> tuple[list[AgentEvent], str, list[str]]:
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
        text, command, output, tool_name, file_changes = _parse_payload(kind, payload)

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


def _parse_payload(
    kind: str,
    payload: dict,
) -> tuple[str | None, str | None, str | None, str | None, list[str]]:
    text = None
    command = None
    output = None
    tool_name = None
    file_changes: list[str] = []

    if kind in {"thread.started", "turn.started"}:
        text = kind
    elif kind == "turn.completed":
        usage = payload.get("usage", {})
        if isinstance(usage, dict):
            text = (
                "turn completed "
                f"(input={usage.get('input_tokens', 0)}, "
                f"cached={usage.get('cached_input_tokens', 0)}, "
                f"output={usage.get('output_tokens', 0)})"
            )
    elif kind == "turn.failed":
        error = payload.get("error", {})
        if isinstance(error, dict):
            text = error.get("message")
    elif kind == "error":
        text = payload.get("message")
    elif kind in {"item.completed", "item.updated", "item.started"}:
        item = payload.get("item", {})
        if isinstance(item, dict):
            details = item.get("details", {})
            if isinstance(details, dict):
                detail_type = str(details.get("type", "unknown"))
                if detail_type == "unknown":
                    if "command" in details:
                        detail_type = "command_execution"
                    elif "changes" in details:
                        detail_type = "file_change"
                    elif "tool" in details and "server" in details:
                        detail_type = "mcp_tool_call"
                    elif "items" in details:
                        detail_type = "todo_list"
                    elif "message" in details:
                        detail_type = "error"
                    elif "text" in details:
                        detail_type = "agent_message"
                if detail_type in {"agent_message", "reasoning", "error"}:
                    text = details.get("text") or details.get("message")
                elif detail_type == "command_execution":
                    command = details.get("command")
                    output = details.get("aggregated_output")
                    exit_code = details.get("exit_code")
                    status = details.get("status")
                    text = f"command {status}"
                    if exit_code is not None:
                        text += f" (exit={exit_code})"
                elif detail_type == "file_change":
                    status = details.get("status")
                    text = f"file_change {status}"
                    for change in details.get("changes", []) or []:
                        if isinstance(change, dict) and "path" in change:
                            file_changes.append(str(change["path"]))
                elif detail_type == "mcp_tool_call":
                    tool_name = details.get("tool")
                    server = details.get("server")
                    status = details.get("status")
                    text = f"mcp {server}/{tool_name} {status}"
                    result = details.get("result")
                    error = details.get("error")
                    if isinstance(result, dict):
                        output = json.dumps(result, sort_keys=True)
                    elif isinstance(error, dict):
                        output = error.get("message")
                elif detail_type == "collab_tool_call":
                    tool_name = details.get("tool")
                    text = f"collab {tool_name} {details.get('status')}"
                    prompt = details.get("prompt")
                    if isinstance(prompt, str):
                        output = prompt
                elif detail_type == "web_search":
                    tool_name = "web_search"
                    action = details.get("action")
                    query = details.get("query")
                    text = f"web_search {action}"
                    if isinstance(query, str):
                        output = query
                elif detail_type == "todo_list":
                    items = details.get("items", []) or []
                    if isinstance(items, list):
                        rendered = []
                        for item_payload in items:
                            if not isinstance(item_payload, dict):
                                continue
                            marker = "[x]" if item_payload.get("completed") else "[ ]"
                            rendered.append(f"{marker} {item_payload.get('text', '')}".rstrip())
                        text = "\n".join(rendered)
                else:
                    text = details.get("text")
    elif "text" in payload:
        text = payload.get("text")

    return text, command, output, tool_name, file_changes
