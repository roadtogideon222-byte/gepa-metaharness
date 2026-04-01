from __future__ import annotations

import subprocess
import sys
import unittest
from pathlib import Path

from benchcli.cli import compute_status


class BenchCliTests(unittest.TestCase):
    def test_compute_status(self) -> None:
        self.assertEqual("ready:3", compute_status({"name": "ready", "values": [1, 1, 1]}))

    def test_module_cli(self) -> None:
        root = Path(__file__).resolve().parents[1]
        completed = subprocess.run(
            [
                sys.executable,
                "-m",
                "benchcli.cli",
                "status",
                "--config",
                str(root / "fixture_config.json"),
            ],
            text=True,
            capture_output=True,
            check=False,
        )
        self.assertEqual(0, completed.returncode, completed.stderr)
        self.assertEqual("ready:3", completed.stdout.strip())


if __name__ == "__main__":
    unittest.main()
