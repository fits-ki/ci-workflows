"""Tests for the merge-gate.yml inline Python run block.

The exact code between the BEGIN/END MERGE GATE markers in
.github/workflows/merge-gate.yml is extracted and executed in a
subprocess; this file never duplicates the gate logic itself.
Only the Python standard library is used; no GitHub or network access.
"""
import json
import os
import re
import subprocess
import sys
import textwrap
import unittest

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
WORKFLOW = os.path.join(REPO, ".github", "workflows", "merge-gate.yml")


def extract_gate_code():
    with open(WORKFLOW, "r", encoding="utf-8") as fh:
        text = fh.read()
    match = re.search(
        r"^[ \t]*# BEGIN MERGE GATE\n(.*?)^[ \t]*# END MERGE GATE\n",
        text, re.DOTALL | re.MULTILINE)
    assert match, "merge-gate.yml must contain BEGIN/END MERGE GATE markers"
    return textwrap.dedent(match.group(1))


GATE_CODE = extract_gate_code()


def gate(results=None, required=None, conditional=None, env_extra=None):
    env = dict(os.environ)
    for key in ("RESULTS_JSON", "REQUIRED_JOBS_JSON", "CONDITIONAL_JOBS_JSON"):
        env.pop(key, None)
    if results is not None:
        env["RESULTS_JSON"] = results if isinstance(results, str) else json.dumps(results)
    if required is not None:
        env["REQUIRED_JOBS_JSON"] = required if isinstance(required, str) else json.dumps(required)
    if conditional is not None:
        env["CONDITIONAL_JOBS_JSON"] = conditional if isinstance(conditional, str) else json.dumps(conditional)
    if env_extra:
        env.update(env_extra)
    return subprocess.run(
        [sys.executable, "-c", GATE_CODE],
        capture_output=True, text=True, env=env, timeout=30)


def jobs(spec):
    return {name: {"result": result} for name, result in spec.items()}


class TestMergeGate(unittest.TestCase):
    def test_required_success(self):
        p = gate(jobs({"build": "success"}), ["build"], "{}")
        self.assertEqual(p.returncode, 0, p.stdout + p.stderr)
        self.assertIn("every declared job", p.stdout)

    def test_multiple_required_and_conditional_mix(self):
        results = jobs({"a": "success", "b": "success", "c": "skipped"})
        p = gate(results, ["a", "b"], {"c": "false"})
        self.assertEqual(p.returncode, 0, p.stdout + p.stderr)

    def test_failed_job_rejected(self):
        p = gate(jobs({"build": "failure"}), ["build"], "{}")
        self.assertEqual(p.returncode, 1)

    def test_cancelled_job_rejected(self):
        p = gate(jobs({"build": "cancelled"}), ["build"], "{}")
        self.assertEqual(p.returncode, 1)

    def test_unexpectedly_skipped_required_rejected(self):
        p = gate(jobs({"build": "skipped"}), ["build"], "{}")
        self.assertEqual(p.returncode, 1)

    def test_missing_job_result_rejected(self):
        p = gate(jobs({"build": "success"}), ["build", "test"], "{}")
        self.assertEqual(p.returncode, 1)

    def test_unlisted_extra_result_rejected(self):
        results = jobs({"build": "success", "extra": "success"})
        p = gate(results, ["build"], "{}")
        self.assertEqual(p.returncode, 1)

    def test_conditional_true_requires_success(self):
        p = gate(jobs({"web": "success"}), [], None)  # empty required is invalid anyway
        self.assertNotEqual(p.returncode, 0)
        ok = gate(jobs({"web": "success", "ci": "success"}),
                  ["ci"], {"web": "true"})
        self.assertEqual(ok.returncode, 0, ok.stdout + ok.stderr)
        bad = gate(jobs({"web": "skipped", "ci": "success"}),
                   ["ci"], {"web": "true"})
        self.assertEqual(bad.returncode, 1)

    def test_conditional_false_requires_skipped(self):
        ok = gate(jobs({"ci": "success", "web": "skipped"}),
                  ["ci"], {"web": "false"})
        self.assertEqual(ok.returncode, 0, ok.stdout + ok.stderr)
        bad = gate(jobs({"ci": "success", "web": "success"}),
                   ["ci"], {"web": "false"})
        self.assertEqual(bad.returncode, 1)

    def test_missing_env_vars_rejected(self):
        self.assertEqual(gate(None, ["a"], "{}").returncode, 1)
        self.assertEqual(gate(jobs({"a": "success"}), None, "{}").returncode, 1)
        self.assertEqual(gate(jobs({"a": "success"}), ["a"], None).returncode, 1)

    def test_invalid_conditional_selection_rejected(self):
        for sel in ("yes", "TRUE", "1", ""):
            p = gate(jobs({"ci": "success", "web": "success"}),
                     ["ci"], {"web": sel})
            self.assertEqual(p.returncode, 1, sel)
        p = gate(jobs({"ci": "success", "web": "success"}),
                 ["ci"], {"web": True})
        self.assertEqual(p.returncode, 1)

    def test_duplicate_json_keys_rejected(self):
        raw = '{"a":{"result":"success"},"a":{"result":"success"}}'
        self.assertEqual(gate(raw, ["a"], "{}").returncode, 1)
        raw_req = '["a","a"]'
        self.assertEqual(gate(jobs({"a": "success"}), raw_req, "{}").returncode, 1)

    def test_wrong_and_null_shapes_rejected(self):
        self.assertEqual(gate("null", ["a"], "{}").returncode, 1)
        self.assertEqual(gate("[]", ["a"], "{}").returncode, 1)
        self.assertEqual(gate(jobs({"a": "success"}), "null", "{}").returncode, 1)
        self.assertEqual(gate(jobs({"a": "success"}), "{}", "{}").returncode, 1)
        self.assertEqual(gate(jobs({"a": "success"}), ["a"], "[]").returncode, 1)
        self.assertEqual(gate({"a": None}, ["a"], "{}").returncode, 1)

    def test_empty_and_overlapping_required_rejected(self):
        self.assertEqual(gate("{}", [], "{}").returncode, 1)
        results = jobs({"a": "success", "b": "success"})
        self.assertEqual(gate(results, ["a"], {"a": "true"}).returncode, 1)

    def test_invalid_job_names_rejected(self):
        for name in ("1bad", "a b", "a.b", "", "a/b"):
            self.assertEqual(
                gate(jobs({name: "success", "ok": "success"}),
                     ["ok"], {name: "true"}).returncode, 1, name)

    def test_unknown_result_rejected(self):
        for result in ("neutral", "running", "timed_out", "stale"):
            self.assertEqual(
                gate(jobs({"a": result}), ["a"], "{}").returncode, 1, result)

    def test_invalid_json_rejected(self):
        self.assertEqual(gate("{not json", ["a"], "{}").returncode, 1)


if __name__ == "__main__":
    unittest.main()
