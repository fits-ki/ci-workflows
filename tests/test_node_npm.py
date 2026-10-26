"""Contract tests for .github/workflows/node-npm.yml.

Text-level checks (pinned actions, persist-credentials, npm ci, env-passed
script, no secret inheritance or deploy steps) plus subprocess tests that
execute the literal `run:` block of the Verify step with CHECK_SCRIPT set,
covering rejected script names so a weak check cannot go falsely green.
Only the Python standard library and a POSIX shell are used.
"""
import os
import re
import subprocess
import textwrap
import unittest

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
WORKFLOW = os.path.join(REPO, ".github", "workflows", "node-npm.yml")

with open(WORKFLOW, "r", encoding="utf-8") as fh:
    TEXT = fh.read()

SHA_PIN = re.compile(r"uses: [A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+@[0-9a-f]{40}")


def verify_run_block():
    """Return the literal shell of the Verify step's `run:` block."""
    match = re.search(
        r"CHECK_SCRIPT: \$\{\{ inputs\.check-script \}\}\n"
        r"[ \t]+run: \|\n((?:[ \t]+\S[^\n]*\n?)+)",
        TEXT)
    assert match, "Verify step with CHECK_SCRIPT env and run: | block not found"
    return textwrap.dedent(match.group(1))


RUN_BLOCK = verify_run_block()


def run_block(check_script):
    env = dict(os.environ)
    env["CHECK_SCRIPT"] = check_script
    # Replace the real npm invocation; only the name validation is under test.
    script = RUN_BLOCK.replace('npm run "$CHECK_SCRIPT"',
                               'echo "WOULD RUN: $CHECK_SCRIPT"')
    return subprocess.run(["sh", "-c", script],
                          capture_output=True, text=True, env=env, timeout=10)


class TestTextContract(unittest.TestCase):
    def test_actions_sha_pinned(self):
        uses = re.findall(r"uses: (\S+)", TEXT)
        self.assertTrue(uses, "no actions used")
        for use in uses:
            self.assertRegex(use + " ",
                             r"^[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+@[0-9a-f]{40} ",
                             use)

    def test_persist_credentials_false(self):
        self.assertIn("persist-credentials: false", TEXT)

    def test_npm_ci_no_audit(self):
        self.assertIn("npm ci --no-audit --no-fund", TEXT)

    def test_script_passed_via_env_not_interpolated(self):
        self.assertIn("CHECK_SCRIPT: ${{ inputs.check-script }}", TEXT)
        self.assertNotIn('npm run "${{ inputs.check-script }}"', TEXT)
        # no user-controlled expression directly inside run blocks
        run_blocks = re.findall(r"run: \|\n((?:[ \t]+\S[^\n]*\n?)+)", TEXT)
        for block in run_blocks:
            self.assertNotIn("${{ inputs.", block)

    def test_no_secret_inheritance_or_deploy(self):
        self.assertNotIn("secrets: inherit", TEXT)
        self.assertNotIn("secrets:", TEXT)
        lowered = TEXT.lower()
        self.assertNotIn("deploy", lowered)
        self.assertIn("contents: read", TEXT)


class TestScriptNameValidation(unittest.TestCase):
    def test_valid_names_accepted(self):
        for name in ("verify", "verify:ci", "test-unit", "build_all", "V2"):
            p = run_block(name)
            self.assertEqual(p.returncode, 0, name + ": " + p.stderr)
            self.assertIn("WOULD RUN: " + name, p.stdout)

    def test_empty_name_rejected(self):
        self.assertEqual(run_block("").returncode, 1)

    def test_leading_dash_rejected(self):
        for name in ("--if-present", "-w", "--"):
            p = run_block(name)
            self.assertEqual(p.returncode, 1, name)
            self.assertNotIn("WOULD RUN", p.stdout)

    def test_illegal_characters_rejected(self):
        for name in ("verify;rm -rf /", "a b", "$(id)", "a`b`", "a|b",
                     "a&b", "a>b", "a'b", 'a"b', "a$b", "a/b", "a*b"):
            p = run_block(name)
            self.assertEqual(p.returncode, 1, name)
            self.assertNotIn("WOULD RUN", p.stdout)


if __name__ == "__main__":
    unittest.main()
