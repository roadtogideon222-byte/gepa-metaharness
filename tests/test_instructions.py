import unittest

from metaharness.models import AgentInstructions
from metaharness.proposer.instructions import render_backend_instructions


class InstructionRenderingTests(unittest.TestCase):
    def test_render_codex_instructions_contains_objective(self) -> None:
        text = render_backend_instructions(
            "codex",
            AgentInstructions(
                objective="Improve latency.",
                constraints=["Keep tests passing."],
                workspace_layout="workspace/ holds the harness.",
                allowed_actions=["Edit Python files."],
                forbidden_actions=["Do not touch external artifacts."],
                evaluation_contract="External evaluator decides success.",
            ),
        )
        self.assertIn("Improve latency.", text)
        self.assertIn("Keep tests passing.", text)
        self.assertIn("External evaluator decides success.", text)


if __name__ == "__main__":
    unittest.main()
