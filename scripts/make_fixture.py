"""Stage only the fictional agent-facing files; this does not sandbox an agent."""

import argparse
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
FIXTURE = ROOT / "examples" / "fixture"
AGENT_FILES = (
    "TASKS.md",
    "memory/README.md",
    "memory/state.md",
    "memory/episodes/E001.md",
    "memory/episodes/E002.md",
    "memory/episodes/E003.md",
    "memory/episodes/E004.md",
    "memory/episodes/E005.md",
)


def stage(destination):
    destination = Path(destination).resolve()
    if destination == ROOT or destination.is_relative_to(ROOT):
        raise ValueError("Trial workspace must be outside the original repository")
    if destination.exists() and (not destination.is_dir() or any(destination.iterdir())):
        raise ValueError("Trial destination must be a new or empty directory")
    files = [FIXTURE / relative for relative in AGENT_FILES]
    if any(not path.is_file() or path.is_symlink() for path in files):
        raise ValueError("Allowlisted fixture files must be ordinary files")
    if any(path.is_symlink() for path in FIXTURE.rglob("*")):
        raise ValueError("Fixture must not contain symlinks")
    destination.mkdir(parents=True, exist_ok=True)
    for source in files:
        target = destination / source.relative_to(FIXTURE)
        target.parent.mkdir(parents=True, exist_ok=True)
        # Exclusive creation refuses an overwrite if another writer races staging.
        with target.open("xb") as stream:
            stream.write(source.read_bytes())
    return [path.relative_to(FIXTURE).as_posix() for path in files]


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("destination")
    args = parser.parse_args()
    paths = stage(args.destination)
    print(f"Staged {len(paths)} fictional files; evaluator materials excluded.")
    print("Enforce workspace/network isolation separately before a fresh-agent trial.")
