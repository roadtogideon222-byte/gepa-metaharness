import json
import tempfile
import unittest
from pathlib import Path

from metaharness.proposer.parsers.opencode import parse_opencode_jsonl


class OpenCodeParserTests(unittest.TestCase):
    def test_parse_opencode_jsonl_extracts_text_commands_and_files(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "stdout.jsonl"
            lines = [
                {
                    "type": "step_start",
                    "timestamp": 1,
                    "sessionID": "session-1",
                    "part": {"type": "step-start"},
                },
                {
                    "type": "tool_use",
                    "timestamp": 2,
                    "sessionID": "session-1",
                    "part": {
                        "type": "tool",
                        "tool": "write",
                        "state": {
                            "status": "completed",
                            "input": {"filePath": "scripts/validate.sh"},
                            "output": "wrote file",
                        },
                    },
                },
                {
                    "type": "tool_use",
                    "timestamp": 3,
                    "sessionID": "session-1",
                    "part": {
                        "type": "tool",
                        "tool": "bash",
                        "state": {
                            "status": "completed",
                            "input": {"command": "bash scripts/validate.sh"},
                            "output": "ok",
                        },
                    },
                },
                {
                    "type": "text",
                    "timestamp": 4,
                    "sessionID": "session-1",
                    "part": {"type": "text", "text": "Updated the harness."},
                },
            ]
            path.write_text("\n".join(json.dumps(line) for line in lines), encoding="utf-8")

            events, final_text, changed_files = parse_opencode_jsonl(path)

            self.assertEqual(4, len(events))
            self.assertEqual("Updated the harness.", final_text)
            self.assertEqual(["scripts/validate.sh"], changed_files)
            self.assertEqual("write", events[1].tool_name)
            self.assertEqual("bash scripts/validate.sh", events[2].command)
            self.assertEqual("ok", events[2].output)


if __name__ == "__main__":
    unittest.main()
