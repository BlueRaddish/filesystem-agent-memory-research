"""Check the frozen pilot maintenance replay without rewriting study files.

Run: python scripts/check_maintenance_replay.py --self-check
"""
import argparse
import hashlib
import json
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile


STUDY = Path(__file__).resolve().parents[1] / "evaluation/study-2026-10-09"
NAMES = ("replay_maintenance.py", "secondary-cases.json", "maintenance-results.json")


def verify(study):
    before = {name: (study / name).read_bytes() for name in NAMES}
    try:
        with tempfile.TemporaryDirectory(prefix="maintenance-check-") as temporary:
            root = Path(temporary)
            for name in NAMES[:2]:
                (root / name).write_bytes(before[name])
            process = subprocess.run(
                [sys.executable, "-B", str(root / NAMES[0]), "--self-check"],
                cwd=root, capture_output=True, text=True, timeout=60,
                creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
            )
            if process.returncode:
                raise RuntimeError("isolated replay failed: " + process.stderr)
            generated = (root / NAMES[2]).read_bytes()
            if generated != before[NAMES[2]]:
                raise ValueError("isolated replay differs from frozen expected bytes")
    finally:
        if any((study / name).read_bytes() != payload for name, payload in before.items()):
            raise RuntimeError("original study inputs or expected output changed")
    return {"state": "PASS_ISOLATED_FROZEN_REPLAY", "original_files_unchanged": True,
            "result_sha256": hashlib.sha256(generated).hexdigest(),
            "scope": "Engineered deterministic traces; no model or provider calls."}


def self_check():
    with tempfile.TemporaryDirectory(prefix="maintenance-check-negative-") as temporary:
        root = Path(temporary)
        for name in NAMES:
            shutil.copyfile(STUDY / name, root / name)
        (root / NAMES[2]).write_bytes(b"known wrong output\n")
        try:
            verify(root)
        except ValueError:
            pass
        else:
            raise AssertionError("wrong expected output accepted")
        (root / NAMES[1]).unlink()
        try:
            verify(root)
        except FileNotFoundError:
            pass
        else:
            raise AssertionError("missing fixture accepted")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--self-check", action="store_true")
    args = parser.parse_args()
    result = verify(STUDY)
    if args.self_check:
        self_check()
        result["known_bad_rejections"] = ["wrong_expected_output", "missing_fixture"]
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
