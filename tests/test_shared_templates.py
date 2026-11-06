"""Text contracts for the shared quick, full, and release workflows.

Stdlib only. These checks lock the public, secret-free shape of the
templates. They do not call GitHub.
"""
import os
import re
import unittest

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
WORKFLOWS = os.path.join(REPO, ".github", "workflows")
SHA_PIN = re.compile(r"^[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+@[0-9a-f]{40}$")
TEMPLATES = ("quick-check.yml", "full-check.yml", "release-desktop.yml")


def read(name):
    with open(os.path.join(WORKFLOWS, name), "r", encoding="utf-8") as fh:
        return fh.read()


class TestSharedTemplates(unittest.TestCase):
    def test_templates_are_workflow_call_only(self):
        for name in TEMPLATES:
            text = read(name)
            self.assertIn("workflow_call:", text, name)
            self.assertNotIn("pull_request:", text, name)
            self.assertNotIn("\n  push:", text, name)
            self.assertNotRegex(text, r"^\s*secrets:", name)
            self.assertNotIn("srv-development", text, name)
            self.assertIn("persist-credentials: false", text, name)

    def test_actions_are_sha_pinned(self):
        for name in TEMPLATES + ("actionlint.yml",):
            uses = re.findall(r"uses: (\S+)", read(name))
            self.assertTrue(uses, name)
            for use in uses:
                self.assertRegex(use, SHA_PIN, name + ": " + use)

    def test_quick_check_runner_and_skipped_commands(self):
        text = read("quick-check.yml")
        self.assertIn("fromJSON(inputs.runner)", text)
        self.assertIn("default: '\"ubuntu-latest\"'", text)
        self.assertIn("default: 15", text)
        for cmd in ("install-cmd", "lint-cmd", "typecheck-cmd", "test-cmd"):
            self.assertIn("inputs." + cmd + " != ''", text)
        self.assertIn("cache: npm", text)
        self.assertIn("cache: gradle", text)
        self.assertIn("extensions: sqlite3, pdo_sqlite", text)

    def test_full_check_is_ubuntu_and_has_build_and_e2e(self):
        text = read("full-check.yml")
        self.assertIn("runs-on: ubuntu-latest", text)
        self.assertNotIn("inputs.runner", text)
        self.assertIn("default: 30", text)
        self.assertIn("inputs.build-cmd != ''", text)
        self.assertIn("inputs.e2e-cmd != ''", text)

    def test_release_desktop_uploads_dist(self):
        text = read("release-desktop.yml")
        self.assertIn("fromJSON(inputs.build-matrix)", text)
        self.assertIn("default: 75", text)
        self.assertIn("actions/upload-artifact@", text)
        self.assertIn("path: dist/", text)
        self.assertIn("if-no-files-found: error", text)
        self.assertIn("shell: bash", text)

    def test_actionlint_self_check(self):
        text = read("actionlint.yml")
        self.assertIn("timeout-minutes: 5", text)
        self.assertIn("cancel-in-progress: true", text)
        self.assertIn("github.event.pull_request.draft == false", text)
        self.assertIn("ACTIONLINT_VERSION: \"1.7.12\"", text)

    def test_readme_pins_by_sha_placeholder(self):
        with open(os.path.join(REPO, "README.md"), "r", encoding="utf-8") as fh:
            readme = fh.read()
        self.assertIn(
            "uses: fits-ki/ci-workflows/.github/workflows/quick-check.yml@<SHA>",
            readme)
        self.assertIn(
            "uses: fits-ki/ci-workflows/.github/workflows/full-check.yml@<SHA>",
            readme)
        self.assertIn(
            "uses: fits-ki/ci-workflows/.github/workflows/release-desktop.yml@<SHA>",
            readme)
        self.assertNotIn("srv-development", readme)
        self.assertIn("secrets: inherit", readme)
