import json
import tempfile
import unittest
from pathlib import Path

from metaharness.proposer.parsers.gemini import parse_gemini_json


class GeminiParserTests(unittest.TestCase):
    def test_parse_stream_json_output(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "stdout.jsonl"
            lines = [
                {
                    "type": "init",
                    "timestamp": "2026-04-02T00:00:00Z",
                    "session_id": "session-1",
                    "model": "gemini-2.5-pro",
                },
                {
                    "type": "message",
                    "timestamp": "2026-04-02T00:00:01Z",
                    "role": "assistant",
                    "content": "Planning changes",
                    "delta": True,
                },
                {
                    "type": "tool_use",
                    "timestamp": "2026-04-02T00:00:02Z",
                    "tool_name": "write_file",
                    "tool_id": "tool-1",
                    "parameters": {"file_path": "scripts/test.sh"},
                },
                {
                    "type": "tool_result",
                    "timestamp": "2026-04-02T00:00:03Z",
                    "tool_id": "tool-1",
                    "status": "success",
                    "output": "updated scripts/test.sh",
                },
                {
                    "type": "message",
                    "timestamp": "2026-04-02T00:00:04Z",
                    "role": "assistant",
                    "content": "Updated the harness.",
                },
                {
                    "type": "result",
                    "timestamp": "2026-04-02T00:00:05Z",
                    "status": "success",
                },
            ]
            path.write_text("\n".join(json.dumps(line) for line in lines), encoding="utf-8")

            events, final_text, changed_files = parse_gemini_json(path)

            self.assertEqual(6, len(events))
            self.assertEqual("Updated the harness.", final_text)
            self.assertEqual(["scripts/test.sh"], changed_files)
            self.assertEqual("write_file", events[2].tool_name)
            self.assertEqual("updated scripts/test.sh", events[3].output)

    def test_parse_json_output_object(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "stdout.json"
            payload = {
                "response": "Final answer text",
                "stats": {"total_tokens": 42},
            }
            path.write_text(json.dumps(payload), encoding="utf-8")

            events, final_text, changed_files = parse_gemini_json(path)

            self.assertEqual(1, len(events))
            self.assertEqual("unknown", events[0].kind)
            self.assertEqual("Final answer text", final_text)
            self.assertEqual([], changed_files)


if __name__ == "__main__":
    unittest.main()
