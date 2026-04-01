from __future__ import annotations


LABELS = {"billing", "bug", "feature", "security"}


def route_ticket(text: str) -> str:
    lower = text.lower()

    if "crash" in lower or "error" in lower or "spins forever" in lower:
        return "bug"

    if "feature" in lower or "add " in lower or "would help" in lower:
        return "feature"

    if "security" in lower or "vulnerability" in lower:
        return "security"

    if "invoice" in lower or "refund" in lower or "charged" in lower:
        return "billing"

    return "bug"


def validate_label(label: str) -> str:
    if label not in LABELS:
        raise ValueError(f"unexpected label: {label}")
    return label
