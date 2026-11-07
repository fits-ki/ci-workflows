"""Tests for the workflow-integrity.yml inline Python run block.

The exact code between the BEGIN/END WORKFLOW INTEGRITY markers is
extracted and executed. This file does not duplicate the check.
"""
import os
import re
import subprocess
import sys
import tempfile
import textwrap
import unittest

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
WORKFLOW = os.path.join(REPO, ".github", "workflows", "workflow-integrity.yml")

START = "<!-- agent-infra:shared:start -->"
END = "<!-- agent-infra:shared:end -->"


def extract_code():
    with open(WORKFLOW, "r", encoding="utf-8") as handle:
        text = handle.read()
    match = re.search(
        r"^[ \t]*# BEGIN WORKFLOW INTEGRITY\n(.*?)^[ \t]*# END WORKFLOW INTEGRITY\n",
        text,
        re.DOTALL | re.MULTILINE,
    )
    assert match, "workflow-integrity.yml must contain BEGIN/END markers"
    return textwrap.dedent(match.group(1))


CODE = extract_code()


def valid_tree(root):
    with open(os.path.join(root, "AGENTS.md"), "w", encoding="utf-8") as handle:
        handle.write(
            "intro\n" + START + "\n## Regeln\n" + END + "\n"
        )
    os.makedirs(os.path.join(root, "openspec", "specs"))
    os.makedirs(os.path.join(root, "openspec", "changes", "archive"))
    with open(os.path.join(root, "openspec", "config.yaml"), "w", encoding="utf-8") as handle:
        handle.write("schema: spec-driven\n")


def run_check(root):
    env = dict(os.environ)
    env["INTEGRITY_ROOT"] = root
    return subprocess.run(
        [sys.executable, "-c", CODE],
        capture_output=True,
        text=True,
        env=env,
        timeout=30,
    )


class TestWorkflowIntegrity(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = self.tmp.name
        valid_tree(self.root)

    def tearDown(self):
        self.tmp.cleanup()

    def test_valid_tree_passes_without_legacy_files(self):
        proc = run_check(self.root)
        self.assertEqual(proc.returncode, 0, proc.stdout + proc.stderr)
        self.assertIn("workflow-integrity ok", proc.stdout)
        self.assertFalse(os.path.exists(os.path.join(self.root, "scripts", "ai_workflow.py")))

    def test_legacy_files_do_not_affect_the_result(self):
        os.makedirs(os.path.join(self.root, ".wiki", "90-meta", "agent-workflows"))
        legacy = os.path.join(
            self.root, ".wiki", "90-meta", "agent-workflows", "ai-engineering.json"
        )
        with open(legacy, "w", encoding="utf-8") as handle:
            handle.write("{}\n")
        os.makedirs(os.path.join(self.root, "scripts"))
        with open(os.path.join(self.root, "scripts", "ai_workflow.py"), "w", encoding="utf-8") as handle:
            handle.write("raise SystemExit('must not run')\n")
        proc = run_check(self.root)
        self.assertEqual(proc.returncode, 0, proc.stdout + proc.stderr)

    def test_missing_agents_fails(self):
        os.remove(os.path.join(self.root, "AGENTS.md"))
        proc = run_check(self.root)
        self.assertEqual(proc.returncode, 1)
        self.assertIn("AGENTS.md fehlt", proc.stdout)

    def test_duplicate_shared_block_fails(self):
        path = os.path.join(self.root, "AGENTS.md")
        with open(path, "a", encoding="utf-8") as handle:
            handle.write("\n" + START + "\nzwei\n" + END + "\n")
        proc = run_check(self.root)
        self.assertEqual(proc.returncode, 1)
        self.assertIn("Shared-Block", proc.stdout)

    def test_empty_shared_block_fails(self):
        with open(os.path.join(self.root, "AGENTS.md"), "w", encoding="utf-8") as handle:
            handle.write(START + "\n\n" + END + "\n")
        proc = run_check(self.root)
        self.assertEqual(proc.returncode, 1)

    def test_markers_in_wrong_order_fail(self):
        with open(os.path.join(self.root, "AGENTS.md"), "w", encoding="utf-8") as handle:
            handle.write(END + "\ntext\n" + START + "\n")
        proc = run_check(self.root)
        self.assertEqual(proc.returncode, 1)

    def test_missing_openspec_pieces_fail(self):
        os.remove(os.path.join(self.root, "openspec", "config.yaml"))
        proc = run_check(self.root)
        self.assertEqual(proc.returncode, 1)
        self.assertIn("openspec/config.yaml", proc.stdout)

    def test_empty_config_fails(self):
        with open(os.path.join(self.root, "openspec", "config.yaml"), "w", encoding="utf-8") as handle:
            handle.write("")
        proc = run_check(self.root)
        self.assertEqual(proc.returncode, 1)

    def test_missing_archive_fails(self):
        os.rmdir(os.path.join(self.root, "openspec", "changes", "archive"))
        proc = run_check(self.root)
        self.assertEqual(proc.returncode, 1)
        self.assertIn("openspec/changes/archive/", proc.stdout)

    def test_symlink_agents_fails(self):
        target = os.path.join(self.root, "other.md")
        with open(target, "w", encoding="utf-8") as handle:
            handle.write(START + "\ntext\n" + END + "\n")
        os.remove(os.path.join(self.root, "AGENTS.md"))
        os.symlink(target, os.path.join(self.root, "AGENTS.md"))
        proc = run_check(self.root)
        self.assertEqual(proc.returncode, 1)

    def test_symlink_specs_outside_fails(self):
        specs = os.path.join(self.root, "openspec", "specs")
        os.rmdir(specs)
        os.symlink(tempfile.gettempdir(), specs)
        proc = run_check(self.root)
        self.assertEqual(proc.returncode, 1)
        self.assertIn("openspec/specs/", proc.stdout)

    def test_workflow_does_not_name_legacy_inputs(self):
        with open(WORKFLOW, "r", encoding="utf-8") as handle:
            text = handle.read()
        for banned in (
            "agent_pointer_sha256",
            "ai-engineering.json",
            "ai_workflow.py",
            "Pointer-Block",
        ):
            self.assertNotIn(banned, text)
