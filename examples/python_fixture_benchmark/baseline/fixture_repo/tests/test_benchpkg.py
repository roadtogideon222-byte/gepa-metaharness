import unittest

from benchpkg import add, normalize_title


class BenchPkgTests(unittest.TestCase):
    def test_add(self) -> None:
        self.assertEqual(5, add(2, 3))

    def test_normalize_title(self) -> None:
        self.assertEqual("Meta Harness", normalize_title("meta harness"))


if __name__ == "__main__":
    unittest.main()
