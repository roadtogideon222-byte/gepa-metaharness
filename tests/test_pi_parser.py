import json
import tempfile
import unittest
from pathlib import Path

from metaharness.proposer.parsers.pi import parse_pi_jsonl


class PiParserTests(unittest.TestCase):
    def test_parse_pi_jsonl_extracts_text_commands_and_files(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "stdout.jsonl"
            lines = [
                {
                    "type": "session",
                    "version": 3,
                    "id": "session-1",
                    "timestamp": "2026-04-02T00:00:00Z",
                    "cwd": "/tmp/demo",
                },
                {
                    "type": "message_update",
                    "timestamp": "2026-04-02T00:00:01Z",
                    "assistantMessageEvent": {"type": "text_delta", "delta": "Planning"},
                },
                {
                    "type": "tool_execution_start",
                    "timestamp": "2026-04-02T00:00:02Z",
                    "toolCallId": "tool-1",
                    "toolName": "write",
                    "args": {"filePath": "scripts/validate.sh"},
                },
                {
                    "type": "tool_execution_end",
                    "timestamp": "2026-04-02T00:00:03Z",
                    "toolCallId": "tool-1",
                    "toolName": "bash",
                    "result": {"stdout": "ok", "command": "bash scripts/validate.sh"},
                    "isError": False,
                },
                {
                    "type": "message_end",
                    "timestamp": "2026-04-02T00:00:04Z",
                    "message": {
                        "role": "assistant",
                        "content": [{"type": "text", "text": "Updated the harness."}],
                    },
                },
            ]
            path.write_text("\n".join(json.dumps(line) for line in lines), encoding="utf-8")

            events, final_text, changed_files = parse_pi_jsonl(path)

            self.assertEqual(5, len(events))
            self.assertEqual("Updated the harness.", final_text)
            self.assertEqual(["scripts/validate.sh"], changed_files)
            self.assertEqual("write", events[2].tool_name)
            self.assertEqual("ok", events[3].output)


if __name__ == "__main__":
    unittest.main()
