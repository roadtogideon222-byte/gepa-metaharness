from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any


def compute_status(payload: dict[str, Any]) -> str:
    name = str(payload.get("name", "fixture"))
    raw_values = payload.get("values", [])
    if not isinstance(raw_values, list):
        raise ValueError("values must be a list")
    total = sum(int(value) for value in raw_values)
    return f"{name}:{total}"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="benchcli")
    subparsers = parser.add_subparsers(dest="command", required=True)

    status_parser = subparsers.add_parser("status")
    status_parser.add_argument("--config", required=True)

    args = parser.parse_args(argv)
    if args.command != "status":
        raise ValueError(f"unsupported command: {args.command}")

    payload = json.loads(Path(args.config).read_text(encoding="utf-8"))
    print(compute_status(payload))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
