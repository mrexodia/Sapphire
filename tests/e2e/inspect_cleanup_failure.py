"""Inspect one private terminal cleanup-failure artifact without exposing identities."""
import argparse
import json
from pathlib import Path

from .support.cleanup_failure_result import inspect_cleanup_failure


def main(argv=None):
    parser = argparse.ArgumentParser()
    parser.add_argument("--artifact-dir", type=Path, required=True)
    args = parser.parse_args(argv)
    print(json.dumps(inspect_cleanup_failure(args.artifact_dir), indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
