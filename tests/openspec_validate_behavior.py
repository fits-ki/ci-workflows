"""Fail-closed proof for the openspec-validate gate (CIW-7).

Creates a temporary broken OpenSpec tree and asserts that
`openspec validate --all --strict` exits non-zero. Used both locally
and in CI so the gate cannot become an unconditional success.
"""
from __future__ import annotations

import os
import shutil
import subprocess
import tempfile


def main() -> None:
    root = tempfile.mkdtemp(prefix="ciw-7-openspec-")
    try:
        os.makedirs(os.path.join(root, "openspec", "specs", "broken"))
        os.makedirs(os.path.join(root, "openspec", "changes", "archive"))
        with open(os.path.join(root, "openspec", "config.yaml"), "w", encoding="utf-8") as fh:
            fh.write("schema: spec-driven\n")
        with open(
            os.path.join(root, "openspec", "specs", "broken", "spec.md"),
            "w",
            encoding="utf-8",
        ) as fh:
            fh.write("# broken\n\nnot a spec\n")
        proc = subprocess.run(
            ["openspec", "validate", "--all", "--strict", "--no-interactive"],
            cwd=root,
            capture_output=True,
            text=True,
            timeout=60,
        )
        if proc.returncode == 0:
            raise SystemExit(
                "openspec validate succeeded on a broken tree; gate would be unconditional success\n"
                + proc.stdout
                + proc.stderr
            )
        combined = f"{proc.stdout}\n{proc.stderr}"
        if "Purpose" not in combined and "purpose" not in combined.lower() and "invalid" not in combined.lower() and "error" not in combined.lower():
            # Still ok as long as non-zero; print output for debugging
            print(combined)
        print("ok: invalid OpenSpec fails closed")
    finally:
        shutil.rmtree(root, ignore_errors=True)


if __name__ == "__main__":
    main()
