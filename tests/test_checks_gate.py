"""Contract tests for .github/workflows/checks.yml (CIW-7 Kepler Action 6 gate)."""
from __future__ import annotations

import os
import re
import unittest

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
WORKFLOW = os.path.join(REPO, ".github", "workflows", "checks.yml")

with open(WORKFLOW, "r", encoding="utf-8") as fh:
    TEXT = fh.read()


def job_block(name: str) -> str:
    match = re.search(
        rf"^  {re.escape(name)}:\n([\s\S]*?)(?=\n  [A-Za-z0-9_-]+:\n|\Z)",
        TEXT,
        re.MULTILINE,
    )
    assert match, f'job "{name}" fehlt'
    return match.group(1)


def on_block() -> str:
    match = re.search(r"^on:\n([\s\S]*?)^\S", TEXT, re.MULTILINE)
    assert match, "on:-Block fehlt"
    return match.group(1)


class TestChecksGate(unittest.TestCase):
    def test_exact_check_contexts(self):
        for job, context in (("test", "test"), ("openspec-validate", "openspec-validate")):
            block = job_block(job)
            self.assertRegex(block, rf"(?m)^    name: {context}$")
            self.assertNotRegex(block, r"(?m)^    uses:")

    def test_no_push_only_non_draft_pr_to_develop(self):
        on = on_block()
        self.assertRegex(on, r"(?m)^  pull_request:")
        self.assertIn("branches: [develop]", on)
        self.assertIn("ready_for_review", on)
        self.assertNotRegex(on, r"(?m)^  (push|schedule|issues|issue_comment):")
        for job in ("test", "openspec-validate"):
            self.assertIn(
                "if: github.event.pull_request.draft == false",
                job_block(job),
            )

    def test_path_filters_docs_skipped_openspec_reincluded(self):
        on = on_block()
        self.assertIn('- "**"', on)
        self.assertIn('- "!**/*.md"', on)
        self.assertIn('- "!docs/**"', on)
        self.assertIn('- "!.wiki/**"', on)
        self.assertIn('- "!.agents/**"', on)
        self.assertIn('- "openspec/**"', on)
        self.assertNotIn("paths-ignore:", TEXT)

    def test_openspec_validate_is_fail_closed(self):
        block = job_block("openspec-validate")
        self.assertIn("openspec_validate_behavior.py", block)
        self.assertIn("openspec validate --all --strict", block)
        self.assertNotIn("continue-on-error", TEXT)
        self.assertNotRegex(TEXT, r"\|\| true")

    def test_test_job_runs_unittest_suite(self):
        block = job_block("test")
        self.assertIn("python3 -m unittest discover -s tests -v", block)

    def test_concurrency_and_timeouts(self):
        self.assertRegex(TEXT, r"(?m)^concurrency:")
        self.assertIn("cancel-in-progress: true", TEXT)
        for job in ("test", "openspec-validate"):
            block = job_block(job)
            self.assertIn("runs-on: ubuntu-latest", block)
            self.assertRegex(block, r"timeout-minutes: \d+")

    def test_actions_sha_pinned(self):
        uses = re.findall(r"^\s*uses:\s*(\S+)", TEXT, re.MULTILINE)
        bad = [u for u in uses if not re.search(r"@[0-9a-f]{40}$", u)]
        self.assertEqual(bad, [], f"unpinned uses: {bad}")

    def test_skipped_docs_policy_documented(self):
        self.assertIn("Doku", TEXT)
        self.assertIn("skipped", TEXT)
        self.assertIn("Action 6", TEXT)


if __name__ == "__main__":
    unittest.main()
