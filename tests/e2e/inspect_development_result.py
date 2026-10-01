"""Inspect one retained external shared-development result read-only."""
import argparse
import json
from pathlib import Path

from .support.development_result import inspect_development_result


def main(argv=None):
    parser = argparse.ArgumentParser()
    parser.add_argument("--summary", type=Path, required=True)
    args = parser.parse_args(argv)
    print(json.dumps(inspect_development_result(args.summary), indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
