import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from metaharness.integrations.coding_tool.config import load_coding_tool_project
from metaharness.integrations.coding_tool.runtime import _resolve_command_shell, make_backend


class CodingToolConfigTests(unittest.TestCase):
    def test_make_backend_applies_codex_backend_config(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            (root / "baseline").mkdir()
            (root / "tasks.json").write_text("[]", encoding="utf-8")
            (root / "metaharness.json").write_text(
                """
                {
                  "objective": "demo",
                  "constraints": [],
                  "required_files": [],
                  "backends": {
                    "codex": {
                      "use_oss": true,
                      "local_provider": "ollama",
                      "model": "gpt-oss:20b",
                      "approval_policy": "never",
                      "sandbox_mode": "workspace-write"
                    }
                  }
                }
                """.strip(),
                encoding="utf-8",
            )

            project = load_coding_tool_project(root)
            backend = make_backend("codex", project)

            self.assertTrue(backend.use_oss)
            self.assertEqual("ollama", backend.local_provider)
            self.assertEqual("gpt-oss:20b", backend.model)
            self.assertIsNone(backend.timeout_seconds)
            self.assertEqual([], project.allowed_write_paths)

    def test_make_backend_can_override_local_codex_config_to_hosted(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            (root / "baseline").mkdir()
            (root / "tasks.json").write_text("[]", encoding="utf-8")
            (root / "metaharness.json").write_text(
                """
                {
                  "objective": "demo",
                  "constraints": [],
                  "required_files": [],
                  "backends": {
                    "codex": {
                      "use_oss": true,
                      "local_provider": "ollama",
                      "model": "gpt-oss:20b",
                      "approval_policy": "never",
                      "sandbox_mode": "workspace-write"
                    }
                  }
                }
                """.strip(),
                encoding="utf-8",
            )

            project = load_coding_tool_project(root)
            backend = make_backend(
                "codex",
                project,
                overrides={"use_oss": False, "local_provider": "", "model": ""},
            )

            self.assertFalse(backend.use_oss)
            self.assertIsNone(backend.local_provider)
            self.assertIsNone(backend.model)

    def test_load_project_reads_allowed_write_paths(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            (root / "baseline").mkdir()
            (root / "tasks.json").write_text("[]", encoding="utf-8")
            (root / "metaharness.json").write_text(
                """
                {
                  "objective": "demo",
                  "constraints": [],
                  "required_files": [],
                  "allowed_write_paths": ["AGENTS.md", "scripts"],
                  "backends": {}
                }
                """.strip(),
                encoding="utf-8",
            )

            project = load_coding_tool_project(root)
            self.assertEqual(["AGENTS.md", "scripts"], project.allowed_write_paths)

    def test_make_backend_applies_gemini_backend_config(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            (root / "baseline").mkdir()
            (root / "tasks.json").write_text("[]", encoding="utf-8")
            (root / "metaharness.json").write_text(
                """
                {
                  "objective": "demo",
                  "constraints": [],
                  "required_files": [],
                  "backends": {
                    "gemini": {
                      "gemini_binary": "gemini",
                      "model": "gemini-2.5-pro",
                      "output_format": "stream-json",
                      "approval_mode": "default",
                      "sandbox": "workspace-write",
                      "proposal_timeout_seconds": 45
                    }
                  }
                }
                """.strip(),
                encoding="utf-8",
            )

            project = load_coding_tool_project(root)
            backend = make_backend("gemini", project)

            self.assertEqual("gemini", backend.gemini_binary)
            self.assertEqual("gemini-2.5-pro", backend.model)
            self.assertEqual("stream-json", backend.output_format)
            self.assertEqual("default", backend.approval_mode)
            self.assertEqual("workspace-write", backend.sandbox)
            self.assertEqual(45.0, backend.timeout_seconds)

    def test_make_backend_applies_pi_backend_config(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            (root / "baseline").mkdir()
            (root / "tasks.json").write_text("[]", encoding="utf-8")
            (root / "metaharness.json").write_text(
                """
                {
                  "objective": "demo",
                  "constraints": [],
                  "required_files": [],
                  "backends": {
                    "pi": {
                      "pi_binary": "pi",
                      "model": "anthropic/claude-sonnet-4-5",
                      "mode": "json",
                      "no_session": true,
                      "proposal_timeout_seconds": 60
                    }
                  }
                }
                """.strip(),
                encoding="utf-8",
            )

            project = load_coding_tool_project(root)
            backend = make_backend("pi", project)

            self.assertEqual("pi", backend.pi_binary)
            self.assertEqual("anthropic/claude-sonnet-4-5", backend.model)
            self.assertEqual("json", backend.mode)
            self.assertTrue(backend.no_session)
            self.assertEqual(60.0, backend.timeout_seconds)

    def test_make_backend_applies_opencode_backend_config(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            (root / "baseline").mkdir()
            (root / "tasks.json").write_text("[]", encoding="utf-8")
            (root / "metaharness.json").write_text(
                """
                {
                  "objective": "demo",
                  "constraints": [],
                  "required_files": [],
                  "backends": {
                    "opencode": {
                      "opencode_binary": "opencode",
                      "model": "openai/gpt-5",
                      "agent": "build",
                      "variant": "high",
                      "output_format": "json",
                      "proposal_timeout_seconds": 75
                    }
                  }
                }
                """.strip(),
                encoding="utf-8",
            )

            project = load_coding_tool_project(root)
            backend = make_backend("opencode", project)

            self.assertEqual("opencode", backend.opencode_binary)
            self.assertEqual("openai/gpt-5", backend.model)
            self.assertEqual("build", backend.agent)
            self.assertEqual("high", backend.variant)
            self.assertEqual("json", backend.output_format)
            self.assertEqual(75.0, backend.timeout_seconds)

    def test_resolve_command_shell_falls_back_when_zsh_is_unavailable(self) -> None:
        with patch.dict("os.environ", {}, clear=True):
            with patch("shutil.which") as which:
                which.side_effect = lambda name: {
                    "bash": "/usr/bin/bash",
                    "zsh": None,
                    "sh": "/usr/bin/sh",
                }.get(name)
                self.assertEqual("/usr/bin/bash", _resolve_command_shell())


if __name__ == "__main__":
    unittest.main()
