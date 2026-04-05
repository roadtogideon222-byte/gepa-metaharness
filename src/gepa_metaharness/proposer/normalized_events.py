from __future__ import annotations

from ..models import AgentEvent


def collect_changed_files(events: list[AgentEvent]) -> list[str]:
    changed: list[str] = []
    for event in events:
        for path in event.file_changes:
            if path not in changed:
                changed.append(path)
    return changed


def last_text_message(events: list[AgentEvent]) -> str:
    for event in reversed(events):
        if event.text:
            return event.text
    return ""
