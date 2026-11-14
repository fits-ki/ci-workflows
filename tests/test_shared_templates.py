"""Text contracts for the shared quick, full, and release workflows.

Stdlib only. These checks lock the public, secret-free shape of the
templates. They do not call GitHub.
"""
import os
import re
import unittest

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
WORKFLOWS = os.path.join(REPO, ".github", "workflows")
GENERIC_DEFAULT = "default: '[\"self-hosted\", \"linux\", \"generic\"]'"
SHA_PIN = re.compile(r"^[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+@[0-9a-f]{40}$")
TEMPLATES = (
    "quick-check.yml",
    "full-check.yml",
    "release-desktop.yml",
    "workflow-integrity.yml",
)


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
        self.assertIn(GENERIC_DEFAULT, text)
        self.assertIn("default: 15", text)
        for cmd in ("install-cmd", "lint-cmd", "typecheck-cmd", "test-cmd"):
            self.assertIn("inputs." + cmd + " != ''", text)
        self.assertIn("package-manager", text)
        self.assertIn("cache: gradle", text)
        self.assertIn("extensions: sqlite3, pdo_sqlite", text)

    def test_node_package_manager_input_npm_default_and_pnpm(self):
        for name in ("quick-check.yml", "full-check.yml"):
            text = read(name)
            self.assertIn("package-manager:", text, name)
            self.assertIn('default: "npm"', text, name)
            self.assertIn("cache: ${{ inputs.package-manager }}", text, name)
            self.assertIn("'pnpm-lock.yaml' || 'package-lock.json'", text, name)
            self.assertIn("npm|pnpm) ;;", text, name)
            setup_pnpm = text.index("name: Set up pnpm")
            setup_node = text.index("name: Set up Node")
            self.assertLess(setup_pnpm, setup_node, name)
            self.assertIn("inputs.package-manager == 'pnpm'", text, name)
            self.assertIn("pnpm/action-setup@", text, name)

    def test_full_check_defaults_to_generic_and_has_build_and_e2e(self):
        text = read("full-check.yml")
        self.assertIn("fromJSON(inputs.runner)", text)
        self.assertIn(GENERIC_DEFAULT, text)
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
        self.assertIn(
            "uses: fits-ki/ci-workflows/.github/workflows/workflow-integrity.yml@<SHA>",
            readme)
        self.assertNotIn("srv-development", readme)
        self.assertIn("secrets: inherit", readme)


class TestRunnerInput(unittest.TestCase):
    def test_linux_templates_take_runner_input_defaulting_to_generic(self):
        for name in ("quick-check.yml", "full-check.yml", "merge-gate.yml",
                     "node-npm.yml", "workflow-integrity.yml"):
            with self.subTest(name=name):
                text = read(name)
                self.assertIn("runs-on: ${{ fromJSON(inputs.runner) }}", text)
                self.assertIn(GENERIC_DEFAULT, text)
                self.assertNotIn("runs-on: ubuntu-latest", text)


class TestBareMetalPhp(unittest.TestCase):
    def test_setup_php_only_on_github_hosted_native_php_on_self_hosted(self):
        for name in ("quick-check.yml", "full-check.yml", "node-npm.yml"):
            with self.subTest(name=name):
                text = read(name)
                setup = re.search(r"- name: Set up (?:optional )?PHP\n\s+if: (.+)\n\s+uses: shivammathur/setup-php@", text)
                self.assertIsNotNone(setup, name)
                self.assertIn("runner.environment == 'github-hosted'", setup.group(1))
                native = re.search(r"- name: Use native PHP \(self-hosted\)\n\s+if: (.+)\n", text)
                self.assertIsNotNone(native, name)
                self.assertIn("runner.environment == 'self-hosted'", native.group(1))
                self.assertIn('"/opt/php/${PHP_VERSION}/bin/php" "/usr/bin/php${PHP_VERSION}"', text)
                self.assertNotIn("default: '\"ubuntu-latest\"'", text)
